#include "encrypt.h"
#include <cstdint>
#include <vector>

// C FFI to Rust samp_rust staticlib
extern "C" {
    void        samp_encrypt(const uint8_t* data, size_t len, uint16_t port, uint8_t* out);
    const char* samp_auth_response(const char* challenge);
}

namespace samp {

std::vector<uint8_t> encrypt(const uint8_t* data, int len, uint16_t port) {
    std::vector<uint8_t> out(len + 1);
    samp_encrypt(data, (size_t)len, port, out.data());
    return out;
}

const char* auth_response(const char* challenge) {
    return samp_auth_response(challenge);
}

} // namespace samp
