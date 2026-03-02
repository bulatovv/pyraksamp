#pragma once
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <vector>

// Minimal RakNet-compatible BitStream.
// Bits are stored MSB-first within each byte (bit 0 of stream = MSB of byte 0).
// Multi-byte values use little-endian byte order (matching RakNet on x86).
class BitStream {
public:
    BitStream() : wpos_(0), rpos_(0) { buf_.reserve(64); }

    explicit BitStream(const uint8_t* data, int len)
        : buf_(data, data + len), wpos_(len * 8), rpos_(0) {}

    // ---- Write ----

    void write_bit(int bit) {
        ensure_space(1);
        int byte_idx = wpos_ >> 3;
        int bit_idx  = wpos_ & 7;
        if (bit_idx == 0)
            buf_[byte_idx] = 0;
        if (bit)
            buf_[byte_idx] |= (0x80u >> bit_idx);
        ++wpos_;
    }

    // Write `count` bits from `data` (MSB-first within each byte).
    // right_aligned=true: if count%8 != 0, the useful bits are in the
    //                      LOWER bits of the first byte (right side).
    void write_bits(const uint8_t* data, int count, bool right_aligned = true) {
        if (count <= 0) return;
        ensure_space(count);

        int offset    = 0;
        int remaining = count;
        while (remaining > 0) {
            uint8_t b = data[offset];
            if (remaining < 8 && right_aligned)
                b = static_cast<uint8_t>(b << (8 - remaining));

            int mod8 = wpos_ & 7;
            if (mod8 == 0) {
                buf_[wpos_ >> 3] = b;
            } else {
                buf_[wpos_ >> 3] |= (b >> mod8);
                int bits_in_first = 8 - mod8;
                if (bits_in_first < std::min(8, remaining))
                    buf_[(wpos_ >> 3) + 1] = static_cast<uint8_t>(b << bits_in_first);
            }

            if (remaining >= 8) { wpos_ += 8; remaining -= 8; }
            else                { wpos_ += remaining; remaining = 0; }
            ++offset;
        }
    }

    void write_bool(bool v)        { write_bit(v ? 1 : 0); }
    void write_uint8(uint8_t v)    { write_bits(&v, 8, true); }

    void write_uint16_le(uint16_t v) {
        uint8_t d[2]; memcpy(d, &v, 2);
        write_bits(d, 16, true);
    }
    void write_uint32_le(uint32_t v) {
        uint8_t d[4]; memcpy(d, &v, 4);
        write_bits(d, 32, true);
    }
    void write_int32_le(int32_t v) {
        uint8_t d[4]; memcpy(d, &v, 4);
        write_bits(d, 32, true);
    }
    void write_float_le(float v) {
        uint8_t d[4]; memcpy(d, &v, 4);
        write_bits(d, 32, true);
    }

    // WriteCompressed for uint16: skips zero high byte and optionally high nibble
    void write_compressed_uint16(uint16_t v) {
        uint8_t lo = v & 0xFF, hi = (v >> 8) & 0xFF;
        if (hi == 0) {
            write_bit(1);
            if ((lo & 0xF0) == 0) { write_bit(1); write_bits(&lo, 4, true); }
            else                   { write_bit(0); write_bits(&lo, 8, true); }
        } else {
            write_bit(0);
            write_bits(&lo, 8, true);
            write_bits(&hi, 8, true);
        }
    }

    // WriteCompressed for uint32 (matches RakNet's WriteCompressed<unsigned int>).
    // Writes 1 bit per zero high byte, then 0 bit + remaining bytes for the first non-zero high byte.
    // For the last (lowest) byte: if upper nibble is 0, writes nibble flag (1) + 4 bits; else writes nibble flag (0) + 8 bits.
    void write_compressed_uint32(uint32_t v) {
        uint8_t b[4]; memcpy(b, &v, 4); // little-endian bytes
        for (int cur = 3; cur > 0; --cur) {
            if (b[cur] == 0) {
                write_bit(1);
            } else {
                write_bit(0);
                write_bits(b, (cur + 1) * 8, false); // write cur+1 bytes from byte 0
                return;
            }
        }
        // Last byte: nibble-level compression matching RakNet
        if ((b[0] & 0xF0) == 0) {
            write_bit(1);            // nibble flag: upper nibble is 0
            write_bits(b, 4, true);  // write only lower 4 bits
        } else {
            write_bit(0);
            write_bits(b, 8, true);  // full byte
        }
    }

    // Align write position to byte boundary, then write raw bytes
    void write_aligned_bytes(const uint8_t* data, int len) {
        if (wpos_ & 7) wpos_ = (wpos_ + 7) & ~7;
        ensure_space(len * 8);
        memcpy(&buf_[wpos_ >> 3], data, len);
        wpos_ += len * 8;
    }

    // ---- Read ----

    int read_bit() {
        if (rpos_ >= wpos_) throw std::runtime_error("BitStream underflow");
        int bit = (buf_[rpos_ >> 3] >> (7 - (rpos_ & 7))) & 1;
        ++rpos_;
        return bit;
    }

    // Read `count` bits into `out`.
    // right_aligned=true: if count%8 != 0, shifts last byte right so bits land in lower positions.
    void read_bits(uint8_t* out, int count, bool right_aligned = true) {
        int nbytes = (count + 7) / 8;
        memset(out, 0, nbytes);

        int offset    = 0;
        int remaining = count;
        while (remaining > 0) {
            int mod8 = rpos_ & 7;
            uint8_t b = buf_[rpos_ >> 3] << mod8;
            if (mod8 > 0 && remaining > (8 - mod8))
                b |= buf_[(rpos_ >> 3) + 1] >> (8 - mod8);

            out[offset] = b;
            if (remaining >= 8) { rpos_ += 8; remaining -= 8; }
            else                { rpos_ += remaining; remaining = 0; }
            ++offset;
        }

        // Right-align last partial byte
        if (right_aligned && (count % 8 != 0)) {
            int last = nbytes - 1;
            out[last] >>= (8 - (count % 8));
        }
    }

    bool     read_bool()      { return read_bit() != 0; }
    uint8_t  read_uint8()     { uint8_t v=0; read_bits(&v,8,true); return v; }

    uint16_t read_uint16_le() {
        uint8_t d[2]; read_bits(d, 16, true);
        uint16_t v; memcpy(&v, d, 2); return v;
    }
    uint32_t read_uint32_le() {
        uint8_t d[4]; read_bits(d, 32, true);
        uint32_t v; memcpy(&v, d, 4); return v;
    }
    int32_t  read_int32_le()  {
        uint8_t d[4]; read_bits(d, 32, true);
        int32_t v; memcpy(&v, d, 4); return v;
    }
    float    read_float_le()  {
        uint8_t d[4]; read_bits(d, 32, true);
        float v; memcpy(&v, d, 4); return v;
    }

    uint16_t read_compressed_uint16() {
        uint8_t lo = 0, hi = 0;
        if (read_bit()) {          // high byte is 0
            if (read_bit())        // high nibble of low byte is also 0
                read_bits(&lo, 4, true);
            else
                read_bits(&lo, 8, true);
        } else {
            read_bits(&lo, 8, true);
            read_bits(&hi, 8, true);
        }
        return static_cast<uint16_t>(lo | (hi << 8));
    }

    // ReadCompressed for uint32 (matches RakNet's ReadCompressed<unsigned int>).
    // For the last (lowest) byte: reads nibble flag; if true, reads 4 bits; else reads 8 bits.
    uint32_t read_compressed_uint32() {
        uint32_t v = 0;
        uint8_t* b = reinterpret_cast<uint8_t*>(&v);
        for (int cur = 3; cur > 0; --cur) {
            if (read_bit()) {      // byte is 0
                b[cur] = 0;
            } else {               // this byte and below are non-trivial
                read_bits(b, (cur + 1) * 8, false); // read cur+1 bytes
                return v;
            }
        }
        // Last byte: nibble-level compression matching RakNet
        bool nibble_flag = read_bit();
        if (nibble_flag) {
            read_bits(b, 4, true); // upper nibble is 0, read only lower 4 bits
        } else {
            read_bits(b, 8, true); // full byte
        }
        return v;
    }

    // Align read position to byte boundary, then read raw bytes
    void read_aligned_bytes(uint8_t* out, int len) {
        if (rpos_ & 7) rpos_ = (rpos_ + 7) & ~7;
        memcpy(out, &buf_[rpos_ >> 3], len);
        rpos_ += len * 8;
    }

    void skip_bits(int count) { rpos_ += count; }

    // ---- Accessors ----
    const uint8_t* data()    const { return buf_.data(); }
    int num_bytes()          const { return (wpos_ + 7) / 8; }
    int num_bits()           const { return wpos_; }
    int bits_remaining()     const { return wpos_ - rpos_; }
    int bytes_remaining()    const { return (wpos_ - rpos_ + 7) / 8; }
    int rpos_bits()          const { return rpos_; }

private:
    void ensure_space(int bits) {
        int needed = (wpos_ + bits + 7) / 8;
        if (needed > static_cast<int>(buf_.size()))
            buf_.resize(needed + 32, 0);
    }

    std::vector<uint8_t> buf_;
    int wpos_;
    int rpos_;
};
