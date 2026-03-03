#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "encrypt.h"
#include "reliability.h"
#include "bitstream.h"

namespace py = pybind11;
using namespace samp;

PYBIND11_MODULE(_core_test, m) {
    m.doc() = "Internal test bindings for pyraksamp (encrypt, reliability, bitstream)";

    // ── encrypt ──────────────────────────────────────────────────────────────

    m.def("encrypt", [](py::bytes data, uint16_t port) -> py::bytes {
        std::string s = data;
        auto out = samp::encrypt(
            reinterpret_cast<const uint8_t*>(s.data()),
            static_cast<int>(s.size()), port);
        return py::bytes(reinterpret_cast<const char*>(out.data()), out.size());
    }, py::arg("data"), py::arg("port"));

    m.def("auth_response", [](const std::string& challenge) -> py::object {
        const char* resp = samp::auth_response(challenge.c_str());
        if (resp == nullptr) return py::none();
        return py::str(resp);
    }, py::arg("challenge"));

    // ── reliability ──────────────────────────────────────────────────────────

    py::class_<SplitBuffer>(m, "SplitBuffer")
        .def(py::init<>());

    m.def("make_packet",
        [](py::bytes data, uint16_t msg_num, uint8_t rel, uint8_t oc, uint16_t oi) -> py::bytes {
            std::string s = data;
            auto out = samp::make_packet(
                reinterpret_cast<const uint8_t*>(s.data()),
                static_cast<int>(s.size()),
                msg_num,
                static_cast<Reliability>(rel),
                oc, oi);
            return py::bytes(reinterpret_cast<const char*>(out.data()), out.size());
        },
        py::arg("data"), py::arg("msg_num"),
        py::arg("rel") = static_cast<uint8_t>(RELIABLE),
        py::arg("oc") = 0, py::arg("oi") = 0);

    m.def("make_ack",
        [](std::vector<uint16_t> nums) -> py::bytes {
            auto out = samp::make_ack(nums);
            return py::bytes(reinterpret_cast<const char*>(out.data()), out.size());
        },
        py::arg("nums"));

    // parse() returns None if malformed, otherwise a dict:
    // {"is_ack": bool, "acked": [int], "packets": [{"msg_num", "reliability", "oc", "oi", "data"}]}
    m.def("parse",
        [](py::bytes data, SplitBuffer& buf) -> py::object {
            std::string s = data;
            auto result = samp::parse(
                reinterpret_cast<const uint8_t*>(s.data()),
                static_cast<int>(s.size()),
                buf);
            if (!result.has_value()) return py::none();

            py::dict d;
            d["is_ack"] = result->is_ack;

            py::list acked;
            for (auto n : result->acked) acked.append(n);
            d["acked"] = acked;

            py::list packets;
            for (const auto& pkt : result->packets) {
                py::dict pd;
                pd["msg_num"]     = pkt.msg_num;
                pd["reliability"] = static_cast<int>(pkt.reliability);
                pd["oc"]          = pkt.ordering_channel;
                pd["oi"]          = pkt.ordering_index;
                pd["data"]        = py::bytes(
                    reinterpret_cast<const char*>(pkt.data.data()),
                    pkt.data.size());
                packets.append(pd);
            }
            d["packets"] = packets;
            return d;
        },
        py::arg("data"), py::arg("buf"));

    // ── BitStream ─────────────────────────────────────────────────────────────

    py::class_<BitStream>(m, "BitStream")
        // Default constructor: empty write buffer
        .def(py::init<>())
        // Construct from bytes: initialises a read buffer
        .def(py::init([](py::bytes b) {
            std::string s = b;
            return new BitStream(
                reinterpret_cast<const uint8_t*>(s.data()),
                static_cast<int>(s.size()));
        }))

        // ---- Write ----
        .def("write_bool",  &BitStream::write_bool,  py::arg("v"))
        .def("write_u8",    &BitStream::write_uint8,  py::arg("v"))
        .def("write_u16",   &BitStream::write_uint16_le, py::arg("v"))
        .def("write_u32",   &BitStream::write_uint32_le, py::arg("v"))
        .def("write_i32",   &BitStream::write_int32_le,  py::arg("v"))
        .def("write_float", &BitStream::write_float_le,  py::arg("v"))
        .def("write_bits",
            [](BitStream& self, py::bytes data, int count, bool right_aligned) {
                std::string s = data;
                self.write_bits(
                    reinterpret_cast<const uint8_t*>(s.data()),
                    count, right_aligned);
            },
            py::arg("data"), py::arg("count"), py::arg("right_aligned") = true)
        .def("write_compressed_u16", &BitStream::write_compressed_uint16, py::arg("v"))
        .def("write_compressed_u32", &BitStream::write_compressed_uint32, py::arg("v"))
        .def("write_aligned_bytes",
            [](BitStream& self, py::bytes data) {
                std::string s = data;
                self.write_aligned_bytes(
                    reinterpret_cast<const uint8_t*>(s.data()),
                    static_cast<int>(s.size()));
            },
            py::arg("data"))

        // ---- Read ----
        .def("read_bool",  &BitStream::read_bool)
        .def("read_u8",    &BitStream::read_uint8)
        .def("read_u16",   &BitStream::read_uint16_le)
        .def("read_u32",   &BitStream::read_uint32_le)
        .def("read_i32",   &BitStream::read_int32_le)
        .def("read_float", &BitStream::read_float_le)
        .def("read_bits",
            [](BitStream& self, int count, bool right_aligned) -> py::bytes {
                int nbytes = (count + 7) / 8;
                std::vector<uint8_t> out(nbytes, 0);
                self.read_bits(out.data(), count, right_aligned);
                return py::bytes(
                    reinterpret_cast<const char*>(out.data()), out.size());
            },
            py::arg("count"), py::arg("right_aligned") = true)
        .def("read_compressed_u16", &BitStream::read_compressed_uint16)
        .def("read_compressed_u32", &BitStream::read_compressed_uint32)
        .def("read_aligned_bytes",
            [](BitStream& self, int count) -> py::bytes {
                std::vector<uint8_t> out(count);
                self.read_aligned_bytes(out.data(), count);
                return py::bytes(
                    reinterpret_cast<const char*>(out.data()), out.size());
            },
            py::arg("count"))
        .def("skip_bits", &BitStream::skip_bits, py::arg("count"))
        .def("read_compressed_string", &BitStream::read_compressed_string,
             py::arg("max_chars") = 256)

        // ---- Accessors ----
        .def("bytes", [](BitStream& self) -> py::bytes {
            return py::bytes(
                reinterpret_cast<const char*>(self.data()), self.num_bytes());
        })
        .def("num_bits",       &BitStream::num_bits)
        .def("bits_remaining", &BitStream::bits_remaining);

    // ── Reliability constants ─────────────────────────────────────────────────
    m.attr("UNRELIABLE")           = static_cast<int>(UNRELIABLE);
    m.attr("UNRELIABLE_SEQUENCED") = static_cast<int>(UNRELIABLE_SEQUENCED);
    m.attr("RELIABLE")             = static_cast<int>(RELIABLE);
    m.attr("RELIABLE_ORDERED")     = static_cast<int>(RELIABLE_ORDERED);
    m.attr("RELIABLE_SEQUENCED")   = static_cast<int>(RELIABLE_SEQUENCED);
}
