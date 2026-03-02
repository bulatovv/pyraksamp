#include <pybind11/functional.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "client.h"

namespace py = pybind11;
using namespace samp;

PYBIND11_MODULE(_core, m) {
    m.doc() = "SA:MP 0.3.7 headless client core (C++)";

    py::class_<SAMPClient>(m, "SAMPClient")
        .def(py::init<const std::string&, uint16_t,
                      const std::string&, const std::string&,
                      const std::string&>(),
             py::arg("host"), py::arg("port"), py::arg("nickname"),
             py::arg("password") = "", py::arg("gpci") = "")

        // Connect: release GIL during socket waits
        .def("connect",
             [](SAMPClient& self, double timeout) {
                 py::gil_scoped_release release;
                 return self.connect(timeout);
             },
             py::arg("timeout") = 15.0)

        // Run loop: release GIL; callbacks re-acquire it via pybind11::gil_scoped_acquire
        .def("run",
             [](SAMPClient& self) {
                 py::gil_scoped_release release;
                 self.run();
             })

        .def("stop",       &SAMPClient::stop)
        .def("disconnect", &SAMPClient::disconnect)

        .def("send_rpc",
             [](SAMPClient& self, uint8_t rpc_id, py::bytes data, int rel) {
                 std::string s = data;
                 std::vector<uint8_t> v(s.begin(), s.end());
                 return self.send_rpc(rpc_id, v, static_cast<Reliability>(rel));
             },
             py::arg("rpc_id"), py::arg("data") = py::bytes(""),
             py::arg("reliability") = static_cast<int>(RELIABLE))

        .def_property_readonly("is_connected", &SAMPClient::is_connected)
        .def_property_readonly("player_id",    &SAMPClient::player_id)

        // ── Callbacks (Python functions called with GIL held) ─────────────────

        .def_property("on_connect",
            [](const SAMPClient& self) { return self.on_connect; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_connect = nullptr; return; }
                self.on_connect = [cb]() { py::gil_scoped_acquire _; cb(); };
            })
        .def_property("on_disconnect",
            [](const SAMPClient& self) { return self.on_disconnect; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_disconnect = nullptr; return; }
                self.on_disconnect = [cb]() { py::gil_scoped_acquire _; cb(); };
            })
        .def_property("on_rpc",
            [](const SAMPClient& self) { return self.on_rpc; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_rpc = nullptr; return; }
                self.on_rpc = [cb](uint8_t rpc_id, std::vector<uint8_t> data) {
                    py::gil_scoped_acquire _;
                    cb(rpc_id, py::bytes(reinterpret_cast<const char*>(data.data()),
                                        data.size()));
                };
            })

        // Player roster
        .def_property("on_player_join",
            [](const SAMPClient& self) { return self.on_player_join; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_player_join = nullptr; return; }
                self.on_player_join = [cb](int pid, std::string name) {
                    py::gil_scoped_acquire _; cb(pid, name);
                };
            })
        .def_property("on_player_quit",
            [](const SAMPClient& self) { return self.on_player_quit; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_player_quit = nullptr; return; }
                self.on_player_quit = [cb](int pid, int reason) {
                    py::gil_scoped_acquire _; cb(pid, reason);
                };
            })

        // Chat
        .def_property("on_chat",
            [](const SAMPClient& self) { return self.on_chat; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_chat = nullptr; return; }
                self.on_chat = [cb](int pid, std::string text) {
                    py::gil_scoped_acquire _; cb(pid, text);
                };
            })
        .def_property("on_client_message",
            [](const SAMPClient& self) { return self.on_client_message; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_client_message = nullptr; return; }
                self.on_client_message = [cb](uint32_t color, std::string text) {
                    py::gil_scoped_acquire _; cb(color, text);
                };
            })

        // Dialogs
        .def_property("on_dialog",
            [](const SAMPClient& self) { return self.on_dialog; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_dialog = nullptr; return; }
                self.on_dialog = [cb](uint16_t did, uint8_t style,
                                      std::string title, std::string btn1,
                                      std::string btn2, std::string body) {
                    py::gil_scoped_acquire _; cb(did, style, title, btn1, btn2, body);
                };
            })

        // HUD
        .def_property("on_game_text",
            [](const SAMPClient& self) { return self.on_game_text; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_game_text = nullptr; return; }
                self.on_game_text = [cb](int style, int ms, std::string text) {
                    py::gil_scoped_acquire _; cb(style, ms, text);
                };
            })

        // Player state
        .def_property("on_set_health",
            [](const SAMPClient& self) { return self.on_set_health; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_set_health = nullptr; return; }
                self.on_set_health = [cb](float hp) {
                    py::gil_scoped_acquire _; cb(hp);
                };
            })
        .def_property("on_set_armour",
            [](const SAMPClient& self) { return self.on_set_armour; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_set_armour = nullptr; return; }
                self.on_set_armour = [cb](float arm) {
                    py::gil_scoped_acquire _; cb(arm);
                };
            })
        .def_property("on_set_position",
            [](const SAMPClient& self) { return self.on_set_position; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_set_position = nullptr; return; }
                self.on_set_position = [cb](float x, float y, float z) {
                    py::gil_scoped_acquire _; cb(x, y, z);
                };
            })

        // World
        .def_property("on_checkpoint",
            [](const SAMPClient& self) { return self.on_checkpoint; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_checkpoint = nullptr; return; }
                self.on_checkpoint = [cb](float x, float y, float z, float sz) {
                    py::gil_scoped_acquire _; cb(x, y, z, sz);
                };
            })
        .def_property("on_checkpoint_disabled",
            [](const SAMPClient& self) { return self.on_checkpoint_disabled; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_checkpoint_disabled = nullptr; return; }
                self.on_checkpoint_disabled = [cb]() {
                    py::gil_scoped_acquire _; cb();
                };
            })

        // Stream in/out
        .def_property("on_player_streamed_in",
            [](const SAMPClient& self) { return self.on_player_streamed_in; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_player_streamed_in = nullptr; return; }
                self.on_player_streamed_in = [cb](int pid, int team, int skin,
                                                   float x, float y, float z, float rot,
                                                   uint32_t color, int fs) {
                    py::gil_scoped_acquire _; cb(pid, team, skin, x, y, z, rot, color, fs);
                };
            })
        .def_property("on_player_streamed_out",
            [](const SAMPClient& self) { return self.on_player_streamed_out; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_player_streamed_out = nullptr; return; }
                self.on_player_streamed_out = [cb](int pid) {
                    py::gil_scoped_acquire _; cb(pid);
                };
            })

        // Player info / name
        .def_property("on_player_name",
            [](const SAMPClient& self) { return self.on_player_name; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_player_name = nullptr; return; }
                self.on_player_name = [cb](uint16_t pid, std::string name, uint8_t success) {
                    py::gil_scoped_acquire _; cb(pid, name, success);
                };
            })
        .def_property("on_toggle_controllable",
            [](const SAMPClient& self) { return self.on_toggle_controllable; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_toggle_controllable = nullptr; return; }
                self.on_toggle_controllable = [cb](uint8_t moveable) {
                    py::gil_scoped_acquire _; cb(moveable);
                };
            })
        .def_property("on_player_time",
            [](const SAMPClient& self) { return self.on_player_time; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_player_time = nullptr; return; }
                self.on_player_time = [cb](uint8_t hour, uint8_t minute) {
                    py::gil_scoped_acquire _; cb(hour, minute);
                };
            })
        .def_property("on_death_message",
            [](const SAMPClient& self) { return self.on_death_message; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_death_message = nullptr; return; }
                self.on_death_message = [cb](uint16_t killer_id, uint16_t player_id, uint8_t weapon) {
                    py::gil_scoped_acquire _; cb(killer_id, player_id, weapon);
                };
            })
        .def_property("on_set_armed_weapon",
            [](const SAMPClient& self) { return self.on_set_armed_weapon; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_set_armed_weapon = nullptr; return; }
                self.on_set_armed_weapon = [cb](uint32_t weapon_id) {
                    py::gil_scoped_acquire _; cb(weapon_id);
                };
            })
        .def_property("on_spawn_info",
            [](const SAMPClient& self) { return self.on_spawn_info; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_spawn_info = nullptr; return; }
                self.on_spawn_info = [cb](uint8_t team, uint32_t skin,
                                          float x, float y, float z, float rot,
                                          uint32_t w1, uint32_t w2, uint32_t w3,
                                          uint32_t a1, uint32_t a2, uint32_t a3) {
                    py::gil_scoped_acquire _; cb(team, skin, x, y, z, rot, w1, w2, w3, a1, a2, a3);
                };
            })
        .def_property("on_player_team",
            [](const SAMPClient& self) { return self.on_player_team; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_player_team = nullptr; return; }
                self.on_player_team = [cb](uint16_t pid, uint8_t team) {
                    py::gil_scoped_acquire _; cb(pid, team);
                };
            })
        .def_property("on_put_in_vehicle",
            [](const SAMPClient& self) { return self.on_put_in_vehicle; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_put_in_vehicle = nullptr; return; }
                self.on_put_in_vehicle = [cb](uint16_t vehicle_id, uint8_t seat_id) {
                    py::gil_scoped_acquire _; cb(vehicle_id, seat_id);
                };
            })
        .def_property("on_remove_from_vehicle",
            [](const SAMPClient& self) { return self.on_remove_from_vehicle; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_remove_from_vehicle = nullptr; return; }
                self.on_remove_from_vehicle = [cb]() {
                    py::gil_scoped_acquire _; cb();
                };
            })
        .def_property("on_player_color",
            [](const SAMPClient& self) { return self.on_player_color; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_player_color = nullptr; return; }
                self.on_player_color = [cb](uint16_t pid, uint32_t color) {
                    py::gil_scoped_acquire _; cb(pid, color);
                };
            })
        .def_property("on_world_time",
            [](const SAMPClient& self) { return self.on_world_time; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_world_time = nullptr; return; }
                self.on_world_time = [cb](uint8_t hour) {
                    py::gil_scoped_acquire _; cb(hour);
                };
            })
        .def_property("on_toggle_spectating",
            [](const SAMPClient& self) { return self.on_toggle_spectating; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_toggle_spectating = nullptr; return; }
                self.on_toggle_spectating = [cb](bool spectating) {
                    py::gil_scoped_acquire _; cb(spectating);
                };
            })
        .def_property("on_wanted_level",
            [](const SAMPClient& self) { return self.on_wanted_level; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_wanted_level = nullptr; return; }
                self.on_wanted_level = [cb](uint8_t level) {
                    py::gil_scoped_acquire _; cb(level);
                };
            })
        .def_property("on_weapon_ammo",
            [](const SAMPClient& self) { return self.on_weapon_ammo; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_weapon_ammo = nullptr; return; }
                self.on_weapon_ammo = [cb](uint8_t weapon_id, uint16_t ammo) {
                    py::gil_scoped_acquire _; cb(weapon_id, ammo);
                };
            })
        .def_property("on_gravity",
            [](const SAMPClient& self) { return self.on_gravity; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_gravity = nullptr; return; }
                self.on_gravity = [cb](float gravity) {
                    py::gil_scoped_acquire _; cb(gravity);
                };
            })
        .def_property("on_weather",
            [](const SAMPClient& self) { return self.on_weather; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_weather = nullptr; return; }
                self.on_weather = [cb](uint8_t weather_id) {
                    py::gil_scoped_acquire _; cb(weather_id);
                };
            })
        .def_property("on_player_skin",
            [](const SAMPClient& self) { return self.on_player_skin; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_player_skin = nullptr; return; }
                self.on_player_skin = [cb](int32_t pid, uint32_t skin_id) {
                    py::gil_scoped_acquire _; cb(pid, skin_id);
                };
            })
        .def_property("on_set_interior",
            [](const SAMPClient& self) { return self.on_set_interior; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_set_interior = nullptr; return; }
                self.on_set_interior = [cb](uint8_t interior_id) {
                    py::gil_scoped_acquire _; cb(interior_id);
                };
            })
        .def_property("on_vehicle_streamed_in",
            [](const SAMPClient& self) { return self.on_vehicle_streamed_in; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_vehicle_streamed_in = nullptr; return; }
                self.on_vehicle_streamed_in = [cb](uint16_t vid, int32_t model,
                                                    float x, float y, float z, float angle,
                                                    uint8_t color1, uint8_t color2,
                                                    float health, uint8_t interior,
                                                    uint32_t door_dmg, uint32_t panel_dmg,
                                                    uint8_t light_dmg, uint8_t tire_dmg,
                                                    uint8_t add_siren, uint8_t paintjob,
                                                    uint32_t body_color1, uint32_t body_color2) {
                    py::gil_scoped_acquire _;
                    cb(vid, model, x, y, z, angle, color1, color2, health, interior,
                       door_dmg, panel_dmg, light_dmg, tire_dmg,
                       add_siren, paintjob, body_color1, body_color2);
                };
            })
        .def_property("on_vehicle_streamed_out",
            [](const SAMPClient& self) { return self.on_vehicle_streamed_out; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_vehicle_streamed_out = nullptr; return; }
                self.on_vehicle_streamed_out = [cb](uint16_t vid) {
                    py::gil_scoped_acquire _; cb(vid);
                };
            })
        .def_property("on_player_death",
            [](const SAMPClient& self) { return self.on_player_death; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_player_death = nullptr; return; }
                self.on_player_death = [cb](uint16_t pid) {
                    py::gil_scoped_acquire _; cb(pid);
                };
            })

        // ── Send helpers ───────────────────────────────────────────────────────
        .def("send_dialog_response",
             [](SAMPClient& self, uint16_t did, uint8_t btn, uint16_t item, const std::string& text) {
                 self.send_dialog_response(did, btn, item, text);
             },
             py::arg("dialog_id"), py::arg("button"),
             py::arg("list_item") = 0, py::arg("text") = "")
        .def("send_death",
             [](SAMPClient& self, uint8_t weapon, uint16_t killer) {
                 self.send_death(weapon, killer);
             },
             py::arg("weapon_id") = 0, py::arg("killer_id") = 0xFFFF)
        .def("send_enter_vehicle",
             [](SAMPClient& self, uint16_t vid, bool pass) {
                 self.send_enter_vehicle(vid, pass);
             },
             py::arg("vehicle_id"), py::arg("is_passenger") = false)
        .def("send_exit_vehicle",
             [](SAMPClient& self, uint16_t vid) { self.send_exit_vehicle(vid); },
             py::arg("vehicle_id"))
        .def("send_command",
             [](SAMPClient& self, const std::string& text) { self.send_command(text); },
             py::arg("text"));

    // Reliability enum values for send_rpc
    m.attr("UNRELIABLE")           = static_cast<int>(UNRELIABLE);
    m.attr("UNRELIABLE_SEQUENCED") = static_cast<int>(UNRELIABLE_SEQUENCED);
    m.attr("RELIABLE")             = static_cast<int>(RELIABLE);
    m.attr("RELIABLE_ORDERED")     = static_cast<int>(RELIABLE_ORDERED);
    m.attr("RELIABLE_SEQUENCED")   = static_cast<int>(RELIABLE_SEQUENCED);

    // ── RPC IDs ────────────────────────────────────────────────────────────────
    // server→client
    m.attr("RPC_SERVER_JOIN")        = static_cast<int>(RPC_SERVER_JOIN);
    m.attr("RPC_SERVER_QUIT")        = static_cast<int>(RPC_SERVER_QUIT);
    m.attr("RPC_INIT_GAME")          = static_cast<int>(RPC_INIT_GAME);
    m.attr("RPC_CHAT")               = static_cast<int>(RPC_CHAT);
    m.attr("RPC_CLIENT_MESSAGE")     = static_cast<int>(RPC_CLIENT_MESSAGE);
    m.attr("RPC_DIALOG_BOX")         = static_cast<int>(RPC_DIALOG_BOX);
    m.attr("RPC_GAME_TEXT")          = static_cast<int>(RPC_GAME_TEXT);
    m.attr("RPC_SET_HEALTH")         = static_cast<int>(RPC_SET_HEALTH);
    m.attr("RPC_SET_ARMOUR")         = static_cast<int>(RPC_SET_ARMOUR);
    m.attr("RPC_SET_POSITION")       = static_cast<int>(RPC_SET_POSITION);
    m.attr("RPC_SET_CHECKPOINT")     = static_cast<int>(RPC_SET_CHECKPOINT);
    m.attr("RPC_DISABLE_CHECKPOINT") = static_cast<int>(RPC_DISABLE_CHECKPOINT);
    m.attr("RPC_WORLD_PLAYER_ADD")   = static_cast<int>(RPC_WORLD_PLAYER_ADD);
    m.attr("RPC_WORLD_PLAYER_REMOVE")= static_cast<int>(RPC_WORLD_PLAYER_REMOVE);
    m.attr("RPC_CONNECTION_REJ")     = static_cast<int>(RPC_CONNECTION_REJ);
    // client→server
    m.attr("RPC_CLIENT_JOIN")        = static_cast<int>(RPC_CLIENT_JOIN);
    m.attr("RPC_REQUEST_CLASS")      = static_cast<int>(RPC_REQUEST_CLASS);
    m.attr("RPC_REQUEST_SPAWN")      = static_cast<int>(RPC_REQUEST_SPAWN);
    m.attr("RPC_SPAWN")              = static_cast<int>(RPC_SPAWN);
    m.attr("RPC_DIALOG_RESPONSE")    = static_cast<int>(RPC_DIALOG_RESPONSE);
    m.attr("RPC_DEATH")              = static_cast<int>(RPC_DEATH);
    m.attr("RPC_ENTER_VEHICLE")          = static_cast<int>(RPC_ENTER_VEHICLE);
    m.attr("RPC_EXIT_VEHICLE")           = static_cast<int>(RPC_EXIT_VEHICLE);
    m.attr("RPC_SERVER_COMMAND")         = static_cast<int>(RPC_SERVER_COMMAND);
    // new server→client
    m.attr("RPC_SET_PLAYER_NAME")        = static_cast<int>(RPC_SET_PLAYER_NAME);
    m.attr("RPC_TOGGLE_CONTROLLABLE")    = static_cast<int>(RPC_TOGGLE_CONTROLLABLE);
    m.attr("RPC_SET_PLAYER_TIME")        = static_cast<int>(RPC_SET_PLAYER_TIME);
    m.attr("RPC_SEND_DEATH_MESSAGE")     = static_cast<int>(RPC_SEND_DEATH_MESSAGE);
    m.attr("RPC_SET_ARMED_WEAPON")       = static_cast<int>(RPC_SET_ARMED_WEAPON);
    m.attr("RPC_SET_SPAWN_INFO")         = static_cast<int>(RPC_SET_SPAWN_INFO);
    m.attr("RPC_SET_PLAYER_TEAM")        = static_cast<int>(RPC_SET_PLAYER_TEAM);
    m.attr("RPC_PUT_IN_VEHICLE")         = static_cast<int>(RPC_PUT_IN_VEHICLE);
    m.attr("RPC_REMOVE_FROM_VEHICLE")    = static_cast<int>(RPC_REMOVE_FROM_VEHICLE);
    m.attr("RPC_SET_PLAYER_COLOR")       = static_cast<int>(RPC_SET_PLAYER_COLOR);
    m.attr("RPC_SET_WORLD_TIME")         = static_cast<int>(RPC_SET_WORLD_TIME);
    m.attr("RPC_TOGGLE_SPECTATING")      = static_cast<int>(RPC_TOGGLE_SPECTATING);
    m.attr("RPC_SET_WANTED_LEVEL")       = static_cast<int>(RPC_SET_WANTED_LEVEL);
    m.attr("RPC_SET_WEAPON_AMMO")        = static_cast<int>(RPC_SET_WEAPON_AMMO);
    m.attr("RPC_SET_GRAVITY")            = static_cast<int>(RPC_SET_GRAVITY);
    m.attr("RPC_SET_WEATHER")            = static_cast<int>(RPC_SET_WEATHER);
    m.attr("RPC_SET_PLAYER_SKIN")        = static_cast<int>(RPC_SET_PLAYER_SKIN);
    m.attr("RPC_SET_INTERIOR")           = static_cast<int>(RPC_SET_INTERIOR);
    m.attr("RPC_WORLD_VEHICLE_ADD")      = static_cast<int>(RPC_WORLD_VEHICLE_ADD);
    m.attr("RPC_WORLD_VEHICLE_REMOVE")   = static_cast<int>(RPC_WORLD_VEHICLE_REMOVE);
    m.attr("RPC_DEATH_BROADCAST")        = static_cast<int>(RPC_DEATH_BROADCAST);
}
