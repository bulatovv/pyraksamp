#include "client.h"
#include "bitstream.h"
#include "encrypt.h"
#include "reliability.h"

#include <arpa/inet.h>
#include <cerrno>
#include <chrono>
#include <cstring>
#include <ctime>
#include <netdb.h>
#include <stdexcept>
#include <sys/socket.h>
#include <thread>
#include <unistd.h>

namespace samp {

// ─── helpers ────────────────────────────────────────────────────────────────

static double now_sec() {
    using namespace std::chrono;
    return duration<double>(steady_clock::now().time_since_epoch()).count();
}

static bool recv_with_timeout(int fd, uint8_t* buf, int buflen,
                               uint32_t server_ip_be, int& out_len,
                               double timeout_sec)
{
    auto deadline = now_sec() + timeout_sec;
    while (now_sec() < deadline) {
        fd_set fds; FD_ZERO(&fds); FD_SET(fd, &fds);
        double remaining = deadline - now_sec();
        if (remaining <= 0) break;
        struct timeval tv;
        tv.tv_sec  = static_cast<long>(remaining);
        tv.tv_usec = static_cast<long>((remaining - tv.tv_sec) * 1e6);

        int ret = select(fd + 1, &fds, nullptr, nullptr, &tv);
        if (ret <= 0) break;

        struct sockaddr_in from{};
        socklen_t fromlen = sizeof(from);
        int n = recvfrom(fd, buf, buflen, 0,
                         reinterpret_cast<sockaddr*>(&from), &fromlen);
        if (n > 0 && from.sin_addr.s_addr == server_ip_be) {
            out_len = n;
            return true;
        }
    }
    return false;
}

// ─── ctor/dtor ───────────────────────────────────────────────────────────────

SAMPClient::SAMPClient(const std::string& host, uint16_t port,
                       const std::string& nick, const std::string& pass,
                       const std::string& gpci)
    : host_(host), port_(port), nickname_(nick), password_(pass), gpci_(gpci)
{
    if (gpci_.empty()) {
        // Hardcoded valid GPCI (divisible by 1001, 36 hex chars)
        gpci_ = "3E9B8D0C4A7F2E6B1D5A3C9E8F2B4D6A0C7E9B3";
    }
}

SAMPClient::~SAMPClient() {
    if (sock_fd_ >= 0) { ::close(sock_fd_); sock_fd_ = -1; }
}

// ─── network primitives ──────────────────────────────────────────────────────

void SAMPClient::send_raw(const void* data, int len) {
    struct sockaddr_in addr{};
    addr.sin_family      = AF_INET;
    addr.sin_addr.s_addr = server_ip_;
    addr.sin_port        = htons(port_);
    sendto(sock_fd_, data, len, 0, reinterpret_cast<sockaddr*>(&addr), sizeof(addr));
}

void SAMPClient::send_encrypted(const void* data, int len) {
    auto enc = encrypt(reinterpret_cast<const uint8_t*>(data), len, port_);
    send_raw(enc.data(), static_cast<int>(enc.size()));
}

void SAMPClient::send_reliability_pkt(const std::vector<uint8_t>& data,
                                       Reliability rel, uint8_t oc, uint16_t oi)
{
    uint16_t num = send_msg_num_++;
    auto pkt = make_packet(data.data(), static_cast<int>(data.size()), num, rel, oc, oi);
    send_encrypted(pkt.data(), static_cast<int>(pkt.size()));
}

void SAMPClient::send_acks(const std::vector<uint16_t>& nums) {
    if (nums.empty()) return;
    auto pkt = make_ack(nums);
    send_encrypted(pkt.data(), static_cast<int>(pkt.size()));
}

void SAMPClient::flush_acks() {
    std::vector<uint16_t> acks;
    { std::lock_guard<std::mutex> lk(ack_mutex_); acks.swap(pending_acks_); }
    send_acks(acks);
}

// ─── handshake ───────────────────────────────────────────────────────────────

bool SAMPClient::do_handshake(double timeout_sec) {
    uint8_t req[3] = {ID_OPEN_CONNECTION_REQUEST, 0, 0};
    send_encrypted(req, 3);

    uint8_t buf[256];
    int     len = 0;
    auto    deadline = now_sec() + timeout_sec;

    while (now_sec() < deadline) {
        double remaining = deadline - now_sec();
        if (!recv_with_timeout(sock_fd_, buf, sizeof(buf), server_ip_, len, std::min(remaining, 1.0)))
            continue;

        if (len >= 3 && buf[0] == ID_OPEN_CONNECTION_COOKIE) {
            uint8_t lo = buf[1], hi = buf[2];
            uint8_t reply[3] = {
                ID_OPEN_CONNECTION_REQUEST,
                static_cast<uint8_t>(lo ^ (NETCODE_CONNCOOKIELULZ & 0xFF)),
                static_cast<uint8_t>(hi ^ ((NETCODE_CONNCOOKIELULZ >> 8) & 0xFF)),
            };
            send_encrypted(reply, 3);
            continue;
        }

        if (len >= 1 && buf[0] == ID_OPEN_CONNECTION_REPLY) {
            return true;
        }
    }
    return false;
}

// ─── auth/connection ─────────────────────────────────────────────────────────

void SAMPClient::handle_auth_key(const uint8_t* data, int len) {
    if (len < 2) return;
    int key_len = data[1];
    if (len < 2 + key_len) return;

    // Challenge is key_len bytes (includes null terminator sent by server)
    std::string challenge(reinterpret_cast<const char*>(data + 2), key_len);
    // Strip null bytes
    while (!challenge.empty() && challenge.back() == '\0') challenge.pop_back();

    const char* resp = auth_response(challenge.c_str());
    if (!resp) resp = "";  // unknown key → send empty (will likely be rejected)

    int resp_len = static_cast<int>(strlen(resp));
    std::vector<uint8_t> pkt(2 + resp_len);
    pkt[0] = ID_AUTH_KEY;
    pkt[1] = static_cast<uint8_t>(resp_len);
    memcpy(pkt.data() + 2, resp, resp_len);
    send_reliability_pkt(pkt, RELIABLE);
}

void SAMPClient::handle_connection_accepted(const uint8_t* data, int len) {
    if (len < 9) return;
    BitStream bs(data, len);
    try {
        bs.skip_bits(8);   // ID_CONNECTION_REQUEST_ACCEPTED
        bs.skip_bits(32);  // binaryAddress
        bs.skip_bits(16);  // port
        player_id_ = bs.read_uint16_le();
        challenge_  = bs.read_uint32_le();
    } catch (...) { return; }

    // Send ID_NEW_INCOMING_CONNECTION so server transitions to CONNECTED state.
    // Without this, GetPlayerIDFromIndex() returns UNASSIGNED_PLAYER_ID and the
    // server's ClientJoin handler silently drops our RPC as a "possible bot".
    {
        std::vector<uint8_t> nic(7);
        nic[0] = ID_NEW_INCOMING_CONNECTION;
        memcpy(nic.data() + 1, &server_ip_, 4);  // server IP (network byte order)
        uint16_t p = port_;
        memcpy(nic.data() + 5, &p, 2);           // server port (LE)
        send_reliability_pkt(nic, RELIABLE);
        fprintf(stderr, "[cj] sent ID_NEW_INCOMING_CONNECTION\n");
    }

    send_client_join();
}

void SAMPClient::send_client_join() {
    BitStream bs;
    std::string nick = nickname_.substr(0, 20);
    std::string gpci = gpci_.substr(0, 63);
    std::string ver  = "0.3.7";

    uint32_t challenge_resp = static_cast<uint32_t>(challenge_ ^ NETGAME_VERSION);

    // Write as flat LE bytes (all Write() calls on aligned BitStream = raw bytes)
    int32_t version = NETGAME_VERSION;
    bs.write_bits(reinterpret_cast<const uint8_t*>(&version), 32, true);
    uint8_t mod = 1;
    bs.write_uint8(mod);
    bs.write_uint8(static_cast<uint8_t>(nick.size()));
    bs.write_aligned_bytes(reinterpret_cast<const uint8_t*>(nick.data()),
                           static_cast<int>(nick.size()));
    bs.write_bits(reinterpret_cast<const uint8_t*>(&challenge_resp), 32, true);
    bs.write_uint8(static_cast<uint8_t>(gpci.size()));
    bs.write_aligned_bytes(reinterpret_cast<const uint8_t*>(gpci.data()),
                           static_cast<int>(gpci.size()));
    bs.write_uint8(static_cast<uint8_t>(ver.size()));
    bs.write_aligned_bytes(reinterpret_cast<const uint8_t*>(ver.data()),
                           static_cast<int>(ver.size()));

    std::vector<uint8_t> payload(bs.data(), bs.data() + bs.num_bytes());
    // Build RPC packet
    BitStream rpc_bs;
    rpc_bs.write_uint8(ID_RPC);
    rpc_bs.write_uint8(RPC_CLIENT_JOIN);
    rpc_bs.write_compressed_uint32(static_cast<uint32_t>(payload.size() * 8));
    rpc_bs.write_bits(payload.data(), static_cast<int>(payload.size() * 8), false);

    std::vector<uint8_t> rpc_pkt(rpc_bs.data(), rpc_bs.data() + rpc_bs.num_bytes());
    fprintf(stderr, "[cj] ClientJoin RPC len=%d: ", (int)rpc_pkt.size());
    for (int i = 0; i < std::min((int)rpc_pkt.size(), 32); i++)
        fprintf(stderr, "%02x ", rpc_pkt[i]);
    fprintf(stderr, "...\n");
    fprintf(stderr, "[cj] payload len=%d ch=0x%08x pid=%d\n",
            (int)payload.size(), challenge_resp, player_id_);
    send_reliability_pkt(rpc_pkt, RELIABLE);
}

bool SAMPClient::do_connection_request(double timeout_sec) {
    // Send ID_CONNECTION_REQUEST
    std::vector<uint8_t> cr = {ID_CONNECTION_REQUEST};
    if (!password_.empty()) {
        cr.insert(cr.end(), password_.begin(), password_.end());
    }
    send_reliability_pkt(cr, RELIABLE);

    uint8_t buf[2048];
    int     len = 0;
    auto    deadline = now_sec() + timeout_sec;
    int dcr_pkt = 0;

    while (now_sec() < deadline) {
        double remaining = deadline - now_sec();
        if (!recv_with_timeout(sock_fd_, buf, sizeof(buf), server_ip_, len, std::min(remaining, 0.5)))
            continue;

        ++dcr_pkt;
        fprintf(stderr, "[dcr] pkt#%d len=%d id=0x%02x\n", dcr_pkt, len, buf[0]);

        // Try to parse as raw auth key (sometimes sent before reliability layer)
        if (len >= 2 && buf[0] == ID_AUTH_KEY) {
            handle_auth_key(buf, len);
            continue;
        }

        auto result = parse(buf, len);
        if (!result) {
            fprintf(stderr, "[dcr] parse failed pkt#%d\n", dcr_pkt);
            continue;
        }

        if (result->is_ack) {
            fprintf(stderr, "[dcr] ACK pkt#%d acked=%zu\n", dcr_pkt, result->acked.size());
            continue;
        }

        fprintf(stderr, "[dcr] data pkt#%d: %zu internal packets\n", dcr_pkt, result->packets.size());
        for (auto& pkt : result->packets) {
            fprintf(stderr, "  -> msg_num=%d rel=%d data_len=%zu id=0x%02x\n",
                    pkt.msg_num, (int)pkt.reliability,
                    pkt.data.size(), pkt.data.empty() ? 0 : pkt.data[0]);
            // ACK reliable packets
            if (pkt.reliability == RELIABLE || pkt.reliability == RELIABLE_ORDERED) {
                std::lock_guard<std::mutex> lk(ack_mutex_);
                pending_acks_.push_back(pkt.msg_num);
            }
            flush_acks();

            if (pkt.data.empty()) continue;

            switch (pkt.data[0]) {
            case ID_AUTH_KEY:
                handle_auth_key(pkt.data.data(), static_cast<int>(pkt.data.size()));
                break;
            case ID_CONNECTION_REQUEST_ACCEPTED:
                handle_connection_accepted(pkt.data.data(), static_cast<int>(pkt.data.size()));
                connected_ = true;
                fprintf(stderr, "[dcr] ConnectionAccepted! player_id=%d\n", player_id_);
                return true;
            case ID_CONNECTION_BANNED:
            case ID_INVALID_PASSWORD:
            case ID_NO_FREE_INCOMING_CONNECTIONS:
            case ID_CONNECTION_ATTEMPT_FAILED:
                fprintf(stderr, "[dcr] Connection REJECTED id=0x%02x\n", pkt.data[0]);
                return false;
            }
        }
    }
    return false;
}

// ─── game packet handlers ────────────────────────────────────────────────────

bool SAMPClient::send_rpc(uint8_t rpc_id, const std::vector<uint8_t>& payload,
                           Reliability rel)
{
    BitStream bs;
    bs.write_uint8(ID_RPC);
    bs.write_uint8(rpc_id);
    bs.write_compressed_uint32(static_cast<uint32_t>(payload.size() * 8));
    if (!payload.empty())
        bs.write_bits(payload.data(), static_cast<int>(payload.size() * 8), false);

    std::vector<uint8_t> pkt(bs.data(), bs.data() + bs.num_bytes());
    send_reliability_pkt(pkt, rel);
    return true;
}

void SAMPClient::request_class_and_spawn() {
    // RequestClass
    {
        int32_t class_id = 0;
        std::vector<uint8_t> p(4);
        memcpy(p.data(), &class_id, 4);
        send_rpc(RPC_REQUEST_CLASS, p);
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    // RequestSpawn
    send_rpc(RPC_REQUEST_SPAWN, {});
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    // Spawn
    send_rpc(RPC_SPAWN, {});
}

void SAMPClient::handle_init_game(const uint8_t* /*data*/, int /*len*/) {
    // We don't need to parse InitGame fully for a PoC.
    // Just trigger spawn sequence.
    request_class_and_spawn();
    connected_ = true;

    if (on_connect) on_connect();
}

void SAMPClient::handle_rpc(uint8_t rpc_id, const uint8_t* payload, int len) {
    fprintf(stderr, "[rpc] id=%d (0x%02x) payload_len=%d\n", rpc_id, rpc_id, len);
    if (rpc_id == RPC_INIT_GAME) {
        handle_init_game(payload, len);
    } else if (rpc_id == RPC_CONNECTION_REJ) {
        running_ = false;
    } else if (rpc_id == RPC_SERVER_JOIN && len >= 8) {
        if (on_player_join) {
            uint16_t pid; memcpy(&pid, payload, 2);
            int isNPC = payload[6];
            int nameLen = payload[7];
            std::string name;
            if (nameLen > 0 && len >= 8 + nameLen)
                name.assign(reinterpret_cast<const char*>(payload + 8), nameLen);
            on_player_join(pid, name);
        }
    }

    if (on_rpc) {
        on_rpc(rpc_id, std::vector<uint8_t>(payload, payload + len));
    }
}

void SAMPClient::process_packet(const InternalPacket& pkt) {
    if (pkt.data.empty()) return;

    switch (pkt.data[0]) {
    case ID_RPC: {
        if (pkt.data.size() < 2) return;
        BitStream bs(pkt.data.data(), static_cast<int>(pkt.data.size()));
        bs.skip_bits(8);  // ID_RPC
        uint8_t rpc_id = 0;
        uint32_t bit_len = 0;
        int byte_len = 0;
        try {
            rpc_id = bs.read_uint8();
            bit_len = bs.read_compressed_uint32();
            byte_len = (static_cast<int>(bit_len) + 7) / 8;
        } catch (const std::exception& e) {
            fprintf(stderr, "[rpc] parse header failed: %s (data_len=%zu)\n",
                    e.what(), pkt.data.size());
            return;
        }
        std::vector<uint8_t> payload(byte_len);
        try {
            if (byte_len > 0)
                bs.read_bits(payload.data(), static_cast<int>(bit_len), false);
        } catch (const std::exception& e) {
            fprintf(stderr, "[rpc] read payload failed rpc_id=%d bit_len=%u: %s\n",
                    rpc_id, bit_len, e.what());
            return;
        }
        handle_rpc(rpc_id, payload.data(), byte_len);
        break;
    }
    case ID_INTERNAL_PING: {
        if (pkt.data.size() < 5) return;
        uint32_t ts; memcpy(&ts, pkt.data.data() + 1, 4);
        BitStream resp;
        resp.write_uint8(ID_CONNECTED_PONG);
        resp.write_bits(reinterpret_cast<uint8_t*>(&ts), 32, true);
        std::vector<uint8_t> rpkt(resp.data(), resp.data() + resp.num_bytes());
        send_reliability_pkt(rpkt, UNRELIABLE);
        break;
    }
    case ID_DISCONNECTION_NOTIFICATION:
    case ID_CONNECTION_LOST:
        running_ = false;
        if (on_disconnect) on_disconnect();
        break;
    case ID_AUTH_KEY:
        handle_auth_key(pkt.data.data(), static_cast<int>(pkt.data.size()));
        break;
    case ID_CONNECTION_REQUEST_ACCEPTED:
        if (!connected_) handle_connection_accepted(pkt.data.data(),
                                                     static_cast<int>(pkt.data.size()));
        break;
    }
}

void SAMPClient::send_keepalive() {
    // Minimal on-foot sync: just booleans/zeros to satisfy the server
    BitStream bs;
    bs.write_uint8(207);  // ID_PLAYER_SYNC
    bs.write_bool(false); // bHasLR
    bs.write_bool(false); // bHasUD
    bs.write_uint16_le(0); // wKeys
    // vecPos (3 floats)
    float zero = 0.0f; float ground = 3.0f;
    bs.write_bits(reinterpret_cast<uint8_t*>(&zero),   32, true);
    bs.write_bits(reinterpret_cast<uint8_t*>(&zero),   32, true);
    bs.write_bits(reinterpret_cast<uint8_t*>(&ground), 32, true);
    // quat (4 floats, identity)
    bs.write_bits(reinterpret_cast<uint8_t*>(&zero), 32, true);
    bs.write_bits(reinterpret_cast<uint8_t*>(&zero), 32, true);
    bs.write_bits(reinterpret_cast<uint8_t*>(&zero), 32, true);
    float one = 1.0f;
    bs.write_bits(reinterpret_cast<uint8_t*>(&one),  32, true);
    bs.write_uint8(0xF0); // health=100, armour=0
    bs.write_uint8(0);    // weapon
    bs.write_uint8(0);    // special action
    bs.write_bits(reinterpret_cast<uint8_t*>(&zero), 32, true); // moveSpeed x
    bs.write_bits(reinterpret_cast<uint8_t*>(&zero), 32, true); // moveSpeed y
    bs.write_bits(reinterpret_cast<uint8_t*>(&zero), 32, true); // moveSpeed z
    bs.write_bool(false); // bHasSurfInfo
    bs.write_bool(false); // bHasAnim

    std::vector<uint8_t> pkt(bs.data(), bs.data() + bs.num_bytes());
    send_reliability_pkt(pkt, UNRELIABLE);
}

// ─── public API ──────────────────────────────────────────────────────────────

bool SAMPClient::connect(double timeout_sec) {
    // Resolve host
    struct hostent* he = gethostbyname(host_.c_str());
    if (!he) return false;
    server_ip_ = *reinterpret_cast<uint32_t*>(he->h_addr_list[0]); // network byte order

    // Open UDP socket
    sock_fd_ = ::socket(AF_INET, SOCK_DGRAM, 0);
    if (sock_fd_ < 0) return false;

    double half = timeout_sec / 2.0;
    if (!do_handshake(half))           return false;
    if (!do_connection_request(half))  return false;
    return connected_.load();
}

void SAMPClient::run() {
    running_ = true;
    double last_keepalive = now_sec();
    double last_ack_flush = now_sec();
    int total_pkts = 0;

    while (running_) {
        double n = now_sec();

        if (n - last_ack_flush > 0.05) {
            flush_acks();
            last_ack_flush = n;
        }
        if (n - last_keepalive > 0.5) {
            send_keepalive();
            last_keepalive = n;
        }

        uint8_t buf[2048];
        int     len = 0;
        if (!recv_with_timeout(sock_fd_, buf, sizeof(buf), server_ip_, len, 0.1))
            continue;

        ++total_pkts;
        fprintf(stderr, "[run] pkt#%d len=%d id=0x%02x\n", total_pkts, len, buf[0]);

        // Raw auth key (before reliability layer)
        if (len >= 2 && buf[0] == ID_AUTH_KEY) {
            handle_auth_key(buf, len);
            continue;
        }

        auto result = parse(buf, len);
        if (!result) {
            fprintf(stderr, "[run] parse failed for pkt#%d\n", total_pkts);
            continue;
        }
        if (result->is_ack) {
            fprintf(stderr, "[run] pkt#%d is ACK, acked=%zu:", total_pkts, result->acked.size());
            for (auto n : result->acked) fprintf(stderr, " %d", (int)n);
            fprintf(stderr, "\n");
            continue;
        }

        fprintf(stderr, "[run] pkt#%d has %zu internal packets\n", total_pkts, result->packets.size());
        for (auto& pkt : result->packets) {
            fprintf(stderr, "  -> msg_num=%d rel=%d data_len=%zu id=0x%02x hex=",
                    pkt.msg_num, (int)pkt.reliability,
                    pkt.data.size(), pkt.data.empty() ? 0 : pkt.data[0]);
            for (int i = 0; i < std::min((int)pkt.data.size(), 16); i++)
                fprintf(stderr, "%02x ", pkt.data[i]);
            fprintf(stderr, "\n");
            if (pkt.reliability == RELIABLE || pkt.reliability == RELIABLE_ORDERED) {
                std::lock_guard<std::mutex> lk(ack_mutex_);
                pending_acks_.push_back(pkt.msg_num);
            }
            process_packet(pkt);
        }
    }
}

void SAMPClient::stop() { running_ = false; }

void SAMPClient::disconnect() {
    running_ = false;
    if (sock_fd_ >= 0) {
        uint8_t disc[2] = {ID_DISCONNECTION_NOTIFICATION, 0};
        std::vector<uint8_t> d(disc, disc + 2);
        send_reliability_pkt(d, RELIABLE);
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        ::close(sock_fd_);
        sock_fd_ = -1;
    }
}

} // namespace samp
