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

std::optional<ParseResult> parse(const uint8_t* data, int len, SplitBuffer& split_buf) {
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
                uint16_t split_id   = bs.read_uint16_le();
                uint32_t frag_index = bs.read_compressed_uint32();
                uint32_t frag_count = bs.read_compressed_uint32();
                uint16_t data_bits  = bs.read_compressed_uint16();
                int      data_bytes = (static_cast<int>(data_bits) + 7) / 8;
                std::vector<uint8_t> chunk(data_bytes);
                if (data_bytes > 0)
                    bs.read_aligned_bytes(chunk.data(), data_bytes);

                // Emit an ACK-only packet so the caller ACKs this fragment's msg_num.
                InternalPacket frag_ack;
                frag_ack.msg_num          = pkt.msg_num;
                frag_ack.reliability      = pkt.reliability;
                frag_ack.ordering_channel = pkt.ordering_channel;
                frag_ack.ordering_index   = pkt.ordering_index;
                // data is empty → process_packet skips it, but msg_num gets ACK'd
                result.packets.push_back(frag_ack);

                // Buffer the fragment
                auto& frag = split_buf.pending[split_id];
                if (frag.chunks.empty()) {
                    frag.count             = frag_count;
                    frag.reliability       = pkt.reliability;
                    frag.ordering_channel  = pkt.ordering_channel;
                    frag.ordering_index    = pkt.ordering_index;
                }
                frag.chunks[frag_index] = std::move(chunk);

                // When all fragments arrive, reassemble and emit
                if (frag.chunks.size() == frag.count) {
                    InternalPacket assembled;
                    assembled.msg_num          = 0;
                    assembled.reliability      = UNRELIABLE; // already ACK'd per-fragment
                    assembled.ordering_channel = frag.ordering_channel;
                    assembled.ordering_index   = frag.ordering_index;
                    for (uint32_t i = 0; i < frag.count; ++i) {
                        auto& c = frag.chunks[i];
                        assembled.data.insert(assembled.data.end(), c.begin(), c.end());
                    }
                    result.packets.push_back(std::move(assembled));
                    split_buf.pending.erase(split_id);
                }
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
