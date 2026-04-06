#!/usr/bin/env python3
"""Generate docs/api/ pages from pyraksamp's public submodules.

Run from the project root:
    python scripts/gen_api_docs.py

Re-run whenever submodules are added or removed. The generated pages use
plain `:::` directives with no member listing — mkdocstrings discovers
public members automatically from each module's __all__.

Pages that are NOT generated (maintained by hand because they contain
non-Python content or Rust-sourced symbols):
    docs/api/index.md     — overview table
    docs/api/constants.md — Keys enum + RPC ID tables
    docs/api/exceptions.md — Rust-sourced exception hierarchy
"""

import pathlib
import textwrap

PACKAGE = "pyraksamp"
SRC_ROOT = pathlib.Path("src") / PACKAGE
DOCS_API = pathlib.Path("docs") / "api"


def public_submodules() -> list[tuple[str, str, str]]:
    """Return (dotpath, page_stem, title) for each public submodule."""
    results = []
    for path in sorted(SRC_ROOT.iterdir()):
        name = path.name
        if name.startswith("_"):
            continue
        if path.suffix == ".py":
            stem = path.stem
        elif path.is_dir() and (path / "__init__.py").exists():
            stem = name
        else:
            continue
        dotpath = f"{PACKAGE}.{stem}"
        title = stem.replace("_", " ").title()
        results.append((dotpath, stem, title))
    return results


def page_content(dotpath: str, title: str) -> str:
    """Return the markdown content for one API page."""
    return textwrap.dedent(f"""\
        # {title}

        ::: {dotpath}
    """)


def main() -> None:
    DOCS_API.mkdir(parents=True, exist_ok=True)
    modules = public_submodules()

    # Always generate the main SAMPBot page from pyraksamp itself.
    bot_page = DOCS_API / "bot.md"
    bot_page.write_text(textwrap.dedent(f"""\
        # SAMPBot

        ::: {PACKAGE}.SAMPBot

        ::: {PACKAGE}.gen_gpci
    """))
    print(f"  wrote {bot_page}")

    # Generate one page per public submodule.
    for dotpath, stem, title in modules:
        page = DOCS_API / f"{stem}.md"
        page.write_text(page_content(dotpath, title))
        print(f"  wrote {page}  ({dotpath})")

    # Print a reminder about manually maintained pages.
    manual = ["index.md", "constants.md", "exceptions.md"]
    print(f"\nManually maintained (not touched): {', '.join(manual)}")


if __name__ == "__main__":
    main()
