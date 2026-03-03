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
struct HuffNode {
    left: i16,
    right: i16,
    value: u8,
    weight: u32,
}

impl Default for HuffNode {
    fn default() -> Self {
        HuffNode { left: 0, right: 0, value: 0, weight: 0 }
    }
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

// Thread-safe singleton using std::sync::OnceLock
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

impl BitStream {
    pub fn new() -> Self {
        let mut buf = Vec::with_capacity(64);
        buf.resize(8, 0u8); // initial capacity
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
                b = b << (8 - remaining);
            }

            let mod8 = (self.wpos & 7) as u32;
            if mod8 == 0 {
                self.buf[(self.wpos >> 3) as usize] = b;
            } else {
                self.buf[(self.wpos >> 3) as usize] |= b >> mod8;
                let bits_in_first = 8 - mod8 as i32;
                if bits_in_first < cmp::min(8, remaining) {
                    let idx = (self.wpos >> 3) as usize + 1;
                    self.buf[idx] = (b << bits_in_first as u32) as u8;
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

    pub fn read_compressed_string(&mut self, max_chars: i32) -> Result<String, &'static str> {
        let bit_len = self.read_compressed_uint16()? as i32;
        if bit_len == 0 {
            return Ok(String::new());
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

        Ok(String::from_utf8_lossy(&result).into_owned())
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

// ── C FFI exports ─────────────────────────────────────────────────────────────

#[no_mangle]
pub unsafe extern "C" fn bs_new() -> *mut BitStream {
    Box::into_raw(Box::new(BitStream::new()))
}

#[no_mangle]
pub unsafe extern "C" fn bs_new_from_bytes(data: *const u8, len: i32) -> *mut BitStream {
    let slice = std::slice::from_raw_parts(data, len as usize);
    Box::into_raw(Box::new(BitStream::from_bytes(slice)))
}

#[no_mangle]
pub unsafe extern "C" fn bs_free(p: *mut BitStream) {
    if !p.is_null() {
        drop(Box::from_raw(p));
    }
}

#[no_mangle]
pub unsafe extern "C" fn bs_write_bit(p: *mut BitStream, bit: i32) {
    (*p).write_bit(bit);
}

#[no_mangle]
pub unsafe extern "C" fn bs_write_bits(p: *mut BitStream, data: *const u8, count: i32, right_aligned: bool) {
    let slice = std::slice::from_raw_parts(data, ((count + 7) / 8) as usize);
    (*p).write_bits(slice, count, right_aligned);
}

#[no_mangle]
pub unsafe extern "C" fn bs_write_bool(p: *mut BitStream, v: bool) {
    (*p).write_bool(v);
}

#[no_mangle]
pub unsafe extern "C" fn bs_write_u8(p: *mut BitStream, v: u8) {
    (*p).write_uint8(v);
}

#[no_mangle]
pub unsafe extern "C" fn bs_write_u16(p: *mut BitStream, v: u16) {
    (*p).write_uint16_le(v);
}

#[no_mangle]
pub unsafe extern "C" fn bs_write_u32(p: *mut BitStream, v: u32) {
    (*p).write_uint32_le(v);
}

#[no_mangle]
pub unsafe extern "C" fn bs_write_i32(p: *mut BitStream, v: i32) {
    (*p).write_int32_le(v);
}

#[no_mangle]
pub unsafe extern "C" fn bs_write_float(p: *mut BitStream, v: f32) {
    (*p).write_float_le(v);
}

#[no_mangle]
pub unsafe extern "C" fn bs_write_compressed_u16(p: *mut BitStream, v: u16) {
    (*p).write_compressed_uint16(v);
}

#[no_mangle]
pub unsafe extern "C" fn bs_write_compressed_u32(p: *mut BitStream, v: u32) {
    (*p).write_compressed_uint32(v);
}

#[no_mangle]
pub unsafe extern "C" fn bs_write_aligned_bytes(p: *mut BitStream, data: *const u8, len: i32) {
    let slice = std::slice::from_raw_parts(data, len as usize);
    (*p).write_aligned_bytes(slice);
}

/// Returns 0 on success, -1 on underflow.
#[no_mangle]
pub unsafe extern "C" fn bs_read_bit(p: *mut BitStream) -> i32 {
    match (*p).read_bit() {
        Ok(v) => v,
        Err(_) => -1,
    }
}

/// Reads `count` bits into caller-provided buffer of size (count+7)/8.
/// Returns 0 on success, 1 on underflow.
#[no_mangle]
pub unsafe extern "C" fn bs_read_bits(p: *mut BitStream, out: *mut u8, count: i32, right_aligned: bool) -> i32 {
    let nbytes = ((count + 7) / 8) as usize;
    let slice = std::slice::from_raw_parts_mut(out, nbytes);
    match (*p).read_bits(slice, count, right_aligned) {
        Ok(()) => 0,
        Err(_) => 1,
    }
}

/// Returns 0=false, 1=true, -1=underflow.
#[no_mangle]
pub unsafe extern "C" fn bs_read_bool(p: *mut BitStream) -> i32 {
    match (*p).read_bool() {
        Ok(v) => v as i32,
        Err(_) => -1,
    }
}

/// Returns value on success, 0xFF on underflow (caller must check via bs_read_bits for errors).
#[no_mangle]
pub unsafe extern "C" fn bs_read_u8(p: *mut BitStream, out: *mut u8) -> i32 {
    match (*p).read_uint8() {
        Ok(v) => { *out = v; 0 }
        Err(_) => 1,
    }
}

#[no_mangle]
pub unsafe extern "C" fn bs_read_u16(p: *mut BitStream, out: *mut u16) -> i32 {
    match (*p).read_uint16_le() {
        Ok(v) => { *out = v; 0 }
        Err(_) => 1,
    }
}

#[no_mangle]
pub unsafe extern "C" fn bs_read_u32(p: *mut BitStream, out: *mut u32) -> i32 {
    match (*p).read_uint32_le() {
        Ok(v) => { *out = v; 0 }
        Err(_) => 1,
    }
}

#[no_mangle]
pub unsafe extern "C" fn bs_read_i32(p: *mut BitStream, out: *mut i32) -> i32 {
    match (*p).read_int32_le() {
        Ok(v) => { *out = v; 0 }
        Err(_) => 1,
    }
}

#[no_mangle]
pub unsafe extern "C" fn bs_read_float(p: *mut BitStream, out: *mut f32) -> i32 {
    match (*p).read_float_le() {
        Ok(v) => { *out = v; 0 }
        Err(_) => 1,
    }
}

#[no_mangle]
pub unsafe extern "C" fn bs_read_compressed_u16(p: *mut BitStream, out: *mut u16) -> i32 {
    match (*p).read_compressed_uint16() {
        Ok(v) => { *out = v; 0 }
        Err(_) => 1,
    }
}

#[no_mangle]
pub unsafe extern "C" fn bs_read_compressed_u32(p: *mut BitStream, out: *mut u32) -> i32 {
    match (*p).read_compressed_uint32() {
        Ok(v) => { *out = v; 0 }
        Err(_) => 1,
    }
}

/// Returns 0 on success, 1 on underflow.
#[no_mangle]
pub unsafe extern "C" fn bs_read_aligned_bytes(p: *mut BitStream, out: *mut u8, len: i32) -> i32 {
    let slice = std::slice::from_raw_parts_mut(out, len as usize);
    match (*p).read_aligned_bytes(slice) {
        Ok(()) => 0,
        Err(_) => 1,
    }
}

#[no_mangle]
pub unsafe extern "C" fn bs_skip_bits(p: *mut BitStream, count: i32) {
    (*p).skip_bits(count);
}

/// Reads a Huffman-compressed string into `out` (caller provides max_chars bytes).
/// Returns number of chars written (< max_chars), or -1 on error.
#[no_mangle]
pub unsafe extern "C" fn bs_read_compressed_string(p: *mut BitStream, out: *mut u8, max_chars: i32) -> i32 {
    match (*p).read_compressed_string(max_chars) {
        Ok(s) => {
            let bytes = s.as_bytes();
            let n = bytes.len().min((max_chars - 1) as usize);
            std::ptr::copy_nonoverlapping(bytes.as_ptr(), out, n);
            *out.add(n) = 0;
            n as i32
        }
        Err(_) => -1,
    }
}

#[no_mangle]
pub unsafe extern "C" fn bs_data(p: *const BitStream) -> *const u8 {
    (*p).buf.as_ptr()
}

#[no_mangle]
pub unsafe extern "C" fn bs_num_bytes(p: *const BitStream) -> i32 {
    (*p).num_bytes()
}

#[no_mangle]
pub unsafe extern "C" fn bs_num_bits(p: *const BitStream) -> i32 {
    (*p).num_bits()
}

#[no_mangle]
pub unsafe extern "C" fn bs_bits_remaining(p: *const BitStream) -> i32 {
    (*p).bits_remaining()
}

#[no_mangle]
pub unsafe extern "C" fn bs_bytes_remaining(p: *const BitStream) -> i32 {
    (*p).bytes_remaining()
}

#[no_mangle]
pub unsafe extern "C" fn bs_rpos_bits(p: *const BitStream) -> i32 {
    (*p).rpos_bits()
}
