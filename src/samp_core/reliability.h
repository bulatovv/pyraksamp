#pragma once
#include <cstdint>
#include <vector>
#include <optional>

namespace samp {

// Packet reliability types (SAMP legacy offset: UNRELIABLE starts at 6)
enum Reliability : uint8_t {
    UNRELIABLE           = 6,
    UNRELIABLE_SEQUENCED = 7,
    RELIABLE             = 8,
    RELIABLE_ORDERED     = 9,
    RELIABLE_SEQUENCED   = 10,
};

struct InternalPacket {
    uint16_t    msg_num;
    Reliability reliability;
    uint8_t     ordering_channel;
    uint16_t    ordering_index;
    std::vector<uint8_t> data;
};

// Build a reliability-layer datagram wrapping `data`.
std::vector<uint8_t> make_packet(
    const uint8_t* data, int len,
    uint16_t msg_num,
    Reliability reliability = RELIABLE,
    uint8_t ordering_channel = 0,
    uint16_t ordering_index  = 0
);

// Build an ACK datagram for a list of message numbers.
std::vector<uint8_t> make_ack(const std::vector<uint16_t>& msg_nums);

// Parse a reliability-layer datagram.
// Returns nullopt if the datagram is malformed.
struct ParseResult {
    bool is_ack;
    std::vector<uint16_t>       acked;    // populated when is_ack == true
    std::vector<InternalPacket> packets;  // populated when is_ack == false
};
std::optional<ParseResult> parse(const uint8_t* data, int len);

} // namespace samp
