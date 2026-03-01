#pragma once
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>

namespace samp {

// Encrypt a packet for client→server transmission.
// Returns encrypted bytes (length = input_len + 1, first byte is checksum).
std::vector<uint8_t> encrypt(const uint8_t* data, int len, uint16_t port);

// Decrypt a packet received from server (server→client is NOT encrypted in vanilla SAMP).
// Returns decrypted bytes (NULL if checksum mismatch).
// Note: open.mp servers can optionally use their own encryption (omp mode).
// For SAMP-compatible servers, server→client is plain RakNet (no decryption needed).

// Auth key table: given the challenge string the server sent us,
// return the response string to send back.
// Returns nullptr if challenge is unknown.
const char* auth_response(const char* challenge);

} // namespace samp
