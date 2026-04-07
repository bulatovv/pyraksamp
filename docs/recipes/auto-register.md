# Auto Register

Handle a login/registration dialog flow sequentially, then stay connected for regular events.

This recipe assumes a typical SA:MP RP server that shows:

1. An `InputDialog` asking for a password (if the account exists) or
2. Two `InputDialog`s for choosing and confirming a new password (if the account is new)

```python
import asyncio
import pyraksamp
from pyraksamp import InputDialog, MsgboxDialog

PASSWORD = "s3cr3t"
USERNAME = "MyBot"

async def main():
    bot = pyraksamp.SAMPBot("play.example.com", 7777, USERNAME)

    await bot.start()
    print(f"Connected as player {bot.player_id}")

    # First dialog: login or register
    dlg = await bot.wait_for_dialog(dialog_type=InputDialog)
    title = dlg.title.stripped.lower()

    if "login" in title:
        dlg.submit(PASSWORD)
        print("Submitted login")

    elif "register" in title:
        dlg.submit(PASSWORD)
        print("Submitted registration password")

        # Confirmation dialog
        dlg2 = await bot.wait_for_dialog(dialog_type=InputDialog)
        dlg2.submit(PASSWORD)
        print("Submitted password confirmation")

    # Wait for server welcome message
    welcome = await bot.wait_for_client_message(
        predicate=lambda m: "welcome" in m.text.stripped.lower()
    )
    print(f"Logged in: {welcome.text.stripped}")

    # Regular event processing from here
    @bot.on_chat()
    async def on_chat(msg):
        print(f"[chat] {msg.text.stripped}")

    @bot.on_dialog()
    async def on_dialog(dlg):
        # dismiss any unexpected dialogs
        dlg.buttons[0].click()

    await bot.run_until_disconnected()

asyncio.run(main())
```

### Notes

- `wait_for_dialog` accepts a `predicate` for more specific matching when multiple dialog types are possible
- If the server shows a `MsgboxDialog` before the input (e.g. a MOTD), add `await bot.wait_for_dialog(dialog_type=MsgboxDialog)` and call `.ok()` on it first
- For servers with multiple login steps, chain `wait_for_dialog` calls sequentially
