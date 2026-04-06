# Working with TextDraws

## Design

Unlike dialogs (which are one-shot request/response objects), textdraws are **persistent visual elements**. The server can show, edit, and hide them at any point during the session, and many can be active at once.

pyraksamp maintains a **live registry** (`bot.textdraws`) that mirrors what the server currently has visible. When the server sends a show, edit, or hide RPC, the registry is updated automatically. `bot.textdraws[id]` always reflects the current state.

This design matches how textdraws actually work: rather than handing you one-off objects, the library gives you a persistent view of the server's textdraw state that you can query at any time.

Selectable textdraws — those the server has made clickable — are represented as `SelectableTextDraw`, a subclass with a `.click()` method.

---

## The registry

`bot.textdraws` is a `TextDraws` instance. You can query it at any point:

```python
# all currently visible textdraws
all_tds = bot.textdraws.all()

# find the first matching one (returns None if not found)
td = bot.textdraws.find(lambda t: "Score" in t.text)
td = bot.textdraws.find(selectable=True)

# find all matching
tds = bot.textdraws.find_all(lambda t: t.style == 1)
tds = bot.textdraws.find_all(selectable=True)
```

Access by ID directly:

```python
# bot.textdraws is not directly subscriptable, use find or find_all
td = bot.textdraws.find(lambda t: t.id == 42)
```

---

## TextDraw attributes

| Attribute | Type | Description |
|---|---|---|
| `id` | `int` | Server-assigned textdraw ID |
| `text` | `str` | Display text (may contain SA:MP color codes) |
| `x`, `y` | `float` | Screen position |
| `style` | `int` | Render style (0=text, 1=box, 2=sprite, 3=model) |
| `flags` | `int` | Raw flag bitmask |
| `letter_width`, `letter_height` | `float` | Letter dimensions |
| `letter_color` | `int` | Letter color (0xRRGGBBAA) |
| `line_width`, `line_height` | `float` | Box dimensions |
| `box_color` | `int` | Box background color |
| `shadow` | `int` | Shadow size |
| `outline` | `int` | Outline size |
| `background_color` | `int` | Background color |
| `model_id` | `int` | Model ID (for style 3) |
| `rot_x`, `rot_y`, `rot_z` | `float` | Model rotation |
| `zoom` | `float` | Model zoom |
| `color1`, `color2` | `int` | Vehicle/model colors |

---

## Listening for changes

### Decorator

`@bot.on_textdraw()` fires each time a matching textdraw is shown or re-shown. The callback receives the live `TextDraw` object from the registry (already updated).

```python
@bot.on_textdraw()
async def any_textdraw(td):
    print(f"textdraw {td.id}: {td.text!r}")

# filter by id
@bot.on_textdraw(id=42)
async def td_42(td): ...

# filter by text
@bot.on_textdraw(text="Score")
async def score_td(td): ...

# only selectable textdraws
@bot.on_textdraw(selectable=True)
async def on_selectable(td: pyraksamp.SelectableTextDraw):
    td.click()

# custom predicate
@bot.on_textdraw(predicate=lambda td: td.style == 1 and td.x < 100)
async def left_box(td): ...
```

---

## Waiting for textdraws

`TextDraws.wait_for()` returns immediately if a match already exists, otherwise waits until one appears:

```python
# wait until a selectable textdraw exists
td = await bot.textdraws.wait_for(selectable=True)
td.click()

# wait for a specific textdraw by id
td = await bot.textdraws.wait_for(lambda t: t.id == 100)

# wait until a known textdraw disappears
td = await bot.textdraws.wait_for(lambda t: t.id == 55)
await bot.textdraws.wait_until_gone(td)
print("textdraw 55 is gone")
```

---

## Clicking selectable textdraws

`SelectableTextDraw.click()` sends the SelectTextDraw RPC (83) for that textdraw ID.

```python
@bot.on_textdraw(selectable=True)
async def on_selectable(td: pyraksamp.SelectableTextDraw):
    td.click()
```

You can also click directly by ID:

```python
bot.click_textdraw(42)
```

---

## Textdraw selection mode

Some servers enable a "click to select" mode. When this is toggled, the server sends a `textdraw_toggle_select` event. You can listen for it via `@bot.on_rpc(rpc_id=...)` or the raw events stream if needed.
