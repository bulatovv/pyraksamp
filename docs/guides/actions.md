# Actions

Actions are outbound operations — things the bot sends to the server.
All send methods are **synchronous** and safe to call directly from async code (no `await` needed).

---

## Chat and commands

```python
bot.send_chat("Hello world!")          # public chat (max 144 bytes)
bot.send_command("/stats")             # slash command (max 100 bytes)
```

---

## Dialog responses

Normally you respond through the dialog object directly (see [Dialogs](dialogs.md)).
The low-level method is also available:

```python
bot.send_dialog_response(
    dialog_id=1,
    button=1,        # 1 = OK/first, 0 = Cancel/second
    list_item=0,     # row index for list dialogs
    text="input",    # text for input dialogs
)
```

---

## Vehicles

```python
bot.send_enter_vehicle(vehicle_id=42, is_passenger=False)
bot.send_exit_vehicle(vehicle_id=42)
```

---

## Key presses

`send_keys` sets the key state reported in on-foot sync packets. The state is **sticky** — it persists until you call `send_keys` again.

```python
from pyraksamp import Keys

bot.send_keys(Keys.SPRINT)
bot.send_keys(Keys.SPRINT | Keys.JUMP)
bot.send_keys(0)              # release all keys
```

`press_keys` is async and auto-releases after a duration:

```python
await bot.press_keys(Keys.FIRE, duration=1.0)   # fire for 1 second

# fire-and-forget (non-blocking):
asyncio.create_task(bot.press_keys(Keys.SPRINT, duration=2.0))
```

Multiple concurrent `press_keys` calls for the same key are ref-counted — the key stays held until the last call releases it.

### Keys reference

| Constant | In-game key |
|---|---|
| `Keys.ACTION` | TAB |
| `Keys.CROUCH` | C |
| `Keys.FIRE` | Left Ctrl |
| `Keys.SPRINT` | Space |
| `Keys.JUMP` | Left Shift |
| `Keys.SECONDARY_ATTACK` | Enter |
| `Keys.AIM` | Right Mouse Button |
| `Keys.WALK` | Left Alt |
| `Keys.LOOK_LEFT` | Q |
| `Keys.LOOK_RIGHT` | E |
| `Keys.YES` | Y |
| `Keys.NO` | N |
| `Keys.ANALOG_UP/DOWN/LEFT/RIGHT` | Numpad 8/2/4/6 |

---

## TextDraw clicks

```python
bot.click_textdraw(42)          # send SelectTextDraw RPC for textdraw 42
```

Usually you call `.click()` on a `SelectableTextDraw` object instead (see [TextDraws](textdraws.md)).

---

## Raw RPC

For anything not covered by the higher-level methods:

```python
bot.send_rpc(rpc_id, data=b"", reliability=pyraksamp.RELIABLE)
```

Reliability constants: `UNRELIABLE`, `UNRELIABLE_SEQUENCED`, `RELIABLE`, `RELIABLE_ORDERED`, `RELIABLE_SEQUENCED`.

See [Constants](../api/constants.md) for the full list of RPC IDs.

---

## Color codes

SA:MP embeds color codes in strings using the format `{RRGGBB}`. Text returned by the library (dialog titles, chat messages, server messages) is wrapped in `ColoredString`, which is a `str` subclass with two extra properties:

```python
msg.text                    # "Hello {FF0000}world"  (raw, with color codes)
msg.text.stripped           # "Hello world"          (codes removed)

for part in msg.text._components:
    if isinstance(part, pyraksamp.colors.Color):
        print(f"color: #{part.to_hex()}")
    else:
        print(f"text: {part}")
```

When sending chat or commands, pass plain strings — the server applies its own formatting.
