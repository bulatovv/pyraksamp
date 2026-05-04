"""PTY driver subclass and relay server/client for remote shell attachment."""

import asyncio
import contextlib
import fcntl
import os
import signal
import struct
import sys
import termios
import tty
from typing import TYPE_CHECKING

from textual.drivers.linux_driver import LinuxDriver

if TYPE_CHECKING:
    pass


def make_pty_driver_class(slave_fd: int) -> type:
    """Return a LinuxDriver subclass that uses *slave_fd* for I/O."""

    class _PTYDriver(LinuxDriver):
        def __init__(self, app, **kwargs):
            super().__init__(app, **kwargs)
            self._slave_file = open(slave_fd, "w", closefd=False)  # noqa: SIM115
            self._file = self._slave_file
            self.fileno = slave_fd
            self.input_tty = True

        def _get_terminal_size(self) -> tuple[int, int]:
            try:
                sz = os.get_terminal_size(slave_fd)
                return sz.columns, sz.lines
            except OSError:
                return 80, 25

    return _PTYDriver


# ── Relay server (bot side) ────────────────────────────────────────────────────


async def _relay_client(
    master_fd: int, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    """Handle one relay client connection.

    Protocol (client→server direction only is framed):
    - ``\\x00`` + data  — raw keystrokes / input bytes
    - ``\\x01`` + 4 bytes (``HH``: cols, rows)  — terminal resize

    Server→client direction: raw unframed ANSI bytes.
    """
    loop = asyncio.get_running_loop()

    async def pty_to_sock() -> None:
        while True:
            try:
                data = await loop.run_in_executor(None, os.read, master_fd, 4096)
            except OSError:
                break
            if not data:
                break
            writer.write(data)
            await writer.drain()

    async def sock_to_pty() -> None:
        while True:
            try:
                typ_byte = await reader.readexactly(1)
            except (asyncio.IncompleteReadError, ConnectionResetError):
                break
            typ = typ_byte[0]
            if typ == 0:  # input
                try:
                    chunk = await reader.read(4096)
                except (asyncio.IncompleteReadError, ConnectionResetError):
                    break
                if not chunk:
                    break
                try:
                    os.write(master_fd, chunk)
                except OSError:
                    break
            elif typ == 1:  # resize
                try:
                    size_bytes = await reader.readexactly(4)
                except (asyncio.IncompleteReadError, ConnectionResetError):
                    break
                cols, rows = struct.unpack("HH", size_bytes)
                with contextlib.suppress(OSError):
                    fcntl.ioctl(
                        master_fd,
                        termios.TIOCSWINSZ,
                        struct.pack("HHHH", rows, cols, 0, 0),
                    )

    try:
        await asyncio.gather(pty_to_sock(), sock_to_pty())
    finally:
        writer.close()


# ── Relay client (attach side) ────────────────────────────────────────────────


async def attach(sock_path: str) -> None:
    """Connect to a relay server and forward the TUI to the local terminal.

    Run with ``pyraksamp shell --attach [SOCK]``.
    """
    reader, writer = await asyncio.open_unix_connection(sock_path)

    # Send initial terminal size
    cols, rows = os.get_terminal_size()
    writer.write(b"\x01" + struct.pack("HH", cols, rows))
    await writer.drain()

    old_attrs = termios.tcgetattr(sys.stdin.fileno())
    tty.setraw(sys.stdin.fileno())

    def on_resize(*_):
        try:
            cols, rows = os.get_terminal_size()
            writer.write(b"\x01" + struct.pack("HH", cols, rows))
        except OSError:
            pass

    signal.signal(signal.SIGWINCH, on_resize)

    try:

        async def sock_to_stdout() -> None:
            while True:
                try:
                    chunk = await reader.read(4096)
                except (asyncio.IncompleteReadError, ConnectionResetError):
                    break
                if not chunk:
                    break
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()

        async def stdin_to_sock() -> None:
            loop = asyncio.get_running_loop()
            while True:
                try:
                    data = await loop.run_in_executor(
                        None,
                        sys.stdin.buffer.read1,  # ty: ignore[unresolved-attribute]
                    )
                except OSError:
                    break
                if not data:
                    break
                writer.write(b"\x00" + data)
                await writer.drain()

        await asyncio.gather(sock_to_stdout(), stdin_to_sock())
    finally:
        signal.signal(signal.SIGWINCH, signal.SIG_DFL)
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_attrs)
        writer.close()
