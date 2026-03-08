import asyncio
import random
import string
import time

import pyraksamp


def random_name() -> str:
    length = random.randint(6, 10)
    return "".join(random.choices(string.ascii_letters, k=length))


def ts() -> str:
    return f"{time.monotonic():.3f}"


async def main():
    name = random_name()
    bot = pyraksamp.SAMPBot("51.91.91.67", 7777, name, server_encoding="windows-1251")
    print(f"[{ts()}] Connecting as {name!r} ...")

    if not await bot.start():
        print(f"[{ts()}] Failed to connect.")
        return

    print(f"[{ts()}] Connected (player_id={bot.player_id})")

    async for event in bot.events():
        tag = event[0]
        t = ts()
        if tag == "disconnect":
            print(f"[{t}] DISCONNECT")
            break
        elif tag == "dialog":
            dlg = event[1]
            print(f"[{t}] DIALOG #{dlg.dialog_id} [{type(dlg).__name__}]")
            print(f"       title  : {dlg.title!r}")
            print(f"       btn1   : {dlg.button1!r}  btn2: {dlg.button2!r}")
            body_preview = dlg.body[:120].replace("\n", "\\n")
            print(f"       body   : {body_preview!r}")
        elif tag == "client_message":
            msg = event[1]
            print(f"[{t}] SERVER_MSG  {msg.text!r}")
        elif tag == "chat":
            msg = event[1]
            print(f"[{t}] CHAT        pid={msg.player_id} {msg.text!r}")
        elif tag == "game_text":
            gt = event[1]
            print(f"[{t}] GAME_TEXT   style={gt.style} {gt.text!r}")
        elif tag == "connect":
            print(f"[{t}] CONNECT")
        elif tag == "rpc":
            rpc_id, data = event[1], event[2]
            print(f"[{t}] RPC #{rpc_id:3d}  ({len(data)} bytes)")
        elif tag in (
            "set_health",
            "set_armour",
            "set_position",
            "spawn_info",
            "toggle_controllable",
            "player_time",
            "world_time",
            "set_armed_weapon",
            "gravity",
            "weather",
            "wanted_level",
            "set_interior",
            "toggle_spectating",
        ):
            print(f"[{t}] {tag.upper():30s} {event[1]}")
        else:
            print(f"[{t}] {tag.upper()}")


asyncio.run(main())
