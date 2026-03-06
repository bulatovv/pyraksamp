//! SA:MP 0.3.7 pure-Rust client — port of client.cpp.

use std::net::{IpAddr, Ipv4Addr, SocketAddr, ToSocketAddrs, UdpSocket};
use std::sync::{Arc, Mutex};
use std::sync::atomic::{AtomicBool, AtomicU16, Ordering};
use std::time::{Duration, Instant};

use crate::bitstream::BitStream;
use crate::encrypt::{encrypt as samp_encrypt, auth_response as samp_auth_response};
use crate::reliability::{make_packet, make_ack, parse as rel_parse, SplitBuffer};

// ── Packet IDs ────────────────────────────────────────────────────────────────
const ID_INTERNAL_PING:                u8 = 6;
const ID_CONNECTED_PONG:               u8 = 9;
const ID_CONNECTION_REQUEST:           u8 = 11;
const ID_AUTH_KEY:                     u8 = 12;
const ID_RPC:                          u8 = 20;
const ID_OPEN_CONNECTION_REQUEST:      u8 = 24;
const ID_OPEN_CONNECTION_REPLY:        u8 = 25;
const ID_OPEN_CONNECTION_COOKIE:       u8 = 26;
const ID_CONNECTION_ATTEMPT_FAILED:    u8 = 29;
const ID_NEW_INCOMING_CONNECTION:      u8 = 30;
const ID_NO_FREE_INCOMING_CONNECTIONS: u8 = 31;
const ID_DISCONNECTION_NOTIFICATION:   u8 = 32;
const ID_CONNECTION_LOST:              u8 = 33;
const ID_CONNECTION_REQUEST_ACCEPTED:  u8 = 34;
const ID_CONNECTION_BANNED:            u8 = 36;
const ID_INVALID_PASSWORD:             u8 = 37;
const ID_TIMESTAMP:                    u8 = 40;
const ID_PLAYER_SYNC:                  u8 = 207;

// ── RPC IDs ──────────────────────────────────────────────────────────────────
const RPC_SERVER_JOIN:          u8 = 137;
const RPC_SERVER_QUIT:          u8 = 138;
const RPC_INIT_GAME:            u8 = 139;
const RPC_CONNECTION_REJ:       u8 = 130;
const RPC_CHAT:                 u8 = 101;
const RPC_CLIENT_MESSAGE:       u8 = 93;
const RPC_DIALOG_BOX:           u8 = 61;
const RPC_GAME_TEXT:            u8 = 73;
const RPC_SET_HEALTH:           u8 = 14;
const RPC_SET_ARMOUR:           u8 = 66;
const RPC_SET_POSITION:         u8 = 12;
const RPC_SET_CHECKPOINT:       u8 = 107;
const RPC_DISABLE_CHECKPOINT:   u8 = 37;
const RPC_WORLD_PLAYER_ADD:     u8 = 32;
const RPC_WORLD_PLAYER_REMOVE:  u8 = 163;
const RPC_SET_PLAYER_NAME:      u8 = 11;
const RPC_TOGGLE_CONTROLLABLE:  u8 = 15;
const RPC_SET_PLAYER_TIME:      u8 = 29;
const RPC_SEND_DEATH_MESSAGE:   u8 = 55;
const RPC_SET_ARMED_WEAPON:     u8 = 67;
const RPC_SET_SPAWN_INFO:       u8 = 68;
const RPC_SET_PLAYER_TEAM:      u8 = 69;
const RPC_PUT_IN_VEHICLE:       u8 = 70;
const RPC_REMOVE_FROM_VEHICLE:  u8 = 71;
const RPC_SET_PLAYER_COLOR:     u8 = 72;
const RPC_SET_WORLD_TIME:       u8 = 94;
const RPC_TOGGLE_SPECTATING:    u8 = 124;
const RPC_SET_WANTED_LEVEL:     u8 = 133;
const RPC_SET_WEAPON_AMMO:      u8 = 145;
const RPC_SET_GRAVITY:          u8 = 146;
const RPC_SET_WEATHER:          u8 = 152;
const RPC_SET_PLAYER_SKIN:      u8 = 153;
const RPC_SET_INTERIOR:         u8 = 156;
const RPC_WORLD_VEHICLE_ADD:    u8 = 164;
const RPC_WORLD_VEHICLE_REMOVE: u8 = 165;
const RPC_DEATH_BROADCAST:      u8 = 166;

const RPC_CLIENT_JOIN:     u8 = 25;
const RPC_REQUEST_CLASS:   u8 = 128;
const RPC_REQUEST_SPAWN:   u8 = 129;
const RPC_SPAWN:           u8 = 52;
const RPC_DIALOG_RESPONSE: u8 = 62;
const RPC_DEATH:           u8 = 53;
const RPC_ENTER_VEHICLE:   u8 = 26;
const RPC_EXIT_VEHICLE:    u8 = 154;
const RPC_SERVER_COMMAND:  u8 = 50;
const RPC_UPDATE_SCORES:   u8 = 155;

const NETGAME_VERSION:       u32 = 4057;
const NETCODE_CONNCOOKIELULZ: u16 = 0x6969;
const DEFAULT_GPCI: &str = "3E9B8D0C4A7F2E6B1D5A3C9E8F2B4D6A0C7E9B3";

// Reliability constants (SAMP legacy offset)
const REL_UNRELIABLE:           u8 = 6;
const REL_UNRELIABLE_SEQUENCED: u8 = 7;
const REL_RELIABLE:             u8 = 8;
const REL_RELIABLE_ORDERED:     u8 = 9;
const REL_RELIABLE_SEQUENCED:   u8 = 10;

fn needs_ordering(rel: u8) -> bool {
    rel == REL_UNRELIABLE_SEQUENCED || rel == REL_RELIABLE_ORDERED || rel == REL_RELIABLE_SEQUENCED
}

// ── Callbacks ─────────────────────────────────────────────────────────────────

pub struct Callbacks {
    pub on_connect:             Option<Arc<dyn Fn() + Send + Sync>>,
    pub on_disconnect:          Option<Arc<dyn Fn() + Send + Sync>>,
    pub on_rpc:                 Option<Arc<dyn Fn(u8, Vec<u8>) + Send + Sync>>,
    pub on_player_join:         Option<Arc<dyn Fn(u16, String) + Send + Sync>>,
    pub on_player_quit:         Option<Arc<dyn Fn(u16, u8) + Send + Sync>>,
    pub on_chat:                Option<Arc<dyn Fn(u16, String) + Send + Sync>>,
    pub on_client_message:      Option<Arc<dyn Fn(u32, String) + Send + Sync>>,
    pub on_dialog:              Option<Arc<dyn Fn(u16, u8, String, String, String, String) + Send + Sync>>,
    pub on_game_text:           Option<Arc<dyn Fn(i32, i32, String) + Send + Sync>>,
    pub on_set_health:          Option<Arc<dyn Fn(f32) + Send + Sync>>,
    pub on_set_armour:          Option<Arc<dyn Fn(f32) + Send + Sync>>,
    pub on_set_position:        Option<Arc<dyn Fn(f32, f32, f32) + Send + Sync>>,
    pub on_checkpoint:          Option<Arc<dyn Fn(f32, f32, f32, f32) + Send + Sync>>,
    pub on_checkpoint_disabled: Option<Arc<dyn Fn() + Send + Sync>>,
    pub on_player_streamed_in:  Option<Arc<dyn Fn(u16, u8, i32, f32, f32, f32, f32, u32, u8) + Send + Sync>>,
    pub on_player_streamed_out: Option<Arc<dyn Fn(u16) + Send + Sync>>,
    pub on_player_name:         Option<Arc<dyn Fn(u16, String, u8) + Send + Sync>>,
    pub on_toggle_controllable: Option<Arc<dyn Fn(u8) + Send + Sync>>,
    pub on_player_time:         Option<Arc<dyn Fn(u8, u8) + Send + Sync>>,
    pub on_death_message:       Option<Arc<dyn Fn(u16, u16, u8) + Send + Sync>>,
    pub on_set_armed_weapon:    Option<Arc<dyn Fn(u32) + Send + Sync>>,
    pub on_spawn_info:          Option<Arc<dyn Fn(u8, u32, f32, f32, f32, f32, u32, u32, u32, u32, u32, u32) + Send + Sync>>,
    pub on_player_team:         Option<Arc<dyn Fn(u16, u8) + Send + Sync>>,
    pub on_put_in_vehicle:      Option<Arc<dyn Fn(u16, u8) + Send + Sync>>,
    pub on_remove_from_vehicle: Option<Arc<dyn Fn() + Send + Sync>>,
    pub on_player_color:        Option<Arc<dyn Fn(u16, u32) + Send + Sync>>,
    pub on_world_time:          Option<Arc<dyn Fn(u8) + Send + Sync>>,
    pub on_toggle_spectating:   Option<Arc<dyn Fn(bool) + Send + Sync>>,
    pub on_wanted_level:        Option<Arc<dyn Fn(u8) + Send + Sync>>,
    pub on_weapon_ammo:         Option<Arc<dyn Fn(u8, u16) + Send + Sync>>,
    pub on_gravity:             Option<Arc<dyn Fn(f32) + Send + Sync>>,
    pub on_weather:             Option<Arc<dyn Fn(u8) + Send + Sync>>,
    pub on_player_skin:         Option<Arc<dyn Fn(i32, u32) + Send + Sync>>,
    pub on_set_interior:        Option<Arc<dyn Fn(u8) + Send + Sync>>,
    pub on_vehicle_streamed_in: Option<Arc<dyn Fn(u16, i32, f32, f32, f32, f32, u8, u8, f32, u8, u32, u32, u8, u8, u8, u8, u32, u32) + Send + Sync>>,
    pub on_vehicle_streamed_out:Option<Arc<dyn Fn(u16) + Send + Sync>>,
    pub on_player_death:        Option<Arc<dyn Fn(u16) + Send + Sync>>,
}

impl Callbacks {
    pub fn new() -> Self {
        Callbacks {
            on_connect: None, on_disconnect: None, on_rpc: None,
            on_player_join: None, on_player_quit: None,
            on_chat: None, on_client_message: None, on_dialog: None,
            on_game_text: None, on_set_health: None, on_set_armour: None,
            on_set_position: None, on_checkpoint: None, on_checkpoint_disabled: None,
            on_player_streamed_in: None, on_player_streamed_out: None,
            on_player_name: None, on_toggle_controllable: None,
            on_player_time: None, on_death_message: None, on_set_armed_weapon: None,
            on_spawn_info: None, on_player_team: None, on_put_in_vehicle: None,
            on_remove_from_vehicle: None, on_player_color: None, on_world_time: None,
            on_toggle_spectating: None, on_wanted_level: None, on_weapon_ammo: None,
            on_gravity: None, on_weather: None, on_player_skin: None,
            on_set_interior: None, on_vehicle_streamed_in: None,
            on_vehicle_streamed_out: None, on_player_death: None,
        }
    }
}

// Helper: clone a callback from the mutex without holding the lock when calling.
macro_rules! fire {
    ($cbs:expr, $field:ident) => {{
        let cb = $cbs.lock().unwrap().$field.clone();
        if let Some(cb) = cb { cb(); }
    }};
    ($cbs:expr, $field:ident, $($arg:expr),+) => {{
        let cb = $cbs.lock().unwrap().$field.clone();
        if let Some(cb) = cb { cb($($arg),+); }
    }};
}

// ── Network helpers ───────────────────────────────────────────────────────────

struct NetState {
    sock:        Arc<UdpSocket>,
    server_addr: SocketAddr,
}

// ── SampClient ────────────────────────────────────────────────────────────────

pub struct SampClient {
    // Config (immutable after construction)
    port:     u16,
    nickname: String,
    password: String,
    gpci:     String,
    host:     String,

    // Network (set once in connect())
    net: Mutex<Option<NetState>>,

    // Atomic state
    pub connected: AtomicBool,
    pub running:   AtomicBool,
    spawned:       AtomicBool,
    send_msg_num:  AtomicU16,
    ordering_idx:  AtomicU16,

    // Protected state
    player_id:    Mutex<i32>,
    challenge:    Mutex<u32>,
    pending_acks: Mutex<Vec<u16>>,

    pub callbacks: Mutex<Callbacks>,
}

impl SampClient {
    pub fn new(host: &str, port: u16, nickname: &str, password: &str, gpci: &str) -> Arc<Self> {
        let gpci = if gpci.is_empty() {
            DEFAULT_GPCI.to_string()
        } else {
            gpci.to_string()
        };
        Arc::new(SampClient {
            host:         host.to_string(),
            port,
            nickname:     nickname.to_string(),
            password:     password.to_string(),
            gpci,
            net:          Mutex::new(None),
            connected:    AtomicBool::new(false),
            running:      AtomicBool::new(false),
            spawned:      AtomicBool::new(false),
            send_msg_num: AtomicU16::new(0),
            ordering_idx: AtomicU16::new(0),
            player_id:    Mutex::new(-1),
            challenge:    Mutex::new(0),
            pending_acks: Mutex::new(Vec::new()),
            callbacks:    Mutex::new(Callbacks::new()),
        })
    }

    pub fn is_connected(&self) -> bool { self.connected.load(Ordering::Relaxed) }
    pub fn player_id(&self)    -> i32  { *self.player_id.lock().unwrap() }

    // ─── Internal send primitives ─────────────────────────────────────────────

    fn send_raw(&self, data: &[u8]) {
        let guard = self.net.lock().unwrap();
        if let Some(ns) = guard.as_ref() {
            let sock = Arc::clone(&ns.sock);
            let addr = ns.server_addr;
            drop(guard);
            let _ = sock.send_to(data, addr);
        }
    }

    fn send_encrypted(&self, data: &[u8]) {
        let (sock, addr) = {
            let guard = self.net.lock().unwrap();
            match guard.as_ref() {
                Some(ns) => (Arc::clone(&ns.sock), ns.server_addr),
                None => return,
            }
        };
        let enc = samp_encrypt(data, self.port);
        let _ = sock.send_to(&enc, addr);
    }

    fn send_reliability_pkt(&self, data: &[u8], rel: u8, oc: u8, mut oi: u16) {
        let num = self.send_msg_num.fetch_add(1, Ordering::Relaxed);
        if needs_ordering(rel) {
            oi = self.ordering_idx.fetch_add(1, Ordering::Relaxed);
        }
        let pkt = make_packet(data, num, rel, oc, oi);
        self.send_encrypted(&pkt);
    }

    fn send_acks(&self, nums: &[u16]) {
        if nums.is_empty() { return; }
        let pkt = make_ack(nums);
        self.send_encrypted(&pkt);
    }

    fn flush_acks(&self) {
        let acks: Vec<u16> = {
            let mut guard = self.pending_acks.lock().unwrap();
            std::mem::take(&mut *guard)
        };
        self.send_acks(&acks);
    }

    // ─── RPC send ─────────────────────────────────────────────────────────────

    pub fn send_rpc(&self, rpc_id: u8, payload: &[u8], rel: u8) {
        let mut bs = BitStream::new();
        bs.write_uint8(ID_RPC);
        bs.write_uint8(rpc_id);
        bs.write_compressed_uint32((payload.len() * 8) as u32);
        if !payload.is_empty() {
            bs.write_bits(payload, (payload.len() * 8) as i32, false);
        }
        self.send_reliability_pkt(bs.as_bytes(), rel, 0, 0);
    }

    // ─── Handshake phase ──────────────────────────────────────────────────────

    fn do_handshake(&self, sock: &UdpSocket, server_v4: Ipv4Addr, timeout: Duration) -> bool {
        let req = [ID_OPEN_CONNECTION_REQUEST, 0, 0];
        let enc = samp_encrypt(&req, self.port);
        let _ = sock.send_to(&enc, SocketAddr::from((server_v4, self.port)));

        let deadline = Instant::now() + timeout;
        let mut buf = [0u8; 256];
        loop {
            match recv_deadline(sock, &mut buf, server_v4, deadline) {
                None => return false,
                Some(n) => {
                    if n >= 3 && buf[0] == ID_OPEN_CONNECTION_COOKIE {
                        let lo = buf[1];
                        let hi = buf[2];
                        let reply = [
                            ID_OPEN_CONNECTION_REQUEST,
                            lo ^ (NETCODE_CONNCOOKIELULZ & 0xFF) as u8,
                            hi ^ ((NETCODE_CONNCOOKIELULZ >> 8) & 0xFF) as u8,
                        ];
                        let enc = samp_encrypt(&reply, self.port);
                        let _ = sock.send_to(&enc, SocketAddr::from((server_v4, self.port)));
                        continue;
                    }
                    if n >= 1 && buf[0] == ID_OPEN_CONNECTION_REPLY {
                        return true;
                    }
                }
            }
        }
    }

    fn handle_auth_key_raw(&self, data: &[u8]) {
        if data.len() < 2 { return; }
        let key_len = data[1] as usize;
        if data.len() < 2 + key_len { return; }

        // Challenge: strip trailing null bytes
        let raw = &data[2..2 + key_len];
        let challenge = std::str::from_utf8(raw)
            .unwrap_or("")
            .trim_end_matches('\0');

        let resp = samp_auth_response(challenge).unwrap_or("");
        let resp_bytes = resp.as_bytes();

        let mut pkt = vec![0u8; 2 + resp_bytes.len()];
        pkt[0] = ID_AUTH_KEY;
        pkt[1] = resp_bytes.len() as u8;
        pkt[2..].copy_from_slice(resp_bytes);
        self.send_reliability_pkt(&pkt, REL_RELIABLE, 0, 0);
    }

    fn handle_connection_accepted_raw(&self, data: &[u8]) {
        if data.len() < 9 { return; }
        let mut bs = BitStream::from_bytes(data);
        let pid: u16;
        let chal: u32;
        // Skip: ID_CONNECTION_REQUEST_ACCEPTED(8b) + binaryAddress(32b) + port(16b)
        bs.skip_bits(56);
        pid  = match bs.read_uint16_le() { Ok(v) => v, Err(_) => return };
        chal = match bs.read_uint32_le()  { Ok(v) => v, Err(_) => return };

        *self.player_id.lock().unwrap() = pid as i32;
        *self.challenge.lock().unwrap() = chal;

        // ID_NEW_INCOMING_CONNECTION
        let server_ip_be: u32 = {
            let guard = self.net.lock().unwrap();
            match guard.as_ref() {
                Some(ns) => match ns.server_addr.ip() {
                    IpAddr::V4(v4) => u32::from(v4).to_be(),
                    _ => 0,
                },
                None => 0,
            }
        };
        let mut nic = vec![0u8; 7];
        nic[0] = ID_NEW_INCOMING_CONNECTION;
        nic[1..5].copy_from_slice(&server_ip_be.to_be_bytes());
        let port_le = self.port.to_le_bytes();
        nic[5..7].copy_from_slice(&port_le);
        self.send_reliability_pkt(&nic, REL_RELIABLE, 0, 0);

        self.send_client_join();
    }

    fn send_client_join(&self) {
        let nick = {
            let n = &self.nickname;
            if n.len() > 20 { n[..20].to_string() } else { n.clone() }
        };
        let gpci = {
            let g = &self.gpci;
            if g.len() > 63 { g[..63].to_string() } else { g.clone() }
        };
        let ver = "0.3.7";
        let challenge = *self.challenge.lock().unwrap();
        let challenge_resp = challenge ^ NETGAME_VERSION;

        let mut bs = BitStream::new();
        let version = NETGAME_VERSION as i32;
        bs.write_int32_le(version);
        bs.write_uint8(1); // mod = 1
        bs.write_uint8(nick.len() as u8);
        bs.write_aligned_bytes(nick.as_bytes());
        bs.write_uint32_le(challenge_resp);
        bs.write_uint8(gpci.len() as u8);
        bs.write_aligned_bytes(gpci.as_bytes());
        bs.write_uint8(ver.len() as u8);
        bs.write_aligned_bytes(ver.as_bytes());

        let payload = bs.as_bytes().to_vec();
        let mut rpc_bs = BitStream::new();
        rpc_bs.write_uint8(ID_RPC);
        rpc_bs.write_uint8(RPC_CLIENT_JOIN);
        rpc_bs.write_compressed_uint32((payload.len() * 8) as u32);
        rpc_bs.write_bits(&payload, (payload.len() * 8) as i32, false);
        self.send_reliability_pkt(rpc_bs.as_bytes(), REL_RELIABLE, 0, 0);
    }

    fn do_connection_request(&self, sock: &UdpSocket, server_v4: Ipv4Addr, timeout: Duration) -> bool {
        let mut cr = vec![ID_CONNECTION_REQUEST];
        if !self.password.is_empty() {
            cr.extend_from_slice(self.password.as_bytes());
        }
        self.send_reliability_pkt(&cr, REL_RELIABLE, 0, 0);

        let deadline = Instant::now() + timeout;
        let mut buf = [0u8; 2048];
        let mut split_buf = SplitBuffer::new();

        loop {
            let n = match recv_deadline_cap(sock, &mut buf, server_v4, deadline, Duration::from_millis(500)) {
                None => return false,
                Some(n) => n,
            };

            // Raw auth key (before reliability layer)
            if n >= 2 && buf[0] == ID_AUTH_KEY {
                self.handle_auth_key_raw(&buf[..n]);
                continue;
            }

            let result = match rel_parse(&buf[..n], &mut split_buf) {
                Some(r) => r,
                None => continue,
            };
            if result.is_ack { continue; }

            for pkt in &result.packets {
                if pkt.reliability == crate::reliability::Reliability::Reliable
                    || pkt.reliability == crate::reliability::Reliability::ReliableOrdered
                {
                    self.pending_acks.lock().unwrap().push(pkt.msg_num);
                }
                self.flush_acks();

                if pkt.data.is_empty() { continue; }
                match pkt.data[0] {
                    id if id == ID_AUTH_KEY => {
                        self.handle_auth_key_raw(&pkt.data);
                    }
                    id if id == ID_CONNECTION_REQUEST_ACCEPTED => {
                        self.handle_connection_accepted_raw(&pkt.data);
                        self.connected.store(true, Ordering::Relaxed);
                        return true;
                    }
                    id if id == ID_CONNECTION_BANNED
                        || id == ID_INVALID_PASSWORD
                        || id == ID_NO_FREE_INCOMING_CONNECTIONS
                        || id == ID_CONNECTION_ATTEMPT_FAILED =>
                    {
                        return false;
                    }
                    _ => {}
                }
            }
        }
    }

    // ─── RPC handlers ─────────────────────────────────────────────────────────

    fn handle_rpc(&self, rpc_id: u8, payload: &[u8]) {
        let mut bs = BitStream::from_bytes(payload);
        let len = payload.len() as i32;

        let _ = (|| -> Option<()> {
            match rpc_id {
                RPC_INIT_GAME => {
                    fire!(self.callbacks, on_connect);
                    // Request class 0; spawn is deferred until server replies (RPC_REQUEST_CLASS).
                    let class_id: i32 = 0;
                    self.send_rpc(RPC_REQUEST_CLASS, &class_id.to_le_bytes(), REL_RELIABLE);
                }

                RPC_REQUEST_CLASS => {
                    // Server approved class selection (u8 outcome + PLAYER_SPAWN_INFO).
                    // Spawn immediately — mirrors sampSpawn() in the reference.
                    let _outcome = bs.read_uint8().ok()?;
                    self.send_rpc(RPC_REQUEST_SPAWN, &[], REL_RELIABLE);
                    self.send_rpc(RPC_SPAWN, &[], REL_RELIABLE);
                    self.spawned.store(true, Ordering::Relaxed);
                }

                RPC_CONNECTION_REJ => {
                    self.running.store(false, Ordering::Relaxed);
                }

                RPC_SERVER_JOIN => {
                    let pid  = bs.read_uint16_le().ok()?;
                    bs.skip_bits(32); // unk
                    bs.read_uint8().ok()?; // isNPC
                    let nlen = bs.read_uint8().ok()? as usize;
                    let mut name_buf = vec![0u8; nlen];
                    if nlen > 0 { bs.read_aligned_bytes(&mut name_buf).ok()?; }
                    let name = String::from_utf8_lossy(&name_buf).into_owned();
                    fire!(self.callbacks, on_player_join, pid, name);
                }

                RPC_SERVER_QUIT => {
                    let pid    = bs.read_uint16_le().ok()?;
                    let reason = bs.read_uint8().ok()?;
                    fire!(self.callbacks, on_player_quit, pid, reason);
                }

                RPC_CHAT => {
                    let pid  = bs.read_uint16_le().ok()?;
                    let tlen = bs.read_uint8().ok()? as usize;
                    let mut tbuf = vec![0u8; tlen];
                    if tlen > 0 { bs.read_aligned_bytes(&mut tbuf).ok()?; }
                    let text = String::from_utf8_lossy(&tbuf).into_owned();
                    fire!(self.callbacks, on_chat, pid, text);
                }

                RPC_CLIENT_MESSAGE => {
                    let color = bs.read_uint32_le().ok()?;
                    let mlen  = bs.read_uint32_le().ok()? as usize;
                    if mlen > 256 { return None; }
                    let mut mbuf = vec![0u8; mlen];
                    if mlen > 0 { bs.read_aligned_bytes(&mut mbuf).ok()?; }
                    let text = String::from_utf8_lossy(&mbuf).into_owned();
                    fire!(self.callbacks, on_client_message, color, text);
                }

                RPC_DIALOG_BOX => {
                    let did   = bs.read_uint16_le().ok()?;
                    let style = bs.read_uint8().ok()?;

                    let tlen = bs.read_uint8().ok()? as usize;
                    let mut tbuf = vec![0u8; tlen];
                    if tlen > 0 { bs.read_aligned_bytes(&mut tbuf).ok()?; }
                    let title = String::from_utf8_lossy(&tbuf).into_owned();

                    let b1len = bs.read_uint8().ok()? as usize;
                    let mut b1buf = vec![0u8; b1len];
                    if b1len > 0 { bs.read_aligned_bytes(&mut b1buf).ok()?; }
                    let btn1 = String::from_utf8_lossy(&b1buf).into_owned();

                    let b2len = bs.read_uint8().ok()? as usize;
                    let mut b2buf = vec![0u8; b2len];
                    if b2len > 0 { bs.read_aligned_bytes(&mut b2buf).ok()?; }
                    let btn2 = String::from_utf8_lossy(&b2buf).into_owned();

                    let body = bs.read_compressed_string(4095).ok().unwrap_or_default();
                    fire!(self.callbacks, on_dialog, did, style, title, btn1, btn2, body);
                }

                RPC_GAME_TEXT => {
                    let gtype = bs.read_int32_le().ok()?;
                    let time  = bs.read_int32_le().ok()?;
                    let mlen  = bs.read_int32_le().ok()?;
                    if mlen < 0 || mlen > 400 { return None; }
                    let mut mbuf = vec![0u8; mlen as usize];
                    if mlen > 0 { bs.read_aligned_bytes(&mut mbuf).ok()?; }
                    let text = String::from_utf8_lossy(&mbuf).into_owned();
                    fire!(self.callbacks, on_game_text, gtype, time, text);
                }

                RPC_SET_HEALTH => {
                    let hp = bs.read_float_le().ok()?;
                    fire!(self.callbacks, on_set_health, hp);
                }

                RPC_SET_ARMOUR => {
                    let arm = bs.read_float_le().ok()?;
                    fire!(self.callbacks, on_set_armour, arm);
                }

                RPC_SET_POSITION => {
                    let x = bs.read_float_le().ok()?;
                    let y = bs.read_float_le().ok()?;
                    let z = bs.read_float_le().ok()?;
                    fire!(self.callbacks, on_set_position, x, y, z);
                }

                RPC_SET_CHECKPOINT => {
                    let x  = bs.read_float_le().ok()?;
                    let y  = bs.read_float_le().ok()?;
                    let z  = bs.read_float_le().ok()?;
                    let sz = bs.read_float_le().ok()?;
                    fire!(self.callbacks, on_checkpoint, x, y, z, sz);
                }

                RPC_DISABLE_CHECKPOINT => {
                    fire!(self.callbacks, on_checkpoint_disabled);
                }

                RPC_WORLD_PLAYER_ADD => {
                    let pid   = bs.read_uint16_le().ok()?;
                    let team  = bs.read_uint8().ok()?;
                    let skin  = bs.read_int32_le().ok()?;
                    let x     = bs.read_float_le().ok()?;
                    let y     = bs.read_float_le().ok()?;
                    let z     = bs.read_float_le().ok()?;
                    let rot   = bs.read_float_le().ok()?;
                    let color = bs.read_uint32_le().ok()?;
                    let fs    = bs.read_uint8().ok()?;
                    fire!(self.callbacks, on_player_streamed_in, pid, team, skin, x, y, z, rot, color, fs);
                }

                RPC_WORLD_PLAYER_REMOVE => {
                    let pid = bs.read_uint16_le().ok()?;
                    fire!(self.callbacks, on_player_streamed_out, pid);
                }

                RPC_SET_PLAYER_NAME => {
                    let pid  = bs.read_uint16_le().ok()?;
                    let nlen = bs.read_uint8().ok()? as usize;
                    let mut nbuf = vec![0u8; nlen];
                    if nlen > 0 { bs.read_aligned_bytes(&mut nbuf).ok()?; }
                    let name    = String::from_utf8_lossy(&nbuf).into_owned();
                    let success = bs.read_uint8().ok()?;
                    fire!(self.callbacks, on_player_name, pid, name, success);
                }

                RPC_TOGGLE_CONTROLLABLE => {
                    let moveable = bs.read_uint8().ok()?;
                    fire!(self.callbacks, on_toggle_controllable, moveable);
                }

                RPC_SET_PLAYER_TIME => {
                    let hour   = bs.read_uint8().ok()?;
                    let minute = bs.read_uint8().ok()?;
                    fire!(self.callbacks, on_player_time, hour, minute);
                }

                RPC_SEND_DEATH_MESSAGE => {
                    let killer = bs.read_uint16_le().ok()?;
                    let player = bs.read_uint16_le().ok()?;
                    let weapon = bs.read_uint8().ok()?;
                    fire!(self.callbacks, on_death_message, killer, player, weapon);
                }

                RPC_SET_ARMED_WEAPON => {
                    let wid = bs.read_uint32_le().ok()?;
                    fire!(self.callbacks, on_set_armed_weapon, wid);
                }

                RPC_SET_SPAWN_INFO => {
                    let team = bs.read_uint8().ok()?;
                    let skin = bs.read_uint32_le().ok()?;
                    bs.read_uint8().ok()?; // unused
                    let x   = bs.read_float_le().ok()?;
                    let y   = bs.read_float_le().ok()?;
                    let z   = bs.read_float_le().ok()?;
                    let rot = bs.read_float_le().ok()?;
                    let w1  = bs.read_uint32_le().ok()?;
                    let w2  = bs.read_uint32_le().ok()?;
                    let w3  = bs.read_uint32_le().ok()?;
                    let a1  = bs.read_uint32_le().ok()?;
                    let a2  = bs.read_uint32_le().ok()?;
                    let a3  = bs.read_uint32_le().ok()?;
                    fire!(self.callbacks, on_spawn_info, team, skin, x, y, z, rot, w1, w2, w3, a1, a2, a3);
                }

                RPC_SET_PLAYER_TEAM => {
                    let pid  = bs.read_uint16_le().ok()?;
                    let team = bs.read_uint8().ok()?;
                    fire!(self.callbacks, on_player_team, pid, team);
                }

                RPC_PUT_IN_VEHICLE => {
                    let vid  = bs.read_uint16_le().ok()?;
                    let seat = bs.read_uint8().ok()?;
                    fire!(self.callbacks, on_put_in_vehicle, vid, seat);
                }

                RPC_REMOVE_FROM_VEHICLE => {
                    fire!(self.callbacks, on_remove_from_vehicle);
                }

                RPC_SET_PLAYER_COLOR => {
                    let pid   = bs.read_uint16_le().ok()?;
                    let color = bs.read_uint32_le().ok()?;
                    fire!(self.callbacks, on_player_color, pid, color);
                }

                RPC_SET_WORLD_TIME => {
                    let hour = bs.read_uint8().ok()?;
                    fire!(self.callbacks, on_world_time, hour);
                }

                RPC_TOGGLE_SPECTATING => {
                    let spec = bs.read_uint32_le().ok()?;
                    fire!(self.callbacks, on_toggle_spectating, spec != 0);
                }

                RPC_SET_WANTED_LEVEL => {
                    let level = bs.read_uint8().ok()?;
                    fire!(self.callbacks, on_wanted_level, level);
                }

                RPC_SET_WEAPON_AMMO => {
                    let wid  = bs.read_uint8().ok()?;
                    let ammo = bs.read_uint16_le().ok()?;
                    fire!(self.callbacks, on_weapon_ammo, wid, ammo);
                }

                RPC_SET_GRAVITY => {
                    let g = bs.read_float_le().ok()?;
                    fire!(self.callbacks, on_gravity, g);
                }

                RPC_SET_WEATHER => {
                    let w = bs.read_uint8().ok()?;
                    fire!(self.callbacks, on_weather, w);
                }

                RPC_SET_PLAYER_SKIN => {
                    let pid  = bs.read_int32_le().ok()?;
                    let skin = bs.read_uint32_le().ok()?;
                    fire!(self.callbacks, on_player_skin, pid, skin);
                }

                RPC_SET_INTERIOR => {
                    let id = bs.read_uint8().ok()?;
                    fire!(self.callbacks, on_set_interior, id);
                }

                RPC_WORLD_VEHICLE_ADD => {
                    let vid      = bs.read_uint16_le().ok()?;
                    let model    = bs.read_int32_le().ok()?;
                    let x        = bs.read_float_le().ok()?;
                    let y        = bs.read_float_le().ok()?;
                    let z        = bs.read_float_le().ok()?;
                    let angle    = bs.read_float_le().ok()?;
                    let color1   = bs.read_uint8().ok()?;
                    let color2   = bs.read_uint8().ok()?;
                    let health   = bs.read_float_le().ok()?;
                    let interior = bs.read_uint8().ok()?;
                    let door_dmg  = bs.read_uint32_le().ok()?;
                    let panel_dmg = bs.read_uint32_le().ok()?;
                    let light_dmg = bs.read_uint8().ok()?;
                    let tire_dmg  = bs.read_uint8().ok()?;
                    let add_siren = bs.read_uint8().ok()?;
                    let mut mods = [0u8; 14];
                    bs.read_aligned_bytes(&mut mods).ok()?;
                    let paintjob    = bs.read_uint8().ok()?;
                    let body_color1 = bs.read_uint32_le().ok()?;
                    let body_color2 = bs.read_uint32_le().ok()?;
                    // u8 unk ignored
                    fire!(self.callbacks, on_vehicle_streamed_in,
                          vid, model, x, y, z, angle,
                          color1, color2, health, interior,
                          door_dmg, panel_dmg, light_dmg, tire_dmg,
                          add_siren, paintjob, body_color1, body_color2);
                }

                RPC_WORLD_VEHICLE_REMOVE => {
                    let vid = bs.read_uint16_le().ok()?;
                    fire!(self.callbacks, on_vehicle_streamed_out, vid);
                }

                RPC_DEATH_BROADCAST => {
                    let pid = bs.read_uint16_le().ok()?;
                    fire!(self.callbacks, on_player_death, pid);
                }

                _ => {}
            }
            Some(())
        })();

        // Always fire raw escape hatch
        fire!(self.callbacks, on_rpc, rpc_id, payload.to_vec());
        let _ = len; // suppress unused warning
    }

    fn process_packet_data(&self, data: &[u8]) {
        if data.is_empty() { return; }
        match data[0] {
            id if id == ID_TIMESTAMP => {
                if data.len() < 6 { return; }
                self.process_packet_data(&data[5..]);
            }
            id if id == ID_RPC => {
                if data.len() < 2 { return; }
                let mut bs = BitStream::from_bytes(data);
                bs.skip_bits(8); // ID_RPC
                let rpc_id = match bs.read_uint8() { Ok(v) => v, Err(_) => return };
                let bit_len = match bs.read_compressed_uint32() { Ok(v) => v, Err(_) => return };
                let byte_len = ((bit_len as usize) + 7) / 8;
                let mut payload = vec![0u8; byte_len];
                if byte_len > 0 {
                    if bs.read_bits(&mut payload, bit_len as i32, false).is_err() { return; }
                }
                self.handle_rpc(rpc_id, &payload);
            }
            id if id == ID_INTERNAL_PING => {
                if data.len() < 5 { return; }
                let ts = u32::from_le_bytes(data[1..5].try_into().unwrap());
                let mut resp = BitStream::new();
                resp.write_uint8(ID_CONNECTED_PONG);
                resp.write_uint32_le(ts);
                self.send_reliability_pkt(resp.as_bytes(), REL_UNRELIABLE, 0, 0);
            }
            id if id == ID_DISCONNECTION_NOTIFICATION || id == ID_CONNECTION_LOST => {
                self.running.store(false, Ordering::Relaxed);
                fire!(self.callbacks, on_disconnect);
            }
            id if id == ID_AUTH_KEY => {
                self.handle_auth_key_raw(data);
            }
            id if id == ID_CONNECTION_REQUEST_ACCEPTED => {
                if !self.connected.load(Ordering::Relaxed) {
                    self.handle_connection_accepted_raw(data);
                }
            }
            _ => {}
        }
    }

    fn send_keepalive(&self) {
        // OnFootData struct (68 bytes), packed:
        // lrAnalog(u16) udAnalog(u16) wKeys(u16)
        // vecPos(3xf32) fQuaternion(4xf32)
        // byteHealth(u8) byteArmour(u8) weapon(u8) specialAction(u8)
        // moveSpeed(3xf32) surfOffsets(3xf32)
        // wSurfInfo(u16) animID(i32)
        let mut pkt = vec![0u8; 1 + 68];
        pkt[0] = ID_PLAYER_SYNC;
        // vecPos.z = 3.0 at offset 14
        pkt[1 + 14..1 + 18].copy_from_slice(&3.0f32.to_le_bytes());
        // fQuaternion.w = 1.0 at offset 30
        pkt[1 + 30..1 + 34].copy_from_slice(&1.0f32.to_le_bytes());
        // byteHealth = 100 at offset 34
        pkt[1 + 34] = 100;
        // wSurfInfo = 0xFFFF at offset 62
        pkt[1 + 62] = 0xFF;
        pkt[1 + 63] = 0xFF;
        self.send_reliability_pkt(&pkt, REL_UNRELIABLE_SEQUENCED, 0, 0);
    }

    // ─── Public API ───────────────────────────────────────────────────────────

    pub fn connect(&self, timeout_sec: f64) -> bool {
        let server_v4 = match resolve_host(&self.host, self.port) {
            Some(v) => v,
            None => return false,
        };

        let sock = match UdpSocket::bind("0.0.0.0:0") {
            Ok(s) => s,
            Err(_) => return false,
        };

        {
            let mut guard = self.net.lock().unwrap();
            *guard = Some(NetState {
                sock: Arc::new(sock),
                server_addr: SocketAddr::from((server_v4, self.port)),
            });
        }

        let (sock_arc, _) = {
            let guard = self.net.lock().unwrap();
            let ns = guard.as_ref().unwrap();
            (Arc::clone(&ns.sock), ns.server_addr)
        };

        let half = Duration::from_secs_f64(timeout_sec / 2.0);
        if !self.do_handshake(&sock_arc, server_v4, half) { return false; }
        if !self.do_connection_request(&sock_arc, server_v4, half) { return false; }
        self.connected.load(Ordering::Relaxed)
    }

    pub fn run(&self) {
        self.running.store(true, Ordering::Relaxed);

        let (sock, server_v4) = {
            let guard = self.net.lock().unwrap();
            match guard.as_ref() {
                Some(ns) => {
                    let v4 = match ns.server_addr.ip() {
                        IpAddr::V4(v) => v,
                        _ => return,
                    };
                    (Arc::clone(&ns.sock), v4)
                }
                None => return,
            }
        };

        let mut split_buf       = SplitBuffer::new();
        let mut last_keepalive  = Instant::now();
        let mut last_ack_flush  = Instant::now();
        let mut last_scores     = Instant::now();
        let mut recv_buf        = [0u8; 2048];

        while self.running.load(Ordering::Relaxed) {
            let now = Instant::now();

            if now.duration_since(last_ack_flush) > Duration::from_millis(50) {
                self.flush_acks();
                last_ack_flush = now;
            }
            if now.duration_since(last_keepalive) > Duration::from_millis(500) {
                // Only send on-foot sync after spawning — the reference (misc_funcs.cpp)
                // calls onFootUpdateAtNormalPos() only inside the iSpawned == 1 branch.
                // Sending it pre-spawn confuses the server's player state machine.
                if self.spawned.load(Ordering::Relaxed) {
                    self.send_keepalive();
                }
                last_keepalive = now;
            }
            if now.duration_since(last_scores) > Duration::from_secs(3) {
                self.send_rpc(RPC_UPDATE_SCORES, &[], REL_RELIABLE);
                last_scores = now;
            }

            let deadline = Instant::now() + Duration::from_millis(30);
            let _ = sock.set_read_timeout(Some(Duration::from_millis(30)));
            let n = match sock.recv_from(&mut recv_buf) {
                Ok((n, src)) if matches!(src.ip(), IpAddr::V4(v4) if v4 == server_v4) => n,
                _ => continue,
            };

            let data = &recv_buf[..n];

            // Raw auth key
            if n >= 2 && data[0] == ID_AUTH_KEY {
                self.handle_auth_key_raw(data);
                continue;
            }

            let result = match rel_parse(data, &mut split_buf) {
                Some(r) => r,
                None => continue,
            };
            if result.is_ack { continue; }

            for pkt in &result.packets {
                if pkt.reliability == crate::reliability::Reliability::Reliable
                    || pkt.reliability == crate::reliability::Reliability::ReliableOrdered
                {
                    self.pending_acks.lock().unwrap().push(pkt.msg_num);
                }
                self.process_packet_data(&pkt.data);
            }

            let _ = deadline; // keep deadline in scope
        }
    }

    pub fn stop(&self) {
        self.running.store(false, Ordering::Relaxed);
    }

    pub fn disconnect(&self) {
        self.running.store(false, Ordering::Relaxed);
        self.spawned.store(false, Ordering::Relaxed);
        let disc = vec![ID_DISCONNECTION_NOTIFICATION, 0];
        self.send_reliability_pkt(&disc, REL_RELIABLE, 0, 0);
        std::thread::sleep(Duration::from_millis(100));
        if let Ok(mut guard) = self.net.lock() {
            *guard = None;
        }
    }

    // ─── Send helpers ─────────────────────────────────────────────────────────

    pub fn send_dialog_response(&self, dialog_id: u16, button: u8, list_item: u16, text: &str) {
        let mut bs = BitStream::new();
        bs.write_uint16_le(dialog_id);
        bs.write_uint8(button);
        bs.write_uint16_le(list_item);
        let rlen = text.len().min(255) as u8;
        bs.write_uint8(rlen);
        if rlen > 0 {
            bs.write_aligned_bytes(&text.as_bytes()[..rlen as usize]);
        }
        self.send_rpc(RPC_DIALOG_RESPONSE, bs.as_bytes(), REL_RELIABLE_ORDERED);
    }

    pub fn send_death(&self, weapon_id: u8, killer_id: u16) {
        let mut bs = BitStream::new();
        bs.write_uint8(weapon_id);
        bs.write_uint16_le(killer_id);
        self.send_rpc(RPC_DEATH, bs.as_bytes(), REL_RELIABLE_ORDERED);
    }

    pub fn send_enter_vehicle(&self, vehicle_id: u16, is_passenger: bool) {
        let mut bs = BitStream::new();
        bs.write_uint16_le(vehicle_id);
        bs.write_uint8(is_passenger as u8);
        self.send_rpc(RPC_ENTER_VEHICLE, bs.as_bytes(), REL_RELIABLE_SEQUENCED);
    }

    pub fn send_exit_vehicle(&self, vehicle_id: u16) {
        let mut bs = BitStream::new();
        bs.write_uint16_le(vehicle_id);
        self.send_rpc(RPC_EXIT_VEHICLE, bs.as_bytes(), REL_RELIABLE_SEQUENCED);
    }

    pub fn send_command(&self, text: &str) {
        let mut bs = BitStream::new();
        bs.write_uint32_le(text.len() as u32);
        if !text.is_empty() {
            bs.write_aligned_bytes(text.as_bytes());
        }
        self.send_rpc(RPC_SERVER_COMMAND, bs.as_bytes(), REL_RELIABLE);
    }
}

// ── Network helpers ───────────────────────────────────────────────────────────

fn resolve_host(host: &str, port: u16) -> Option<Ipv4Addr> {
    let s = format!("{}:{}", host, port);
    for addr in s.to_socket_addrs().ok()? {
        if let IpAddr::V4(v4) = addr.ip() {
            return Some(v4);
        }
    }
    None
}

// Receive a datagram from `server_v4` before `deadline`.
// Returns None only if deadline is reached without a matching packet.
fn recv_deadline(sock: &UdpSocket, buf: &mut [u8], server_v4: Ipv4Addr, deadline: Instant) -> Option<usize> {
    recv_deadline_cap(sock, buf, server_v4, deadline, Duration::from_secs(1))
}

// Like recv_deadline but caps each poll to `cap`.
fn recv_deadline_cap(sock: &UdpSocket, buf: &mut [u8], server_v4: Ipv4Addr, deadline: Instant, cap: Duration) -> Option<usize> {
    loop {
        let now = Instant::now();
        if now >= deadline { return None; }
        let remaining = deadline - now;
        let poll = remaining.min(cap).max(Duration::from_millis(1));
        let _ = sock.set_read_timeout(Some(poll));
        match sock.recv_from(buf) {
            Ok((n, src)) if matches!(src.ip(), IpAddr::V4(v4) if v4 == server_v4) => {
                return Some(n);
            }
            _ => {}
        }
    }
}
