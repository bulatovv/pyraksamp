# Event-Based and Script-Based Flows

pyraksamp supports two styles for handling server events. You can use either independently or mix them freely.

---

## Event-based flow

Register `@on_*` decorator callbacks. The library calls them automatically as events arrive, each in its own asyncio task.

```python
bot = pyraksamp.SAMPBot("play.example.com", 7777, "MyBot")

@bot.on_chat()
async def on_chat(msg):
    print(msg.text.stripped)

@bot.on_dialog()
async def on_dialog(dlg):
    dlg.buttons[0].click()

await bot.start()
await bot.run_until_disconnected()
```

Filtering is available on most decorators:

```python
@bot.on_chat(player_id=5)
async def from_player_5(msg): ...

@bot.on_dialog(dialog_type=pyraksamp.InputDialog)
async def input_only(dlg): ...

@bot.on_player_join(predicate=lambda e: e.name.startswith("Admin"))
async def admin_joined(evt): ...
```

---

## Script-based flow

Use `wait_for_*` and `async for` to process events sequentially, like a script.

```python
await bot.start()

# wait for a specific dialog
dlg = await bot.wait_for_dialog(dialog_type=pyraksamp.InputDialog)
dlg.submit("MyUsername")

# wait for the server confirmation
msg = await bot.wait_for_client_message(
    predicate=lambda m: "logged in" in m.text.stripped.lower()
)
print("Logged in!")
```

Stream generators let you process a sequence of events in a loop:

```python
async for dlg in bot.dialogs():
    if isinstance(dlg, pyraksamp.ListDialog):
        dlg.rows[0].select()
    else:
        dlg.buttons[0].click()
```

Available `wait_for_*` helpers:

- `wait_for_dialog(predicate=None, *, dialog_type=None, dialog_id=None)`
- `wait_for_chat(predicate=None, *, player_id=None)`
- `wait_for_client_message(predicate=None, *, color=None)`
- `wait_for_player_join(predicate=None, *, player_id=None, name=None)`
- `wait_for_rpc(rpc_id, *, predicate=None)`

Available stream generators (`async for`):

- `bot.dialogs()` — `AnyDialog`
- `bot.chat()` — `ChatMessage`
- `bot.server_messages()` — `ServerMessage`
- `bot.player_joins()` — `PlayerJoin`
- `bot.player_quits()` — `PlayerQuit`
- `bot.death_messages()` — `DeathMessage`
- `bot.game_texts()` — `GameText`
- `bot.events()` — raw event tuples (all events, stops on disconnect)

---

## Mixing: register handlers, then run a sequential flow

You can register `@on_*` handlers for ongoing events, do a sequential login flow after connecting, then let the handlers keep running.

```python
bot = pyraksamp.SAMPBot("play.example.com", 7777, "MyBot")

@bot.on_player_join()
async def on_join(evt):
    print(f"{evt.name} joined")

@bot.on_chat()
async def on_chat(msg):
    print(f"[chat] {msg.text.stripped}")

await bot.start()

# Sequential login flow — events are not lost while awaiting
dlg = await bot.wait_for_dialog(dialog_type=pyraksamp.InputDialog)
dlg.submit("MyPassword")

# Registered handlers continue to fire from here
await bot.run_until_disconnected()
```

---

## Sequential flow inside a decorator

You can use `wait_for_*` inside an `@on_connect` (or any other) handler to drive a series of dialogs or messages sequentially.

```python
@bot.on_connect
async def connected():
    # select a class from a list dialog
    dlg = await bot.wait_for_dialog(dialog_type=pyraksamp.ListDialog)
    dlg.rows(lambda r: "Civilian" in r.text.stripped).select()

    # wait for spawn confirmation
    await bot.wait_for_client_message(
        predicate=lambda m: "spawned" in m.text.stripped.lower()
    )
    print("Ready to play!")

await bot.start()
await bot.run_until_disconnected()
```

!!! note "Concurrency caveat"
    While this handler is suspended at a `wait_for_*` call, the asyncio event loop keeps running. Other registered handlers will still fire for events that arrive during the wait. This is intentional — it lets you safely await long sequences without blocking the rest of the bot.

---

## Strictly sequential: login first, then register handlers

Handlers can be registered at any time — including after `start()`. This makes a fully sequential approach possible: connect, complete a login flow, then add handlers for ongoing events.

```python
await bot.start()

# Sequential login — no handlers registered yet
dlg = await bot.wait_for_dialog(dialog_type=pyraksamp.InputDialog)
dlg.submit("MyPassword")
await bot.wait_for_client_message(
    predicate=lambda m: "Welcome" in m.text.stripped
)

# Now register handlers for the rest of the session
@bot.on_chat()
async def on_chat(msg):
    print(msg.text.stripped)

@bot.on_dialog()
async def on_dialog(dlg):
    dlg.buttons[0].click()

# Keep running
await bot.run_until_disconnected()
```

Events seen during the `wait_for_*` calls are consumed by those calls and are not replayed to subsequently registered handlers. Handlers only receive events that arrive after they are registered.
