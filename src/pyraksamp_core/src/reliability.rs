//! RakNet reliability layer — port of reliability.cpp.
//! Uses `bitstream` module internally (no C FFI needed within Rust).

use crate::bitstream::BitStream;
use std::collections::{BTreeMap, HashMap};

// ── Types ─────────────────────────────────────────────────────────────────────

#[repr(u8)]
#[derive(Copy, Clone, PartialEq, Eq)]
pub enum Reliability {
    Unreliable = 6,
    UnreliableSequenced = 7,
    Reliable = 8,
    ReliableOrdered = 9,
    ReliableSequenced = 10,
}

impl Reliability {
    fn from_u8(v: u8) -> Self {
        match v {
            7 => Self::UnreliableSequenced,
            8 => Self::Reliable,
            9 => Self::ReliableOrdered,
            10 => Self::ReliableSequenced,
            _ => Self::Unreliable,
        }
    }

    fn needs_ordering(self) -> bool {
        matches!(
            self,
            Self::ReliableOrdered | Self::ReliableSequenced | Self::UnreliableSequenced
        )
    }
}

pub struct InternalPacket {
    pub msg_num: u16,
    pub reliability: Reliability,
    pub ordering_channel: u8,
    pub ordering_index: u16,
    pub data: Vec<u8>,
}

#[allow(dead_code)]
struct SplitFragment {
    count: u32,
    reliability: Reliability,
    ordering_channel: u8,
    ordering_index: u16,
    chunks: BTreeMap<u32, Vec<u8>>,
}

pub struct SplitBuffer {
    pending: HashMap<u16, SplitFragment>,
    // Mirrors ReliabilityLayer's hasReceivedPacketQueue: tracks the base
    // message number and a bitmask of received offsets so that retransmitted
    // reliable packets are ACKed but not re-delivered to the application.
    dedup_base: u16,
    dedup_bits: u64, // window of 64 msg_nums ahead of dedup_base
}

impl Default for SplitBuffer {
    fn default() -> Self {
        Self::new()
    }
}

impl SplitBuffer {
    pub fn new() -> Self {
        SplitBuffer {
            pending: HashMap::new(),
            dedup_base: 0,
            dedup_bits: 0,
        }
    }
}

pub struct ParseResult {
    pub is_ack: bool,
    pub acked: Vec<u16>,
    pub packets: Vec<InternalPacket>,
}

// ── Core functions ─────────────────────────────────────────────────────────────

pub fn make_packet(data: &[u8], msg_num: u16, rel: u8, oc: u8, oi: u16) -> Vec<u8> {
    let reliability = Reliability::from_u8(rel);
    let mut bs = BitStream::new();
    bs.write_bool(false); // isACK = false
    bs.write_uint16_le(msg_num);
    bs.write_bits(&[rel], 4, true); // 4-bit reliability field
    if reliability.needs_ordering() {
        bs.write_bits(&[oc], 5, true);
        bs.write_uint16_le(oi);
    }
    bs.write_bool(false); // isSplitPacket = false
    bs.write_compressed_uint16((data.len() * 8) as u16);
    bs.write_aligned_bytes(data);
    bs.as_bytes().to_vec()
}

pub fn make_ack(nums: &[u16]) -> Vec<u8> {
    let mut bs = BitStream::new();
    bs.write_bool(true); // isACK = true
    bs.write_compressed_uint16(nums.len() as u16);
    for &n in nums {
        bs.write_bool(true); // isSingle = true
        bs.write_uint16_le(n);
    }
    bs.as_bytes().to_vec()
}

pub fn parse(data: &[u8], split_buf: &mut SplitBuffer) -> Option<ParseResult> {
    if data.is_empty() {
        return None;
    }

    let mut bs = BitStream::from_bytes(data);
    let mut result = ParseResult {
        is_ack: false,
        acked: Vec::new(),
        packets: Vec::new(),
    };

    result.is_ack = bs.read_bool().ok()?;

    if result.is_ack {
        if let Ok(count) = bs.read_compressed_uint16() {
            for _ in 0..count {
                if bs.bits_remaining() < 17 {
                    break;
                }
                let is_single = bs.read_bool().unwrap_or(false);
                let min_idx = match bs.read_uint16_le() {
                    Ok(v) => v,
                    Err(_) => break,
                };
                if is_single {
                    result.acked.push(min_idx);
                } else {
                    let max_idx = match bs.read_uint16_le() {
                        Ok(v) => v,
                        Err(_) => break,
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
        let msg_num = match bs.read_uint16_le() {
            Ok(v) => v,
            Err(_) => break,
        };
        let mut rel_byte = [0u8];
        if bs.read_bits(&mut rel_byte, 4, true).is_err() {
            break;
        }
        let reliability = Reliability::from_u8(rel_byte[0]);

        let mut ordering_channel = 0u8;
        let mut ordering_index = 0u16;
        if reliability.needs_ordering() {
            let mut oc = [0u8];
            if bs.read_bits(&mut oc, 5, true).is_err() {
                break;
            }
            ordering_channel = oc[0];
            ordering_index = match bs.read_uint16_le() {
                Ok(v) => v,
                Err(_) => break,
            };
        }

        let is_split = match bs.read_bool() {
            Ok(v) => v,
            Err(_) => break,
        };

        if is_split {
            let split_id = match bs.read_uint16_le() {
                Ok(v) => v,
                Err(_) => break,
            };
            let frag_index = match bs.read_compressed_uint32() {
                Ok(v) => v,
                Err(_) => break,
            };
            let frag_count = match bs.read_compressed_uint32() {
                Ok(v) => v,
                Err(_) => break,
            };
            let data_bits = match bs.read_compressed_uint16() {
                Ok(v) => v,
                Err(_) => break,
            };
            let data_bytes = (data_bits as usize).div_ceil(8);
            let mut chunk = vec![0u8; data_bytes];
            if data_bytes > 0 && bs.read_aligned_bytes(&mut chunk).is_err() {
                break;
            }

            // Emit an ACK-only packet so the caller ACKs this fragment's msg_num
            result.packets.push(InternalPacket {
                msg_num,
                reliability,
                ordering_channel,
                ordering_index,
                data: Vec::new(),
            });

            // Track reliable split-fragment msg_nums in the dedup window so that
            // dedup_base advances past them. Without this, any gap left by split
            // fragments (whose msg_nums are never seen in the non-split path) keeps
            // dedup_base stuck, and once reliable msg_nums exceed base+32767 the
            // "hole > u16::MAX/2" guard falsely drops legitimate new packets.
            let is_reliable_split = matches!(
                reliability,
                Reliability::Reliable
                    | Reliability::ReliableOrdered
                    | Reliability::ReliableSequenced
            );
            if is_reliable_split {
                let hole = msg_num.wrapping_sub(split_buf.dedup_base);
                if hole <= u16::MAX / 2 {
                    let hole = hole as usize;
                    if hole < 64 {
                        split_buf.dedup_bits |= 1u64 << hole;
                    }
                    while split_buf.dedup_bits & 1 != 0 {
                        split_buf.dedup_bits >>= 1;
                        split_buf.dedup_base = split_buf.dedup_base.wrapping_add(1);
                    }
                }
            }

            {
                let frag = split_buf
                    .pending
                    .entry(split_id)
                    .or_insert_with(|| SplitFragment {
                        count: frag_count,
                        reliability,
                        ordering_channel,
                        ordering_index,
                        chunks: BTreeMap::new(),
                    });
                frag.chunks.insert(frag_index, chunk);
            }

            // Reassemble when all fragments have arrived
            let done = split_buf
                .pending
                .get(&split_id)
                .map(|f| f.chunks.len() as u32 == f.count)
                .unwrap_or(false);
            if done {
                let frag = split_buf.pending.remove(&split_id).unwrap();
                let mut assembled = Vec::new();
                for (_, c) in frag.chunks {
                    assembled.extend_from_slice(&c);
                }
                result.packets.push(InternalPacket {
                    msg_num: 0,
                    reliability: Reliability::Unreliable,
                    ordering_channel: frag.ordering_channel,
                    ordering_index: frag.ordering_index,
                    data: assembled,
                });
            }
            continue;
        }

        // Non-split data packet
        let data_bits = match bs.read_compressed_uint16() {
            Ok(v) => v,
            Err(_) => break,
        };
        let data_bytes = (data_bits as usize).div_ceil(8);
        let mut pkt_data = vec![0u8; data_bytes];
        if bs.read_aligned_bytes(&mut pkt_data).is_err() {
            break;
        }

        // Dedup for reliable types: mirrors ReliabilityLayer hasReceivedPacketQueue.
        // hole_count wraps intentionally (u16 subtraction); values > u16::MAX/2 are
        // underflows, meaning this msg_num is already past our base = duplicate.
        let is_reliable = matches!(
            reliability,
            Reliability::Reliable | Reliability::ReliableOrdered | Reliability::ReliableSequenced
        );
        if is_reliable {
            let hole = msg_num.wrapping_sub(split_buf.dedup_base);
            if hole > u16::MAX / 2 {
                // Already past base — retransmit we already processed; ACK but skip.
                result.packets.push(InternalPacket {
                    msg_num,
                    reliability,
                    ordering_channel,
                    ordering_index,
                    data: Vec::new(), // empty = ACK-only, caller skips process_packet_data
                });
                continue;
            }
            let hole = hole as usize;
            if hole < 64 {
                let bit = 1u64 << hole;
                if split_buf.dedup_bits & bit != 0 {
                    // Already received this exact msg_num — duplicate.
                    result.packets.push(InternalPacket {
                        msg_num,
                        reliability,
                        ordering_channel,
                        ordering_index,
                        data: Vec::new(),
                    });
                    continue;
                }
                split_buf.dedup_bits |= bit;
            }
            // Advance base past all contiguous received packets.
            while split_buf.dedup_bits & 1 != 0 {
                split_buf.dedup_bits >>= 1;
                split_buf.dedup_base = split_buf.dedup_base.wrapping_add(1);
            }
        }

        result.packets.push(InternalPacket {
            msg_num,
            reliability,
            ordering_channel,
            ordering_index,
            data: pkt_data,
        });
    }

    Some(result)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::bitstream::BitStream;

    #[allow(clippy::too_many_arguments)]
    fn make_split_frag(
        msg_num: u16,
        rel: u8,
        oc: u8,
        oi: u16,
        split_id: u16,
        frag_idx: u32,
        frag_count: u32,
        data: &[u8],
    ) -> Vec<u8> {
        let reliability = Reliability::from_u8(rel);
        let mut bs = BitStream::new();
        bs.write_bool(false); // isACK = false
        bs.write_uint16_le(msg_num);
        bs.write_bits(&[rel], 4, true);
        if reliability.needs_ordering() {
            bs.write_bits(&[oc], 5, true);
            bs.write_uint16_le(oi);
        }
        bs.write_bool(true); // isSplit = true
        bs.write_uint16_le(split_id);
        bs.write_compressed_uint32(frag_idx);
        bs.write_compressed_uint32(frag_count);
        bs.write_compressed_uint16((data.len() * 8) as u16);
        bs.write_aligned_bytes(data);
        bs.as_bytes().to_vec()
    }

    // ── make_packet / parse roundtrips ────────────────────────────────────────

    #[test]
    fn roundtrip_unreliable() {
        let data = b"hello world";
        let pkt = make_packet(data, 42, 6, 0, 0);
        let mut sb = SplitBuffer::new();
        let r = parse(&pkt, &mut sb).unwrap();
        assert!(!r.is_ack);
        assert_eq!(r.packets.len(), 1);
        let p = &r.packets[0];
        assert_eq!(p.msg_num, 42);
        assert_eq!(p.reliability as u8, 6);
        assert_eq!(p.data, data);
    }

    #[test]
    fn roundtrip_reliable_ordered() {
        let data = b"test";
        let pkt = make_packet(data, 100, 9, 3, 7);
        let mut sb = SplitBuffer::new();
        let r = parse(&pkt, &mut sb).unwrap();
        let p = &r.packets[0];
        assert_eq!(p.msg_num, 100);
        assert_eq!(p.reliability as u8, 9);
        assert_eq!(p.ordering_channel, 3);
        assert_eq!(p.ordering_index, 7);
        assert_eq!(p.data, data);
    }

    #[test]
    fn ordering_fields_reliable_sequenced() {
        let pkt = make_packet(b"x", 7, 10, 4, 300);
        let mut sb = SplitBuffer::new();
        let r = parse(&pkt, &mut sb).unwrap();
        let p = &r.packets[0];
        assert_eq!(p.reliability as u8, 10);
        assert_eq!(p.ordering_channel, 4);
        assert_eq!(p.ordering_index, 300);
    }

    // ── ACK ───────────────────────────────────────────────────────────────────

    #[test]
    fn ack_roundtrip() {
        let nums = [1u16, 5, 10, 1000, 65535];
        let pkt = make_ack(&nums);
        let mut sb = SplitBuffer::new();
        let r = parse(&pkt, &mut sb).unwrap();
        assert!(r.is_ack);
        let mut got = r.acked.clone();
        got.sort_unstable();
        assert_eq!(got, &[1u16, 5, 10, 1000, 65535]);
    }

    #[test]
    fn ack_empty() {
        let pkt = make_ack(&[]);
        let mut sb = SplitBuffer::new();
        let r = parse(&pkt, &mut sb).unwrap();
        assert!(r.is_ack);
        assert!(r.acked.is_empty());
    }

    // ── Edge cases ────────────────────────────────────────────────────────────

    #[test]
    fn parse_empty_none() {
        let mut sb = SplitBuffer::new();
        assert!(parse(&[], &mut sb).is_none());
    }

    // ── Split-packet reassembly ───────────────────────────────────────────────

    #[test]
    fn split_single_frag_assembles_immediately() {
        let mut sb = SplitBuffer::new();
        let f = make_split_frag(1, 8, 0, 0, 0, 0, 1, b"complete");
        let r = parse(&f, &mut sb).unwrap();
        // placeholder (empty data) + assembled packet
        assert_eq!(r.packets.len(), 2);
        assert_eq!(r.packets[1].data, b"complete");
        assert!(sb.pending.is_empty());
    }

    #[test]
    fn split_two_frags_in_order() {
        let mut sb = SplitBuffer::new();
        let f0 = make_split_frag(1, 9, 0, 0, 0, 0, 2, b"hello");
        let f1 = make_split_frag(2, 9, 0, 0, 0, 1, 2, b" world");
        let r0 = parse(&f0, &mut sb).unwrap();
        assert_eq!(r0.packets.len(), 1);
        assert!(r0.packets[0].data.is_empty()); // placeholder only
        let r1 = parse(&f1, &mut sb).unwrap();
        assert_eq!(r1.packets.len(), 2);
        assert_eq!(r1.packets[1].data, b"hello world");
        assert!(sb.pending.is_empty());
    }

    #[test]
    fn split_two_frags_out_of_order() {
        let mut sb = SplitBuffer::new();
        let f0 = make_split_frag(1, 9, 0, 0, 0, 0, 2, b"hello");
        let f1 = make_split_frag(2, 9, 0, 0, 0, 1, 2, b" world");
        parse(&f1, &mut sb);
        let r = parse(&f0, &mut sb).unwrap();
        let assembled = r.packets.iter().find(|p| !p.data.is_empty()).unwrap();
        assert_eq!(assembled.data, b"hello world");
    }

    #[test]
    fn split_three_frags_reverse_order() {
        let f0 = make_split_frag(1, 8, 0, 0, 1, 0, 3, b"foo");
        let f1 = make_split_frag(2, 8, 0, 0, 1, 1, 3, b"bar");
        let f2 = make_split_frag(3, 8, 0, 0, 1, 2, 3, b"baz");
        let mut sb = SplitBuffer::new();
        parse(&f2, &mut sb);
        parse(&f1, &mut sb);
        let r = parse(&f0, &mut sb).unwrap();
        let assembled = r.packets.iter().find(|p| !p.data.is_empty()).unwrap();
        assert_eq!(assembled.data, b"foobarbaz");
    }

    #[test]
    fn split_missing_frag_not_assembled() {
        let mut sb = SplitBuffer::new();
        // Only send fragment 0 of a 3-fragment sequence
        let f0 = make_split_frag(1, 8, 0, 0, 5, 0, 3, b"part0");
        let r = parse(&f0, &mut sb).unwrap();
        assert!(!r.packets.iter().any(|p| !p.data.is_empty()));
        assert_eq!(sb.pending.len(), 1); // still waiting
    }

    // ── make_coalesced helper ─────────────────────────────────────────────────
    // Builds a single datagram with one isACK=false bit followed by N packet bodies,
    // matching RakNet's GenerateDatagram wire layout exactly.

    fn make_coalesced(packets: &[(&[u8], u16, u8)]) -> Vec<u8> {
        let mut bs = BitStream::new();
        bs.write_bool(false);
        for &(data, msg_num, rel) in packets {
            let reliability = Reliability::from_u8(rel);
            bs.write_uint16_le(msg_num);
            bs.write_bits(&[rel], 4, true);
            if reliability.needs_ordering() {
                bs.write_bits(&[0u8], 5, true);
                bs.write_uint16_le(0);
            }
            bs.write_bool(false);
            bs.write_compressed_uint16((data.len() * 8) as u16);
            bs.write_aligned_bytes(data);
        }
        bs.as_bytes().to_vec()
    }

    // ── msg_num / reliability parametrized ───────────────────────────────────

    #[test]
    fn msg_num_edge_values() {
        for msg_num in [0u16, 1, 0x7FFF, 0xFFFF] {
            let pkt = make_packet(b"\xAA", msg_num, 8, 0, 0);
            let mut sb = SplitBuffer::new();
            let r = parse(&pkt, &mut sb).unwrap();
            assert_eq!(r.packets[0].msg_num, msg_num, "msg_num={msg_num}");
        }
    }

    #[test]
    fn all_reliability_types_parse() {
        for rel in [6u8, 7, 8, 9, 10] {
            let pkt = make_packet(b"\xDE\xAD\xBE\xEF", 0, rel, 0, 0);
            let mut sb = SplitBuffer::new();
            let r = parse(&pkt, &mut sb).unwrap();
            let p = r.packets.iter().find(|p| !p.data.is_empty()).unwrap();
            assert_eq!(p.reliability as u8, rel, "rel={rel}");
            assert_eq!(p.data, b"\xDE\xAD\xBE\xEF");
        }
    }

    // ── Packet size comparisons ───────────────────────────────────────────────

    #[test]
    fn unreliable_smaller_than_sequenced() {
        let un = make_packet(b"hello", 0, 6, 0, 0);
        let seq = make_packet(b"hello", 0, 7, 0, 0);
        assert!(un.len() < seq.len());
    }

    #[test]
    fn reliable_same_size_as_unreliable() {
        let un = make_packet(b"hello", 0, 6, 0, 0);
        let rel = make_packet(b"hello", 0, 8, 0, 0);
        assert_eq!(un.len(), rel.len());
    }

    // ── Ordering fields parametrized ──────────────────────────────────────────

    #[test]
    fn ordering_channel_values() {
        for rel in [7u8, 9, 10] {
            for oc in [0u8, 1, 31] {
                let pkt = make_packet(b"\xCC", 0, rel, oc, 0);
                let mut sb = SplitBuffer::new();
                let r = parse(&pkt, &mut sb).unwrap();
                assert_eq!(r.packets[0].ordering_channel, oc, "rel={rel} oc={oc}");
            }
        }
    }

    #[test]
    fn ordering_index_values() {
        for rel in [7u8, 9, 10] {
            for oi in [0u16, 1, 0xFFFF] {
                let pkt = make_packet(b"\xDD", 0, rel, 0, oi);
                let mut sb = SplitBuffer::new();
                let r = parse(&pkt, &mut sb).unwrap();
                assert_eq!(r.packets[0].ordering_index, oi, "rel={rel} oi={oi}");
            }
        }
    }

    #[test]
    fn ordering_fields_absent_for_unreliable() {
        let pkt = make_packet(b"\xAA", 0, 6, 0, 0);
        let mut sb = SplitBuffer::new();
        let r = parse(&pkt, &mut sb).unwrap();
        assert_eq!(r.packets[0].ordering_channel, 0);
        assert_eq!(r.packets[0].ordering_index, 0);
    }

    #[test]
    fn ordering_fields_absent_for_reliable() {
        let pkt = make_packet(b"\xAA", 0, 8, 0, 0);
        let mut sb = SplitBuffer::new();
        let r = parse(&pkt, &mut sb).unwrap();
        assert_eq!(r.packets[0].ordering_channel, 0);
        assert_eq!(r.packets[0].ordering_index, 0);
    }

    // ── Payload edge cases ────────────────────────────────────────────────────

    #[test]
    fn is_split_false_no_pending() {
        let data = [0xABu8; 10];
        let pkt = make_packet(&data, 5, 8, 0, 0);
        let mut sb = SplitBuffer::new();
        let r = parse(&pkt, &mut sb).unwrap();
        let filled: Vec<_> = r.packets.iter().filter(|p| !p.data.is_empty()).collect();
        assert_eq!(filled.len(), 1);
        assert_eq!(filled[0].data, &data);
        assert!(sb.pending.is_empty());
    }

    #[test]
    fn empty_payload_parse() {
        let pkt = make_packet(b"", 0, 8, 0, 0);
        let mut sb = SplitBuffer::new();
        let r = parse(&pkt, &mut sb).unwrap();
        assert!(!r.is_ack);
    }

    #[test]
    fn payload_sizes() {
        for n in [1usize, 255] {
            let data = vec![0x55u8; n];
            let pkt = make_packet(&data, 10, 8, 0, 0);
            let mut sb = SplitBuffer::new();
            let r = parse(&pkt, &mut sb).unwrap();
            let p = r.packets.iter().find(|p| !p.data.is_empty()).unwrap();
            assert_eq!(p.data, data, "n={n}");
        }
    }

    #[test]
    fn data_no_garbage_bits() {
        let data = [0xFFu8; 7];
        let pkt = make_packet(&data, 0, 8, 0, 0);
        let mut sb = SplitBuffer::new();
        let r = parse(&pkt, &mut sb).unwrap();
        assert_eq!(r.packets[0].data, &data);
    }

    // ── ACK — more coverage ───────────────────────────────────────────────────

    #[test]
    fn ack_single_num() {
        let pkt = make_ack(&[42]);
        let mut sb = SplitBuffer::new();
        let r = parse(&pkt, &mut sb).unwrap();
        assert!(r.is_ack);
        assert_eq!(r.acked, &[42]);
    }

    #[test]
    fn ack_multiple_preserves_all() {
        for nums in [
            vec![0u16, 1, 100, 0xFFFF],
            vec![0xFFFF],
            vec![0, 0xFFFF],
            (0u16..20).collect::<Vec<_>>(),
        ] {
            let pkt = make_ack(&nums);
            let mut sb = SplitBuffer::new();
            let r = parse(&pkt, &mut sb).unwrap();
            let mut got = r.acked.clone();
            got.sort_unstable();
            let mut exp = nums.clone();
            exp.sort_unstable();
            assert_eq!(got, exp, "nums={nums:?}");
        }
    }

    #[test]
    fn ack_large_list() {
        let nums: Vec<u16> = (0..1000).collect();
        let pkt = make_ack(&nums);
        let mut sb = SplitBuffer::new();
        let r = parse(&pkt, &mut sb).unwrap();
        let mut got = r.acked.clone();
        got.sort_unstable();
        assert_eq!(got, nums);
    }

    #[test]
    fn ack_first_bit_is_set() {
        let pkt = make_ack(&[1]);
        assert!(pkt[0] & 0x80 != 0); // MSB = isACK bit
    }

    #[test]
    fn range_ack_single_entry() {
        // Hand-craft: isACK=1, count=1, is_single=false, min=3, max=7
        let mut bs = BitStream::new();
        bs.write_bool(true);
        bs.write_compressed_uint16(1);
        bs.write_bool(false);
        bs.write_uint16_le(3);
        bs.write_uint16_le(7);
        let mut sb = SplitBuffer::new();
        let r = parse(bs.as_bytes(), &mut sb).unwrap();
        assert!(r.is_ack);
        let mut got = r.acked.clone();
        got.sort_unstable();
        assert_eq!(got, &[3, 4, 5, 6, 7]);
    }

    #[test]
    fn range_ack_two_entries() {
        // Range [1,3] + single [10]
        let mut bs = BitStream::new();
        bs.write_bool(true);
        bs.write_compressed_uint16(2);
        bs.write_bool(false);
        bs.write_uint16_le(1);
        bs.write_uint16_le(3);
        bs.write_bool(true);
        bs.write_uint16_le(10);
        let mut sb = SplitBuffer::new();
        let r = parse(bs.as_bytes(), &mut sb).unwrap();
        let mut got = r.acked.clone();
        got.sort_unstable();
        assert_eq!(got, &[1, 2, 3, 10]);
    }

    // ── Parse edge cases ─────────────────────────────────────────────────────

    #[test]
    fn parse_one_byte_not_none() {
        // 1 byte: isACK bit readable, data loop doesn't start (< 17 bits left)
        let mut sb = SplitBuffer::new();
        let r = parse(&[0x00], &mut sb).unwrap();
        assert!(!r.is_ack);
        assert!(r.packets.is_empty());
    }

    #[test]
    fn truncated_packet_no_crash() {
        let full = make_packet(&[0xAAu8; 50], 1, 8, 0, 0);
        let mut sb = SplitBuffer::new();
        let r = parse(&full[..3], &mut sb);
        assert!(r.is_none() || r.unwrap().packets.is_empty());
    }

    #[test]
    fn coalesced_two_packets() {
        let raw = make_coalesced(&[(b"first", 1, 8), (b"second", 2, 8)]);
        let mut sb = SplitBuffer::new();
        let r = parse(&raw, &mut sb).unwrap();
        let payloads: Vec<_> = r
            .packets
            .iter()
            .filter(|p| !p.data.is_empty())
            .map(|p| p.data.as_slice())
            .collect();
        assert_eq!(payloads.len(), 2);
        assert!(payloads.contains(&b"first".as_slice()));
        assert!(payloads.contains(&b"second".as_slice()));
    }

    #[test]
    fn coalesced_three_packets() {
        let specs: Vec<(&[u8], u16, u8)> = (0u16..3)
            .map(|i| (["p0", "p1", "p2"][i as usize].as_bytes(), i, 8u8))
            .collect();
        let raw = make_coalesced(&specs);
        let mut sb = SplitBuffer::new();
        let r = parse(&raw, &mut sb).unwrap();
        let filled: Vec<_> = r.packets.iter().filter(|p| !p.data.is_empty()).collect();
        assert_eq!(filled.len(), 3);
    }

    // ── Split — additional cases ──────────────────────────────────────────────

    #[test]
    fn split_three_frags_in_order() {
        let chunks: &[&[u8]] = &[b"one", b"two", b"three"];
        let mut sb = SplitBuffer::new();
        let mut last = None;
        for (i, chunk) in chunks.iter().enumerate() {
            let f = make_split_frag(i as u16, 8, 0, 0, 2, i as u32, 3, chunk);
            last = parse(&f, &mut sb);
        }
        assert!(sb.pending.is_empty());
        let assembled = last
            .unwrap()
            .packets
            .into_iter()
            .find(|p| !p.data.is_empty())
            .unwrap();
        assert_eq!(assembled.data, b"onetwothree");
    }

    #[test]
    fn split_three_frags_all_permutations() {
        let chunks: [&[u8]; 3] = [b"AAA", b"BBB", b"CCC"];
        let expected = b"AAABBBCCC";
        let perms = [
            [0, 1, 2],
            [0, 2, 1],
            [1, 0, 2],
            [1, 2, 0],
            [2, 0, 1],
            [2, 1, 0],
        ];
        for perm in &perms {
            let mut sb = SplitBuffer::new();
            let mut last_result = None;
            for &idx in perm {
                let f = make_split_frag(idx as u16, 8, 0, 0, 3, idx as u32, 3, chunks[idx]);
                last_result = parse(&f, &mut sb);
            }
            let all_data: Vec<_> = {
                // collect assembled packet from all parse results — just check sb is empty
                assert!(sb.pending.is_empty(), "perm={perm:?}");
                let r = last_result.unwrap();
                r.packets
                    .into_iter()
                    .filter(|p| !p.data.is_empty())
                    .collect()
            };
            assert_eq!(all_data.len(), 1, "perm={perm:?}");
            assert_eq!(all_data[0].data, expected, "perm={perm:?}");
        }
    }

    #[test]
    fn split_duplicate_fragment_no_crash() {
        let mut sb = SplitBuffer::new();
        // Send frag 0 twice
        let f0a = make_split_frag(1, 8, 0, 0, 5, 0, 2, b"dup");
        let f0b = make_split_frag(2, 8, 0, 0, 5, 0, 2, b"dup");
        let f1 = make_split_frag(3, 8, 0, 0, 5, 1, 2, b"end");
        parse(&f0a, &mut sb);
        parse(&f0b, &mut sb);
        let r = parse(&f1, &mut sb).unwrap();
        let assembled = r.packets.iter().find(|p| !p.data.is_empty()).unwrap();
        assert_eq!(assembled.data, b"dupend");
    }

    #[test]
    fn split_zero_length_fragment_assembles() {
        let mut sb = SplitBuffer::new();
        let f0 = make_split_frag(1, 8, 0, 0, 30, 0, 2, b"");
        let f1 = make_split_frag(2, 8, 0, 0, 30, 1, 2, b"data");
        parse(&f0, &mut sb);
        let r = parse(&f1, &mut sb).unwrap();
        let assembled = r.packets.iter().find(|p| !p.data.is_empty()).unwrap();
        assert_eq!(assembled.data, b"data");
    }

    #[test]
    fn two_independent_split_sequences() {
        let mut sb = SplitBuffer::new();
        let a0 = make_split_frag(1, 8, 0, 0, 10, 0, 2, b"AA");
        let b0 = make_split_frag(2, 8, 0, 0, 11, 0, 2, b"BB");
        let a1 = make_split_frag(3, 8, 0, 0, 10, 1, 2, b"CC");
        let b1 = make_split_frag(4, 8, 0, 0, 11, 1, 2, b"DD");
        parse(&a0, &mut sb);
        parse(&b0, &mut sb);
        let ra = parse(&a1, &mut sb).unwrap();
        let rb = parse(&b1, &mut sb).unwrap();
        let a_data = ra.packets.iter().find(|p| !p.data.is_empty()).unwrap();
        let b_data = rb.packets.iter().find(|p| !p.data.is_empty()).unwrap();
        assert_eq!(a_data.data, b"AACC");
        assert_eq!(b_data.data, b"BBDD");
        assert!(sb.pending.is_empty());
    }

    // ── Dedup base advances past split-fragment msg_nums ─────────────────────
    // Regression: before the fix, split-fragment msg_nums were not tracked in
    // dedup_bits, so dedup_base stayed stuck at 0. Once non-split reliable
    // msg_nums exceeded base+32767 the "hole > u16::MAX/2" guard incorrectly
    // dropped legitimate new packets as past-base retransmits.

    #[test]
    fn dedup_base_advances_past_split_fragments() {
        let mut sb = SplitBuffer::new();
        // Two split fragments with msg_nums 0 and 1
        let f0 = make_split_frag(0, 8, 0, 0, 0, 0, 2, b"hello");
        let f1 = make_split_frag(1, 8, 0, 0, 0, 1, 2, b" world");
        parse(&f0, &mut sb);
        parse(&f1, &mut sb);
        // dedup_base must now be 2 (past both split fragments)
        assert_eq!(sb.dedup_base, 2, "split fragment msg_nums must advance dedup_base");
    }

    #[test]
    fn dedup_no_false_positive_after_split_then_non_split() {
        let mut sb = SplitBuffer::new();
        // Split: msg_nums 0,1 (simulates RPC_INIT_GAME fragments)
        let f0 = make_split_frag(0, 8, 0, 0, 7, 0, 2, b"A");
        let f1 = make_split_frag(1, 8, 0, 0, 7, 1, 2, b"B");
        parse(&f0, &mut sb);
        parse(&f1, &mut sb);
        // Non-split reliable packets starting at msg_num=2
        for i in 2u16..70 {
            let pkt = make_packet(b"data", i, 8, 0, 0);
            let r = parse(&pkt, &mut sb).unwrap();
            let delivered: Vec<_> = r.packets.iter().filter(|p| !p.data.is_empty()).collect();
            assert_eq!(delivered.len(), 1, "packet msg_num={i} must not be dropped as false duplicate");
        }
    }
}
