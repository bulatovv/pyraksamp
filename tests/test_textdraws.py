"""Unit tests for TextDraw registry (TextDraws) and on_textdraw decorator."""

import asyncio
from unittest.mock import MagicMock, patch

from pyraksamp._listener import _CallbackListener
from pyraksamp.textdraws import SelectableTextDraw, TextDraw, TextDraws, _make_textdraw

# ── Helpers ───────────────────────────────────────────────────────────────────

_SHOW_ARGS = dict(
    flags=0,
    lw=1.0,
    lh=1.0,
    lcol=0xFFFFFFFF,
    linew=0.0,
    lineh=0.0,
    bcol=0,
    shadow=0,
    outline=0,
    bgcol=0,
    style=0,
    x=100.0,
    y=200.0,
    model=0,
    rx=0.0,
    ry=0.0,
    rz=0.0,
    zoom=1.0,
    col1=-1,
    col2=-1,
    text='Hello',
)

# 21-element tuple: all show fields except selectable (passed separately)
_SHOW_TUPLE = (
    _SHOW_ARGS['flags'],
    _SHOW_ARGS['lw'],
    _SHOW_ARGS['lh'],
    _SHOW_ARGS['lcol'],
    _SHOW_ARGS['linew'],
    _SHOW_ARGS['lineh'],
    _SHOW_ARGS['bcol'],
    _SHOW_ARGS['shadow'],
    _SHOW_ARGS['outline'],
    _SHOW_ARGS['bgcol'],
    _SHOW_ARGS['style'],
    _SHOW_ARGS['x'],
    _SHOW_ARGS['y'],
    _SHOW_ARGS['model'],
    _SHOW_ARGS['rx'],
    _SHOW_ARGS['ry'],
    _SHOW_ARGS['rz'],
    _SHOW_ARGS['zoom'],
    _SHOW_ARGS['col1'],
    _SHOW_ARGS['col2'],
    _SHOW_ARGS['text'],
)


def make_textdraws():
    click_fn = MagicMock()
    tds = TextDraws(click_fn=click_fn)
    return tds, click_fn


async def _show(tds: TextDraws, td_id: int, sel: int = 0, text: str = 'Hello'):
    args = _SHOW_ARGS.copy()
    args['text'] = text
    await tds._on_show(
        td_id,
        args['flags'],
        args['lw'],
        args['lh'],
        args['lcol'],
        args['linew'],
        args['lineh'],
        args['bcol'],
        args['shadow'],
        args['outline'],
        args['bgcol'],
        args['style'],
        sel,
        args['x'],
        args['y'],
        args['model'],
        args['rx'],
        args['ry'],
        args['rz'],
        args['zoom'],
        args['col1'],
        args['col2'],
        args['text'],
    )


def run(coro):
    return asyncio.run(coro)


# ── TextDraw / SelectableTextDraw ─────────────────────────────────────────────


def test_make_textdraw_non_selectable():
    td = _make_textdraw(1, *_SHOW_TUPLE, 0, None)
    assert isinstance(td, TextDraw)
    assert not isinstance(td, SelectableTextDraw)
    assert td.id == 1
    assert td.text == 'Hello'
    assert td.x == 100.0


def test_make_textdraw_selectable():
    click_fn = MagicMock()
    td = _make_textdraw(2, *_SHOW_TUPLE, 1, click_fn)
    assert isinstance(td, SelectableTextDraw)
    assert td.id == 2


def test_selectable_click_calls_fn():
    click_fn = MagicMock()
    td = _make_textdraw(5, *_SHOW_TUPLE, 1, click_fn)
    td.click()
    click_fn.assert_called_once_with(5)


def test_update_text():
    td = _make_textdraw(1, *_SHOW_TUPLE, 0, None)
    td._update_text('World')
    assert td.text == 'World'


# ── TextDraws registry ────────────────────────────────────────────────────────


def test_show_adds_to_registry():
    async def _test():
        tds, _ = make_textdraws()
        await _show(tds, 10)
        assert 10 in tds._registry
        assert tds._registry[10].text == 'Hello'

    run(_test())


def test_hide_removes_from_registry():
    async def _test():
        tds, _ = make_textdraws()
        await _show(tds, 10)
        await tds._on_hide(10)
        assert 10 not in tds._registry

    run(_test())


def test_edit_updates_text():
    async def _test():
        tds, _ = make_textdraws()
        await _show(tds, 10)
        await tds._on_edit(10, 'Updated')
        assert tds._registry[10].text == 'Updated'

    run(_test())


def test_edit_unknown_id_noop():
    async def _test():
        tds, _ = make_textdraws()
        await tds._on_edit(999, 'X')  # must not raise

    run(_test())


def test_disconnect_clears_registry():
    async def _test():
        tds, _ = make_textdraws()
        await _show(tds, 10)
        await _show(tds, 20)
        await tds._on_disconnect()
        assert len(tds._registry) == 0

    run(_test())


def test_show_updates_existing_same_type():
    async def _test():
        tds, _ = make_textdraws()
        await _show(tds, 10, sel=0, text='A')
        td_ref = tds._registry[10]
        await _show(tds, 10, sel=0, text='B')
        assert tds._registry[10] is td_ref
        assert td_ref.text == 'B'

    run(_test())


def test_show_replaces_if_selectability_changes():
    async def _test():
        tds, _ = make_textdraws()
        await _show(tds, 10, sel=0)
        td_old = tds._registry[10]
        await _show(tds, 10, sel=1)
        td_new = tds._registry[10]
        assert td_new is not td_old
        assert isinstance(td_new, SelectableTextDraw)

    run(_test())


# ── find / find_all / all ────────────────────────────────────────────────────


def test_find_returns_match():
    async def _test():
        tds, _ = make_textdraws()
        await _show(tds, 1, text='Foo')
        td = tds.find(lambda t: t.text == 'Foo')
        assert td is not None
        assert td.id == 1

    run(_test())


def test_find_returns_none_when_no_match():
    async def _test():
        tds, _ = make_textdraws()
        await _show(tds, 1, text='Foo')
        assert tds.find(lambda t: t.text == 'Bar') is None

    run(_test())


def test_find_selectable_filter():
    async def _test():
        tds, _ = make_textdraws()
        await _show(tds, 1, sel=0)
        await _show(tds, 2, sel=1)
        sel = tds.find(selectable=True)
        assert isinstance(sel, SelectableTextDraw)
        assert sel.id == 2

    run(_test())


def test_find_all_empty_registry():
    tds, _ = make_textdraws()
    assert tds.find_all() == []


def test_all_returns_all():
    async def _test():
        tds, _ = make_textdraws()
        await _show(tds, 1)
        await _show(tds, 2)
        assert len(tds.all()) == 2

    run(_test())


# ── wait_for / wait_until_gone ────────────────────────────────────────────────


def test_wait_for_existing_returns_immediately():
    async def _test():
        tds, _ = make_textdraws()
        await _show(tds, 1)
        td = await tds.wait_for(lambda t: t.id == 1)
        assert td.id == 1

    run(_test())


def test_wait_for_future():
    async def _test():
        tds, _ = make_textdraws()

        async def producer():
            await asyncio.sleep(0.01)
            await _show(tds, 42)

        asyncio.ensure_future(producer())
        td = await tds.wait_for(lambda t: t.id == 42)
        assert td.id == 42

    run(_test())


def test_wait_until_gone():
    async def _test():
        tds, _ = make_textdraws()
        await _show(tds, 7)
        td = tds._registry[7]

        async def hider():
            await asyncio.sleep(0.01)
            await tds._on_hide(7)

        asyncio.ensure_future(hider())
        await tds.wait_until_gone(td)
        assert 7 not in tds._registry

    run(_test())


# ── click_textdraw ────────────────────────────────────────────────────────────


def test_click_textdraw_calls_action():
    with patch('pyraksamp._SAMPClient'):
        from pyraksamp import SAMPBot

        bot = SAMPBot('host')
    bot._client.click_textdraw = MagicMock()
    bot.click_textdraw(77)
    bot._client.click_textdraw.assert_called_once_with(77)


# ── on_textdraw decorator ─────────────────────────────────────────────────────


def _make_bot():
    with patch('pyraksamp._SAMPClient'):
        from pyraksamp import SAMPBot

        return SAMPBot('host')


def _wire_registry(bot):
    """Wire textdraw registry listeners (simulates what start() does)."""
    bot._dispatcher.start()
    for tag, fn in [
        ('textdraw_show', bot.textdraws._on_show),
        ('textdraw_hide', bot.textdraws._on_hide),
        ('textdraw_edit', bot.textdraws._on_edit),
        ('textdraw_toggle_select', bot.textdraws._on_toggle_select),
        ('disconnect', bot.textdraws._on_disconnect),
    ]:
        lst = _CallbackListener(bot._dispatcher, tag, fn, extract=lambda e: e[1:])
        bot._register_listener(lst)
        lst.start()


def _broadcast_show(bot, td_id, text='Test', sel=0):
    args = (
        td_id,
        0,
        1.0,
        1.0,
        0xFFFFFFFF,
        0.0,
        0.0,
        0,
        0,
        0,
        0,
        0,
        sel,
        100.0,
        200.0,
        0,
        0.0,
        0.0,
        0.0,
        1.0,
        -1,
        -1,
        text,
    )
    bot._bus.broadcast(('textdraw_show', *args))


def test_on_textdraw_fires_on_show():
    async def _test():
        bot = _make_bot()
        received = []

        @bot.on_textdraw
        def handler(td: TextDraw):
            received.append(td)

        # Save the on_textdraw listener before _wire_registry appends its own
        td_listener = bot._listeners[-1]
        _wire_registry(bot)
        td_listener.start()

        _broadcast_show(bot, 55, text='Test')
        await asyncio.sleep(0.05)

        assert len(received) == 1
        assert received[0].id == 55
        assert received[0].text == 'Test'

    run(_test())


def test_on_textdraw_predicate_filters():
    async def _test():
        bot = _make_bot()
        received = []

        @bot.on_textdraw(predicate=lambda td: td.text == 'Match')
        def handler(td: TextDraw):
            received.append(td)

        td_listener = bot._listeners[-1]
        _wire_registry(bot)
        td_listener.start()

        _broadcast_show(bot, 1, text='NoMatch')
        _broadcast_show(bot, 2, text='Match')
        await asyncio.sleep(0.05)

        assert len(received) == 1
        assert received[0].id == 2

    run(_test())


def test_on_textdraw_selectable_filter():
    async def _test():
        bot = _make_bot()
        received = []

        @bot.on_textdraw(selectable=True)
        def handler(td):
            received.append(td)

        td_listener = bot._listeners[-1]
        _wire_registry(bot)
        td_listener.start()

        _broadcast_show(bot, 1, sel=0)
        _broadcast_show(bot, 2, sel=1)
        await asyncio.sleep(0.05)

        assert len(received) == 1
        assert isinstance(received[0], SelectableTextDraw)
        assert received[0].id == 2

    run(_test())


def test_on_textdraw_text_filter():
    async def _test():
        bot = _make_bot()
        received = []

        @bot.on_textdraw(text='OK')
        def handler(td):
            received.append(td)

        td_listener = bot._listeners[-1]
        _wire_registry(bot)
        td_listener.start()

        _broadcast_show(bot, 1, text='Cancel')
        _broadcast_show(bot, 2, text='OK')
        await asyncio.sleep(0.05)

        assert len(received) == 1
        assert received[0].id == 2

    run(_test())


def test_on_textdraw_id_filter():
    async def _test():
        bot = _make_bot()
        received = []

        @bot.on_textdraw(id=42)
        def handler(td):
            received.append(td)

        td_listener = bot._listeners[-1]
        _wire_registry(bot)
        td_listener.start()

        _broadcast_show(bot, 10, text='A')
        _broadcast_show(bot, 42, text='B')
        await asyncio.sleep(0.05)

        assert len(received) == 1
        assert received[0].id == 42

    run(_test())
