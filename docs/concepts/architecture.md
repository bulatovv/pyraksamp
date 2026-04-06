# Architecture

## Overview

pyraksamp is split into two layers:

```
Your code (async Python)
        │
        ▼
  SAMPBot  ─── decorators, wait_for_*, streams, send_*
        │
        ▼
  _bridge  ─── translates raw RPC bytes → typed Python objects
        │
        ▼
  _core (Rust / PyO3)
        │
        ▼
  SA:MP UDP wire protocol
```

### Rust core (`pyraksamp._core`)

The Rust extension handles everything that must be fast and correct:

- SA:MP handshake sequence (open-connection, connection-request, auth, init-game)
- UDP keepalive loop running in a dedicated daemon thread
- Packet encode/decode (RakNet framing, bitstream reading/writing)
- Synchronous send methods (`send_rpc`, `send_dialog_response`, `send_keys`, etc.)
- Incoming packet demux: each received RPC is pushed to an asyncio queue via `call_soon_threadsafe`

The Rust thread runs independently of the asyncio event loop. Sends are synchronous (no await needed). Receives are pushed from the Rust thread into the Python event loop without blocking it.

### Bridge (`pyraksamp._bridge`)

The bridge is a Python module that subscribes to raw `(rpc_id, bytes)` pairs from the Rust layer and translates them into typed Python objects, then publishes named events. For example:

- RPC 101 (chat) → parses player ID and text → emits `("chat", ChatMessage(...))`
- RPC 156 (dialog) → parses style/title/buttons/body → constructs the appropriate dialog type → emits `("dialog", InputDialog(...))`
- RPC 83 (textdraw show) → parses all textdraw fields → emits `("textdraw_show", id, flags, ...)`

The bridge runs in the asyncio event loop.

### Dispatcher and listeners

The dispatcher routes named events to registered listeners. Each `@on_*` decorator creates a `_CallbackListener` that subscribes to a specific event tag and spawns an asyncio task for each matching event. `wait_for_*` and `async for` streams use `_StreamListener`, which buffers matching events in a queue.

Handlers registered before `start()` are queued and all started together when the dispatcher begins. Handlers registered after `start()` start immediately. This means you can register handlers at any time without missing events.

### TextDraw registry

The `TextDraws` registry is wired into the dispatcher during `start()` — before any user listeners — so it is always up-to-date by the time your `@on_textdraw()` callbacks fire.

---

## Threading model

| Layer | Thread |
|---|---|
| Rust receive/keepalive loop | background daemon thread (1 per bot) |
| All Python callbacks and streams | asyncio event loop thread |
| Send methods | safe to call from either thread |

You never need to think about threads. All user-facing code runs in the asyncio event loop.
