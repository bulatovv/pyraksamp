#pragma once
#include <cstdint>
#include <stdexcept>
#include <string>

// C FFI to Rust samp_rust staticlib
extern "C" {
    void*          bs_new();
    void*          bs_new_from_bytes(const uint8_t* data, int32_t len);
    void           bs_free(void* p);

    void           bs_write_bit(void* p, int32_t bit);
    void           bs_write_bits(void* p, const uint8_t* data, int32_t count, bool right_aligned);
    void           bs_write_bool(void* p, bool v);
    void           bs_write_u8(void* p, uint8_t v);
    void           bs_write_u16(void* p, uint16_t v);
    void           bs_write_u32(void* p, uint32_t v);
    void           bs_write_i32(void* p, int32_t v);
    void           bs_write_float(void* p, float v);
    void           bs_write_compressed_u16(void* p, uint16_t v);
    void           bs_write_compressed_u32(void* p, uint32_t v);
    void           bs_write_aligned_bytes(void* p, const uint8_t* data, int32_t len);

    int32_t        bs_read_bit(void* p);
    int32_t        bs_read_bits(void* p, uint8_t* out, int32_t count, bool right_aligned);
    int32_t        bs_read_bool(void* p);
    int32_t        bs_read_u8(void* p, uint8_t* out);
    int32_t        bs_read_u16(void* p, uint16_t* out);
    int32_t        bs_read_u32(void* p, uint32_t* out);
    int32_t        bs_read_i32(void* p, int32_t* out);
    int32_t        bs_read_float(void* p, float* out);
    int32_t        bs_read_compressed_u16(void* p, uint16_t* out);
    int32_t        bs_read_compressed_u32(void* p, uint32_t* out);
    int32_t        bs_read_aligned_bytes(void* p, uint8_t* out, int32_t len);
    void           bs_skip_bits(void* p, int32_t count);
    int32_t        bs_read_compressed_string(void* p, uint8_t* out, int32_t max_chars);

    const uint8_t* bs_data(const void* p);
    int32_t        bs_num_bytes(const void* p);
    int32_t        bs_num_bits(const void* p);
    int32_t        bs_bits_remaining(const void* p);
    int32_t        bs_bytes_remaining(const void* p);
    int32_t        bs_rpos_bits(const void* p);
} // extern "C"

// Thin C++ wrapper around the Rust BitStream.
// All bit-ordering and integer-layout semantics are identical to the original C++ version.
class BitStream {
    void* h_;
public:
    BitStream() : h_(bs_new()) {}
    explicit BitStream(const uint8_t* data, int len)
        : h_(bs_new_from_bytes(data, (int32_t)len)) {}
    ~BitStream() { bs_free(h_); }

    BitStream(const BitStream&) = delete;
    BitStream& operator=(const BitStream&) = delete;

    // ---- Write ----
    void write_bit(int bit) { bs_write_bit(h_, bit); }
    void write_bits(const uint8_t* data, int count, bool right_aligned = true) {
        bs_write_bits(h_, data, (int32_t)count, right_aligned);
    }
    void write_bool(bool v)        { bs_write_bool(h_, v); }
    void write_uint8(uint8_t v)    { bs_write_u8(h_, v); }
    void write_uint16_le(uint16_t v) { bs_write_u16(h_, v); }
    void write_uint32_le(uint32_t v) { bs_write_u32(h_, v); }
    void write_int32_le(int32_t v)   { bs_write_i32(h_, v); }
    void write_float_le(float v)     { bs_write_float(h_, v); }
    void write_compressed_uint16(uint16_t v) { bs_write_compressed_u16(h_, v); }
    void write_compressed_uint32(uint32_t v) { bs_write_compressed_u32(h_, v); }
    void write_aligned_bytes(const uint8_t* data, int len) {
        bs_write_aligned_bytes(h_, data, (int32_t)len);
    }

    // ---- Read (throw on underflow to match original C++ behaviour) ----
    int read_bit() {
        int32_t v = bs_read_bit(h_);
        if (v < 0) throw std::runtime_error("BitStream underflow");
        return v;
    }
    void read_bits(uint8_t* out, int count, bool right_aligned = true) {
        if (bs_read_bits(h_, out, (int32_t)count, right_aligned) != 0)
            throw std::runtime_error("BitStream underflow");
    }
    bool read_bool() {
        int32_t v = bs_read_bool(h_);
        if (v < 0) throw std::runtime_error("BitStream underflow");
        return v != 0;
    }
    uint8_t read_uint8() {
        uint8_t v = 0;
        if (bs_read_u8(h_, &v) != 0) throw std::runtime_error("BitStream underflow");
        return v;
    }
    uint16_t read_uint16_le() {
        uint16_t v = 0;
        if (bs_read_u16(h_, &v) != 0) throw std::runtime_error("BitStream underflow");
        return v;
    }
    uint32_t read_uint32_le() {
        uint32_t v = 0;
        if (bs_read_u32(h_, &v) != 0) throw std::runtime_error("BitStream underflow");
        return v;
    }
    int32_t read_int32_le() {
        int32_t v = 0;
        if (bs_read_i32(h_, &v) != 0) throw std::runtime_error("BitStream underflow");
        return v;
    }
    float read_float_le() {
        float v = 0.0f;
        if (bs_read_float(h_, &v) != 0) throw std::runtime_error("BitStream underflow");
        return v;
    }
    uint16_t read_compressed_uint16() {
        uint16_t v = 0;
        if (bs_read_compressed_u16(h_, &v) != 0)
            throw std::runtime_error("BitStream underflow");
        return v;
    }
    uint32_t read_compressed_uint32() {
        uint32_t v = 0;
        if (bs_read_compressed_u32(h_, &v) != 0)
            throw std::runtime_error("BitStream underflow");
        return v;
    }
    void read_aligned_bytes(uint8_t* out, int len) {
        if (bs_read_aligned_bytes(h_, out, (int32_t)len) != 0)
            throw std::runtime_error("BitStream underflow");
    }
    void skip_bits(int count) { bs_skip_bits(h_, (int32_t)count); }

    std::string read_compressed_string(int max_chars = 256) {
        std::string buf(max_chars, '\0');
        int32_t n = bs_read_compressed_string(
            h_, reinterpret_cast<uint8_t*>(&buf[0]), (int32_t)max_chars);
        if (n < 0) throw std::runtime_error("BitStream underflow");
        buf.resize(n);
        return buf;
    }

    // ---- Accessors ----
    const uint8_t* data()    const { return bs_data(h_); }
    int num_bytes()          const { return (int)bs_num_bytes(h_); }
    int num_bits()           const { return (int)bs_num_bits(h_); }
    int bits_remaining()     const { return (int)bs_bits_remaining(h_); }
    int bytes_remaining()    const { return (int)bs_bytes_remaining(h_); }
    int rpos_bits()          const { return (int)bs_rpos_bits(h_); }
};
