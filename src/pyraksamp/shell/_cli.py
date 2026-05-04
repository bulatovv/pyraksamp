"""Shell subcommand CLI entry point.

Usage:
    pyraksamp shell module:attr          # import bot or shell object
    pyraksamp shell --host H --port P --nick N [--password PW] [--proxy URL]
    pyraksamp shell --attach [SOCK]
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog='pyraksamp shell',
        description='pyraksamp interactive shell',
        add_help=True,
    )
    parser.add_argument(
        'module_attr',
        nargs='?',
        metavar='module:attr',
        help='Import a SAMPBot or Shell object (e.g. mymodule:bot)',
    )
    parser.add_argument(
        '--attach',
        nargs='?',
        const=True,
        metavar='SOCK',
        help='Attach to a running shell via Unix socket relay',
    )
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=7777)
    parser.add_argument('--nick', default='PyBot')
    parser.add_argument('--password', default='')
    parser.add_argument(
        '--proxy',
        default=None,
        metavar='URL',
        help='SOCKS5 proxy URL, e.g. socks5://user:pass@host:1080',
    )
    parser.add_argument(
        '--encoding',
        default='ascii',
        metavar='ENC',
        help='Server text encoding (default: ascii)',
    )

    args = parser.parse_args()

    if args.attach is not None:
        # relay client mode — no bot dependency needed
        sock_path = args.attach if isinstance(args.attach, str) else None
        if sock_path is None:
            # auto-detect: look for /tmp/pyraksamp-*.sock
            import glob as _glob

            matches = sorted(_glob.glob('/tmp/pyraksamp-*.sock'))
            if not matches:
                sys.exit('No pyraksamp socket found. Start a bot with expose_shell() first.')
            sock_path = matches[-1]
            print(f'Attaching to {sock_path} ...', flush=True)

        from pyraksamp.shell._pty import attach

        asyncio.run(attach(sock_path))
        return

    if args.module_attr:
        # import mode: module:attr
        if ':' not in args.module_attr:
            parser.error('module:attr must contain a colon, e.g. mymodule:bot')
        module_name, attr = args.module_attr.rsplit(':', 1)
        mod = importlib.import_module(module_name)
        obj = getattr(mod, attr)

        from pyraksamp import SAMPBot
        from pyraksamp.shell import Shell

        if isinstance(obj, SAMPBot):
            shell = Shell(obj)
        elif isinstance(obj, Shell):
            shell = obj
        else:
            sys.exit(f'Expected a SAMPBot or Shell instance, got {type(obj).__name__!r}')

        # bot.start() is handled by SampShellApp.on_mount when the bot is not
        # yet started; if already started, TUI attaches to ongoing events.
        asyncio.run(shell.run())
        return

    # standalone mode: create bot from CLI args
    from pyraksamp import SAMPBot
    from pyraksamp.shell import Shell

    bot = SAMPBot(
        args.host,
        args.port,
        args.nick,
        args.password,
        proxy=args.proxy,
        server_encoding=args.encoding,
    )
    shell = Shell(bot)
    # bot.start() is called by SampShellApp.on_mount after subscribing to the
    # event bus, so no events are lost between connection and TUI startup.
    asyncio.run(shell.run())
