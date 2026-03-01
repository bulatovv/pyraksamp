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

        // Callbacks: Python functions called with GIL held
        .def_property("on_connect",
            [](const SAMPClient& self) { return self.on_connect; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_connect = nullptr; return; }
                self.on_connect = [cb]() {
                    py::gil_scoped_acquire gil;
                    cb();
                };
            })
        .def_property("on_disconnect",
            [](const SAMPClient& self) { return self.on_disconnect; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_disconnect = nullptr; return; }
                self.on_disconnect = [cb]() {
                    py::gil_scoped_acquire gil;
                    cb();
                };
            })
        .def_property("on_rpc",
            [](const SAMPClient& self) { return self.on_rpc; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_rpc = nullptr; return; }
                self.on_rpc = [cb](uint8_t rpc_id, std::vector<uint8_t> data) {
                    py::gil_scoped_acquire gil;
                    cb(rpc_id, py::bytes(reinterpret_cast<const char*>(data.data()),
                                        data.size()));
                };
            })
        .def_property("on_player_join",
            [](const SAMPClient& self) { return self.on_player_join; },
            [](SAMPClient& self, py::object cb) {
                if (cb.is_none()) { self.on_player_join = nullptr; return; }
                self.on_player_join = [cb](int pid, std::string name) {
                    py::gil_scoped_acquire gil;
                    cb(pid, name);
                };
            });

    // Reliability enum values for send_rpc
    m.attr("UNRELIABLE")           = static_cast<int>(UNRELIABLE);
    m.attr("UNRELIABLE_SEQUENCED") = static_cast<int>(UNRELIABLE_SEQUENCED);
    m.attr("RELIABLE")             = static_cast<int>(RELIABLE);
    m.attr("RELIABLE_ORDERED")     = static_cast<int>(RELIABLE_ORDERED);
    m.attr("RELIABLE_SEQUENCED")   = static_cast<int>(RELIABLE_SEQUENCED);

    // Common RPC IDs
    m.attr("RPC_CLIENT_JOIN")   = static_cast<int>(RPC_CLIENT_JOIN);
    m.attr("RPC_INIT_GAME")     = static_cast<int>(RPC_INIT_GAME);
    m.attr("RPC_REQUEST_CLASS") = static_cast<int>(RPC_REQUEST_CLASS);
    m.attr("RPC_REQUEST_SPAWN") = static_cast<int>(RPC_REQUEST_SPAWN);
    m.attr("RPC_SPAWN")         = static_cast<int>(RPC_SPAWN);
    m.attr("RPC_CHAT")          = 101;
}
