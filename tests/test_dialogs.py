"""Offline tests for dialogs.py — no network, no SAMPBot needed."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

from pyraksamp import SAMPBot
from pyraksamp.dialogs import (
    _make_buttons,
    _make_dialog,
    MsgboxDialog,
    InputDialog,
    PasswordDialog,
    ListDialog,
    TablistDialog,
    TablistHeadersDialog,
)


def make_bot():
    bot = MagicMock()
    bot.send_dialog_response = MagicMock()
    return bot


# ── ButtonSelector ──────────────────────────────────────────────────────────


def test_buttons_one():
    bot = make_bot()
    sel = _make_buttons(10, "OK", "", bot)
    assert len(sel) == 1
    assert sel[0].label == "OK"
    assert sel[0].id == 1
    try:
        sel[1]
        assert False, "should raise IndexError"
    except IndexError:
        pass


def test_buttons_two():
    bot = make_bot()
    sel = _make_buttons(10, "Yes", "No", bot)
    assert len(sel) == 2
    assert sel[0].label == "Yes" and sel[0].id == 1
    assert sel[1].label == "No" and sel[1].id == 0


def test_button_click():
    bot = make_bot()
    sel = _make_buttons(7, "OK", "Cancel", bot)
    sel[0].click()
    bot.send_dialog_response.assert_called_once_with(7, button=1)
    sel[1].click()
    bot.send_dialog_response.assert_called_with(7, button=0)


def test_button_predicate():
    bot = make_bot()
    sel = _make_buttons(1, "Accept", "Decline", bot)
    b = sel(lambda b: b.label == "Decline")
    assert b.id == 0


def test_button_iter():
    bot = make_bot()
    sel = _make_buttons(1, "A", "B", bot)
    labels = [b.label for b in sel]
    assert labels == ["A", "B"]


def test_buttons_frozen():
    bot = make_bot()
    sel = _make_buttons(1, "OK", "", bot)
    try:
        sel[0].label = "X"
        assert False, "should be frozen"
    except (AttributeError, TypeError):
        pass


# ── MsgboxDialog ────────────────────────────────────────────────────────────


def test_msgbox():
    bot = make_bot()
    dlg = _make_dialog(1, 0, "Title", "OK", "Cancel", "Hello", bot)
    assert isinstance(dlg, MsgboxDialog)
    assert dlg.style == 0
    assert dlg.title == "Title"
    assert dlg.body == "Hello"
    dlg.ok()
    bot.send_dialog_response.assert_called_with(1, button=1)
    dlg.cancel()
    bot.send_dialog_response.assert_called_with(1, button=0)


def test_msgbox_frozen():
    bot = make_bot()
    dlg = _make_dialog(1, 0, "T", "OK", "", "body", bot)
    try:
        dlg.title = "X"
        assert False, "should be frozen"
    except (AttributeError, TypeError):
        pass


# ── InputDialog ─────────────────────────────────────────────────────────────


def test_input():
    bot = make_bot()
    dlg = _make_dialog(2, 1, "Login", "Submit", "Cancel", "Enter name:", bot)
    assert isinstance(dlg, InputDialog)
    dlg.submit("alice")
    bot.send_dialog_response.assert_called_with(2, button=1, text="alice")
    dlg.cancel()
    bot.send_dialog_response.assert_called_with(2, button=0)


# ── PasswordDialog ───────────────────────────────────────────────────────────


def test_password():
    bot = make_bot()
    dlg = _make_dialog(3, 3, "Password", "OK", "Cancel", "Enter password:", bot)
    assert isinstance(dlg, PasswordDialog)
    dlg.submit("secret")
    bot.send_dialog_response.assert_called_with(3, button=1, text="secret")


# ── ListDialog ───────────────────────────────────────────────────────────────


def test_list():
    bot = make_bot()
    body = "Item A\nItem B\nItem C"
    dlg = _make_dialog(4, 2, "Pick one", "Select", "Cancel", body, bot)
    assert isinstance(dlg, ListDialog)
    assert len(dlg.rows) == 3
    assert dlg.rows[0].text == "Item A"
    assert dlg.rows[2].text == "Item C"
    dlg.rows[1].select()
    bot.send_dialog_response.assert_called_with(4, button=1, list_item=1)
    dlg.cancel()
    bot.send_dialog_response.assert_called_with(4, button=0)


def test_list_predicate():
    bot = make_bot()
    body = "Apple\nBanana\nCherry"
    dlg = _make_dialog(5, 2, "Fruit", "OK", "", body, bot)
    row = dlg.rows(lambda r: r.text == "Banana")
    assert row.index == 1


def test_list_empty_lines_skipped():
    bot = make_bot()
    body = "A\n\nB\n"
    dlg = _make_dialog(6, 2, "T", "OK", "", body, bot)
    assert len(dlg.rows) == 2


# ── TablistDialog ────────────────────────────────────────────────────────────


def test_tablist():
    bot = make_bot()
    body = "Alice\t100\nBob\t200"
    dlg = _make_dialog(7, 4, "Players", "Select", "Cancel", body, bot)
    assert isinstance(dlg, TablistDialog)
    assert len(dlg.rows) == 2
    row = dlg.rows[0]
    assert isinstance(row.columns, tuple)
    assert row.columns == ("Alice", "100")
    row.select()
    bot.send_dialog_response.assert_called_with(7, button=1, list_item=0)


# ── TablistHeadersDialog ─────────────────────────────────────────────────────


def test_tablist_headers():
    bot = make_bot()
    body = "Name\tScore\nAlice\t100\nBob\t200"
    dlg = _make_dialog(8, 5, "Leaderboard", "OK", "Close", body, bot)
    assert isinstance(dlg, TablistHeadersDialog)
    assert isinstance(dlg.headers, tuple)
    assert dlg.headers == ("Name", "Score")
    assert len(dlg.rows) == 2
    assert dlg.rows[1].columns == ("Bob", "200")


def test_tablist_headers_frozen():
    bot = make_bot()
    body = "H1\tH2\nA\tB"
    dlg = _make_dialog(9, 5, "T", "OK", "", body, bot)
    try:
        dlg.headers = ("X",)
        assert False, "should be frozen"
    except (AttributeError, TypeError):
        pass


# ── Unknown style fallback ────────────────────────────────────────────────────


def test_unknown_style_fallback():
    bot = make_bot()
    dlg = _make_dialog(99, 99, "T", "OK", "", "body", bot)
    assert isinstance(dlg, MsgboxDialog)


# ── on_dialog decorator filtering ────────────────────────────────────────────


def _mock_self():
    """Minimal stand-in for SAMPBot — only needs _cb_dialog."""
    return SimpleNamespace(_cb_dialog=None)


def _run(coro):
    return asyncio.run(coro)


def _input_dlg():
    return _make_dialog(1, 1, "Login", "Submit", "Cancel", "Enter name:", MagicMock())


def _msgbox_dlg():
    return _make_dialog(2, 0, "Info", "OK", "", "Hello", MagicMock())


def _call(cb, dlg):
    """Call a callback that may be plain or async (no-filter vs filtered)."""
    import asyncio, inspect
    if inspect.iscoroutinefunction(cb):
        asyncio.run(cb(dlg))
    else:
        cb(dlg)


def test_on_dialog_bare_receives_all():
    """Bare @bot.on_dialog passes every dialog to the handler."""
    bot = _mock_self()
    received = []
    SAMPBot.on_dialog(bot, lambda dlg: received.append(dlg))
    _call(bot._cb_dialog, _input_dlg())
    _call(bot._cb_dialog, _msgbox_dlg())
    assert len(received) == 2


def test_on_dialog_no_filter_receives_all():
    """@bot.on_dialog() with no args passes every dialog."""
    bot = _mock_self()
    received = []
    SAMPBot.on_dialog(bot)(lambda dlg: received.append(dlg))
    _call(bot._cb_dialog, _input_dlg())
    _call(bot._cb_dialog, _msgbox_dlg())
    assert len(received) == 2


def test_on_dialog_type_filter_passes_matching():
    """dialog_type=InputDialog lets InputDialog through."""
    bot = _mock_self()
    received = []
    SAMPBot.on_dialog(bot, dialog_type=InputDialog)(lambda dlg: received.append(dlg))
    _run(bot._cb_dialog(_input_dlg()))
    assert len(received) == 1
    assert isinstance(received[0], InputDialog)


def test_on_dialog_type_filter_blocks_other():
    """dialog_type=InputDialog blocks MsgboxDialog."""
    bot = _mock_self()
    received = []
    SAMPBot.on_dialog(bot, dialog_type=InputDialog)(lambda dlg: received.append(dlg))
    _run(bot._cb_dialog(_msgbox_dlg()))
    assert len(received) == 0


def test_on_dialog_dialog_id_filter():
    """dialog_id= matches only the exact ID."""
    bot = _mock_self()
    received = []
    SAMPBot.on_dialog(bot, dialog_id=1)(lambda dlg: received.append(dlg))
    _run(bot._cb_dialog(_input_dlg()))   # id=1 — should pass
    _run(bot._cb_dialog(_msgbox_dlg()))  # id=2 — should be blocked
    assert len(received) == 1


def test_on_dialog_predicate_filter():
    """predicate= is applied on top of type filter."""
    bot = _mock_self()
    received = []
    SAMPBot.on_dialog(
        bot,
        dialog_type=InputDialog,
        predicate=lambda d: "Login" in d.title,
    )(lambda dlg: received.append(dlg))
    _run(bot._cb_dialog(_input_dlg()))   # title="Login" — passes
    other = _make_dialog(3, 1, "Register", "OK", "", "", MagicMock())
    _run(bot._cb_dialog(other))          # title="Register" — blocked by predicate
    assert len(received) == 1


def test_on_dialog_async_handler():
    """Async handlers are awaited correctly."""
    bot = _mock_self()
    received = []

    async def handler(dlg):
        received.append(dlg)

    SAMPBot.on_dialog(bot, dialog_type=InputDialog)(handler)
    _run(bot._cb_dialog(_input_dlg()))
    assert len(received) == 1


# ── Run all ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    if failed:
        raise SystemExit(1)
