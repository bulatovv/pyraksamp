#include "reliability.h"
#include <cstdint>
#include <cstddef>

// C FFI to Rust samp_rust staticlib
extern "C" {
    // make_packet / make_ack — return heap-allocated Vec<u8>, free with samp_bytes_free
    void*          samp_make_packet(const uint8_t* data, size_t len,
                                    uint16_t msg_num, uint8_t rel,
                                    uint8_t oc, uint16_t oi);
    void*          samp_make_ack(const uint16_t* nums, size_t count);
    const uint8_t* samp_bytes_data(const void* buf);
    size_t         samp_bytes_len(const void* buf);
    void           samp_bytes_free(void* buf);

    // SplitBuffer lifecycle
    void*          samp_split_buf_new();
    void           samp_split_buf_free(void* p);

    // parse — returns null if malformed, otherwise opaque ParseResult handle
    void*          samp_parse(const uint8_t* data, size_t len, void* split_buf);
    void           samp_parse_result_free(void* r);
    bool           samp_parse_result_is_ack(const void* r);
    size_t         samp_parse_result_acked_len(const void* r);
    uint16_t       samp_parse_result_acked_at(const void* r, size_t i);
    size_t         samp_parse_result_packets_len(const void* r);
    uint16_t       samp_parse_result_packet_msg_num(const void* r, size_t i);
    uint8_t        samp_parse_result_packet_rel(const void* r, size_t i);
    uint8_t        samp_parse_result_packet_oc(const void* r, size_t i);
    uint16_t       samp_parse_result_packet_oi(const void* r, size_t i);
    const uint8_t* samp_parse_result_packet_data(const void* r, size_t i, size_t* len_out);
} // extern "C"

namespace samp {

SplitBuffer::SplitBuffer()  : rust_handle(samp_split_buf_new()) {}
SplitBuffer::~SplitBuffer() { samp_split_buf_free(rust_handle); }

std::vector<uint8_t> make_packet(
    const uint8_t* data, int len,
    uint16_t msg_num,
    Reliability reliability,
    uint8_t ordering_channel,
    uint16_t ordering_index)
{
    void* buf = samp_make_packet(data, (size_t)len, msg_num,
                                 (uint8_t)reliability,
                                 ordering_channel, ordering_index);
    std::vector<uint8_t> out(samp_bytes_data(buf),
                              samp_bytes_data(buf) + samp_bytes_len(buf));
    samp_bytes_free(buf);
    return out;
}

std::vector<uint8_t> make_ack(const std::vector<uint16_t>& msg_nums) {
    void* buf = samp_make_ack(msg_nums.data(), msg_nums.size());
    std::vector<uint8_t> out(samp_bytes_data(buf),
                              samp_bytes_data(buf) + samp_bytes_len(buf));
    samp_bytes_free(buf);
    return out;
}

std::optional<ParseResult> parse(const uint8_t* data, int len, SplitBuffer& split_buf) {
    void* r = samp_parse(data, (size_t)len, split_buf.rust_handle);
    if (!r) return std::nullopt;

    ParseResult result;
    result.is_ack = samp_parse_result_is_ack(r);

    size_t acked_len = samp_parse_result_acked_len(r);
    result.acked.reserve(acked_len);
    for (size_t i = 0; i < acked_len; ++i)
        result.acked.push_back(samp_parse_result_acked_at(r, i));

    size_t pkts_len = samp_parse_result_packets_len(r);
    result.packets.reserve(pkts_len);
    for (size_t i = 0; i < pkts_len; ++i) {
        InternalPacket pkt;
        pkt.msg_num          = samp_parse_result_packet_msg_num(r, i);
        pkt.reliability      = static_cast<Reliability>(samp_parse_result_packet_rel(r, i));
        pkt.ordering_channel = samp_parse_result_packet_oc(r, i);
        pkt.ordering_index   = samp_parse_result_packet_oi(r, i);

        size_t dlen = 0;
        const uint8_t* dptr = samp_parse_result_packet_data(r, i, &dlen);
        pkt.data.assign(dptr, dptr + dlen);
        result.packets.push_back(std::move(pkt));
    }

    samp_parse_result_free(r);
    return result;
}

} // namespace samp
