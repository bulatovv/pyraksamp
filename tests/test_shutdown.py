"""Regression test: background thread exits cleanly when SIGINT fires.

Simulates the Rust receive-loop scenario: a daemon thread continuously
acquires the GIL (by executing Python bytecode) while the main thread
receives SIGINT.  Without the atexit handler that stops the thread, Python
can crash with "Fatal Python error: PyGILState_Release" during interpreter
finalization.  With it, the thread is stopped before finalization begins.
"""

import signal
import subprocess
import sys

# ---------------------------------------------------------------------------
# Script run in a subprocess.  Mirrors the SAMPBot lifecycle:
#   1. Background thread runs (simulates samp-recv-* Rust thread calling callbacks).
#   2. atexit handler stops the thread (the fix under test).
#   3. Main thread signals readiness via stdout so the parent never sleeps blindly.
# ---------------------------------------------------------------------------
_SCRIPT = """\
import sys
import threading
import atexit

stop = threading.Event()

def loop():
    while not stop.is_set():
        _ = object()  # Python allocation – exercises GIL acquisition

# Mirror of SAMPBot.start(): register stop() as atexit handler.
atexit.register(stop.set)

t = threading.Thread(target=loop, daemon=True)
t.start()

# Tell the parent we are ready; parent sends SIGINT only after this line.
sys.stdout.write("ready\\n")
sys.stdout.flush()

# Block until signal arrives (Event.wait is interrupted by KeyboardInterrupt).
try:
    stop.wait()
except KeyboardInterrupt:
    pass
"""


def test_background_thread_exits_cleanly_on_sigint():
    proc = subprocess.Popen(
        [sys.executable, '-c', _SCRIPT],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Block until the child confirms its thread is running — no arbitrary sleep.
    assert proc.stdout.readline() == b'ready\n'

    proc.send_signal(signal.SIGINT)

    try:
        _, stderr = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        assert False, 'subprocess did not exit within 5 s after SIGINT'

    assert b'Fatal Python error' not in stderr, (
        f'CPython crash detected:\n{stderr.decode(errors="replace")}'
    )
    # 0  – clean exit
    # 1  – unhandled KeyboardInterrupt (acceptable; not a crash)
    # 130 / -SIGINT – terminated by signal (shell convention / subprocess convention)
    assert proc.returncode in (0, 1, 130, -signal.SIGINT), (
        f'Unexpected exit code {proc.returncode}; stderr:\n{stderr.decode(errors="replace")}'
    )
