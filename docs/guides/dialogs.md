# Working with Dialogs

## Design

SA:MP dialogs are **modal** — the server shows one at a time and the client must respond before anything else can happen. pyraksamp reflects this by turning each incoming dialog into a **self-contained, typed interaction object**.

Each dialog object:

- Knows its own type (`InputDialog`, `ListDialog`, etc.) as a Python class
- Carries its content as structured data (title, body, rows — not raw bytes)
- Exposes `.click()` / `.select()` / `.submit()` methods that send the response directly
- Tracks whether it has been responded to, and raises `DialogAlreadyRespondedError` if you try to respond twice

This design makes dialog handling straightforward: receive the object, inspect it, call the appropriate method.

!!! note "Color codes in dialog text"
    All text fields (`title`, `body`, row `text`, button `label`) are `ColoredString` objects.
    Use `.stripped` to get plain text with color codes removed, or iterate the string to access
    the interleaved `Color` and `str` segments. See [Actions](actions.md#color-codes) for details.

---

## Receiving dialogs

### Decorator

```python
@bot.on_dialog()
async def on_dialog(dlg):
    ...
```

Fires for every dialog. Filter by type or ID:

```python
@bot.on_dialog(dialog_type=pyraksamp.InputDialog)
async def on_input(dlg: pyraksamp.InputDialog):
    dlg.submit("my text")

@bot.on_dialog(dialog_id=42)
async def specific_dialog(dlg):
    dlg.buttons[0].click()
```

### Stream

```python
async for dlg in bot.dialogs():
    if isinstance(dlg, pyraksamp.ListDialog):
        dlg.rows[0].select()
    else:
        dlg.buttons[0].click()
```

### One-shot await

```python
dlg = await bot.wait_for_dialog(dialog_type=pyraksamp.InputDialog)
dlg.submit("hello")
```

---

## Dialog types

### MsgboxDialog (style 0)

A simple message with OK / Cancel buttons.

```python
@bot.on_dialog(dialog_type=pyraksamp.MsgboxDialog)
async def on_msg(dlg: pyraksamp.MsgboxDialog):
    print(dlg.title.stripped)
    print(dlg.body.stripped)
    dlg.ok()       # click the first/OK button
    # dlg.cancel() # click the second/Cancel button
```

### InputDialog (style 1)

A text input field.

```python
@bot.on_dialog(dialog_type=pyraksamp.InputDialog)
async def on_input(dlg: pyraksamp.InputDialog):
    dlg.submit("MyUsername")   # send OK with text
    # dlg.cancel()             # send Cancel
```

### PasswordDialog (style 3)

Same as `InputDialog` but the server renders the field as masked.

```python
@bot.on_dialog(dialog_type=pyraksamp.PasswordDialog)
async def on_password(dlg: pyraksamp.PasswordDialog):
    dlg.submit("s3cr3t")
```

### ListDialog (style 2)

A scrollable list. Each row is a `ListRow` with a `.select()` method.

```python
@bot.on_dialog(dialog_type=pyraksamp.ListDialog)
async def on_list(dlg: pyraksamp.ListDialog):
    # by index
    dlg.rows[0].select()

    # by predicate
    dlg.rows(lambda r: "Civilian" in r.text.stripped).select()

    # iterate
    for row in dlg.rows:
        print(row.index, row.text.stripped)

    # cancel
    dlg.cancel()
```

### TablistDialog (style 4) and TablistHeadersDialog (style 5)

Tabular lists. Each row is a `TablistRow` with a `columns` tuple.

```python
@bot.on_dialog(dialog_type=pyraksamp.TablistDialog)
async def on_tab(dlg: pyraksamp.TablistDialog):
    dlg.rows[0].select()

@bot.on_dialog(dialog_type=pyraksamp.TablistHeadersDialog)
async def on_tab_headers(dlg: pyraksamp.TablistHeadersDialog):
    for header in dlg.headers:
        print(header.stripped)
    for row in dlg.rows:
        # columns by index
        print(row[0].stripped, row[1].stripped)
```

---

## Buttons

All dialogs expose a `buttons` attribute (`ButtonSelector`):

```python
dlg.buttons[0].click()   # first/left/OK button (wire id 1)
dlg.buttons[1].click()   # second/right/Cancel button (wire id 0)

# by predicate
dlg.buttons(lambda b: b.label.stripped == "Accept").click()

# iterate
for btn in dlg.buttons:
    print(btn.label.stripped)
```

`Button.id` is the SA:MP wire ID (`1` for OK, `0` for Cancel).

---

## Double-respond guard

Each dialog tracks its response state. Responding twice raises `DialogAlreadyRespondedError`:

```python
try:
    dlg.buttons[0].click()
    dlg.buttons[0].click()   # raises DialogAlreadyRespondedError
except pyraksamp.DialogAlreadyRespondedError as e:
    print(f"already responded to dialog {e.dialog_id}")
```

Check first if needed:

```python
if not dlg.is_responded:
    dlg.buttons[0].click()
```
