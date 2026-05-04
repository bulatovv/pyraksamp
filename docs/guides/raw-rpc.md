# Custom RPC

Send and receive raw SA:MP RPC packets for server-specific features not covered by the typed API.

pyraksamp provides typed helpers for common events (chat, dialogs, textdraws, etc.). For everything else, you can work at the RPC level directly.

## Receiving RPCs

```python
import pyraksamp

@bot.on_rpc(rpc_id=pyraksamp.RPC_CHAT)
async def on_chat_rpc(rpc_id, data):
    print(f"raw chat RPC: {data!r}")
```

The callback receives `(rpc_id: int, data: bytes)`. Use `rpc_id=` to filter to one RPC, or omit it to receive all:

```python
@bot.on_rpc()
async def all_rpcs(rpc_id, data):
    print(f"RPC {rpc_id}: {len(data)} bytes")
```

## Sending RPCs

```python
bot.send_rpc(pyraksamp.RPC_SERVER_COMMAND, b"/stats\x00")
```

`send_rpc(rpc_id, data, reliability)` returns `bool`. The default reliability is `RELIABLE` — you rarely need to change it.

## Example: custom RPC with struct packing

```python
import asyncio
import struct
import pyraksamp

# Hypothetical custom RPC a server might use
RPC_CUSTOM_TELEPORT = 200

async def main():
    bot = pyraksamp.SAMPBot("play.example.com", 7777, "MyBot")

    @bot.on_rpc(rpc_id=RPC_CUSTOM_TELEPORT)
    async def on_teleport(rpc_id, data):
        x, y, z = struct.unpack("<fff", data[:12])
        print(f"teleported to ({x:.1f}, {y:.1f}, {z:.1f})")

    await bot.start()
    await bot.run_until_disconnected()

asyncio.run(main())
```

## RPC ID reference

pyraksamp exports `RPC_*` constants for known SA:MP 0.3.7 RPCs. For the full protocol specification, refer to external SA:MP protocol documentation.

### Notes

- `on_rpc` fires before any typed event processing. If you handle an RPC here and also via a typed decorator (e.g. `on_chat`), both will fire.
- `data` is raw bytes — no encoding or parsing is applied. Use `struct` or manual slicing as needed.
- `send_rpc` is synchronous and safe to call from async code.
