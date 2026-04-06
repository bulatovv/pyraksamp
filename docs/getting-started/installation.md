# Installation

## From PyPI

```
pip install pyraksamp
```

Python 3.12 or later is required.

## From Source

Building from source requires:

- [Rust](https://rustup.rs/) (stable toolchain)
- [maturin](https://github.com/PyO3/maturin) — the Rust/Python build backend
- [uv](https://github.com/astral-sh/uv) (optional, but used in development)

```bash
git clone https://github.com/bulatovv/pyraksamp
cd pyraksamp
pip install maturin
maturin develop
```

Or with uv:

```bash
uv sync
```

The Rust extension (`pyraksamp._core`) is compiled automatically during the build.
It contains the SA:MP UDP handshake, packet encode/decode, keepalive loop, and
the synchronous send methods.
