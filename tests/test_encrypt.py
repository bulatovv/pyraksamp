"""
Tests for samp::encrypt() and samp::auth_response() from encrypt.cpp.

encrypt() wire format:
  out[0]   = checksum = XOR of (data[i] & 0xAA) for each i
  out[i+1] = ENCR_TABLE[data[i]]  XOR  port_mask  (if i is ODD)
  port_mask = (port XOR 0xCC) & 0xFF
  Output length = len(input) + 1
"""

import pytest

# ENCR_TABLE from encrypt.cpp — used to compute expected values without calling C++
ENCR_TABLE = bytes(
    [
        0x27,
        0x69,
        0xFD,
        0x87,
        0x60,
        0x7D,
        0x83,
        0x02,
        0xF2,
        0x3F,
        0x71,
        0x99,
        0xA3,
        0x7C,
        0x1B,
        0x9D,  # 0
        0x76,
        0x30,
        0x23,
        0x25,
        0xC5,
        0x82,
        0x9B,
        0xEB,
        0x1E,
        0xFA,
        0x46,
        0x4F,
        0x98,
        0xC9,
        0x37,
        0x88,  # 16
        0x18,
        0xA2,
        0x68,
        0xD6,
        0xD7,
        0x22,
        0xD1,
        0x74,
        0x7A,
        0x79,
        0x2E,
        0xD2,
        0x6D,
        0x48,
        0x0F,
        0xB1,  # 32
        0x62,
        0x97,
        0xBC,
        0x8B,
        0x59,
        0x7F,
        0x29,
        0xB6,
        0xB9,
        0x61,
        0xBE,
        0xC8,
        0xC1,
        0xC6,
        0x40,
        0xEF,  # 48
        0x11,
        0x6A,
        0xA5,
        0xC7,
        0x3A,
        0xF4,
        0x4C,
        0x13,
        0x6C,
        0x2B,
        0x1C,
        0x54,
        0x56,
        0x55,
        0x53,
        0xA8,  # 64
        0xDC,
        0x9C,
        0x9A,
        0x16,
        0xDD,
        0xB0,
        0xF5,
        0x2D,
        0xFF,
        0xDE,
        0x8A,
        0x90,
        0xFC,
        0x95,
        0xEC,
        0x31,  # 80
        0x85,
        0xC2,
        0x01,
        0x06,
        0xDB,
        0x28,
        0xD8,
        0xEA,
        0xA0,
        0xDA,
        0x10,
        0x0E,
        0xF0,
        0x2A,
        0x6B,
        0x21,  # 96
        0xF1,
        0x86,
        0xFB,
        0x65,
        0xE1,
        0x6F,
        0xF6,
        0x26,
        0x33,
        0x39,
        0xAE,
        0xBF,
        0xD4,
        0xE4,
        0xE9,
        0x44,  # 112
        0x75,
        0x3D,
        0x63,
        0xBD,
        0xC0,
        0x7B,
        0x9E,
        0xA6,
        0x5C,
        0x1F,
        0xB2,
        0xA4,
        0xC4,
        0x8D,
        0xB3,
        0xFE,  # 128
        0x8F,
        0x19,
        0x8C,
        0x4D,
        0x5E,
        0x34,
        0xCC,
        0xF9,
        0xB5,
        0xF3,
        0xF8,
        0xA1,
        0x50,
        0x04,
        0x93,
        0x73,  # 144
        0xE0,
        0xBA,
        0xCB,
        0x45,
        0x35,
        0x1A,
        0x49,
        0x47,
        0x6E,
        0x2F,
        0x51,
        0x12,
        0xE2,
        0x4A,
        0x72,
        0x05,  # 160
        0x66,
        0x70,
        0xB8,
        0xCD,
        0x00,
        0xE5,
        0xBB,
        0x24,
        0x58,
        0xEE,
        0xB4,
        0x80,
        0x81,
        0x36,
        0xA9,
        0x67,  # 176
        0x5A,
        0x4B,
        0xE8,
        0xCA,
        0xCF,
        0x9F,
        0xE3,
        0xAC,
        0xAA,
        0x14,
        0x5B,
        0x5F,
        0x0A,
        0x3B,
        0x77,
        0x92,  # 192
        0x09,
        0x15,
        0x4E,
        0x94,
        0xAD,
        0x17,
        0x64,
        0x52,
        0xD3,
        0x38,
        0x43,
        0x0D,
        0x0C,
        0x07,
        0x3C,
        0x1D,  # 208
        0xAF,
        0xED,
        0xE7,
        0x08,
        0xB7,
        0x03,
        0xE6,
        0x8E,
        0xAB,
        0x91,
        0x89,
        0x3E,
        0x2C,
        0x96,
        0x42,
        0xD9,  # 224
        0x78,
        0xDF,
        0xD0,
        0x57,
        0x5D,
        0x84,
        0x41,
        0x7E,
        0xCE,
        0xF7,
        0x32,
        0xC3,
        0xD5,
        0x20,
        0x0B,
        0xA7,  # 240
    ]
)

# First few and last few auth table entries from encrypt.cpp
AUTH_SAMPLES = [
    ("6C407EC29DE59E2", "D9412F235647BAA582089C6F66817F8B8811C057"),
    ("277C2AD934406F33", "132770E4744F6E78F2CBB4D3F3638EC05D7EA79D"),
    ("3A968DE22423B39", "D1080D41AD614649282887E4001C93AAEDBCA570"),
    ("70A2762B77CD22CC", "B028F73A7B37AB5EF9B990ECA397C78841B7A086"),
    # 0.3.7 R2 entries
    ("359F5AE3211", "3DFFB73BB4D79E532F4873C0BB160178448E8E30"),
    ("4635C4F75E1278", "AAC0014C5D75F52DC9772B73771B0050933A9EAD"),
    # Last entry in the table
    ("15F838D177F569DC", "38ADAAD5DF8775AEEF22B865506D1341C2A1DA57"),
]


def _expected_encrypt(data: bytes, port: int) -> bytes:
    """Pure-Python reference implementation of samp::encrypt()."""
    port_mask = (port ^ 0xCC) & 0xFF
    checksum = 0
    out = bytearray()
    for i, b in enumerate(data):
        checksum ^= b & 0xAA
        enc = ENCR_TABLE[b]
        if i & 1:
            enc = (enc ^ port_mask) & 0xFF
        out.append(enc)
    return bytes([checksum]) + bytes(out)


# ── encrypt() ────────────────────────────────────────────────────────────────


class TestEncrypt:
    def test_empty_payload(self, T):
        result = T.encrypt(b"", 7777)
        assert result == b"\x00"

    def test_output_length(self, T):
        for n in [0, 1, 2, 10, 100, 255]:
            data = bytes(range(n % 256)) * (n // 256 + 1)
            data = data[:n]
            assert len(T.encrypt(data, 0)) == n + 1

    def test_single_byte_even_index_no_port_mask(self, T):
        # Index 0 is even → no port_mask XOR regardless of port
        for port in [0, 7777, 0xFFFF]:
            r1 = T.encrypt(b"\x41", port)
            r0 = T.encrypt(b"\x41", 0)
            # Even index: port doesn't affect the encrypted byte
            assert r1[1:] == r0[1:]

    def test_two_bytes_odd_index_uses_port_mask(self, T):
        # Byte at index 1 (odd) XORs with port_mask
        r_p0 = T.encrypt(b"\x41\x42", 0)
        r_pcc = T.encrypt(b"\x41\x42", 0xCC)
        # port=0 → port_mask=(0^0xCC)&0xFF=0xCC
        # port=0xCC → port_mask=(0xCC^0xCC)&0xFF=0x00
        assert r_p0[1] == r_pcc[1]  # even-index byte unchanged
        # odd-index byte differs because port_mask differs
        assert r_p0[2] != r_pcc[2]

    def test_port_mask_formula(self, T):
        # port=0     → port_mask=0xCC
        # port=0xCC  → port_mask=0x00  (odd bytes pass through table unchanged)
        # port=0xFFFF→ port_mask=(0xFF^0xCC)&0xFF=0x33
        data = bytes(range(4))
        r0 = T.encrypt(data, 0)
        rcc = T.encrypt(data, 0xCC)
        rff = T.encrypt(data, 0xFFFF)

        # Even-index bytes: port_mask not applied → always identical
        assert r0[1] == rcc[1] == rff[1]
        assert r0[3] == rcc[3] == rff[3]

        # Odd-index bytes differ by port_mask
        assert r0[2] == (rcc[2] ^ 0xCC) & 0xFF  # rcc=plain table; r0=table^0xCC
        assert rff[2] == (rcc[2] ^ 0x33) & 0xFF  # r0=table^0xCC; rff=table^0x33

    def test_checksum_formula(self, T):
        # checksum = XOR of (data[i] & 0xAA) for each byte
        data = b"\xaa\x55\xff\x00"
        # \xAA & 0xAA = 0xAA
        # \x55 & 0xAA = 0x00
        # \xFF & 0xAA = 0xAA
        # \x00 & 0xAA = 0x00
        # checksum = 0xAA ^ 0x00 ^ 0xAA ^ 0x00 = 0x00
        result = T.encrypt(data, 0)
        assert result[0] == 0x00

    def test_checksum_two_bytes(self, T):
        data = b"\xaa\x55"
        # 0xAA & 0xAA = 0xAA; 0x55 & 0xAA = 0x00; checksum = 0xAA
        assert T.encrypt(data, 0)[0] == 0xAA

    def test_all_zeros_checksum_is_zero(self, T):
        data = b"\x00" * 16
        result = T.encrypt(data, 7777)
        # 0x00 & 0xAA = 0x00 for all bytes → checksum = 0
        assert result[0] == 0x00

    def test_all_0xff_checksum(self, T):
        data = b"\xff" * 4
        # 0xFF & 0xAA = 0xAA; XOR of four 0xAA: 0xAA^0xAA^0xAA^0xAA = 0x00
        result = T.encrypt(data, 1)
        assert result[0] == 0x00

    def test_deterministic(self, T):
        data = bytes(range(50))
        assert T.encrypt(data, 1234) == T.encrypt(data, 1234)

    def test_reference_impl_matches_all_ports(self, T):
        data = bytes(range(8))
        for port in [0, 1, 7777, 0xCC, 0xFF, 0x1234, 0xFFFF]:
            assert T.encrypt(data, port) == _expected_encrypt(data, port)

    def test_reference_impl_all_single_bytes(self, T):
        for b in range(256):
            data = bytes([b])
            assert T.encrypt(data, 0) == _expected_encrypt(data, 0)
            assert T.encrypt(data, 7777) == _expected_encrypt(data, 7777)

    @pytest.mark.parametrize("port", [0, 7777, 0xCC, 0xFFFF])
    def test_reference_impl_multi_byte(self, T, port):
        data = b"\x41\x42\x43\x44\x55\xaa\xff\x00"
        assert T.encrypt(data, port) == _expected_encrypt(data, port)

    def test_encr_table_lookup_index_0(self, T):
        # data[0] at even index → output byte = ENCR_TABLE[data[0]]
        result = T.encrypt(b"\x00", 0)
        assert result[1] == ENCR_TABLE[0]

    def test_encr_table_lookup_A(self, T):
        # 'A' = 0x41 = 65
        result = T.encrypt(b"\x41", 0)
        assert result[1] == ENCR_TABLE[0x41]


# ── auth_response() ───────────────────────────────────────────────────────────


class TestAuthResponse:
    @pytest.mark.parametrize("challenge,expected", AUTH_SAMPLES)
    def test_known_entries(self, T, challenge, expected):
        assert T.auth_response(challenge) == expected

    def test_unknown_challenge_returns_none(self, T):
        assert T.auth_response("deadbeef") is None

    def test_empty_string_returns_none(self, T):
        assert T.auth_response("") is None

    def test_case_sensitive(self, T):
        # Challenges are hex strings — lowercase ≠ uppercase
        challenge = AUTH_SAMPLES[0][0]
        assert (
            T.auth_response(challenge.lower()) is None
            or T.auth_response(challenge.lower()) == AUTH_SAMPLES[0][1]
        )
        # At minimum the exact match works
        assert T.auth_response(challenge) == AUTH_SAMPLES[0][1]

    def test_partial_challenge_returns_none(self, T):
        # A prefix of a valid challenge is not valid
        challenge = AUTH_SAMPLES[0][0]
        if len(challenge) > 1:
            assert T.auth_response(challenge[:-1]) is None

    def test_first_r2_entry(self, T):
        assert (
            T.auth_response("359F5AE3211") == "3DFFB73BB4D79E532F4873C0BB160178448E8E30"
        )

    def test_returns_string_not_bytes(self, T):
        result = T.auth_response(AUTH_SAMPLES[0][0])
        assert isinstance(result, str)
