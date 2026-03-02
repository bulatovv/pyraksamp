#include "reliability.h"
#include "bitstream.h"

namespace samp {

std::vector<uint8_t> make_packet(
    const uint8_t* data, int len,
    uint16_t msg_num,
    Reliability reliability,
    uint8_t ordering_channel,
    uint16_t ordering_index)
{
    BitStream bs;
    bs.write_bool(false);            // isACK = false
    bs.write_uint16_le(msg_num);
    uint8_t rel_byte = static_cast<uint8_t>(reliability);
    bs.write_bits(&rel_byte, 4, true);

    if (reliability == RELIABLE_ORDERED ||
        reliability == RELIABLE_SEQUENCED ||
        reliability == UNRELIABLE_SEQUENCED)
    {
        bs.write_bits(&ordering_channel, 5, true);
        bs.write_uint16_le(ordering_index);
    }

    bs.write_bool(false);            // isSplitPacket = false
    bs.write_compressed_uint16(static_cast<uint16_t>(len * 8));
    bs.write_aligned_bytes(data, len);

    return std::vector<uint8_t>(bs.data(), bs.data() + bs.num_bytes());
}

std::vector<uint8_t> make_ack(const std::vector<uint16_t>& msg_nums) {
    BitStream bs;
    bs.write_bool(true);  // isACK = true
    bs.write_compressed_uint16(static_cast<uint16_t>(msg_nums.size()));
    for (uint16_t n : msg_nums) {
        bs.write_bool(true);   // isSingle = true (each range is a single packet)
        bs.write_uint16_le(n);
    }
    return std::vector<uint8_t>(bs.data(), bs.data() + bs.num_bytes());
}

std::optional<ParseResult> parse(const uint8_t* data, int len) {
    if (len == 0) return std::nullopt;

    BitStream bs(data, len);
    ParseResult result;

    try {
        result.is_ack = bs.read_bool();
    } catch (...) {
        return std::nullopt;
    }

    if (result.is_ack) {
        try {
            uint16_t count = bs.read_compressed_uint16();
            for (uint16_t i = 0; i < count && bs.bits_remaining() >= 17; ++i) {
                bool is_single = bs.read_bool();
                uint16_t min_idx = bs.read_uint16_le();
                if (is_single) {
                    result.acked.push_back(min_idx);
                } else {
                    uint16_t max_idx = bs.read_uint16_le();
                    for (uint16_t j = min_idx; j <= max_idx; ++j)
                        result.acked.push_back(j);
                }
            }
        } catch (...) {}
        return result;
    }

    // Data packet(s): multiple packets may be coalesced in one datagram
    while (bs.bits_remaining() >= 17) {
        try {
            InternalPacket pkt;
            pkt.msg_num = bs.read_uint16_le();

            uint8_t rel_byte = 0;
            bs.read_bits(&rel_byte, 4, true);
            pkt.reliability      = static_cast<Reliability>(rel_byte);
            pkt.ordering_channel = 0;
            pkt.ordering_index   = 0;

            if (pkt.reliability == RELIABLE_ORDERED ||
                pkt.reliability == RELIABLE_SEQUENCED ||
                pkt.reliability == UNRELIABLE_SEQUENCED)
            {
                bs.read_bits(&pkt.ordering_channel, 5, true);
                pkt.ordering_index = bs.read_uint16_le();
            }

            bool is_split = bs.read_bool();
            if (is_split) {
                // Skip: splitPacketId (uint16) + index (compressed uint32) + count (compressed uint32) + data
                bs.read_uint16_le();
                bs.read_compressed_uint32();
                bs.read_compressed_uint32();
                uint16_t data_bits = bs.read_compressed_uint16();
                int data_bytes = (static_cast<int>(data_bits) + 7) / 8;
                std::vector<uint8_t> dummy(data_bytes);
                bs.read_aligned_bytes(dummy.data(), data_bytes);
                continue;
            }

            uint16_t data_bits = bs.read_compressed_uint16();
            int      data_bytes = (data_bits + 7) / 8;

            pkt.data.resize(data_bytes);
            bs.read_aligned_bytes(pkt.data.data(), data_bytes);

            result.packets.push_back(std::move(pkt));
        } catch (...) {
            break;
        }
    }

    return result;
}

} // namespace samp
