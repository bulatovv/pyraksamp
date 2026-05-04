# PIN Pad

Enter a PIN code by finding and clicking on-screen number buttons rendered as textdraws.

Some SA:MP RP servers replace the standard login dialog with a custom on-screen keypad made of clickable textdraws. This recipe finds each digit button by its label and clicks them in sequence.

```python
import asyncio
import pyraksamp
from pyraksamp import SelectableTextDraw

PIN = "1234"

async def enter_pin(bot: pyraksamp.SAMPBot) -> None:
    # wait until at least one selectable textdraw exists
    await bot.textdraws.wait_for(selectable=True)

    for digit in PIN:
        # find the button whose text is just this digit
        btn = bot.textdraws.find(
            lambda td, d=digit: td.text.stripped == d,
            selectable=True,
        )
        if btn is None:
            raise RuntimeError(f"digit {digit!r} not found on screen")
        btn.click()
        await asyncio.sleep(0.3)

    # find and click the submit button (commonly labeled "OK" or ">>")
    submit = bot.textdraws.find(
        lambda td: td.text.stripped.lower() in ("ok", ">>", "enter", "submit"),
        selectable=True,
    )
    if submit is not None:
        submit.click()

async def main():
    bot = pyraksamp.SAMPBot("play.example.com", 7777, "MyBot")

    @bot.on_connect
    async def connected():
        # some servers show a dialog before the PIN pad
        dlg = await bot.wait_for_dialog()
        dlg.buttons[0].click()

        await enter_pin(bot)
        print("PIN submitted")

    await bot.start()
    await bot.run_until_disconnected()

asyncio.run(main())
```

### Notes

- `text.stripped` removes SA:MP color codes (`{RRGGBB}`) before comparing. Button labels often contain embedded colors for styling.
- The `await asyncio.sleep(0.3)` between clicks gives the server time to process each input. Adjust based on server responsiveness.
- The submit button search covers common labels (`"OK"`, `">>"`, `"Enter"`, `"Submit"`). Check what your target server uses and adjust.
- If the server hides the keypad after submission, you can `await bot.textdraws.wait_until_gone(btn)` to confirm.
