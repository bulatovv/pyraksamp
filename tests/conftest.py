"""
Shared fixtures for pyraksamp internal tests.

Build the test module first:
  uv pip install -e . --no-build-isolation -Ccmake.args="-DSAMP_BUILD_TESTS=ON"
"""

import importlib
import pytest

# Fail immediately with a clear message if the test module is not built.
try:
    import _core_test  # noqa: F401
except ImportError as exc:
    raise ImportError(
        "_core_test not found – build it with:\n"
        "  uv pip install -e . --no-build-isolation "
        "-Ccmake.args='-DSAMP_BUILD_TESTS=ON'"
    ) from exc


@pytest.fixture(scope="session")
def T():
    """The _core_test module, loaded once per session."""
    return importlib.import_module("_core_test")


# ── Huffman helpers used by test_bitstream.py ────────────────────────────────

# Same frequency table as englishCharacterFrequencies[] in bitstream.h
_FREQ = [
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    722,
    0,
    0,
    2,
    0,
    0,  # 0-15
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,  # 16-31
    11084,
    58,
    63,
    1,
    0,
    31,
    0,
    317,
    64,
    64,
    44,
    0,
    695,
    62,
    980,
    266,  # 32-47
    69,
    67,
    56,
    7,
    73,
    3,
    14,
    2,
    69,
    1,
    167,
    9,
    1,
    2,
    25,
    94,  # 48-63
    0,
    195,
    139,
    34,
    96,
    48,
    103,
    56,
    125,
    653,
    21,
    5,
    23,
    64,
    85,
    44,  # 64-79
    34,
    7,
    92,
    76,
    147,
    12,
    14,
    57,
    15,
    39,
    15,
    1,
    1,
    1,
    2,
    3,  # 80-95
    0,
    3611,
    845,
    1077,
    1884,
    5870,
    841,
    1057,
    2501,
    3212,
    164,
    531,
    2019,
    1330,
    3056,
    4037,  # 96-111
    848,
    47,
    2586,
    2919,
    4771,
    1707,
    535,
    1106,
    152,
    1243,
    100,
    0,
    2,
    0,
    10,
    0,  # 112-127
    *([0] * 128),  # 128-255
]


def _build_huffman():
    """Build Huffman tree replicating C++ huffman_build() exactly.

    Returns (nodes, root_id) where each node is [value, weight, left, right].
    Leaves: index 0-255, left==right==-1.
    Internal nodes: index 256+.
    Insert-before-first-element-with-weight->= is the tie-breaking rule.
    """
    nodes = []
    for i in range(256):
        w = _FREQ[i] if _FREQ[i] != 0 else 1
        nodes.append([i, w, -1, -1])  # [value, weight, left, right]

    # Build sorted list (ascending weight), insertion sort.
    # "insert BEFORE first element whose weight >= new node's weight"
    sorted_ids = []
    for i in range(256):
        pos = 0
        while pos < len(sorted_ids) and nodes[sorted_ids[pos]][1] < nodes[i][1]:
            pos += 1
        sorted_ids.insert(pos, i)

    # Merge: pop 2 smallest, create parent internal node, re-insert.
    next_id = 256
    while len(sorted_ids) > 1:
        lesser = sorted_ids.pop(0)
        greater = sorted_ids.pop(0)
        pw = nodes[lesser][1] + nodes[greater][1]
        nodes.append([0, pw, lesser, greater])
        parent_id = next_id
        next_id += 1

        pos = 0
        while pos < len(sorted_ids) and nodes[sorted_ids[pos]][1] < pw:
            pos += 1
        sorted_ids.insert(pos, parent_id)

    return nodes, sorted_ids[0]


def _make_code_table(nodes, root):
    """Return dict mapping byte_value → list-of-bits (0=left, 1=right)."""
    codes = {}
    stack = [(root, [])]
    while stack:
        nid, path = stack.pop()
        n = nodes[nid]
        if n[2] == -1:  # leaf
            codes[n[0]] = path
        else:
            stack.append((n[2], path + [0]))  # left  → 0-bit
            stack.append((n[3], path + [1]))  # right → 1-bit
    return codes


_HUFF_NODES, _HUFF_ROOT = _build_huffman()
_HUFF_CODES = _make_code_table(_HUFF_NODES, _HUFF_ROOT)


def huffman_encode(s: str) -> list:
    """Encode string to a list of bits using the RakNet Huffman tree."""
    bits = []
    for ch in s:
        bits.extend(_HUFF_CODES[ord(ch)])
    return bits


def make_compressed_string_bytes(T_mod, s: str) -> bytes:
    """Build the bytes that BitStream.read_compressed_string() decodes to s."""
    bits = huffman_encode(s)
    bs = T_mod.BitStream()
    bs.write_compressed_u16(len(bits))
    for bit in bits:
        bs.write_bool(bool(bit))
    return bs.bytes()


@pytest.fixture(scope="session")
def huff_encode():
    """Return the huffman_encode helper function."""
    return huffman_encode


@pytest.fixture(scope="session")
def make_cstring():
    """Return the make_compressed_string_bytes helper, partially applied to T."""

    def _factory(T_mod):
        def _make(s):
            return make_compressed_string_bytes(T_mod, s)

        return _make

    return _factory
