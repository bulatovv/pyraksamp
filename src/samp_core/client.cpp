#include "client.h"
#include "bitstream.h"
#include "encrypt.h"
#include "reliability.h"

#include <arpa/inet.h>
#include <cerrno>
#include <chrono>
#include <cstring>
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
    if (rel == UNRELIABLE_SEQUENCED ||
        rel == RELIABLE_ORDERED     ||
        rel == RELIABLE_SEQUENCED)
        oi = ordering_idx_++;
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
    while (now_sec() < deadline) {
        double remaining = deadline - now_sec();
        if (!recv_with_timeout(sock_fd_, buf, sizeof(buf), server_ip_, len, std::min(remaining, 0.5)))
            continue;

        // Try to parse as raw auth key (sometimes sent before reliability layer)
        if (len >= 2 && buf[0] == ID_AUTH_KEY) {
            handle_auth_key(buf, len);
            continue;
        }

        auto result = parse(buf, len, split_buffer_);
        if (!result) continue;
        if (result->is_ack) continue;

        for (auto& pkt : result->packets) {
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
                return true;
            case ID_CONNECTION_BANNED:
            case ID_INVALID_PASSWORD:
            case ID_NO_FREE_INCOMING_CONNECTIONS:
            case ID_CONNECTION_ATTEMPT_FAILED:
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
    if (on_connect) on_connect();
    request_class_and_spawn();
}

void SAMPClient::handle_rpc(uint8_t rpc_id, const uint8_t* payload, int len) {
    // Typed dispatch — each case uses BitStream for safe parsing.
    // All cases fall through to the on_rpc raw callback at the bottom.
    try {
        BitStream bs(payload, len);

        switch (rpc_id) {

        case RPC_INIT_GAME:
            handle_init_game(payload, len);
            break;

        case RPC_CONNECTION_REJ:
            running_ = false;
            break;

        case RPC_SERVER_JOIN: {
            // u16 pid, i32 unk, u8 isNPC, u8 nameLen, char[nameLen]
            uint16_t pid  = bs.read_uint16_le();
            bs.skip_bits(32); // unk
            bs.read_uint8();  // isNPC
            uint8_t nlen  = bs.read_uint8();
            std::string name;
            if (nlen > 0) {
                name.resize(nlen);
                bs.read_aligned_bytes(reinterpret_cast<uint8_t*>(&name[0]), nlen);
            }
            if (on_player_join) on_player_join(pid, name);
            break;
        }

        case RPC_SERVER_QUIT: {
            // u16 pid, u8 reason
            uint16_t pid    = bs.read_uint16_le();
            uint8_t  reason = bs.read_uint8();
            if (on_player_quit) on_player_quit(pid, reason);
            break;
        }

        case RPC_CHAT: {
            // u16 pid, u8 textLen, char[textLen]
            uint16_t pid  = bs.read_uint16_le();
            uint8_t  tlen = bs.read_uint8();
            std::string text(tlen, '\0');
            if (tlen > 0)
                bs.read_aligned_bytes(reinterpret_cast<uint8_t*>(&text[0]), tlen);
            if (on_chat) on_chat(pid, text);
            break;
        }

        case RPC_CLIENT_MESSAGE: {
            // u32 color, u32 len, char[len]
            uint32_t color = bs.read_uint32_le();
            uint32_t mlen  = bs.read_uint32_le();
            if (mlen > 256) break;
            std::string text(mlen, '\0');
            if (mlen > 0)
                bs.read_aligned_bytes(reinterpret_cast<uint8_t*>(&text[0]),
                                      static_cast<int>(mlen));
            if (on_client_message) on_client_message(color, text);
            break;
        }

        case RPC_DIALOG_BOX: {
            // u16 dialogID, u8 style, u8 titleLen, title, u8 btn1Len, btn1,
            // u8 btn2Len, btn2, DecodeString(body)
            uint16_t did   = bs.read_uint16_le();
            uint8_t  style = bs.read_uint8();

            uint8_t tlen = bs.read_uint8();
            std::string title(tlen, '\0');
            if (tlen > 0)
                bs.read_aligned_bytes(reinterpret_cast<uint8_t*>(&title[0]), tlen);

            uint8_t b1len = bs.read_uint8();
            std::string btn1(b1len, '\0');
            if (b1len > 0)
                bs.read_aligned_bytes(reinterpret_cast<uint8_t*>(&btn1[0]), b1len);

            uint8_t b2len = bs.read_uint8();
            std::string btn2(b2len, '\0');
            if (b2len > 0)
                bs.read_aligned_bytes(reinterpret_cast<uint8_t*>(&btn2[0]), b2len);

            std::string body = bs.read_compressed_string(4096);

            if (on_dialog) on_dialog(did, style, title, btn1, btn2, body);
            break;
        }

        case RPC_GAME_TEXT: {
            // i32 type, i32 timeMs, i32 len, char[len]
            int32_t  type   = bs.read_int32_le();
            int32_t  timeMs = bs.read_int32_le();
            int32_t  mlen   = bs.read_int32_le();
            if (mlen < 0 || mlen > 400) break;
            std::string text(static_cast<size_t>(mlen), '\0');
            if (mlen > 0)
                bs.read_aligned_bytes(reinterpret_cast<uint8_t*>(&text[0]), mlen);
            if (on_game_text) on_game_text(type, timeMs, text);
            break;
        }

        case RPC_SET_HEALTH: {
            float hp = bs.read_float_le();
            if (on_set_health) on_set_health(hp);
            break;
        }

        case RPC_SET_ARMOUR: {
            float arm = bs.read_float_le();
            if (on_set_armour) on_set_armour(arm);
            break;
        }

        case RPC_SET_POSITION: {
            float x = bs.read_float_le();
            float y = bs.read_float_le();
            float z = bs.read_float_le();
            if (on_set_position) on_set_position(x, y, z);
            break;
        }

        case RPC_SET_CHECKPOINT: {
            float x    = bs.read_float_le();
            float y    = bs.read_float_le();
            float z    = bs.read_float_le();
            float size = bs.read_float_le();
            if (on_checkpoint) on_checkpoint(x, y, z, size);
            break;
        }

        case RPC_DISABLE_CHECKPOINT:
            if (on_checkpoint_disabled) on_checkpoint_disabled();
            break;

        case RPC_WORLD_PLAYER_ADD: {
            // u16 pid, u8 team, i32 skin, f32 x,y,z,rot, u32 color, u8 fightStyle
            uint16_t pid   = bs.read_uint16_le();
            uint8_t  team  = bs.read_uint8();
            int32_t  skin  = bs.read_int32_le();
            float    x     = bs.read_float_le();
            float    y     = bs.read_float_le();
            float    z     = bs.read_float_le();
            float    rot   = bs.read_float_le();
            uint32_t color = bs.read_uint32_le();
            uint8_t  fs    = bs.read_uint8();
            if (on_player_streamed_in)
                on_player_streamed_in(pid, team, skin, x, y, z, rot, color, fs);
            break;
        }

        case RPC_WORLD_PLAYER_REMOVE: {
            uint16_t pid = bs.read_uint16_le();
            if (on_player_streamed_out) on_player_streamed_out(pid);
            break;
        }

        case RPC_SET_PLAYER_NAME: {
            // u16 pid | u8 len | char[len] | u8 success
            uint16_t pid = bs.read_uint16_le();
            uint8_t nlen = bs.read_uint8();
            std::string name(nlen, '\0');
            if (nlen > 0)
                bs.read_aligned_bytes(reinterpret_cast<uint8_t*>(&name[0]), nlen);
            uint8_t success = bs.read_uint8();
            if (on_player_name) on_player_name(pid, name, success);
            break;
        }

        case RPC_TOGGLE_CONTROLLABLE: {
            uint8_t moveable = bs.read_uint8();
            if (on_toggle_controllable) on_toggle_controllable(moveable);
            break;
        }

        case RPC_SET_PLAYER_TIME: {
            uint8_t hour   = bs.read_uint8();
            uint8_t minute = bs.read_uint8();
            if (on_player_time) on_player_time(hour, minute);
            break;
        }

        case RPC_SEND_DEATH_MESSAGE: {
            uint16_t killer_id = bs.read_uint16_le();
            uint16_t player_id = bs.read_uint16_le();
            uint8_t  weapon    = bs.read_uint8();
            if (on_death_message) on_death_message(killer_id, player_id, weapon);
            break;
        }

        case RPC_SET_ARMED_WEAPON: {
            uint32_t weapon_id = bs.read_uint32_le();
            if (on_set_armed_weapon) on_set_armed_weapon(weapon_id);
            break;
        }

        case RPC_SET_SPAWN_INFO: {
            // u8 team | u32 skin | u8 unused | f32 x,y,z | f32 rot
            // | u32 weapon1 | u32 weapon2 | u32 weapon3
            // | u32 ammo1   | u32 ammo2   | u32 ammo3
            uint8_t  team   = bs.read_uint8();
            uint32_t skin   = bs.read_uint32_le();
            bs.read_uint8(); // unused
            float x   = bs.read_float_le();
            float y   = bs.read_float_le();
            float z   = bs.read_float_le();
            float rot = bs.read_float_le();
            uint32_t w1 = bs.read_uint32_le();
            uint32_t w2 = bs.read_uint32_le();
            uint32_t w3 = bs.read_uint32_le();
            uint32_t a1 = bs.read_uint32_le();
            uint32_t a2 = bs.read_uint32_le();
            uint32_t a3 = bs.read_uint32_le();
            if (on_spawn_info) on_spawn_info(team, skin, x, y, z, rot, w1, w2, w3, a1, a2, a3);
            break;
        }

        case RPC_SET_PLAYER_TEAM: {
            uint16_t pid  = bs.read_uint16_le();
            uint8_t  team = bs.read_uint8();
            if (on_player_team) on_player_team(pid, team);
            break;
        }

        case RPC_PUT_IN_VEHICLE: {
            uint16_t vehicle_id = bs.read_uint16_le();
            uint8_t  seat_id    = bs.read_uint8();
            if (on_put_in_vehicle) on_put_in_vehicle(vehicle_id, seat_id);
            break;
        }

        case RPC_REMOVE_FROM_VEHICLE:
            if (on_remove_from_vehicle) on_remove_from_vehicle();
            break;

        case RPC_SET_PLAYER_COLOR: {
            uint16_t pid   = bs.read_uint16_le();
            uint32_t color = bs.read_uint32_le();
            if (on_player_color) on_player_color(pid, color);
            break;
        }

        case RPC_SET_WORLD_TIME: {
            uint8_t hour = bs.read_uint8();
            if (on_world_time) on_world_time(hour);
            break;
        }

        case RPC_TOGGLE_SPECTATING: {
            // u32 spectating (BOOL on Win32)
            uint32_t spec = bs.read_uint32_le();
            if (on_toggle_spectating) on_toggle_spectating(spec != 0);
            break;
        }

        case RPC_SET_WANTED_LEVEL: {
            uint8_t level = bs.read_uint8();
            if (on_wanted_level) on_wanted_level(level);
            break;
        }

        case RPC_SET_WEAPON_AMMO: {
            uint8_t  weapon_id = bs.read_uint8();
            uint16_t ammo      = bs.read_uint16_le();
            if (on_weapon_ammo) on_weapon_ammo(weapon_id, ammo);
            break;
        }

        case RPC_SET_GRAVITY: {
            float gravity = bs.read_float_le();
            if (on_gravity) on_gravity(gravity);
            break;
        }

        case RPC_SET_WEATHER: {
            uint8_t weather_id = bs.read_uint8();
            if (on_weather) on_weather(weather_id);
            break;
        }

        case RPC_SET_PLAYER_SKIN: {
            int32_t  pid     = bs.read_int32_le();
            uint32_t skin_id = bs.read_uint32_le();
            if (on_player_skin) on_player_skin(pid, skin_id);
            break;
        }

        case RPC_SET_INTERIOR: {
            uint8_t interior_id = bs.read_uint8();
            if (on_set_interior) on_set_interior(interior_id);
            break;
        }

        case RPC_WORLD_VEHICLE_ADD: {
            // NEW_VEHICLE packed struct:
            // u16 vid | i32 model | f32 x,y,z | f32 angle
            // | u8 color1 | u8 color2 | f32 health | u8 interior
            // | u32 door_dmg | u32 panel_dmg | u8 light_dmg | u8 tire_dmg
            // | u8 add_siren | u8 mods[14] | u8 paintjob
            // | u32 body_color1 | u32 body_color2 | u8 unk
            uint16_t vid     = bs.read_uint16_le();
            int32_t  model   = bs.read_int32_le();
            float    x       = bs.read_float_le();
            float    y       = bs.read_float_le();
            float    z       = bs.read_float_le();
            float    angle   = bs.read_float_le();
            uint8_t  color1  = bs.read_uint8();
            uint8_t  color2  = bs.read_uint8();
            float    health  = bs.read_float_le();
            uint8_t  interior = bs.read_uint8();
            uint32_t door_dmg   = bs.read_uint32_le();
            uint32_t panel_dmg  = bs.read_uint32_le();
            uint8_t  light_dmg  = bs.read_uint8();
            uint8_t  tire_dmg   = bs.read_uint8();
            uint8_t  add_siren  = bs.read_uint8();
            uint8_t  mods[14];
            bs.read_aligned_bytes(mods, 14);
            uint8_t  paintjob    = bs.read_uint8();
            uint32_t body_color1 = bs.read_uint32_le();
            uint32_t body_color2 = bs.read_uint32_le();
            // u8 unk — ignored
            if (on_vehicle_streamed_in)
                on_vehicle_streamed_in(vid, model, x, y, z, angle,
                                       color1, color2, health, interior,
                                       door_dmg, panel_dmg, light_dmg, tire_dmg,
                                       add_siren, paintjob, body_color1, body_color2);
            break;
        }

        case RPC_WORLD_VEHICLE_REMOVE: {
            uint16_t vid = bs.read_uint16_le();
            if (on_vehicle_streamed_out) on_vehicle_streamed_out(vid);
            break;
        }

        case RPC_DEATH_BROADCAST: {
            uint16_t pid = bs.read_uint16_le();
            if (on_player_death) on_player_death(pid);
            break;
        }

        default:
            break;
        }
    } catch (...) {
        // Malformed packet — silently ignore; do not crash the receive loop.
    }

    // Always fire the raw escape hatch last so user can intercept anything.
    if (on_rpc) {
        on_rpc(rpc_id, std::vector<uint8_t>(payload, payload + len));
    }
}

// ─── send helpers ────────────────────────────────────────────────────────────

void SAMPClient::send_dialog_response(uint16_t dialog_id, uint8_t button,
                                       uint16_t list_item, const std::string& text)
{
    BitStream bs;
    bs.write_uint16_le(dialog_id);
    uint8_t btn = button;
    bs.write_bits(&btn, 8, true);
    bs.write_uint16_le(list_item);
    uint8_t rlen = static_cast<uint8_t>(text.size());
    bs.write_bits(&rlen, 8, true);
    if (rlen > 0)
        bs.write_aligned_bytes(reinterpret_cast<const uint8_t*>(text.data()), rlen);
    std::vector<uint8_t> payload(bs.data(), bs.data() + bs.num_bytes());
    send_rpc(RPC_DIALOG_RESPONSE, payload, RELIABLE_ORDERED);
}

void SAMPClient::send_death(uint8_t weapon_id, uint16_t killer_id)
{
    BitStream bs;
    bs.write_bits(&weapon_id, 8, true);
    bs.write_uint16_le(killer_id);
    std::vector<uint8_t> payload(bs.data(), bs.data() + bs.num_bytes());
    send_rpc(RPC_DEATH, payload, RELIABLE_ORDERED);
}

void SAMPClient::send_enter_vehicle(uint16_t vehicle_id, bool is_passenger)
{
    BitStream bs;
    bs.write_uint16_le(vehicle_id);
    uint8_t pass = is_passenger ? 1 : 0;
    bs.write_bits(&pass, 8, true);
    std::vector<uint8_t> payload(bs.data(), bs.data() + bs.num_bytes());
    send_rpc(RPC_ENTER_VEHICLE, payload, RELIABLE_SEQUENCED);
}

void SAMPClient::send_exit_vehicle(uint16_t vehicle_id)
{
    BitStream bs;
    bs.write_uint16_le(vehicle_id);
    std::vector<uint8_t> payload(bs.data(), bs.data() + bs.num_bytes());
    send_rpc(RPC_EXIT_VEHICLE, payload, RELIABLE_SEQUENCED);
}

void SAMPClient::send_command(const std::string& text)
{
    BitStream bs;
    uint32_t len = static_cast<uint32_t>(text.size());
    bs.write_bits(reinterpret_cast<const uint8_t*>(&len), 32, true);
    if (len > 0)
        bs.write_aligned_bytes(reinterpret_cast<const uint8_t*>(text.data()),
                               static_cast<int>(len));
    std::vector<uint8_t> payload(bs.data(), bs.data() + bs.num_bytes());
    send_rpc(RPC_SERVER_COMMAND, payload, RELIABLE);
}

void SAMPClient::process_packet(const InternalPacket& pkt) {
    if (pkt.data.empty()) return;

    switch (pkt.data[0]) {
    case ID_TIMESTAMP: {
        // Strip [ID_TIMESTAMP(1)][RakNetTime(4)] prefix, then process as normal packet
        // Format: [0x28][4-byte timestamp][actual_packet_id][...]
        if (pkt.data.size() < 6) return;
        InternalPacket stripped = pkt;
        stripped.data = std::vector<uint8_t>(pkt.data.begin() + 5, pkt.data.end());
        process_packet(stripped);
        return;
    }
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
        } catch (...) {
            return;
        }
        std::vector<uint8_t> payload(byte_len);
        try {
            if (byte_len > 0)
                bs.read_bits(payload.data(), static_cast<int>(bit_len), false);
        } catch (...) {
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
    // Client→server on-foot sync: ID_PLAYER_SYNC + raw ONFOOT_SYNC_DATA (#pragma pack(1), 68 bytes)
    // Reference: localplayer.cpp SendOnFootFullSyncData, sent as UNRELIABLE_SEQUENCED
    // Struct layout (common.h): lrAnalog(u16), udAnalog(u16), wKeys(u16),
    //   vecPos(3f), fQuaternion(4f), health(u8), armour(u8), weapon(u8), specialAction(u8),
    //   moveSpeed(3f), surfOffsets(3f), wSurfInfo(u16), animID(i32) = 68 bytes
    struct __attribute__((packed)) OnFootData {
        uint16_t lrAnalog       = 0;
        uint16_t udAnalog       = 0;
        uint16_t wKeys          = 0;
        float    vecPos[3]      = {0.0f, 0.0f, 3.0f};
        float    fQuaternion[4] = {0.0f, 0.0f, 0.0f, 1.0f};
        uint8_t  byteHealth     = 100;
        uint8_t  byteArmour     = 0;
        uint8_t  weapon         = 0;
        uint8_t  specialAction  = 0;
        float    moveSpeed[3]   = {0.0f, 0.0f, 0.0f};
        float    surfOffsets[3] = {0.0f, 0.0f, 0.0f};
        uint16_t wSurfInfo      = 0xFFFF; // no surface
        int32_t  animID         = 0;
    } data;

    std::vector<uint8_t> pkt(1 + sizeof(data));
    pkt[0] = 207; // ID_PLAYER_SYNC
    memcpy(pkt.data() + 1, &data, sizeof(data));
    send_reliability_pkt(pkt, UNRELIABLE_SEQUENCED);
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
    double last_scores    = now_sec();

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
        if (n - last_scores > 3.0) {
            send_rpc(RPC_UPDATE_SCORES, {}, RELIABLE);
            last_scores = n;
        }

        uint8_t buf[2048];
        int     len = 0;
        if (!recv_with_timeout(sock_fd_, buf, sizeof(buf), server_ip_, len, 0.03))
            continue;

        // Raw auth key (before reliability layer)
        if (len >= 2 && buf[0] == ID_AUTH_KEY) {
            handle_auth_key(buf, len);
            continue;
        }

        auto result = parse(buf, len, split_buffer_);
        if (!result) continue;
        if (result->is_ack) continue;

        for (auto& pkt : result->packets) {
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
