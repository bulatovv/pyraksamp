# Key Presser

Control the bot's in-game key state to perform actions like sprinting, firing, or entering vehicles.

## Timed key press

```python
import asyncio
import pyraksamp
from pyraksamp import Keys

async def main():
    bot = pyraksamp.SAMPBot("play.example.com", 7777, "KeyBot")

    @bot.on_connect
    async def connected():
        # Sprint for 3 seconds
        await bot.press_keys(Keys.SPRINT, duration=3.0)

        # Combine keys
        await bot.press_keys(Keys.SPRINT | Keys.JUMP, duration=0.5)

    await bot.start()
    async for _ in bot.events():
        pass

asyncio.run(main())
```

## Sticky key state

`send_keys` sets the state until changed — useful for continuous movement:

```python
@bot.on_spawn_info
async def on_spawn(info):
    # start sprinting
    bot.send_keys(Keys.SPRINT)
    await asyncio.sleep(5)
    # stop
    bot.send_keys(0)
```

## Fire and forget

`press_keys` is awaitable but you can run it in the background:

```python
asyncio.create_task(bot.press_keys(Keys.FIRE, duration=2.0))
# continues immediately; fire keeps going in background
```

## Concurrent key presses

Multiple concurrent `press_keys` calls for the same key are ref-counted: the key stays held until all calls complete.

```python
async def hold_sprint():
    await bot.press_keys(Keys.SPRINT, duration=5.0)

async def also_jump():
    await asyncio.sleep(1)
    await bot.press_keys(Keys.JUMP, duration=0.5)
    # SPRINT is still held from hold_sprint

asyncio.gather(hold_sprint(), also_jump())
```

## Entering a vehicle

```python
# Enter as driver
bot.send_enter_vehicle(vehicle_id=42, is_passenger=False)

# Enter as passenger
bot.send_enter_vehicle(vehicle_id=42, is_passenger=True)

# Exit
bot.send_exit_vehicle(vehicle_id=42)
```
