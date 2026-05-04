"""Offline tests for dialogs.py — no network, no SAMPBot needed."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

from pyraksamp import SAMPBot
from pyraksamp._bus import _EventBus
from pyraksamp._dispatcher import _Dispatcher
from pyraksamp._listener import _CallbackListener
from pyraksamp.dialogs import (
    DialogAlreadyRespondedError,
    InputDialog,
    ListDialog,
    MsgboxDialog,
    PasswordDialog,
    TablistDialog,
    TablistHeadersDialog,
    _make_buttons,
    _make_dialog,
    _Responder,
)


def make_bot():
    bot = MagicMock()
    bot.send_dialog_response = MagicMock()
    return bot


# ── ButtonSelector ──────────────────────────────────────────────────────────


def test_buttons_one():
    bot = make_bot()
    sel = _make_buttons(10, 'OK', '', _Responder(bot.send_dialog_response))
    assert len(sel) == 1
    assert sel[0].label == 'OK'
    assert sel[0].id == 1
    try:
        sel[1]
        assert False, 'should raise IndexError'
    except IndexError:
        pass


def test_buttons_two():
    bot = make_bot()
    sel = _make_buttons(10, 'Yes', 'No', _Responder(bot.send_dialog_response))
    assert len(sel) == 2
    assert sel[0].label == 'Yes' and sel[0].id == 1
    assert sel[1].label == 'No' and sel[1].id == 0


def test_button_click():
    bot1 = make_bot()
    sel1 = _make_buttons(7, 'OK', 'Cancel', _Responder(bot1.send_dialog_response))
    sel1[0].click()
    bot1.send_dialog_response.assert_called_once_with(7, button=1)

    bot2 = make_bot()
    sel2 = _make_buttons(7, 'OK', 'Cancel', _Responder(bot2.send_dialog_response))
    sel2[1].click()
    bot2.send_dialog_response.assert_called_with(7, button=0)


def test_button_predicate():
    bot = make_bot()
    sel = _make_buttons(1, 'Accept', 'Decline', _Responder(bot.send_dialog_response))
    b = sel(lambda b: b.label == 'Decline')
    assert b.id == 0


def test_button_iter():
    bot = make_bot()
    sel = _make_buttons(1, 'A', 'B', _Responder(bot.send_dialog_response))
    labels = [b.label for b in sel]
    assert labels == ['A', 'B']


def test_buttons_frozen():
    bot = make_bot()
    sel = _make_buttons(1, 'OK', '', _Responder(bot.send_dialog_response))
    try:
        sel[0].label = 'X'
        assert False, 'should be frozen'
    except (AttributeError, TypeError):
        pass


# ── MsgboxDialog ────────────────────────────────────────────────────────────


def test_msgbox():
    bot = make_bot()
    dlg = _make_dialog(
        1, 0, 'Title', 'OK', 'Cancel', 'Hello', _Responder(bot.send_dialog_response)
    )
    assert isinstance(dlg, MsgboxDialog)
    assert dlg.style == 0
    assert dlg.title == 'Title'
    assert dlg.body == 'Hello'
    assert not dlg.is_responded
    dlg.ok()
    bot.send_dialog_response.assert_called_with(1, button=1)
    assert dlg.is_responded


def test_msgbox_cancel():
    bot = make_bot()
    dlg = _make_dialog(
        1, 0, 'Title', 'OK', 'Cancel', 'Hello', _Responder(bot.send_dialog_response)
    )
    dlg.cancel()
    bot.send_dialog_response.assert_called_with(1, button=0)


def test_msgbox_frozen():
    bot = make_bot()
    dlg = _make_dialog(1, 0, 'T', 'OK', '', 'body', _Responder(bot.send_dialog_response))
    try:
        dlg.title = 'X'
        assert False, 'should be frozen'
    except (AttributeError, TypeError):
        pass


# ── InputDialog ─────────────────────────────────────────────────────────────


def test_input():
    bot = make_bot()
    dlg = _make_dialog(
        2,
        1,
        'Login',
        'Submit',
        'Cancel',
        'Enter name:',
        _Responder(bot.send_dialog_response),
    )
    assert isinstance(dlg, InputDialog)
    dlg.submit('alice')
    bot.send_dialog_response.assert_called_with(2, button=1, text='alice')


def test_input_cancel():
    bot = make_bot()
    dlg = _make_dialog(
        2,
        1,
        'Login',
        'Submit',
        'Cancel',
        'Enter name:',
        _Responder(bot.send_dialog_response),
    )
    dlg.cancel()
    bot.send_dialog_response.assert_called_with(2, button=0)


# ── PasswordDialog ───────────────────────────────────────────────────────────


def test_password():
    bot = make_bot()
    dlg = _make_dialog(
        3,
        3,
        'Password',
        'OK',
        'Cancel',
        'Enter password:',
        _Responder(bot.send_dialog_response),
    )
    assert isinstance(dlg, PasswordDialog)
    dlg.submit('secret')
    bot.send_dialog_response.assert_called_with(3, button=1, text='secret')


# ── ListDialog ───────────────────────────────────────────────────────────────


def test_list():
    bot = make_bot()
    body = 'Item A\nItem B\nItem C'
    dlg = _make_dialog(
        4, 2, 'Pick one', 'Select', 'Cancel', body, _Responder(bot.send_dialog_response)
    )
    assert isinstance(dlg, ListDialog)
    assert len(dlg.rows) == 3
    assert dlg.rows[0].text == 'Item A'
    assert dlg.rows[2].text == 'Item C'
    dlg.rows[1].select()
    bot.send_dialog_response.assert_called_with(4, button=1, list_item=1)


def test_list_cancel():
    bot = make_bot()
    dlg = _make_dialog(
        4,
        2,
        'Pick one',
        'Select',
        'Cancel',
        'A\nB',
        _Responder(bot.send_dialog_response),
    )
    dlg.cancel()
    bot.send_dialog_response.assert_called_with(4, button=0)


def test_list_predicate():
    bot = make_bot()
    body = 'Apple\nBanana\nCherry'
    dlg = _make_dialog(5, 2, 'Fruit', 'OK', '', body, _Responder(bot.send_dialog_response))
    row = dlg.rows(lambda r: r.text == 'Banana')
    assert row.index == 1


def test_list_empty_lines_skipped():
    bot = make_bot()
    body = 'A\n\nB\n'
    dlg = _make_dialog(6, 2, 'T', 'OK', '', body, _Responder(bot.send_dialog_response))
    assert len(dlg.rows) == 2


# ── TablistDialog ────────────────────────────────────────────────────────────


def test_tablist():
    bot = make_bot()
    body = 'Alice\t100\nBob\t200'
    dlg = _make_dialog(
        7, 4, 'Players', 'Select', 'Cancel', body, _Responder(bot.send_dialog_response)
    )
    assert isinstance(dlg, TablistDialog)
    assert len(dlg.rows) == 2
    row = dlg.rows[0]
    assert isinstance(row.columns, tuple)
    assert row.columns == ('Alice', '100')
    row.select()
    bot.send_dialog_response.assert_called_with(7, button=1, list_item=0)


# ── TablistHeadersDialog ─────────────────────────────────────────────────────


def test_tablist_headers():
    bot = make_bot()
    body = 'Name\tScore\nAlice\t100\nBob\t200'
    dlg = _make_dialog(
        8, 5, 'Leaderboard', 'OK', 'Close', body, _Responder(bot.send_dialog_response)
    )
    assert isinstance(dlg, TablistHeadersDialog)
    assert isinstance(dlg.headers, tuple)
    assert dlg.headers == ('Name', 'Score')
    assert len(dlg.rows) == 2
    assert dlg.rows[1].columns == ('Bob', '200')


def test_tablist_headers_frozen():
    bot = make_bot()
    body = 'H1\tH2\nA\tB'
    dlg = _make_dialog(9, 5, 'T', 'OK', '', body, _Responder(bot.send_dialog_response))
    try:
        dlg.headers = ('X',)
        assert False, 'should be frozen'
    except (AttributeError, TypeError):
        pass


# ── Unknown style fallback ────────────────────────────────────────────────────


def test_unknown_style_fallback():
    bot = make_bot()
    dlg = _make_dialog(99, 99, 'T', 'OK', '', 'body', _Responder(bot.send_dialog_response))
    assert isinstance(dlg, MsgboxDialog)


# ── is_responded / DialogAlreadyRespondedError ───────────────────────────────


def test_dialog_is_responded_false_before_response():
    bot = make_bot()
    dlg = _make_dialog(1, 0, 'T', 'OK', '', 'body', _Responder(bot.send_dialog_response))
    assert not dlg.is_responded


def test_dialog_is_responded_true_after_response():
    bot = make_bot()
    dlg = _make_dialog(1, 0, 'T', 'OK', '', 'body', _Responder(bot.send_dialog_response))
    dlg.ok()
    assert dlg.is_responded


def test_dialog_second_response_raises():
    bot = make_bot()
    dlg = _make_dialog(1, 0, 'T', 'OK', 'Cancel', 'body', _Responder(bot.send_dialog_response))
    dlg.ok()
    try:
        dlg.cancel()
        assert False, 'should raise'
    except DialogAlreadyRespondedError as e:
        assert e.dialog_id == 1


def test_dialog_row_select_marks_responded():
    bot = make_bot()
    dlg = _make_dialog(4, 2, 'Pick', 'Select', '', 'A\nB', _Responder(bot.send_dialog_response))
    dlg.rows[0].select()
    assert dlg.is_responded


def test_dialog_button_click_marks_responded():
    bot = make_bot()
    dlg = _make_dialog(1, 0, 'T', 'OK', 'Cancel', 'body', _Responder(bot.send_dialog_response))
    dlg.buttons[0].click()
    assert dlg.is_responded


def test_dialog_second_response_via_row_raises():
    bot = make_bot()
    dlg = _make_dialog(
        4, 2, 'Pick', 'Select', 'Cancel', 'A\nB', _Responder(bot.send_dialog_response)
    )
    dlg.rows[0].select()
    try:
        dlg.cancel()
        assert False, 'should raise'
    except DialogAlreadyRespondedError:
        pass


def test_responded_state_not_shared_between_events():
    bot = make_bot()
    dlg1 = _make_dialog(1, 0, 'T', 'OK', '', 'body', _Responder(bot.send_dialog_response))
    dlg2 = _make_dialog(1, 0, 'T', 'OK', '', 'body', _Responder(bot.send_dialog_response))
    dlg1.ok()
    assert dlg1.is_responded
    assert not dlg2.is_responded


# ── on_dialog decorator filtering ────────────────────────────────────────────


def _mock_self():
    """Minimal stand-in for SAMPBot — compatible with _CallbackListener."""
    bot = SimpleNamespace()
    bot._bus = _EventBus()
    bot._dispatcher = _Dispatcher(bot._bus)
    bot._listeners = []
    bot._started = False

    def _register_listener(listener):
        bot._listeners.append(listener)
        if bot._started:
            listener.start()

    def _register_handler(tag, fn, predicate=None, extract=None):
        _register_listener(_CallbackListener(bot._dispatcher, tag, fn, predicate, extract))

    bot._register_listener = _register_listener
    bot._register_handler = _register_handler
    return bot


def _input_dlg():
    return _make_dialog(
        1,
        1,
        'Login',
        'Submit',
        'Cancel',
        'Enter name:',
        _Responder(MagicMock().send_dialog_response),
    )


def _msgbox_dlg():
    return _make_dialog(
        2, 0, 'Info', 'OK', '', 'Hello', _Responder(MagicMock().send_dialog_response)
    )


async def _fire(bot, dlg):
    """Start all unstarted listeners, broadcast a dialog event, then yield."""
    if bot._dispatcher._task is None:
        bot._dispatcher.start()
    for listener in bot._listeners:
        if listener._task is None:
            listener.start()
    await asyncio.sleep(0)
    bot._bus.broadcast(('dialog', dlg))
    await asyncio.sleep(0)  # dispatcher routes
    await asyncio.sleep(0)  # listener processes


def test_on_dialog_bare_receives_all():
    """Bare @bot.on_dialog passes every dialog to the handler."""

    async def _inner():
        bot = _mock_self()
        received = []
        SAMPBot.on_dialog(bot, lambda dlg: received.append(dlg))
        await _fire(bot, _input_dlg())
        await _fire(bot, _msgbox_dlg())
        assert len(received) == 2

    asyncio.run(_inner())


def test_on_dialog_no_filter_receives_all():
    """@bot.on_dialog() with no args passes every dialog."""

    async def _inner():
        bot = _mock_self()
        received = []
        SAMPBot.on_dialog(bot)(lambda dlg: received.append(dlg))
        await _fire(bot, _input_dlg())
        await _fire(bot, _msgbox_dlg())
        assert len(received) == 2

    asyncio.run(_inner())


def test_on_dialog_type_filter_passes_matching():
    """dialog_type=InputDialog lets InputDialog through."""

    async def _inner():
        bot = _mock_self()
        received = []
        SAMPBot.on_dialog(bot, dialog_type=InputDialog)(lambda dlg: received.append(dlg))
        await _fire(bot, _input_dlg())
        assert len(received) == 1
        assert isinstance(received[0], InputDialog)

    asyncio.run(_inner())


def test_on_dialog_type_filter_blocks_other():
    """dialog_type=InputDialog blocks MsgboxDialog."""

    async def _inner():
        bot = _mock_self()
        received = []
        SAMPBot.on_dialog(bot, dialog_type=InputDialog)(lambda dlg: received.append(dlg))
        await _fire(bot, _msgbox_dlg())
        assert len(received) == 0

    asyncio.run(_inner())


def test_on_dialog_dialog_id_filter():
    """dialog_id= matches only the exact ID."""

    async def _inner():
        bot = _mock_self()
        received = []
        SAMPBot.on_dialog(bot, dialog_id=1)(lambda dlg: received.append(dlg))
        await _fire(bot, _input_dlg())  # id=1 — should pass
        await _fire(bot, _msgbox_dlg())  # id=2 — should be blocked
        assert len(received) == 1

    asyncio.run(_inner())


def test_on_dialog_predicate_filter():
    """predicate= is applied on top of type filter."""

    async def _inner():
        bot = _mock_self()
        received = []
        SAMPBot.on_dialog(
            bot,
            dialog_type=InputDialog,
            predicate=lambda d: 'Login' in d.title,
        )(lambda dlg: received.append(dlg))
        await _fire(bot, _input_dlg())  # title="Login" — passes
        other = _make_dialog(
            3, 1, 'Register', 'OK', '', '', _Responder(MagicMock().send_dialog_response)
        )
        await _fire(bot, other)  # title="Register" — blocked by predicate
        assert len(received) == 1

    asyncio.run(_inner())


def test_on_dialog_async_handler():
    """Async handlers are awaited correctly."""

    async def _inner():
        bot = _mock_self()
        received = []

        async def handler(dlg):
            received.append(dlg)

        SAMPBot.on_dialog(bot, dialog_type=InputDialog)(handler)
        await _fire(bot, _input_dlg())
        assert len(received) == 1

    asyncio.run(_inner())


# ── Run all ──────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    tests = [v for k, v in list(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f'  PASS  {t.__name__}')
            passed += 1
        except Exception as e:
            print(f'  FAIL  {t.__name__}: {e}')
            failed += 1
    print(f'\n{passed} passed, {failed} failed')
    if failed:
        raise SystemExit(1)
