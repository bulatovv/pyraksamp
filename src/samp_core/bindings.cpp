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
             py::arg("vehicle_id"));

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
    m.attr("RPC_ENTER_VEHICLE")      = static_cast<int>(RPC_ENTER_VEHICLE);
    m.attr("RPC_EXIT_VEHICLE")       = static_cast<int>(RPC_EXIT_VEHICLE);
}
