//! RakNet-compatible BitStream + Huffman decoder.
//! Exact port of bitstream.h — bit ordering and integer layout are identical.

use std::cmp;

// ── Huffman tree ─────────────────────────────────────────────────────────────

static ENGLISH_FREQ: [u32; 256] = [
    0,0,0,0,0,0,0,0,0,0,722,0,0,2,0,0,       // 0-15
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,          // 16-31
    11084,58,63,1,0,31,0,317,64,64,44,0,695,62,980,266, // 32-47
    69,67,56,7,73,3,14,2,69,1,167,9,1,2,25,94,         // 48-63
    0,195,139,34,96,48,103,56,125,653,21,5,23,64,85,44, // 64-79
    34,7,92,76,147,12,14,57,15,39,15,1,1,1,2,3,        // 80-95
    0,3611,845,1077,1884,5870,841,1057,2501,3212,164,531,2019,1330,3056,4037, // 96-111
    848,47,2586,2919,4771,1707,535,1106,152,1243,100,0,2,0,10,0, // 112-127
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, // 128-143
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, // 144-159
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, // 160-175
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, // 176-191
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, // 192-207
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, // 208-223
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, // 224-239
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, // 240-255
];

#[derive(Copy, Clone)]
#[derive(Default)]
struct HuffNode {
    left: i16,
    right: i16,
    value: u8,
    weight: u32,
}

pub struct HuffTree {
    pool: [HuffNode; 511],
    root: i32,
}

fn huffman_build() -> HuffTree {
    let mut pool = [HuffNode::default(); 511];

    // Initialise leaves
    for i in 0..256usize {
        pool[i].left = -1;
        pool[i].right = -1;
        pool[i].value = i as u8;
        pool[i].weight = if ENGLISH_FREQ[i] != 0 { ENGLISH_FREQ[i] } else { 1 };
    }

    // Build sorted list with insertion sort.
    // Insert BEFORE first element whose weight >= new node's weight.
    let mut sorted: Vec<i32> = Vec::with_capacity(512);
    for i in 0..256i32 {
        let mut pos = 0;
        while pos < sorted.len() && pool[sorted[pos] as usize].weight < pool[i as usize].weight {
            pos += 1;
        }
        sorted.insert(pos, i);
    }

    // Merge phase: pop two smallest, create parent, re-insert
    let mut next = 256i32;
    while sorted.len() > 1 {
        let lesser = sorted[0];
        let greater = sorted[1];
        sorted.drain(0..2);

        let parent = next;
        next += 1;
        pool[parent as usize].left = lesser as i16;
        pool[parent as usize].right = greater as i16;
        pool[parent as usize].value = 0;
        pool[parent as usize].weight =
            pool[lesser as usize].weight + pool[greater as usize].weight;

        let pw = pool[parent as usize].weight;
        let mut pos = 0;
        while pos < sorted.len() && pool[sorted[pos] as usize].weight < pw {
            pos += 1;
        }
        sorted.insert(pos, parent);
    }

    HuffTree { pool, root: sorted[0] }
}

static HUFF_TREE: std::sync::OnceLock<HuffTree> = std::sync::OnceLock::new();

fn huff_tree() -> &'static HuffTree {
    HUFF_TREE.get_or_init(huffman_build)
}

// ── BitStream ─────────────────────────────────────────────────────────────────

pub struct BitStream {
    buf: Vec<u8>,
    wpos: i32, // write position in bits
    rpos: i32, // read position in bits
}

impl Default for BitStream {
    fn default() -> Self { Self::new() }
}

impl BitStream {
    pub fn new() -> Self {
        let mut buf = Vec::with_capacity(64);
        buf.resize(8, 0u8);
        BitStream { buf, wpos: 0, rpos: 0 }
    }

    pub fn from_bytes(data: &[u8]) -> Self {
        BitStream {
            buf: data.to_vec(),
            wpos: (data.len() * 8) as i32,
            rpos: 0,
        }
    }

    fn ensure_space(&mut self, bits: i32) {
        let needed = ((self.wpos + bits + 7) / 8) as usize;
        if needed > self.buf.len() {
            self.buf.resize(needed + 32, 0);
        }
    }

    // ── Write ──────────────────────────────────────────────────────────────────

    pub fn write_bit(&mut self, bit: i32) {
        self.ensure_space(1);
        let byte_idx = (self.wpos >> 3) as usize;
        let bit_idx = self.wpos & 7;
        if bit_idx == 0 {
            self.buf[byte_idx] = 0;
        }
        if bit != 0 {
            self.buf[byte_idx] |= 0x80u8 >> bit_idx;
        }
        self.wpos += 1;
    }

    pub fn write_bits(&mut self, data: &[u8], count: i32, right_aligned: bool) {
        if count <= 0 {
            return;
        }
        self.ensure_space(count);

        let mut offset = 0usize;
        let mut remaining = count;

        while remaining > 0 {
            let mut b = data[offset];
            if remaining < 8 && right_aligned {
                b <<= 8 - remaining;
            }

            let mod8 = (self.wpos & 7) as u32;
            if mod8 == 0 {
                self.buf[(self.wpos >> 3) as usize] = b;
            } else {
                self.buf[(self.wpos >> 3) as usize] |= b >> mod8;
                let bits_in_first = 8 - mod8 as i32;
                if bits_in_first < cmp::min(8, remaining) {
                    let idx = (self.wpos >> 3) as usize + 1;
                    self.buf[idx] = b << bits_in_first as u32;
                }
            }

            if remaining >= 8 {
                self.wpos += 8;
                remaining -= 8;
            } else {
                self.wpos += remaining;
                remaining = 0;
            }
            offset += 1;
        }
    }

    pub fn write_bool(&mut self, v: bool) {
        self.write_bit(if v { 1 } else { 0 });
    }

    pub fn write_uint8(&mut self, v: u8) {
        self.write_bits(&[v], 8, true);
    }

    pub fn write_uint16_le(&mut self, v: u16) {
        let d = v.to_le_bytes();
        self.write_bits(&d, 16, true);
    }

    pub fn write_uint32_le(&mut self, v: u32) {
        let d = v.to_le_bytes();
        self.write_bits(&d, 32, true);
    }

    pub fn write_int32_le(&mut self, v: i32) {
        let d = v.to_le_bytes();
        self.write_bits(&d, 32, true);
    }

    pub fn write_float_le(&mut self, v: f32) {
        let d = v.to_le_bytes();
        self.write_bits(&d, 32, true);
    }

    pub fn write_compressed_uint16(&mut self, v: u16) {
        let lo = (v & 0xFF) as u8;
        let hi = ((v >> 8) & 0xFF) as u8;
        if hi == 0 {
            self.write_bit(1);
            if (lo & 0xF0) == 0 {
                self.write_bit(1);
                self.write_bits(&[lo], 4, true);
            } else {
                self.write_bit(0);
                self.write_bits(&[lo], 8, true);
            }
        } else {
            self.write_bit(0);
            self.write_bits(&[lo], 8, true);
            self.write_bits(&[hi], 8, true);
        }
    }

    pub fn write_compressed_uint32(&mut self, v: u32) {
        let b = v.to_le_bytes();
        let mut cur = 3i32;
        while cur > 0 {
            if b[cur as usize] == 0 {
                self.write_bit(1);
            } else {
                self.write_bit(0);
                // write cur+1 bytes from byte 0 (right_aligned=false)
                self.write_bits(&b[..=(cur as usize)], (cur + 1) * 8, false);
                return;
            }
            cur -= 1;
        }
        // Last byte: nibble-level compression
        if (b[0] & 0xF0) == 0 {
            self.write_bit(1);
            self.write_bits(&b[..1], 4, true);
        } else {
            self.write_bit(0);
            self.write_bits(&b[..1], 8, true);
        }
    }

    pub fn write_aligned_bytes(&mut self, data: &[u8]) {
        if self.wpos & 7 != 0 {
            self.wpos = (self.wpos + 7) & !7;
        }
        self.ensure_space((data.len() * 8) as i32);
        let byte_idx = (self.wpos >> 3) as usize;
        let end = byte_idx + data.len();
        if end > self.buf.len() {
            self.buf.resize(end + 32, 0);
        }
        self.buf[byte_idx..end].copy_from_slice(data);
        self.wpos += (data.len() * 8) as i32;
    }

    // ── Read ───────────────────────────────────────────────────────────────────

    pub fn read_bit(&mut self) -> Result<i32, &'static str> {
        if self.rpos >= self.wpos {
            return Err("BitStream underflow");
        }
        let bit = ((self.buf[(self.rpos >> 3) as usize] >> (7 - (self.rpos & 7))) & 1) as i32;
        self.rpos += 1;
        Ok(bit)
    }

    pub fn read_bits(&mut self, out: &mut [u8], count: i32, right_aligned: bool) -> Result<(), &'static str> {
        if self.rpos + count > self.wpos {
            return Err("BitStream underflow");
        }
        let nbytes = ((count + 7) / 8) as usize;
        for b in out[..nbytes].iter_mut() {
            *b = 0;
        }

        let mut offset = 0usize;
        let mut remaining = count;

        while remaining > 0 {
            let mod8 = (self.rpos & 7) as u32;
            let mut b = self.buf[(self.rpos >> 3) as usize] << mod8;
            if mod8 > 0 && remaining > (8 - mod8 as i32) {
                b |= self.buf[(self.rpos >> 3) as usize + 1] >> (8 - mod8);
            }

            out[offset] = b;
            if remaining >= 8 {
                self.rpos += 8;
                remaining -= 8;
            } else {
                self.rpos += remaining;
                remaining = 0;
            }
            offset += 1;
        }

        // Right-align last partial byte
        if right_aligned && (count % 8 != 0) {
            let last = nbytes - 1;
            out[last] >>= (8 - (count % 8)) as u32;
        }

        Ok(())
    }

    pub fn read_bool(&mut self) -> Result<bool, &'static str> {
        Ok(self.read_bit()? != 0)
    }

    pub fn read_uint8(&mut self) -> Result<u8, &'static str> {
        let mut v = [0u8];
        self.read_bits(&mut v, 8, true)?;
        Ok(v[0])
    }

    pub fn read_uint16_le(&mut self) -> Result<u16, &'static str> {
        let mut d = [0u8; 2];
        self.read_bits(&mut d, 16, true)?;
        Ok(u16::from_le_bytes(d))
    }

    pub fn read_int16_le(&mut self) -> Result<i16, &'static str> {
        let mut d = [0u8; 2];
        self.read_bits(&mut d, 16, true)?;
        Ok(i16::from_le_bytes(d))
    }

    pub fn read_uint32_le(&mut self) -> Result<u32, &'static str> {
        let mut d = [0u8; 4];
        self.read_bits(&mut d, 32, true)?;
        Ok(u32::from_le_bytes(d))
    }

    pub fn read_int32_le(&mut self) -> Result<i32, &'static str> {
        let mut d = [0u8; 4];
        self.read_bits(&mut d, 32, true)?;
        Ok(i32::from_le_bytes(d))
    }

    pub fn read_float_le(&mut self) -> Result<f32, &'static str> {
        let mut d = [0u8; 4];
        self.read_bits(&mut d, 32, true)?;
        Ok(f32::from_le_bytes(d))
    }

    pub fn read_compressed_uint16(&mut self) -> Result<u16, &'static str> {
        let mut lo = 0u8;
        let mut hi = 0u8;
        if self.read_bit()? != 0 {
            // high byte is 0
            if self.read_bit()? != 0 {
                // high nibble of low byte also 0
                self.read_bits(std::slice::from_mut(&mut lo), 4, true)?;
            } else {
                self.read_bits(std::slice::from_mut(&mut lo), 8, true)?;
            }
        } else {
            self.read_bits(std::slice::from_mut(&mut lo), 8, true)?;
            self.read_bits(std::slice::from_mut(&mut hi), 8, true)?;
        }
        Ok((lo as u16) | ((hi as u16) << 8))
    }

    pub fn read_compressed_uint32(&mut self) -> Result<u32, &'static str> {
        let mut b = [0u8; 4];
        let mut cur = 3i32;
        while cur > 0 {
            if self.read_bit()? != 0 {
                b[cur as usize] = 0;
            } else {
                // this byte and below are non-trivial: read cur+1 bytes
                self.read_bits(&mut b[..(cur as usize + 1)], (cur + 1) * 8, false)?;
                return Ok(u32::from_le_bytes(b));
            }
            cur -= 1;
        }
        // Last byte: nibble-level
        let nibble_flag = self.read_bit()? != 0;
        if nibble_flag {
            self.read_bits(&mut b[..1], 4, true)?;
        } else {
            self.read_bits(&mut b[..1], 8, true)?;
        }
        Ok(u32::from_le_bytes(b))
    }

    pub fn read_aligned_bytes(&mut self, out: &mut [u8]) -> Result<(), &'static str> {
        if self.rpos & 7 != 0 {
            self.rpos = (self.rpos + 7) & !7;
        }
        let needed_bits = (out.len() * 8) as i32;
        if self.rpos + needed_bits > self.wpos {
            return Err("BitStream underflow");
        }
        let byte_idx = (self.rpos >> 3) as usize;
        out.copy_from_slice(&self.buf[byte_idx..byte_idx + out.len()]);
        self.rpos += needed_bits;
        Ok(())
    }

    pub fn skip_bits(&mut self, count: i32) {
        self.rpos += count;
    }

    pub fn read_compressed_bytes(&mut self, max_chars: i32) -> Result<Vec<u8>, &'static str> {
        let bit_len = self.read_compressed_uint16()? as i32;
        if bit_len == 0 {
            return Ok(Vec::new());
        }
        if self.bits_remaining() < bit_len {
            return Err("BitStream underflow in read_compressed_string");
        }

        let ht = huff_tree();
        let pool = &ht.pool;
        let root = ht.root;
        let mut current = root;

        let mut result = Vec::with_capacity(64.min((max_chars - 1) as usize));

        for _ in 0..bit_len {
            let bit = self.read_bit()?;
            current = if bit == 0 {
                pool[current as usize].left as i32
            } else {
                pool[current as usize].right as i32
            };
            if pool[current as usize].left == -1 {
                // leaf
                if (result.len() as i32) < max_chars - 1 {
                    result.push(pool[current as usize].value);
                }
                current = root;
            }
        }

        Ok(result)
    }

    pub fn read_compressed_string(&mut self, max_chars: i32) -> Result<String, &'static str> {
        self.read_compressed_bytes(max_chars)
            .map(|b| String::from_utf8_lossy(&b).into_owned())
    }

    // ── Accessors ──────────────────────────────────────────────────────────────

    pub fn data(&self) -> *const u8 {
        self.buf.as_ptr()
    }

    pub fn num_bytes(&self) -> i32 {
        (self.wpos + 7) / 8
    }

    pub fn num_bits(&self) -> i32 {
        self.wpos
    }

    pub fn bits_remaining(&self) -> i32 {
        self.wpos - self.rpos
    }

    pub fn bytes_remaining(&self) -> i32 {
        (self.wpos - self.rpos + 7) / 8
    }

    pub fn rpos_bits(&self) -> i32 {
        self.rpos
    }

    pub fn as_bytes(&self) -> &[u8] {
        &self.buf[..self.num_bytes() as usize]
    }
}


#[cfg(test)]
mod tests {
    use super::*;

    // ── Huffman wire fixtures ────────────────────────────────────────────────
    // Pre-generated from the verified implementation (RakNet-compatible output).
    // These are static byte arrays — any change to the Huffman tree or bit packing
    // will break these tests immediately, catching regressions before deployment.
    //
    // Generated with: cargo test _print_huff_fixtures -- --nocapture
    // (generator removed after capture)

    const H_EMPTY:     &[u8] = &[0xC0];
    const H_A:         &[u8] = &[0xD1, 0x80];
    const H_SPACE:     &[u8] = &[0xCF, 0x80];
    const H_NEWLINE:   &[u8] = &[0xD8, 0xD0];
    const H_HELLO:     &[u8] = &[0x85, 0xB0, 0x25, 0x28];
const H_HELLO_W:   &[u8] = &[0x8E, 0x9F, 0x02, 0x52, 0x8E, 0xAE, 0x46, 0x64, 0xE0];
    const H_TEST123:   &[u8] = &[0x8C, 0x6C, 0x6E, 0xE7, 0x55, 0x6D, 0x5E, 0x00];
    const H_AAABBBCCC: &[u8] = &[0x95, 0x15, 0x15, 0x15, 0x2A, 0x15, 0x0A, 0x84, 0xED, 0x9D, 0xB3, 0xB4];
    const H_ABCDEFGHIJ:&[u8] = &[0x8D, 0x98, 0xFA, 0x1C, 0x0E, 0x9B, 0x09, 0x57];
    const H_QUICK:     &[u8] = &[0xA2, 0x2A, 0x58, 0x1C, 0xCC, 0x5A, 0x50, 0xFF, 0x9F, 0x98, 0xA4, 0xB9, 0xD1, 0x53, 0xF5, 0x75, 0xE8, 0xA6, 0xC0];

    // ── Bool ─────────────────────────────────────────────────────────────────

    #[test] fn bool_true_roundtrip() {
        let mut bs = BitStream::new(); bs.write_bool(true);
        assert!(BitStream::from_bytes(bs.as_bytes()).read_bool().unwrap());
    }
    #[test] fn bool_false_roundtrip() {
        let mut bs = BitStream::new(); bs.write_bool(false);
        assert!(!BitStream::from_bytes(bs.as_bytes()).read_bool().unwrap());
    }
    #[test] fn eight_bools_occupy_one_byte() {
        let mut bs = BitStream::new();
        for _ in 0..8 { bs.write_bool(true); }
        assert_eq!(bs.num_bytes(), 1);
    }
    #[test] fn bool_cross_byte_boundary() {
        let mut bs = BitStream::new();
        for _ in 0..7 { bs.write_bool(false); }
        bs.write_bool(true); bs.write_bool(false);
        let raw = bs.as_bytes().to_vec();
        let mut bs2 = BitStream::from_bytes(&raw);
        for _ in 0..7 { assert!(!bs2.read_bool().unwrap()); }
        assert!(bs2.read_bool().unwrap());
        assert!(!bs2.read_bool().unwrap());
    }
    #[test] fn alternating_bools() {
        let mut bs = BitStream::new();
        for i in 0..8u8 { bs.write_bool(i % 2 == 0); }
        let raw = bs.as_bytes().to_vec();
        let mut bs2 = BitStream::from_bytes(&raw);
        for i in 0..8u8 { assert_eq!(bs2.read_bool().unwrap(), i % 2 == 0); }
    }

    // ── Integer roundtrips ───────────────────────────────────────────────────

    #[test] fn u8_roundtrip() {
        for v in [0u8, 1, 127, 128, 255] {
            let mut bs = BitStream::new(); bs.write_uint8(v);
            assert_eq!(BitStream::from_bytes(bs.as_bytes()).read_uint8().unwrap(), v);
        }
    }
    #[test] fn u16_roundtrip() {
        for v in [0u16, 1, 256, 0x1234, 0xFFFF] {
            let mut bs = BitStream::new(); bs.write_uint16_le(v);
            assert_eq!(BitStream::from_bytes(bs.as_bytes()).read_uint16_le().unwrap(), v);
        }
    }
    #[test] fn u32_roundtrip() {
        for v in [0u32, 1, 0xDEAD_BEEF, 0xFFFF_FFFF] {
            let mut bs = BitStream::new(); bs.write_uint32_le(v);
            assert_eq!(BitStream::from_bytes(bs.as_bytes()).read_uint32_le().unwrap(), v);
        }
    }
    #[test] fn i32_roundtrip() {
        for v in [0i32, 1, -1, i32::MIN, i32::MAX] {
            let mut bs = BitStream::new(); bs.write_int32_le(v);
            assert_eq!(BitStream::from_bytes(bs.as_bytes()).read_int32_le().unwrap(), v);
        }
    }
    #[test] fn float_roundtrip() {
        for v in [0.0f32, 1.0, -1.0, 3.14159, f32::MAX, f32::MIN_POSITIVE] {
            let mut bs = BitStream::new(); bs.write_float_le(v);
            assert_eq!(BitStream::from_bytes(bs.as_bytes()).read_float_le().unwrap(), v);
        }
    }
    #[test] fn float_nan_roundtrip() {
        let mut bs = BitStream::new(); bs.write_float_le(f32::NAN);
        assert!(BitStream::from_bytes(bs.as_bytes()).read_float_le().unwrap().is_nan());
    }

    // ── write_bits / read_bits ───────────────────────────────────────────────

    #[test] fn write_read_bits_4bit_right_aligned() {
        let mut bs = BitStream::new(); bs.write_bits(&[0b1010], 4, true);
        let raw = bs.as_bytes().to_vec();
        let mut bs2 = BitStream::from_bytes(&raw);
        let mut out = [0u8]; bs2.read_bits(&mut out, 4, true).unwrap();
        assert_eq!(out[0], 0b1010);
    }
    #[test] fn write_bits_8bit_same_as_write_u8() {
        let mut a = BitStream::new(); a.write_bits(&[0xAB], 8, true);
        let mut b = BitStream::new(); b.write_uint8(0xAB);
        assert_eq!(a.as_bytes(), b.as_bytes());
    }
    #[test] fn write_bits_3_and_5_cross_byte() {
        let mut bs = BitStream::new();
        bs.write_bits(&[0b111], 3, true);
        bs.write_bits(&[0b10101], 5, true);
        let raw = bs.as_bytes().to_vec();
        let mut bs2 = BitStream::from_bytes(&raw);
        let mut a = [0u8]; bs2.read_bits(&mut a, 3, true).unwrap();
        let mut b = [0u8]; bs2.read_bits(&mut b, 5, true).unwrap();
        assert_eq!((a[0], b[0]), (0b111, 0b10101));
    }
    #[test] fn write_bits_single() {
        let mut bs = BitStream::new(); bs.write_bits(&[1], 1, true);
        let raw = bs.as_bytes().to_vec();
        let mut out = [0u8];
        BitStream::from_bytes(&raw).read_bits(&mut out, 1, true).unwrap();
        assert_eq!(out[0], 1);
    }
    #[test] fn write_bits_32() {
        let b = 0xDEAD_BEEFu32.to_le_bytes();
        let mut bs = BitStream::new(); bs.write_bits(&b, 32, true);
        let raw = bs.as_bytes().to_vec();
        let mut out = [0u8; 4];
        BitStream::from_bytes(&raw).read_bits(&mut out, 32, true).unwrap();
        assert_eq!(u32::from_le_bytes(out), 0xDEAD_BEEF);
    }

    // ── Compressed uint16 ────────────────────────────────────────────────────

    #[test] fn compressed_u16_branch1_nibble_6bits() {
        for v in [0u16, 1, 15] {
            let mut bs = BitStream::new(); bs.write_compressed_uint16(v);
            assert_eq!(bs.num_bits(), 6, "v={v}");
            assert_eq!(BitStream::from_bytes(bs.as_bytes()).read_compressed_uint16().unwrap(), v);
        }
    }
    #[test] fn compressed_u16_branch2_byte_10bits() {
        for v in [16u16, 100, 255] {
            let mut bs = BitStream::new(); bs.write_compressed_uint16(v);
            assert_eq!(bs.num_bits(), 10, "v={v}");
            assert_eq!(BitStream::from_bytes(bs.as_bytes()).read_compressed_uint16().unwrap(), v);
        }
    }
    #[test] fn compressed_u16_branch3_full_17bits() {
        for v in [256u16, 1000, 0xFFFF] {
            let mut bs = BitStream::new(); bs.write_compressed_uint16(v);
            assert_eq!(bs.num_bits(), 17, "v={v}");
            assert_eq!(BitStream::from_bytes(bs.as_bytes()).read_compressed_uint16().unwrap(), v);
        }
    }
    #[test] fn compressed_u16_sizes_ascending() {
        let bits = |v: u16| { let mut bs = BitStream::new(); bs.write_compressed_uint16(v); bs.num_bits() };
        assert!(bits(0) < bits(16) && bits(16) < bits(256));
    }

    // ── Compressed uint32 ────────────────────────────────────────────────────

    #[test] fn compressed_u32_roundtrip() {
        for v in [0u32, 1, 15, 16, 255, 256, 0xFFFF, 0x1_0000, 0xFF_FFFF, 0xFFFF_FFFF] {
            let mut bs = BitStream::new(); bs.write_compressed_uint32(v);
            assert_eq!(BitStream::from_bytes(bs.as_bytes()).read_compressed_uint32().unwrap(), v, "v={v}");
        }
    }
    #[test] fn compressed_u32_nibble_smaller_than_byte() {
        let bits = |v: u32| { let mut bs = BitStream::new(); bs.write_compressed_uint32(v); bs.num_bits() };
        assert!(bits(1) < bits(16));
    }

    // ── Aligned bytes ────────────────────────────────────────────────────────

    #[test] fn aligned_bytes_after_bit_writes() {
        let mut bs = BitStream::new();
        bs.write_bool(true);
        bs.write_aligned_bytes(&[0xAB, 0xCD]);
        let raw = bs.as_bytes().to_vec();
        let mut bs2 = BitStream::from_bytes(&raw);
        assert!(bs2.read_bool().unwrap());
        let mut out = [0u8; 2]; bs2.read_aligned_bytes(&mut out).unwrap();
        assert_eq!(out, [0xAB, 0xCD]);
    }
    #[test] fn aligned_bytes_zero_length_no_write() {
        let mut bs = BitStream::new(); bs.write_aligned_bytes(&[]);
        assert_eq!(bs.num_bits(), 0);
    }
    #[test] fn aligned_bytes_100_roundtrip() {
        let data: Vec<u8> = (0..100).map(|i| i as u8).collect();
        let mut bs = BitStream::new(); bs.write_aligned_bytes(&data);
        let raw = bs.as_bytes().to_vec();
        let mut out = vec![0u8; 100];
        BitStream::from_bytes(&raw).read_aligned_bytes(&mut out).unwrap();
        assert_eq!(out, data);
    }

    // ── skip_bits ────────────────────────────────────────────────────────────

    #[test] fn skip_bits_then_read() {
        let mut bs = BitStream::new(); bs.write_uint8(0xAB); bs.write_uint8(0xCD);
        let raw = bs.as_bytes().to_vec();
        let mut bs2 = BitStream::from_bytes(&raw);
        bs2.skip_bits(8);
        assert_eq!(bs2.read_uint8().unwrap(), 0xCD);
    }
    #[test] fn skip_past_byte_boundary() {
        let mut bs = BitStream::new(); bs.write_uint8(0xFF); bs.write_uint8(0x01);
        let raw = bs.as_bytes().to_vec();
        let mut bs2 = BitStream::from_bytes(&raw);
        bs2.skip_bits(5);
        let mut out = [0u8]; bs2.read_bits(&mut out, 3, true).unwrap();
        assert_eq!(out[0], 0b111);  // top 3 bits of 0xFF
    }
    #[test] fn bits_remaining_decreases_on_skip() {
        let mut bs = BitStream::new(); bs.write_uint8(0xFF);
        let raw = bs.as_bytes().to_vec();
        let mut bs2 = BitStream::from_bytes(&raw);
        assert_eq!(bs2.bits_remaining(), 8);
        bs2.skip_bits(3);
        assert_eq!(bs2.bits_remaining(), 5);
    }

    // ── read_compressed_string (Huffman) ─────────────────────────────────────

    #[test] fn compressed_string_empty() {
        assert_eq!(BitStream::from_bytes(H_EMPTY).read_compressed_string(256).unwrap(), "");
    }
    #[test] fn compressed_string_a() {
        assert_eq!(BitStream::from_bytes(H_A).read_compressed_string(256).unwrap(), "a");
    }
    #[test] fn compressed_string_hello() {
        assert_eq!(BitStream::from_bytes(H_HELLO).read_compressed_string(256).unwrap(), "hello");
    }
    #[test] fn compressed_string_space() {
        assert_eq!(BitStream::from_bytes(H_SPACE).read_compressed_string(256).unwrap(), " ");
    }
    #[test] fn compressed_string_longer() {
        assert_eq!(BitStream::from_bytes(H_QUICK).read_compressed_string(256).unwrap(),
                   "The quick brown fox jumps");
    }
    #[test] fn compressed_string_newline() {
        assert_eq!(BitStream::from_bytes(H_NEWLINE).read_compressed_string(256).unwrap(), "\n");
    }
    #[test] fn compressed_string_max_chars_limit() {
        // max_chars=4 → at most 3 chars (max_chars - 1)
        assert_eq!(BitStream::from_bytes(H_HELLO).read_compressed_string(4).unwrap(), "hel");
    }
    #[test] fn compressed_string_underflow_no_crash() {
        let _ = BitStream::from_bytes(&[0x00]).read_compressed_string(256);
    }

    // ── Accessors ────────────────────────────────────────────────────────────

    #[test] fn num_bits_after_writes() {
        let mut bs = BitStream::new();
        bs.write_bool(true); bs.write_uint8(0xFF);
        assert_eq!(bs.num_bits(), 9);
    }
    #[test] fn bits_remaining_tracks_reads() {
        let mut bs = BitStream::new(); bs.write_uint8(0xFF);
        let raw = bs.as_bytes().to_vec();
        let mut bs2 = BitStream::from_bytes(&raw);
        assert_eq!(bs2.bits_remaining(), 8);
        bs2.read_bool().unwrap();
        assert_eq!(bs2.bits_remaining(), 7);
    }
    #[test] fn as_bytes_contains_written_data() {
        let mut bs = BitStream::new(); bs.write_uint8(0xAB); bs.write_uint8(0xCD);
        assert_eq!(bs.as_bytes(), &[0xAB, 0xCD]);
    }
    #[test] fn from_bytes_preserves_content() {
        let data = vec![0x12u8, 0x34, 0x56];
        let mut out = [0u8; 3];
        BitStream::from_bytes(&data).read_aligned_bytes(&mut out).unwrap();
        assert_eq!(out, [0x12, 0x34, 0x56]);
    }
    #[test] fn underflow_returns_err() {
        let mut bs = BitStream::new();
        assert!(bs.read_bool().is_err());
        assert!(bs.read_uint8().is_err());
    }

    // ── Additional integer edge values ────────────────────────────────────────

    #[test] fn u16_edge_values() {
        for v in [0u16, 1, 0x7FFF, 0x8000, 0xFFFF] {
            let mut bs = BitStream::new(); bs.write_uint16_le(v);
            assert_eq!(BitStream::from_bytes(bs.as_bytes()).read_uint16_le().unwrap(), v, "v={v}");
        }
    }
    #[test] fn u32_edge_values() {
        for v in [0u32, 1, 0x7FFF_FFFF, 0x8000_0000, 0xFFFF_FFFF] {
            let mut bs = BitStream::new(); bs.write_uint32_le(v);
            assert_eq!(BitStream::from_bytes(bs.as_bytes()).read_uint32_le().unwrap(), v, "v={v}");
        }
    }
    #[test] fn float_negative_zero_roundtrip() {
        let v = -0.0f32;
        let mut bs = BitStream::new(); bs.write_float_le(v);
        let r = BitStream::from_bytes(bs.as_bytes()).read_float_le().unwrap();
        assert_eq!(r.to_bits(), v.to_bits());
    }
    #[test] fn float_one_point_five_and_large() {
        for v in [1.5f32, -1.5, 1e30, -1e30] {
            let mut bs = BitStream::new(); bs.write_float_le(v);
            assert_eq!(BitStream::from_bytes(bs.as_bytes()).read_float_le().unwrap(), v, "v={v}");
        }
    }

    // ── write_bits mixed ─────────────────────────────────────────────────────

    #[test] fn write_bits_mixed_bool_u8_bits() {
        let mut bs = BitStream::new();
        bs.write_bool(true);
        bs.write_uint8(0xCC);
        bs.write_bits(&[0x03], 2, true);
        let raw = bs.as_bytes().to_vec();
        let mut bs2 = BitStream::from_bytes(&raw);
        assert!(bs2.read_bool().unwrap());
        assert_eq!(bs2.read_uint8().unwrap(), 0xCC);
        let mut out = [0u8]; bs2.read_bits(&mut out, 2, true).unwrap();
        assert_eq!(out[0], 0x03);
    }

    // ── Compressed uint16 — full value coverage ───────────────────────────────

    #[test] fn compressed_u16_all_key_values() {
        for v in [0u16, 1, 15, 16, 128, 255, 256, 0x1234, 0xFFFF] {
            let mut bs = BitStream::new(); bs.write_compressed_uint16(v);
            assert_eq!(BitStream::from_bytes(bs.as_bytes()).read_compressed_uint16().unwrap(), v, "v={v}");
        }
    }
    #[test] fn compressed_u16_sample_roundtrip() {
        let mut x = 0xABCDu32;
        for _ in 0..50 {
            x = x.wrapping_mul(1664525).wrapping_add(1013904223);
            let v = (x >> 16) as u16;
            let mut bs = BitStream::new(); bs.write_compressed_uint16(v);
            assert_eq!(BitStream::from_bytes(bs.as_bytes()).read_compressed_uint16().unwrap(), v, "v={v}");
        }
    }

    // ── Compressed uint32 — full branch coverage ──────────────────────────────

    #[test] fn compressed_u32_all_branches() {
        for v in [0u32, 1, 15, 16, 255, 256, 0xFFFF, 0x1_0000, 0xFF_FFFF, 0x100_0000, 0xFFFF_FFFF] {
            let mut bs = BitStream::new(); bs.write_compressed_uint32(v);
            assert_eq!(BitStream::from_bytes(bs.as_bytes()).read_compressed_uint32().unwrap(), v, "v={v}");
        }
    }
    #[test] fn compressed_u32_sample_roundtrip() {
        let mut x = 0xDEADBEEFu32;
        for _ in 0..50 {
            x = x.wrapping_mul(1664525).wrapping_add(1013904223);
            let mut bs = BitStream::new(); bs.write_compressed_uint32(x);
            assert_eq!(BitStream::from_bytes(bs.as_bytes()).read_compressed_uint32().unwrap(), x, "x={x}");
        }
    }

    // ── Aligned bytes — read after partial bit reads ──────────────────────────

    #[test] fn aligned_read_after_partial_bits() {
        let mut bs = BitStream::new();
        for _ in 0..5 { bs.write_bool(true); }
        bs.write_aligned_bytes(&[0x42]);
        let raw = bs.as_bytes().to_vec();
        let mut bs2 = BitStream::from_bytes(&raw);
        for _ in 0..5 { bs2.read_bool().unwrap(); }
        let mut out = [0u8; 1]; bs2.read_aligned_bytes(&mut out).unwrap();
        assert_eq!(out[0], 0x42);
    }

    // ── skip_bits ─────────────────────────────────────────────────────────────

    #[test] fn skip_bools_then_read_u8() {
        let mut bs = BitStream::new();
        bs.write_bool(false); bs.write_bool(true); bs.write_bool(false);
        bs.write_uint8(0xDE);
        let raw = bs.as_bytes().to_vec();
        let mut bs2 = BitStream::from_bytes(&raw);
        bs2.skip_bits(3);
        assert_eq!(bs2.read_uint8().unwrap(), 0xDE);
    }

    // ── Compressed string — ascii printable strings ───────────────────────────

    #[test] fn compressed_string_ascii_printable_roundtrips() {
        assert_eq!(BitStream::from_bytes(H_HELLO_W).read_compressed_string(256).unwrap(), "Hello World");
        assert_eq!(BitStream::from_bytes(H_TEST123).read_compressed_string(256).unwrap(), "test123");
        assert_eq!(BitStream::from_bytes(H_AAABBBCCC).read_compressed_string(256).unwrap(), "AAABBBCCC");
        assert_eq!(BitStream::from_bytes(H_ABCDEFGHIJ).read_compressed_string(256).unwrap(), "abcdefghij");
    }
}


