"""Top-level ``pyraksamp`` CLI dispatcher."""

import sys


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: pyraksamp <subcommand>")
        print("Subcommands:")
        print("  shell    Interactive TUI shell")
        sys.exit(1)

    sub = sys.argv.pop(1)  # remove subcommand so _cli.py sees clean args

    if sub == "shell":
        from pyraksamp.shell._cli import main as shell_main

        shell_main()
    elif sub in ("-h", "--help", "help"):
        print("Usage: pyraksamp <subcommand>")
        print("Subcommands:")
        print("  shell    Interactive TUI shell")
    else:
        print(f"Unknown subcommand: {sub!r}", file=sys.stderr)
        print("Run 'pyraksamp --help' for usage.", file=sys.stderr)
        sys.exit(1)
