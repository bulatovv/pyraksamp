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
constexpr uint8_t ID_TIMESTAMP                    = 40;
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

// RPC IDs — server→client (receive)
constexpr uint8_t RPC_SERVER_JOIN           = 137;
constexpr uint8_t RPC_SERVER_QUIT           = 138;
constexpr uint8_t RPC_INIT_GAME             = 139;
constexpr uint8_t RPC_CONNECTION_REJ        = 130;
constexpr uint8_t RPC_CHAT                  = 101;
constexpr uint8_t RPC_CLIENT_MESSAGE        = 93;
constexpr uint8_t RPC_DIALOG_BOX            = 61;
constexpr uint8_t RPC_GAME_TEXT             = 73;
constexpr uint8_t RPC_SET_HEALTH            = 14;
constexpr uint8_t RPC_SET_ARMOUR            = 66;
constexpr uint8_t RPC_SET_POSITION          = 12;
constexpr uint8_t RPC_SET_CHECKPOINT        = 107;
constexpr uint8_t RPC_DISABLE_CHECKPOINT    = 37;
constexpr uint8_t RPC_WORLD_PLAYER_ADD      = 32;
constexpr uint8_t RPC_WORLD_PLAYER_REMOVE   = 163;
constexpr uint8_t RPC_SET_PLAYER_NAME       = 11;
constexpr uint8_t RPC_TOGGLE_CONTROLLABLE   = 15;
constexpr uint8_t RPC_SET_PLAYER_TIME       = 29;
constexpr uint8_t RPC_SEND_DEATH_MESSAGE    = 55;
constexpr uint8_t RPC_SET_ARMED_WEAPON      = 67;
constexpr uint8_t RPC_SET_SPAWN_INFO        = 68;
constexpr uint8_t RPC_SET_PLAYER_TEAM       = 69;
constexpr uint8_t RPC_PUT_IN_VEHICLE        = 70;
constexpr uint8_t RPC_REMOVE_FROM_VEHICLE   = 71;
constexpr uint8_t RPC_SET_PLAYER_COLOR      = 72;
constexpr uint8_t RPC_SET_WORLD_TIME        = 94;
constexpr uint8_t RPC_TOGGLE_SPECTATING     = 124;
constexpr uint8_t RPC_SET_WANTED_LEVEL      = 133;
constexpr uint8_t RPC_SET_WEAPON_AMMO       = 145;
constexpr uint8_t RPC_SET_GRAVITY           = 146;
constexpr uint8_t RPC_SET_WEATHER           = 152;
constexpr uint8_t RPC_SET_PLAYER_SKIN       = 153;
constexpr uint8_t RPC_SET_INTERIOR          = 156;
constexpr uint8_t RPC_WORLD_VEHICLE_ADD     = 164;
constexpr uint8_t RPC_WORLD_VEHICLE_REMOVE  = 165;
constexpr uint8_t RPC_DEATH_BROADCAST       = 166;

// RPC IDs — client→server (send)
constexpr uint8_t RPC_CLIENT_JOIN      = 25;
constexpr uint8_t RPC_REQUEST_CLASS    = 128;
constexpr uint8_t RPC_REQUEST_SPAWN    = 129;
constexpr uint8_t RPC_SPAWN            = 52;
constexpr uint8_t RPC_DIALOG_RESPONSE  = 62;
constexpr uint8_t RPC_DEATH            = 53;
constexpr uint8_t RPC_ENTER_VEHICLE    = 26;
constexpr uint8_t RPC_EXIT_VEHICLE     = 154;
constexpr uint8_t RPC_SERVER_COMMAND   = 50;
constexpr uint8_t RPC_UPDATE_SCORES    = 155; // UpdateScoresPingsIPs — empty payload, every 3s

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

    // ── Callbacks ─────────────────────────────────────────────────────────────
    // Connection
    std::function<void()>                                    on_connect;
    std::function<void()>                                    on_disconnect;

    // Raw RPC escape hatch (fired for every RPC after typed callbacks)
    std::function<void(uint8_t, std::vector<uint8_t>)>      on_rpc;

    // Player roster
    std::function<void(int, std::string)>                    on_player_join;   // pid, name
    std::function<void(int, int)>                            on_player_quit;   // pid, reason

    // Chat
    std::function<void(int, std::string)>                    on_chat;          // pid, text
    std::function<void(uint32_t, std::string)>               on_client_message;// color, text

    // Dialogs
    std::function<void(uint16_t, uint8_t,
                       std::string, std::string,
                       std::string, std::string)>            on_dialog;        // id,style,title,btn1,btn2,body

    // HUD
    std::function<void(int, int, std::string)>               on_game_text;     // style, ms, text

    // Player state
    std::function<void(float)>                               on_set_health;
    std::function<void(float)>                               on_set_armour;
    std::function<void(float, float, float)>                 on_set_position;  // x,y,z

    // World
    std::function<void(float, float, float, float)>          on_checkpoint;    // x,y,z,size
    std::function<void()>                                    on_checkpoint_disabled;

    // Stream in/out (proximity)
    std::function<void(int,int,int,float,float,float,float,uint32_t,int)> on_player_streamed_in;
    std::function<void(int)>                                 on_player_streamed_out;

    // Player info
    std::function<void(uint16_t, std::string, uint8_t)>      on_player_name;       // pid, name, success
    std::function<void(uint8_t)>                             on_toggle_controllable;
    std::function<void(uint8_t, uint8_t)>                    on_player_time;       // hour, minute
    std::function<void(uint16_t, uint16_t, uint8_t)>         on_death_message;     // killer, player, weapon
    std::function<void(uint32_t)>                            on_set_armed_weapon;  // weapon_id
    std::function<void(uint8_t, uint32_t,
                       float, float, float, float,
                       uint32_t, uint32_t, uint32_t,
                       uint32_t, uint32_t, uint32_t)>        on_spawn_info;        // team,skin,x,y,z,rot,w[3],a[3]
    std::function<void(uint16_t, uint8_t)>                   on_player_team;       // pid, team
    std::function<void(uint16_t, uint8_t)>                   on_put_in_vehicle;    // vehicle_id, seat_id
    std::function<void()>                                    on_remove_from_vehicle;
    std::function<void(uint16_t, uint32_t)>                  on_player_color;      // pid, color
    std::function<void(uint8_t)>                             on_world_time;        // hour
    std::function<void(bool)>                                on_toggle_spectating;
    std::function<void(uint8_t)>                             on_wanted_level;
    std::function<void(uint8_t, uint16_t)>                   on_weapon_ammo;       // weapon_id, ammo
    std::function<void(float)>                               on_gravity;
    std::function<void(uint8_t)>                             on_weather;
    std::function<void(int32_t, uint32_t)>                   on_player_skin;       // pid, skin_id
    std::function<void(uint8_t)>                             on_set_interior;
    std::function<void(uint16_t, int32_t,
                       float, float, float, float,
                       uint8_t, uint8_t, float, uint8_t,
                       uint32_t, uint32_t, uint8_t, uint8_t,
                       uint8_t, uint8_t, uint32_t, uint32_t)> on_vehicle_streamed_in;
    std::function<void(uint16_t)>                            on_vehicle_streamed_out;
    std::function<void(uint16_t)>                            on_player_death;

    // ── Send helpers ───────────────────────────────────────────────────────────
    void send_dialog_response(uint16_t dialog_id, uint8_t button,
                              uint16_t list_item, const std::string& text);
    void send_death(uint8_t weapon_id = 0, uint16_t killer_id = 0xFFFF);
    void send_enter_vehicle(uint16_t vehicle_id, bool is_passenger = false);
    void send_exit_vehicle(uint16_t vehicle_id);
    void send_command(const std::string& text);

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
    // Atomic because the run() thread (keepalives/acks) and the Python asyncio
    // thread (user send_rpc calls) both increment this concurrently; run()
    // releases the GIL so the two threads truly execute C++ in parallel.
    std::atomic<uint16_t> send_msg_num_{0};
    std::atomic<uint16_t> ordering_idx_{0};   // per-channel ordering index (ch 0 only)
    std::mutex            ack_mutex_;
    std::vector<uint16_t> pending_acks_;
    SplitBuffer           split_buffer_; // reassembly state for split packets
};

} // namespace samp
