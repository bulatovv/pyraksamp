"""
Tests for the BitStream class defined in bitstream.h.

Bits are stored MSB-first within each byte (bit 0 of stream = MSB of byte 0).
Multi-byte integers use little-endian byte order (matching RakNet on x86).

write_bits(data, count, right_aligned=True):
  If count%8 != 0 and right_aligned=True, the useful bits are in the LOWER
  (right-side) bits of the first data byte.

read_bits(count, right_aligned=True):
  Returns (count+7)//8 bytes; if count%8 != 0 and right_aligned=True, the
  last partial byte is right-shifted so bits land in the lower positions.
"""

import math
import struct
import pytest


# ── Boolean / bit-level ───────────────────────────────────────────────────────


class TestBools:
    def test_write_read_true_false(self, T):
        bs = T.BitStream()
        bs.write_bool(True)
        bs.write_bool(False)
        bs2 = T.BitStream(bs.bytes())
        assert bs2.read_bool() is True
        assert bs2.read_bool() is False

    def test_eight_bools_occupy_one_byte(self, T):
        bs = T.BitStream()
        for _ in range(8):
            bs.write_bool(True)
        assert bs.num_bits() == 8
        assert len(bs.bytes()) == 1

    def test_bool_cross_byte_boundary(self, T):
        bs = T.BitStream()
        for _ in range(7):
            bs.write_bool(True)
        bs.write_u8(0xAB)
        bs2 = T.BitStream(bs.bytes())
        for _ in range(7):
            assert bs2.read_bool() is True
        assert bs2.read_u8() == 0xAB

    def test_alternating_bools(self, T):
        pattern = [True, False, True, True, False, True, False, False]
        bs = T.BitStream()
        for v in pattern:
            bs.write_bool(v)
        bs2 = T.BitStream(bs.bytes())
        for v in pattern:
            assert bs2.read_bool() is v


# ── Integer roundtrips ────────────────────────────────────────────────────────

UINT8_VALS = [0, 1, 127, 128, 255]
UINT16_VALS = [0, 1, 0x7FFF, 0x8000, 0xFFFF]
UINT32_VALS = [0, 1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF]
INT32_VALS = [0, 1, -1, 0x7FFFFFFF, -0x80000000]
FLOAT_VALS = [0.0, -0.0, 1.0, -1.0, 1.5, -1.5, 3.14159, 1e30, -1e30]


@pytest.mark.parametrize("v", UINT8_VALS)
def test_u8_roundtrip(v, T):
    bs = T.BitStream()
    bs.write_u8(v)
    bs2 = T.BitStream(bs.bytes())
    assert bs2.read_u8() == v


@pytest.mark.parametrize("v", UINT16_VALS)
def test_u16_roundtrip(v, T):
    bs = T.BitStream()
    bs.write_u16(v)
    bs2 = T.BitStream(bs.bytes())
    assert bs2.read_u16() == v


@pytest.mark.parametrize("v", UINT32_VALS)
def test_u32_roundtrip(v, T):
    bs = T.BitStream()
    bs.write_u32(v)
    bs2 = T.BitStream(bs.bytes())
    assert bs2.read_u32() == v


@pytest.mark.parametrize("v", INT32_VALS)
def test_i32_roundtrip(v, T):
    bs = T.BitStream()
    bs.write_i32(v)
    bs2 = T.BitStream(bs.bytes())
    assert bs2.read_i32() == v


@pytest.mark.parametrize("v", FLOAT_VALS)
def test_float_roundtrip(v, T):
    bs = T.BitStream()
    bs.write_float(v)
    bs2 = T.BitStream(bs.bytes())
    # Bit-exact roundtrip (including -0.0)
    result = bs2.read_float()
    assert struct.pack("f", result) == struct.pack("f", v)


def test_float_nan_roundtrip(T):

    bs = T.BitStream()
    bs.write_float(float("nan"))
    bs2 = T.BitStream(bs.bytes())
    assert math.isnan(bs2.read_float())


# ── write_bits / read_bits ────────────────────────────────────────────────────


class TestWriteReadBits:
    def test_4bit_right_aligned_roundtrip(self, T):
        bs = T.BitStream()
        bs.write_bits(bytes([0x0A]), 4, True)  # lower 4 bits of 0x0A
        bs2 = T.BitStream(bs.bytes())
        result = bs2.read_bits(4, True)
        assert result == bytes([0x0A])

    def test_8bit_same_as_write_u8(self, T):
        for v in [0x00, 0x55, 0xAA, 0xFF]:
            bs1 = T.BitStream()
            bs1.write_bits(bytes([v]), 8, False)
            bs2 = T.BitStream()
            bs2.write_u8(v)
            assert bs1.bytes() == bs2.bytes()

    def test_3_and_5_bits_cross_byte(self, T):
        bs = T.BitStream()
        bs.write_bits(bytes([0x05]), 3, True)  # 3-bit value: 101
        bs.write_bits(bytes([0x1F]), 5, True)  # 5-bit value: 11111
        bs2 = T.BitStream(bs.bytes())
        r3 = bs2.read_bits(3, True)
        r5 = bs2.read_bits(5, True)
        assert r3 == bytes([0x05])
        assert r5 == bytes([0x1F])

    def test_single_bit(self, T):
        for bit in [0, 1]:
            bs = T.BitStream()
            bs.write_bits(bytes([bit]), 1, True)
            bs2 = T.BitStream(bs.bytes())
            result = bs2.read_bits(1, True)
            assert result == bytes([bit])

    def test_32_bits_roundtrip(self, T):
        data = bytes([0xDE, 0xAD, 0xBE, 0xEF])
        bs = T.BitStream()
        bs.write_bits(data, 32, False)
        bs2 = T.BitStream(bs.bytes())
        result = bs2.read_bits(32, False)
        assert result == data

    def test_mixed_bool_u8_bits(self, T):
        bs = T.BitStream()
        bs.write_bool(True)
        bs.write_u8(0xCC)
        bs.write_bits(bytes([0x03]), 2, True)
        bs2 = T.BitStream(bs.bytes())
        assert bs2.read_bool() is True
        assert bs2.read_u8() == 0xCC
        assert bs2.read_bits(2, True) == bytes([0x03])


# ── Compressed uint16 ─────────────────────────────────────────────────────────
#
# Branch 1: hi==0 AND lo&0xF0==0  → writes: 1 1 [4 bits]       (values 0-15)
# Branch 2: hi==0 AND lo&0xF0!=0  → writes: 1 0 [8 bits]       (values 16-255)
# Branch 3: hi!=0                  → writes: 0 [8 bits lo] [8 bits hi] (values 256-65535)

COMPRESSED_U16_CASES = [
    (0, "branch1"),
    (1, "branch1"),
    (15, "branch1"),
    (16, "branch2"),
    (128, "branch2"),
    (255, "branch2"),
    (256, "branch3"),
    (0x1234, "branch3"),
    (0xFFFF, "branch3"),
]


@pytest.mark.parametrize("v,branch", COMPRESSED_U16_CASES)
def test_compressed_u16_roundtrip(v, branch, T):
    bs = T.BitStream()
    bs.write_compressed_u16(v)
    bs2 = T.BitStream(bs.bytes())
    assert bs2.read_compressed_u16() == v


def test_compressed_u16_branch1_smaller_than_branch2(T):
    """Branch 1 (0-15) uses 6 bits; branch 2 (16-255) uses 10 bits."""
    bs1 = T.BitStream()
    bs1.write_compressed_u16(0)  # branch 1
    bs2 = T.BitStream()
    bs2.write_compressed_u16(16)  # branch 2
    assert bs1.num_bits() < bs2.num_bits()


def test_compressed_u16_branch2_smaller_than_branch3(T):
    bs2 = T.BitStream()
    bs2.write_compressed_u16(255)  # branch 2
    bs3 = T.BitStream()
    bs3.write_compressed_u16(256)  # branch 3
    assert bs2.num_bits() < bs3.num_bits()


def test_compressed_u16_sample_roundtrip(T):
    """Roundtrip a sample of values across the full 0-65535 range."""
    import random

    rng = random.Random(42)
    sample = [0, 15, 16, 255, 256, 0xFFFF] + [rng.randint(0, 0xFFFF) for _ in range(50)]
    for v in sample:
        bs = T.BitStream()
        bs.write_compressed_u16(v)
        bs2 = T.BitStream(bs.bytes())
        assert bs2.read_compressed_u16() == v


# ── Compressed uint32 ─────────────────────────────────────────────────────────
#
# Byte structure: b[0]=LSB .. b[3]=MSB
# b[3]!=0  → 0-bit + all 4 bytes
# b[2]!=0  → 1-bit + 0-bit + b[0..2]
# b[1]!=0  → 1-bit + 1-bit + 0-bit + b[0..1]
# b[0]&F0  → 1*3 + 0-bit + b[0]      (full low byte)
# else     → 1*3 + 1-bit + 4 bits     (nibble)

COMPRESSED_U32_CASES = [
    0,
    1,
    15,  # nibble branch
    16,  # b[0] full byte
    255,  # b[0] full byte
    256,  # b[1] nonzero
    0xFFFF,
    0x10000,  # b[2] nonzero
    0xFFFFFF,
    0x1000000,  # b[3] nonzero
    0xFFFFFFFF,
]


@pytest.mark.parametrize("v", COMPRESSED_U32_CASES)
def test_compressed_u32_roundtrip(v, T):
    bs = T.BitStream()
    bs.write_compressed_u32(v)
    bs2 = T.BitStream(bs.bytes())
    assert bs2.read_compressed_u32() == v


def test_compressed_u32_nibble_branch_smaller(T):
    """0-15 (nibble) should be more compact than 16-255 (byte)."""
    bs_nibble = T.BitStream()
    bs_nibble.write_compressed_u32(0)
    bs_byte = T.BitStream()
    bs_byte.write_compressed_u32(16)
    assert bs_nibble.num_bits() < bs_byte.num_bits()


def test_compressed_u32_sample_roundtrip(T):
    import random

    rng = random.Random(123)
    sample = COMPRESSED_U32_CASES + [rng.randint(0, 0xFFFFFFFF) for _ in range(50)]
    for v in sample:
        bs = T.BitStream()
        bs.write_compressed_u32(v)
        bs2 = T.BitStream(bs.bytes())
        assert bs2.read_compressed_u32() == v


# ── Aligned bytes ─────────────────────────────────────────────────────────────


class TestAlignedBytes:
    def test_write_after_bit_writes(self, T):
        bs = T.BitStream()
        bs.write_bool(True)
        bs.write_bool(False)
        bs.write_bool(True)  # 3 bits written; not byte-aligned
        bs.write_aligned_bytes(b"\xab\xcd")
        bs2 = T.BitStream(bs.bytes())
        assert bs2.read_bool() is True
        assert bs2.read_bool() is False
        assert bs2.read_bool() is True
        # read_aligned_bytes aligns read position to next byte first
        result = bs2.read_aligned_bytes(2)
        assert result == b"\xab\xcd"

    def test_read_aligned_after_bit_reads(self, T):
        bs = T.BitStream()
        bs.write_bool(True)
        bs.write_bool(False)
        bs.write_bool(False)
        bs.write_bool(True)
        bs.write_bool(True)  # 5 bits
        bs.write_aligned_bytes(b"\x42")
        bs2 = T.BitStream(bs.bytes())
        for _ in range(5):
            bs2.read_bool()  # consume 5 bits (not byte-aligned)
        result = bs2.read_aligned_bytes(1)
        assert result == b"\x42"

    def test_zero_length_no_bytes_written(self, T):
        bs = T.BitStream()
        bs.write_u8(0xFF)
        bs.write_aligned_bytes(b"")
        bs2 = T.BitStream(bs.bytes())
        assert bs2.read_u8() == 0xFF

    def test_100_bytes_roundtrip(self, T):
        data = bytes(range(100))
        bs = T.BitStream()
        bs.write_aligned_bytes(data)
        bs2 = T.BitStream(bs.bytes())
        assert bs2.read_aligned_bytes(100) == data


# ── skip_bits ────────────────────────────────────────────────────────────────


class TestSkipBits:
    def test_skip_then_read(self, T):
        bs = T.BitStream()
        bs.write_u8(0xAA)
        bs.write_u8(0xBB)
        bs2 = T.BitStream(bs.bytes())
        bs2.skip_bits(8)  # skip 0xAA
        assert bs2.read_u8() == 0xBB

    def test_skip_past_boundary(self, T):
        bs = T.BitStream()
        bs.write_u8(0x11)
        bs.write_u8(0x22)
        bs2 = T.BitStream(bs.bytes())
        bs2.skip_bits(9)  # skip 8 bits of 0x11 + 1 bit of 0x22
        # Remaining 7 bits of 0x22 (0010001_), then read 7 bits
        remaining = bs2.read_bits(7, True)
        assert remaining == bytes([0x22 & 0x7F])  # lower 7 bits of 0x22

    def test_skip_bools_then_read_u8(self, T):
        bs = T.BitStream()
        bs.write_bool(False)
        bs.write_bool(True)
        bs.write_bool(False)
        bs.write_u8(0xDE)
        bs2 = T.BitStream(bs.bytes())
        bs2.skip_bits(3)
        assert bs2.read_u8() == 0xDE

    def test_bits_remaining_decreases_on_skip(self, T):
        bs = T.BitStream()
        bs.write_u32(0xDEADBEEF)  # 32 bits
        bs2 = T.BitStream(bs.bytes())
        assert bs2.bits_remaining() == 32
        bs2.skip_bits(16)
        assert bs2.bits_remaining() == 16


# ── read_compressed_string (Huffman) ─────────────────────────────────────────


class TestCompressedString:
    def test_empty_string(self, T):
        bs = T.BitStream()
        bs.write_compressed_u16(0)  # bit_len = 0
        bs2 = T.BitStream(bs.bytes())
        assert bs2.read_compressed_string() == ""

    def test_single_char_a(self, T, make_cstring):
        make = make_cstring(T)
        data = make("a")
        bs = T.BitStream(data)
        assert bs.read_compressed_string() == "a"

    def test_short_string_hello(self, T, make_cstring):
        make = make_cstring(T)
        data = make("Hello")
        bs = T.BitStream(data)
        assert bs.read_compressed_string() == "Hello"

    def test_space_character(self, T, make_cstring):
        make = make_cstring(T)
        data = make(" ")
        bs = T.BitStream(data)
        assert bs.read_compressed_string() == " "

    def test_ascii_printable_roundtrip(self, T, make_cstring):
        make = make_cstring(T)
        for text in ["Hello World", "test123", "AAABBBCCC", "abcdefghij"]:
            data = make(text)
            bs = T.BitStream(data)
            assert bs.read_compressed_string() == text

    def test_max_chars_limit(self, T, make_cstring):
        make = make_cstring(T)
        text = "abcde"  # 5 chars
        data = make(text)
        bs = T.BitStream(data)
        # max_chars=4 → result truncated to at most 3 chars (max_chars - 1)
        result = bs.read_compressed_string(4)
        assert len(result) <= 3
        assert result == text[:3]

    def test_newline_character(self, T, make_cstring):
        make = make_cstring(T)
        data = make("\n")
        bs = T.BitStream(data)
        assert bs.read_compressed_string() == "\n"

    def test_longer_string(self, T, make_cstring):
        make = make_cstring(T)
        text = "the quick brown fox jumps"
        data = make(text)
        bs = T.BitStream(data)
        assert bs.read_compressed_string() == text

    def test_underflow_no_crash(self, T, make_cstring):
        """A truncated stream should raise or return partial, never crash."""
        make = make_cstring(T)
        data = make("Hello World")
        # Truncate to half
        truncated = data[: max(1, len(data) // 2)]
        bs = T.BitStream(truncated)
        try:
            result = bs.read_compressed_string()
            # If it doesn't raise, partial is fine
            assert isinstance(result, str)
        except RuntimeError:
            pass  # Expected: BitStream underflow exception


# ── Accessor methods ──────────────────────────────────────────────────────────


class TestAccessors:
    def test_num_bits_after_writes(self, T):
        bs = T.BitStream()
        assert bs.num_bits() == 0
        bs.write_bool(True)
        assert bs.num_bits() == 1
        bs.write_u8(0xFF)
        assert bs.num_bits() == 9
        bs.write_u16(0)
        assert bs.num_bits() == 25

    def test_bits_remaining(self, T):
        bs = T.BitStream()
        bs.write_u16(0x1234)
        bs2 = T.BitStream(bs.bytes())
        assert bs2.bits_remaining() == 16
        bs2.read_u8()
        assert bs2.bits_remaining() == 8
        bs2.read_u8()
        assert bs2.bits_remaining() == 0

    def test_bytes_contains_written_data(self, T):
        bs = T.BitStream()
        bs.write_u8(0xAB)
        bs.write_u8(0xCD)
        buf = bs.bytes()
        assert len(buf) == 2
        assert buf[0] == 0xAB
        assert buf[1] == 0xCD

    def test_construct_from_bytes_preserves_content(self, T):
        data = bytes([0x12, 0x34, 0x56, 0x78])
        bs = T.BitStream(data)
        assert bs.num_bits() == 32
        assert bs.read_u8() == 0x12
        assert bs.read_u8() == 0x34
        assert bs.read_u8() == 0x56
        assert bs.read_u8() == 0x78
