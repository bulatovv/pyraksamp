//! RakNet reliability layer — port of reliability.cpp.
//! Uses `bitstream` module internally (no C FFI needed within Rust).

use std::collections::{BTreeMap, HashMap};
use crate::bitstream::BitStream;

// ── Types ─────────────────────────────────────────────────────────────────────

#[repr(u8)]
#[derive(Copy, Clone, PartialEq, Eq)]
pub enum Reliability {
    Unreliable          = 6,
    UnreliableSequenced = 7,
    Reliable            = 8,
    ReliableOrdered     = 9,
    ReliableSequenced   = 10,
}

impl Reliability {
    fn from_u8(v: u8) -> Self {
        match v {
            7  => Self::UnreliableSequenced,
            8  => Self::Reliable,
            9  => Self::ReliableOrdered,
            10 => Self::ReliableSequenced,
            _  => Self::Unreliable,
        }
    }

    fn needs_ordering(self) -> bool {
        matches!(self,
            Self::ReliableOrdered | Self::ReliableSequenced | Self::UnreliableSequenced)
    }
}

pub struct InternalPacket {
    pub msg_num:          u16,
    pub reliability:      Reliability,
    pub ordering_channel: u8,
    pub ordering_index:   u16,
    pub data:             Vec<u8>,
}

#[allow(dead_code)]
struct SplitFragment {
    count:            u32,
    reliability:      Reliability,
    ordering_channel: u8,
    ordering_index:   u16,
    chunks:           BTreeMap<u32, Vec<u8>>,
}

pub struct SplitBuffer {
    pending: HashMap<u16, SplitFragment>,
}

impl SplitBuffer {
    pub fn new() -> Self {
        SplitBuffer { pending: HashMap::new() }
    }
}

pub struct ParseResult {
    pub is_ack:  bool,
    pub acked:   Vec<u16>,
    pub packets: Vec<InternalPacket>,
}

// ── Core functions ─────────────────────────────────────────────────────────────

pub fn make_packet(data: &[u8], msg_num: u16, rel: u8, oc: u8, oi: u16) -> Vec<u8> {
    let reliability = Reliability::from_u8(rel);
    let mut bs = BitStream::new();
    bs.write_bool(false);                               // isACK = false
    bs.write_uint16_le(msg_num);
    bs.write_bits(&[rel], 4, true);                     // 4-bit reliability field
    if reliability.needs_ordering() {
        bs.write_bits(&[oc], 5, true);
        bs.write_uint16_le(oi);
    }
    bs.write_bool(false);                               // isSplitPacket = false
    bs.write_compressed_uint16((data.len() * 8) as u16);
    bs.write_aligned_bytes(data);
    bs.as_bytes().to_vec()
}

pub fn make_ack(nums: &[u16]) -> Vec<u8> {
    let mut bs = BitStream::new();
    bs.write_bool(true);                                // isACK = true
    bs.write_compressed_uint16(nums.len() as u16);
    for &n in nums {
        bs.write_bool(true);                            // isSingle = true
        bs.write_uint16_le(n);
    }
    bs.as_bytes().to_vec()
}

pub fn parse(data: &[u8], split_buf: &mut SplitBuffer) -> Option<ParseResult> {
    if data.is_empty() {
        return None;
    }

    let mut bs = BitStream::from_bytes(data);
    let mut result = ParseResult { is_ack: false, acked: Vec::new(), packets: Vec::new() };

    result.is_ack = bs.read_bool().ok()?;

    if result.is_ack {
        if let Ok(count) = bs.read_compressed_uint16() {
            for _ in 0..count {
                if bs.bits_remaining() < 17 { break; }
                let is_single = bs.read_bool().unwrap_or(false);
                let min_idx = match bs.read_uint16_le() {
                    Ok(v) => v, Err(_) => break,
                };
                if is_single {
                    result.acked.push(min_idx);
                } else {
                    let max_idx = match bs.read_uint16_le() {
                        Ok(v) => v, Err(_) => break,
                    };
                    for j in min_idx..=max_idx {
                        result.acked.push(j);
                    }
                }
            }
        }
        return Some(result);
    }

    // Data packet(s): multiple may be coalesced in one datagram
    while bs.bits_remaining() >= 17 {
        // Read msg_num + reliability
        let msg_num = match bs.read_uint16_le() {
            Ok(v) => v, Err(_) => break,
        };
        let mut rel_byte = [0u8];
        if bs.read_bits(&mut rel_byte, 4, true).is_err() { break; }
        let reliability = Reliability::from_u8(rel_byte[0]);

        let mut ordering_channel = 0u8;
        let mut ordering_index   = 0u16;
        if reliability.needs_ordering() {
            let mut oc = [0u8];
            if bs.read_bits(&mut oc, 5, true).is_err() { break; }
            ordering_channel = oc[0];
            ordering_index = match bs.read_uint16_le() {
                Ok(v) => v, Err(_) => break,
            };
        }

        let is_split = match bs.read_bool() {
            Ok(v) => v, Err(_) => break,
        };

        if is_split {
            let split_id = match bs.read_uint16_le() {
                Ok(v) => v, Err(_) => break,
            };
            let frag_index = match bs.read_compressed_uint32() {
                Ok(v) => v, Err(_) => break,
            };
            let frag_count = match bs.read_compressed_uint32() {
                Ok(v) => v, Err(_) => break,
            };
            let data_bits = match bs.read_compressed_uint16() {
                Ok(v) => v, Err(_) => break,
            };
            let data_bytes = ((data_bits as usize) + 7) / 8;
            let mut chunk = vec![0u8; data_bytes];
            if data_bytes > 0 && bs.read_aligned_bytes(&mut chunk).is_err() { break; }

            // Emit an ACK-only packet so the caller ACKs this fragment's msg_num
            result.packets.push(InternalPacket {
                msg_num, reliability, ordering_channel, ordering_index,
                data: Vec::new(),
            });

            // Buffer the fragment
            {
                let frag = split_buf.pending.entry(split_id).or_insert_with(|| SplitFragment {
                    count: frag_count, reliability, ordering_channel, ordering_index,
                    chunks: BTreeMap::new(),
                });
                frag.chunks.insert(frag_index, chunk);
            }

            // Reassemble when all fragments have arrived
            let done = split_buf.pending.get(&split_id)
                .map(|f| f.chunks.len() as u32 == f.count)
                .unwrap_or(false);
            if done {
                let frag = split_buf.pending.remove(&split_id).unwrap();
                let mut assembled = Vec::new();
                for (_, c) in frag.chunks {
                    assembled.extend_from_slice(&c);
                }
                result.packets.push(InternalPacket {
                    msg_num:          0,
                    reliability:      Reliability::Unreliable,
                    ordering_channel: frag.ordering_channel,
                    ordering_index:   frag.ordering_index,
                    data:             assembled,
                });
            }
            continue;
        }

        // Non-split data packet
        let data_bits = match bs.read_compressed_uint16() {
            Ok(v) => v, Err(_) => break,
        };
        let data_bytes = ((data_bits as usize) + 7) / 8;
        let mut pkt_data = vec![0u8; data_bytes];
        if bs.read_aligned_bytes(&mut pkt_data).is_err() { break; }

        result.packets.push(InternalPacket {
            msg_num, reliability, ordering_channel, ordering_index, data: pkt_data,
        });
    }

    Some(result)
}

// ── C FFI exports ─────────────────────────────────────────────────────────────

// --- make_packet / make_ack ---
// Both return a heap-allocated Vec<u8> that the caller must free with samp_bytes_free.

#[no_mangle]
pub unsafe extern "C" fn samp_make_packet(
    data: *const u8, len: usize,
    msg_num: u16, rel: u8, oc: u8, oi: u16,
) -> *mut Vec<u8> {
    let slice = std::slice::from_raw_parts(data, len);
    Box::into_raw(Box::new(make_packet(slice, msg_num, rel, oc, oi)))
}

#[no_mangle]
pub unsafe extern "C" fn samp_make_ack(
    nums: *const u16, count: usize,
) -> *mut Vec<u8> {
    let slice = std::slice::from_raw_parts(nums, count);
    Box::into_raw(Box::new(make_ack(slice)))
}

// Byte buffer accessors (for results of make_packet / make_ack).
#[no_mangle]
pub unsafe extern "C" fn samp_bytes_data(p: *const Vec<u8>) -> *const u8 {
    (*p).as_ptr()
}

#[no_mangle]
pub unsafe extern "C" fn samp_bytes_len(p: *const Vec<u8>) -> usize {
    (*p).len()
}

#[no_mangle]
pub unsafe extern "C" fn samp_bytes_free(p: *mut Vec<u8>) {
    if !p.is_null() {
        drop(Box::from_raw(p));
    }
}

// --- SplitBuffer ---

#[no_mangle]
pub unsafe extern "C" fn samp_split_buf_new() -> *mut SplitBuffer {
    Box::into_raw(Box::new(SplitBuffer::new()))
}

#[no_mangle]
pub unsafe extern "C" fn samp_split_buf_free(p: *mut SplitBuffer) {
    if !p.is_null() {
        drop(Box::from_raw(p));
    }
}

// --- parse ---
// Returns null if datagram is malformed; otherwise an opaque ParseResult handle
// that the caller must free with samp_parse_result_free.

#[no_mangle]
pub unsafe extern "C" fn samp_parse(
    data: *const u8, len: usize,
    split_buf: *mut SplitBuffer,
) -> *mut ParseResult {
    let slice = std::slice::from_raw_parts(data, len);
    match parse(slice, &mut *split_buf) {
        Some(r) => Box::into_raw(Box::new(r)),
        None    => std::ptr::null_mut(),
    }
}

#[no_mangle]
pub unsafe extern "C" fn samp_parse_result_free(p: *mut ParseResult) {
    if !p.is_null() {
        drop(Box::from_raw(p));
    }
}

#[no_mangle]
pub unsafe extern "C" fn samp_parse_result_is_ack(p: *const ParseResult) -> bool {
    (*p).is_ack
}

#[no_mangle]
pub unsafe extern "C" fn samp_parse_result_acked_len(p: *const ParseResult) -> usize {
    (*p).acked.len()
}

#[no_mangle]
pub unsafe extern "C" fn samp_parse_result_acked_at(p: *const ParseResult, i: usize) -> u16 {
    (&(*p).acked)[i]
}

#[no_mangle]
pub unsafe extern "C" fn samp_parse_result_packets_len(p: *const ParseResult) -> usize {
    (*p).packets.len()
}

#[no_mangle]
pub unsafe extern "C" fn samp_parse_result_packet_msg_num(
    p: *const ParseResult, i: usize) -> u16 {
    (&(*p).packets)[i].msg_num
}

#[no_mangle]
pub unsafe extern "C" fn samp_parse_result_packet_rel(
    p: *const ParseResult, i: usize) -> u8 {
    (&(*p).packets)[i].reliability as u8
}

#[no_mangle]
pub unsafe extern "C" fn samp_parse_result_packet_oc(
    p: *const ParseResult, i: usize) -> u8 {
    (&(*p).packets)[i].ordering_channel
}

#[no_mangle]
pub unsafe extern "C" fn samp_parse_result_packet_oi(
    p: *const ParseResult, i: usize) -> u16 {
    (&(*p).packets)[i].ordering_index
}

#[no_mangle]
pub unsafe extern "C" fn samp_parse_result_packet_data(
    p: *const ParseResult, i: usize, len_out: *mut usize,
) -> *const u8 {
    let d = &(&(*p).packets)[i].data;
    *len_out = d.len();
    d.as_ptr()
}
