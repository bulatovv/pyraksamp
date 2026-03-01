#pragma once
#include "reliability.h"
#include <atomic>
#include <cstdint>
#include <functional>
#include <mutex>
#include <string>
#include <vector>

namespace samp {

// Packet IDs
constexpr uint8_t ID_INTERNAL_PING                = 6;
constexpr uint8_t ID_CONNECTED_PONG               = 9;
constexpr uint8_t ID_CONNECTION_REQUEST           = 11;
constexpr uint8_t ID_AUTH_KEY                     = 12;
constexpr uint8_t ID_RPC                          = 20;
constexpr uint8_t ID_OPEN_CONNECTION_REQUEST      = 24;
constexpr uint8_t ID_OPEN_CONNECTION_REPLY        = 25;
constexpr uint8_t ID_OPEN_CONNECTION_COOKIE       = 26;
constexpr uint8_t ID_CONNECTION_ATTEMPT_FAILED    = 29;
constexpr uint8_t ID_NEW_INCOMING_CONNECTION      = 30;
constexpr uint8_t ID_NO_FREE_INCOMING_CONNECTIONS = 31;
constexpr uint8_t ID_DISCONNECTION_NOTIFICATION   = 32;
constexpr uint8_t ID_CONNECTION_LOST              = 33;
constexpr uint8_t ID_CONNECTION_REQUEST_ACCEPTED  = 34;
constexpr uint8_t ID_CONNECTION_BANNED            = 36;
constexpr uint8_t ID_INVALID_PASSWORD             = 37;

// RPC IDs
constexpr uint8_t RPC_CLIENT_JOIN      = 25;
constexpr uint8_t RPC_INIT_GAME        = 139;
constexpr uint8_t RPC_REQUEST_CLASS    = 128;
constexpr uint8_t RPC_REQUEST_SPAWN    = 129;
constexpr uint8_t RPC_SPAWN            = 52;
constexpr uint8_t RPC_CONNECTION_REJ   = 130;
constexpr uint8_t RPC_SERVER_JOIN      = 137;
constexpr uint8_t RPC_SERVER_QUIT      = 138;

constexpr int     NETGAME_VERSION = 4057;
constexpr uint16_t NETCODE_CONNCOOKIELULZ = 0x6969;

class SAMPClient {
public:
    SAMPClient(
        const std::string& host,
        uint16_t           port,
        const std::string& nickname,
        const std::string& password = "",
        const std::string& gpci     = ""
    );
    ~SAMPClient();

    // Connect: performs handshake → auth → ClientJoin.
    // Returns true when fully connected (InitGame received).
    bool connect(double timeout_sec = 15.0);

    // Main receive/dispatch loop. Blocks until stop() or disconnect.
    // Call from Python (GIL is released internally during socket waits,
    // re-acquired when invoking callbacks).
    void run();

    void stop();
    void disconnect();

    // Send an RPC to the server.
    bool send_rpc(uint8_t rpc_id,
                  const std::vector<uint8_t>& payload,
                  Reliability rel = RELIABLE);

    // State queries
    bool is_connected()  const { return connected_.load(); }
    int  player_id()     const { return player_id_; }

    // Callbacks (set before connect())
    std::function<void()>                                    on_connect;
    std::function<void()>                                    on_disconnect;
    std::function<void(uint8_t, std::vector<uint8_t>)>      on_rpc;
    std::function<void(int, std::string)>                    on_player_join;  // id, name

private:
    // ---- Network helpers ----
    void  send_raw(const void* data, int len);
    void  send_encrypted(const void* data, int len);
    void  send_reliability_pkt(const std::vector<uint8_t>& data,
                               Reliability rel = RELIABLE,
                               uint8_t ordering_channel = 0,
                               uint16_t ordering_index = 0);
    void  send_acks(const std::vector<uint16_t>& nums);
    void  flush_acks();

    // ---- Connection phases ----
    bool  do_handshake(double timeout_sec);
    bool  do_connection_request(double timeout_sec);
    void  handle_auth_key(const uint8_t* data, int len);
    void  handle_connection_accepted(const uint8_t* data, int len);
    void  send_client_join();

    // ---- Packet dispatch ----
    void  process_packet(const InternalPacket& pkt);
    void  handle_rpc(uint8_t rpc_id, const uint8_t* payload, int len);
    void  handle_init_game(const uint8_t* data, int len);
    void  request_class_and_spawn();
    void  send_keepalive();

    // ---- Config ----
    std::string  host_;
    uint16_t     port_;
    std::string  nickname_;
    std::string  password_;
    std::string  gpci_;

    // ---- Socket ----
    int          sock_fd_  = -1;
    uint32_t     server_ip_ = 0;  // big-endian

    // ---- State ----
    std::atomic<bool> connected_{false};
    std::atomic<bool> running_{false};
    int               player_id_  = -1;
    uint32_t          challenge_  = 0;

    // ---- Reliability layer ----
    uint16_t              send_msg_num_  = 0;
    std::mutex            ack_mutex_;
    std::vector<uint16_t> pending_acks_;
};

} // namespace samp
