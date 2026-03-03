"""
Tests for samp::make_packet(), samp::make_ack(), samp::parse() from reliability.cpp.

Wire layout of a data packet (bits, MSB-first within each byte):
  1  bit : isACK = 0
  16 bits: msg_num (little-endian)
  4  bits: reliability (right-aligned)
  [ordering fields, only for UNRELIABLE_SEQUENCED / RELIABLE_ORDERED / RELIABLE_SEQUENCED:]
    5  bits: ordering_channel (right-aligned)
    16 bits: ordering_index (little-endian)
  1  bit : isSplitPacket
  N  bits: compressed_uint16(data_bit_len)
  (alignment to byte boundary)
  data bytes

ACK packet:
  1  bit : isACK = 1
  N  bits: compressed_uint16(count)
  for each entry:
    1  bit : is_single
    16 bits: min_msg_num (little-endian)
    [if not is_single: 16 bits max_msg_num]
"""

import pytest
import itertools

# ── Constants (must match bindings_test.cpp exports) ─────────────────────────
# These are validated by their own assertions, not hardcoded values.

ALL_RELS = None  # filled in fixture
SEQUENCED_RELS = None


@pytest.fixture(autouse=True, scope="module")
def _rel_constants(T):
    global ALL_RELS, SEQUENCED_RELS
    ALL_RELS = [
        T.UNRELIABLE,
        T.UNRELIABLE_SEQUENCED,
        T.RELIABLE,
        T.RELIABLE_ORDERED,
        T.RELIABLE_SEQUENCED,
    ]
    SEQUENCED_RELS = [T.UNRELIABLE_SEQUENCED, T.RELIABLE_ORDERED, T.RELIABLE_SEQUENCED]


def _craft_split_frag(
    T, msg_num, rel, split_id, frag_idx, frag_count, chunk: bytes
) -> bytes:
    """Manually build a split-packet datagram using BitStream."""
    bs = T.BitStream()
    bs.write_bool(False)  # isACK
    bs.write_u16(msg_num)
    bs.write_bits(bytes([rel]), 4, True)
    # Only RELIABLE_ORDERED / RELIABLE_SEQUENCED / UNRELIABLE_SEQUENCED have ordering fields
    if rel in (T.UNRELIABLE_SEQUENCED, T.RELIABLE_ORDERED, T.RELIABLE_SEQUENCED):
        bs.write_bits(bytes([0]), 5, True)  # ordering_channel = 0
        bs.write_u16(0)  # ordering_index = 0
    bs.write_bool(True)  # isSplitPacket
    bs.write_u16(split_id)
    bs.write_compressed_u32(frag_idx)
    bs.write_compressed_u32(frag_count)
    bs.write_compressed_u16(len(chunk) * 8)
    bs.write_aligned_bytes(chunk)
    return bs.bytes()


def _make_coalesced(T, *packet_specs) -> bytes:
    """Build a properly coalesced RakNet datagram from multiple packet specs.

    Each spec is (data: bytes, msg_num: int, rel: int).  All packet bodies share
    a single BitStream so write_aligned_bytes aligns relative to the datagram
    start — exactly as RakNet's GenerateDatagram does.  Concatenating individual
    make_packet() outputs is wrong because each has its own isACK bit and
    independently-aligned byte fields.
    """
    bs = T.BitStream()
    bs.write_bool(False)  # single isACK=0 for the whole datagram
    for data, msg_num, rel in packet_specs:
        bs.write_u16(msg_num)
        bs.write_bits(bytes([rel]), 4, True)
        if rel in (T.UNRELIABLE_SEQUENCED, T.RELIABLE_ORDERED, T.RELIABLE_SEQUENCED):
            bs.write_bits(bytes([0]), 5, True)  # ordering_channel = 0
            bs.write_u16(0)  # ordering_index = 0
        bs.write_bool(False)  # isSplitPacket
        bs.write_compressed_u16(len(data) * 8)
        bs.write_aligned_bytes(data)
    return bs.bytes()


# ── make_packet / parse roundtrips ───────────────────────────────────────────


class TestMakePacketParse:
    def test_isack_bit_is_zero(self, T):
        pkt = T.make_packet(b"x", 0)
        # First bit of output must be 0 (isACK=false)
        assert (pkt[0] & 0x80) == 0

    @pytest.mark.parametrize("msg_num", [0, 1, 0x7FFF, 0xFFFF])
    def test_msg_num_preserved(self, T, msg_num):
        buf = T.SplitBuffer()
        raw = T.make_packet(b"\xaa", msg_num, T.RELIABLE)
        result = T.parse(raw, buf)
        assert result is not None
        assert len(result["packets"]) == 1
        assert result["packets"][0]["msg_num"] == msg_num

    @pytest.mark.parametrize("rel", [6, 7, 8, 9, 10])  # all five reliability values
    def test_reliability_preserved(self, T, rel):
        buf = T.SplitBuffer()
        raw = T.make_packet(b"\xbb", 0, rel)
        result = T.parse(raw, buf)
        assert result is not None
        assert len(result["packets"]) == 1
        assert result["packets"][0]["reliability"] == rel

    def test_unreliable_smaller_than_sequenced(self, T):
        buf = T.SplitBuffer()
        r_un = T.make_packet(b"hello", 0, T.UNRELIABLE)
        r_seq = T.make_packet(b"hello", 0, T.UNRELIABLE_SEQUENCED)
        assert len(r_un) < len(r_seq)

    def test_reliable_no_ordering_same_size_as_unreliable(self, T):
        buf = T.SplitBuffer()
        r_un = T.make_packet(b"hello", 0, T.UNRELIABLE)
        r_rel = T.make_packet(b"hello", 0, T.RELIABLE)
        assert len(r_un) == len(r_rel)

    @pytest.mark.parametrize("rel", [7, 9, 10])  # SEQUENCED types
    def test_ordering_channel_preserved(self, T, rel):
        for oc in [0, 1, 31]:
            buf = T.SplitBuffer()
            raw = T.make_packet(b"\xcc", 0, rel, oc, 0)
            result = T.parse(raw, buf)
            assert result["packets"][0]["oc"] == oc

    @pytest.mark.parametrize("rel", [7, 9, 10])
    def test_ordering_index_preserved(self, T, rel):
        for oi in [0, 1, 0xFFFF]:
            buf = T.SplitBuffer()
            raw = T.make_packet(b"\xdd", 0, rel, 0, oi)
            result = T.parse(raw, buf)
            assert result["packets"][0]["oi"] == oi

    def test_ordering_fields_absent_for_unreliable(self, T):
        buf = T.SplitBuffer()
        raw = T.make_packet(b"\xaa", 0, T.UNRELIABLE)
        result = T.parse(raw, buf)
        # parse should succeed; ordering fields default to 0
        assert result["packets"][0]["oc"] == 0
        assert result["packets"][0]["oi"] == 0

    def test_ordering_fields_absent_for_reliable(self, T):
        buf = T.SplitBuffer()
        raw = T.make_packet(b"\xaa", 0, T.RELIABLE)
        result = T.parse(raw, buf)
        assert result["packets"][0]["oc"] == 0
        assert result["packets"][0]["oi"] == 0

    def test_is_split_bit_is_false(self, T):
        # After roundtrip, no split reassembly should be in the buffer
        buf = T.SplitBuffer()
        data = b"\xab" * 10
        raw = T.make_packet(data, 5, T.RELIABLE)
        result = T.parse(raw, buf)
        # Exactly one packet with the full data
        pkts = [p for p in result["packets"] if p["data"]]
        assert len(pkts) == 1
        assert pkts[0]["data"] == data

    def test_empty_payload(self, T):
        buf = T.SplitBuffer()
        raw = T.make_packet(b"", 0)
        result = T.parse(raw, buf)
        assert result is not None
        pkts = [p for p in result["packets"] if not p["data"]]
        # Even if data is empty the packet should parse OK
        assert result["is_ack"] is False

    @pytest.mark.parametrize("n", [1, 255])
    def test_payload_sizes(self, T, n):
        buf = T.SplitBuffer()
        data = bytes([0x55] * n)
        raw = T.make_packet(data, 10, T.RELIABLE)
        result = T.parse(raw, buf)
        pkts = [p for p in result["packets"] if p["data"]]
        assert len(pkts) == 1
        assert pkts[0]["data"] == data

    def test_data_round_trip_no_garbage_bits(self, T):
        buf = T.SplitBuffer()
        data = b"\xff" * 7
        raw = T.make_packet(data, 0, T.RELIABLE)
        result = T.parse(raw, buf)
        pkts = [p for p in result["packets"] if p["data"]]
        assert pkts[0]["data"] == data


# ── make_ack / parse ACK branch ──────────────────────────────────────────────


class TestMakeAckParse:
    def test_empty_list(self, T):
        buf = T.SplitBuffer()
        raw = T.make_ack([])
        result = T.parse(raw, buf)
        assert result is not None
        assert result["is_ack"] is True
        assert result["acked"] == []

    def test_single_num(self, T):
        buf = T.SplitBuffer()
        raw = T.make_ack([42])
        result = T.parse(raw, buf)
        assert result["is_ack"] is True
        assert result["acked"] == [42]

    @pytest.mark.parametrize(
        "nums",
        [
            [0, 1, 100, 0xFFFF],
            [0xFFFF],
            [0, 0xFFFF],
            list(range(20)),
        ],
    )
    def test_multiple_nums_preserved(self, T, nums):
        buf = T.SplitBuffer()
        raw = T.make_ack(nums)
        result = T.parse(raw, buf)
        assert result["acked"] == nums

    def test_large_list(self, T):
        nums = list(range(1000))
        buf = T.SplitBuffer()
        raw = T.make_ack(nums)
        result = T.parse(raw, buf)
        assert result["acked"] == nums

    def test_isack_bit_is_set(self, T):
        raw = T.make_ack([1])
        assert raw[0] & 0x80  # first bit is 1 (ACK frame)

    def test_range_ack_parsed(self, T):
        """Hand-craft a range ACK entry: is_single=False, min=3, max=7."""
        bs = T.BitStream()
        bs.write_bool(True)  # isACK
        bs.write_compressed_u16(1)  # count = 1 entry
        bs.write_bool(False)  # is_single = False (range)
        bs.write_u16(3)  # min_idx = 3
        bs.write_u16(7)  # max_idx = 7
        buf = T.SplitBuffer()
        result = T.parse(bs.bytes(), buf)
        assert result["is_ack"] is True
        assert result["acked"] == [3, 4, 5, 6, 7]

    def test_range_ack_two_entries(self, T):
        """Two ACK entries: one range [1,3] and one single [10]."""
        bs = T.BitStream()
        bs.write_bool(True)
        bs.write_compressed_u16(2)  # count = 2
        bs.write_bool(False)
        bs.write_u16(1)
        bs.write_u16(3)  # range 1-3
        bs.write_bool(True)
        bs.write_u16(10)  # single 10
        buf = T.SplitBuffer()
        result = T.parse(bs.bytes(), buf)
        assert set(result["acked"]) == {1, 2, 3, 10}


# ── parse() edge cases ────────────────────────────────────────────────────────


class TestParseEdgeCases:
    def test_empty_input_returns_none(self, T):
        buf = T.SplitBuffer()
        assert T.parse(b"", buf) is None

    def test_one_byte_returns_dict_not_none(self, T):
        buf = T.SplitBuffer()
        # 1 byte: reads isACK bit fine, data loop doesn't execute (< 17 bits remaining)
        result = T.parse(b"\x00", buf)
        assert result is not None
        assert result["is_ack"] is False
        assert result["packets"] == []

    def test_truncated_packet_no_crash(self, T):
        buf = T.SplitBuffer()
        full = T.make_packet(b"\xaa" * 50, 1, T.RELIABLE)
        # Parse only first 3 bytes of a valid packet
        result = T.parse(full[:3], buf)
        # Must not crash; result may be None or empty
        assert result is None or result["packets"] == []

    def test_coalesced_two_packets(self, T):
        buf = T.SplitBuffer()
        result = T.parse(
            _make_coalesced(T, (b"first", 1, T.RELIABLE), (b"second", 2, T.RELIABLE)),
            buf,
        )
        assert result is not None
        data_pkts = [p for p in result["packets"] if p["data"]]
        assert len(data_pkts) == 2
        payloads = {p["data"] for p in data_pkts}
        assert b"first" in payloads
        assert b"second" in payloads

    def test_coalesced_three_packets(self, T):
        buf = T.SplitBuffer()
        specs = [(f"payload{i}".encode(), i, T.RELIABLE) for i in range(3)]
        result = T.parse(_make_coalesced(T, *specs), buf)
        data_pkts = [p for p in result["packets"] if p["data"]]
        assert len(data_pkts) == 3

    @pytest.mark.parametrize("rel", [6, 7, 8, 9, 10])
    def test_all_reliability_types_roundtrip(self, T, rel):
        buf = T.SplitBuffer()
        data = b"\xde\xad\xbe\xef"
        raw = T.make_packet(data, 0, rel)
        result = T.parse(raw, buf)
        pkts = [p for p in result["packets"] if p["data"]]
        assert len(pkts) == 1
        assert pkts[0]["data"] == data
        assert pkts[0]["reliability"] == rel


# ── Split packet reassembly ───────────────────────────────────────────────────


class TestSplitPackets:
    def test_two_frags_in_order(self, T):
        buf = T.SplitBuffer()
        chunk0 = b"Hello, "
        chunk1 = b"World!"
        r0 = T.parse(
            _craft_split_frag(
                T, 1, T.RELIABLE, split_id=0, frag_idx=0, frag_count=2, chunk=chunk0
            ),
            buf,
        )
        r1 = T.parse(
            _craft_split_frag(
                T, 2, T.RELIABLE, split_id=0, frag_idx=1, frag_count=2, chunk=chunk1
            ),
            buf,
        )

        # After first fragment: ACK-only, no assembled packet
        assert not any(p["data"] for p in r0["packets"])
        # After second fragment: assembled packet appears
        assembled = [p for p in r1["packets"] if p["data"]]
        assert len(assembled) == 1
        assert assembled[0]["data"] == chunk0 + chunk1

    def test_two_frags_out_of_order(self, T):
        buf = T.SplitBuffer()
        chunk0 = b"Alpha"
        chunk1 = b"Beta"
        # Send fragment 1 first, then fragment 0
        r1 = T.parse(
            _craft_split_frag(
                T, 1, T.RELIABLE, split_id=1, frag_idx=1, frag_count=2, chunk=chunk1
            ),
            buf,
        )
        r0 = T.parse(
            _craft_split_frag(
                T, 2, T.RELIABLE, split_id=1, frag_idx=0, frag_count=2, chunk=chunk0
            ),
            buf,
        )

        # After sending frag 1 first: no assembly
        assert not any(p["data"] for p in r1["packets"])
        # After frag 0 arrives: assembly complete
        assembled = [p for p in r0["packets"] if p["data"]]
        assert len(assembled) == 1
        assert assembled[0]["data"] == chunk0 + chunk1

    def test_three_frags_in_order(self, T):
        buf = T.SplitBuffer()
        chunks = [b"one", b"two", b"three"]
        results = []
        for i, chunk in enumerate(chunks):
            raw = _craft_split_frag(
                T, i, T.RELIABLE, split_id=2, frag_idx=i, frag_count=3, chunk=chunk
            )
            results.append(T.parse(raw, buf))

        # Only the last result has the assembled packet
        for r in results[:-1]:
            assert not any(p["data"] for p in r["packets"])
        assembled = [p for p in results[-1]["packets"] if p["data"]]
        assert len(assembled) == 1
        assert assembled[0]["data"] == b"".join(chunks)

    def test_three_frags_all_permutations(self, T):
        chunks = [b"AAA", b"BBB", b"CCC"]
        expected = b"AAABBBCCC"
        for perm in itertools.permutations(range(3)):
            buf = T.SplitBuffer()
            results = []
            for idx in perm:
                raw = _craft_split_frag(
                    T,
                    idx,
                    T.RELIABLE,
                    split_id=3,
                    frag_idx=idx,
                    frag_count=3,
                    chunk=chunks[idx],
                )
                results.append(T.parse(raw, buf))
            # The last parse in the permutation should produce the assembled packet
            all_data = [p["data"] for r in results for p in r["packets"] if p["data"]]
            assert len(all_data) == 1
            assert all_data[0] == expected

    def test_missing_fragment_no_output(self, T):
        buf = T.SplitBuffer()
        # Only send fragment 0 of a 2-fragment sequence
        r = T.parse(
            _craft_split_frag(
                T, 1, T.RELIABLE, split_id=4, frag_idx=0, frag_count=2, chunk=b"half"
            ),
            buf,
        )
        assert not any(p["data"] for p in r["packets"])

    def test_duplicate_fragment_no_crash(self, T):
        buf = T.SplitBuffer()
        chunk0 = b"dup"
        chunk1 = b"end"
        # Send frag 0 twice then frag 1
        T.parse(
            _craft_split_frag(
                T, 1, T.RELIABLE, split_id=5, frag_idx=0, frag_count=2, chunk=chunk0
            ),
            buf,
        )
        T.parse(
            _craft_split_frag(
                T, 2, T.RELIABLE, split_id=5, frag_idx=0, frag_count=2, chunk=chunk0
            ),
            buf,
        )
        r = T.parse(
            _craft_split_frag(
                T, 3, T.RELIABLE, split_id=5, frag_idx=1, frag_count=2, chunk=chunk1
            ),
            buf,
        )
        assembled = [p for p in r["packets"] if p["data"]]
        assert len(assembled) == 1
        assert assembled[0]["data"] == chunk0 + chunk1

    def test_two_independent_sequences(self, T):
        buf = T.SplitBuffer()
        # Sequence A (split_id=10), sequence B (split_id=11), interleaved
        T.parse(
            _craft_split_frag(
                T, 0, T.RELIABLE, split_id=10, frag_idx=0, frag_count=2, chunk=b"A0"
            ),
            buf,
        )
        T.parse(
            _craft_split_frag(
                T, 1, T.RELIABLE, split_id=11, frag_idx=0, frag_count=2, chunk=b"B0"
            ),
            buf,
        )
        rA = T.parse(
            _craft_split_frag(
                T, 2, T.RELIABLE, split_id=10, frag_idx=1, frag_count=2, chunk=b"A1"
            ),
            buf,
        )
        rB = T.parse(
            _craft_split_frag(
                T, 3, T.RELIABLE, split_id=11, frag_idx=1, frag_count=2, chunk=b"B1"
            ),
            buf,
        )

        aA = [p["data"] for p in rA["packets"] if p["data"]]
        aB = [p["data"] for p in rB["packets"] if p["data"]]
        assert aA == [b"A0A1"]
        assert aB == [b"B0B1"]

    def test_single_fragment_split(self, T):
        """A split sequence with count=1 reassembles immediately."""
        buf = T.SplitBuffer()
        chunk = b"solo"
        r = T.parse(
            _craft_split_frag(
                T, 0, T.RELIABLE, split_id=20, frag_idx=0, frag_count=1, chunk=chunk
            ),
            buf,
        )
        assembled = [p for p in r["packets"] if p["data"]]
        assert len(assembled) == 1
        assert assembled[0]["data"] == chunk

    def test_zero_length_fragment_no_crash(self, T):
        buf = T.SplitBuffer()
        # Fragment with empty chunk
        r0 = T.parse(
            _craft_split_frag(
                T, 0, T.RELIABLE, split_id=30, frag_idx=0, frag_count=2, chunk=b""
            ),
            buf,
        )
        r1 = T.parse(
            _craft_split_frag(
                T, 1, T.RELIABLE, split_id=30, frag_idx=1, frag_count=2, chunk=b"data"
            ),
            buf,
        )
        assembled = [p for p in r1["packets"] if p["data"]]
        assert assembled[0]["data"] == b"data"
