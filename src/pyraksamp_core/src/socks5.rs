//! SOCKS5 proxy client — RFC 1928 (protocol) + RFC 1929 (username/password auth).
//!
//! Only the UDP ASSOCIATE command is implemented since SA:MP uses UDP.

use std::io::{self, Read, Write};
use std::net::{IpAddr, Ipv4Addr, SocketAddr, TcpStream, ToSocketAddrs};
use std::time::Duration;

// ── Constants ─────────────────────────────────────────────────────────────────

const SOCKS_VER:          u8 = 0x05;
const AUTH_NONE:          u8 = 0x00;
const AUTH_USERPASS:      u8 = 0x02;
const AUTH_NO_ACCEPTABLE: u8 = 0xFF;
const USERPASS_VER:       u8 = 0x01;
const CMD_UDP_ASSOCIATE:  u8 = 0x03;
const RSV:                u8 = 0x00;
const ATYP_IPV4:          u8 = 0x01;
const ATYP_DOMAIN:        u8 = 0x03;
const REP_SUCCESS:        u8 = 0x00;

// ── Public types ──────────────────────────────────────────────────────────────

/// Configuration for a SOCKS5 proxy.
#[derive(Clone)]
pub struct ProxyConfig {
    pub host: String,
    pub port: u16,
    /// Optional username/password authentication.
    pub auth: Option<(String, String)>,
}

// ── SOCKS5 UDP ASSOCIATE ──────────────────────────────────────────────────────

/// Perform a SOCKS5 UDP ASSOCIATE handshake.
///
/// Returns `(relay_addr, tcp_control_stream)`.  The `TcpStream` **must** be
/// kept alive for the entire UDP session — closing it causes the proxy to drop
/// the relay.
pub fn udp_associate(proxy: &ProxyConfig) -> io::Result<(SocketAddr, TcpStream)> {
    let proxy_addr = format!("{}:{}", proxy.host, proxy.port)
        .to_socket_addrs()?
        .next()
        .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "cannot resolve proxy host"))?;

    let mut stream = TcpStream::connect_timeout(&proxy_addr, Duration::from_secs(10))?;
    stream.set_read_timeout(Some(Duration::from_secs(10)))?;
    stream.set_write_timeout(Some(Duration::from_secs(10)))?;

    // ── Method negotiation ────────────────────────────────────────────────────
    let method = if proxy.auth.is_some() { AUTH_USERPASS } else { AUTH_NONE };
    stream.write_all(&[SOCKS_VER, 1u8, method])?;

    let mut resp = [0u8; 2];
    stream.read_exact(&mut resp)?;

    if resp[0] != SOCKS_VER {
        return Err(io::Error::new(io::ErrorKind::Other, "unexpected SOCKS version in method reply"));
    }
    match resp[1] {
        AUTH_NO_ACCEPTABLE => {
            return Err(io::Error::new(io::ErrorKind::PermissionDenied, "proxy rejected all auth methods"));
        }
        m if m != method => {
            return Err(io::Error::new(io::ErrorKind::Other, "proxy chose unexpected auth method"));
        }
        _ => {}
    }

    // ── Username/password auth (RFC 1929) ─────────────────────────────────────
    if method == AUTH_USERPASS {
        let (user, pass) = proxy.auth.as_ref().unwrap();
        if user.len() > 255 || pass.len() > 255 {
            return Err(io::Error::new(io::ErrorKind::InvalidInput, "username or password too long"));
        }
        let mut req = Vec::with_capacity(3 + user.len() + pass.len());
        req.push(USERPASS_VER);
        req.push(user.len() as u8);
        req.extend_from_slice(user.as_bytes());
        req.push(pass.len() as u8);
        req.extend_from_slice(pass.as_bytes());
        stream.write_all(&req)?;

        stream.read_exact(&mut resp)?;
        if resp[1] != 0x00 {
            return Err(io::Error::new(io::ErrorKind::PermissionDenied, "SOCKS5 username/password auth failed"));
        }
    }

    // ── UDP ASSOCIATE request ─────────────────────────────────────────────────
    // We pass 0.0.0.0:0 — the proxy derives our address from the TCP source.
    let req = [SOCKS_VER, CMD_UDP_ASSOCIATE, RSV, ATYP_IPV4, 0, 0, 0, 0, 0, 0];
    stream.write_all(&req)?;

    // ── Parse reply ───────────────────────────────────────────────────────────
    let mut hdr = [0u8; 4]; // VER, REP, RSV, ATYP
    stream.read_exact(&mut hdr)?;

    if hdr[0] != SOCKS_VER {
        return Err(io::Error::new(io::ErrorKind::Other, "unexpected SOCKS version in reply"));
    }
    if hdr[1] != REP_SUCCESS {
        return Err(io::Error::new(
            io::ErrorKind::Other,
            format!("SOCKS5 UDP ASSOCIATE failed: reply code {:#04x}", hdr[1]),
        ));
    }

    let relay: SocketAddr = match hdr[3] {
        ATYP_IPV4 => {
            let mut buf = [0u8; 6]; // 4-byte addr + 2-byte port
            stream.read_exact(&mut buf)?;
            let ip = Ipv4Addr::new(buf[0], buf[1], buf[2], buf[3]);
            let port = u16::from_be_bytes([buf[4], buf[5]]);
            // Many proxies return 0.0.0.0 meaning "same host as TCP connection"
            let ip = if ip.is_unspecified() {
                match proxy_addr {
                    SocketAddr::V4(v4) => *v4.ip(),
                    SocketAddr::V6(_) => ip,
                }
            } else {
                ip
            };
            SocketAddr::from((ip, port))
        }
        ATYP_DOMAIN => {
            let mut len = [0u8; 1];
            stream.read_exact(&mut len)?;
            let mut domain = vec![0u8; len[0] as usize];
            stream.read_exact(&mut domain)?;
            let mut port_buf = [0u8; 2];
            stream.read_exact(&mut port_buf)?;
            let host = String::from_utf8_lossy(&domain);
            let port = u16::from_be_bytes(port_buf);
            format!("{}:{}", host, port)
                .to_socket_addrs()?
                .next()
                .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "cannot resolve relay host"))?
        }
        other => {
            return Err(io::Error::new(
                io::ErrorKind::Other,
                format!("unsupported relay address type: {:#04x}", other),
            ));
        }
    };

    // Keep the control stream alive but don't timeout on idle reads.
    stream.set_read_timeout(None)?;
    stream.set_write_timeout(None)?;

    Ok((relay, stream))
}

// ── UDP datagram helpers ──────────────────────────────────────────────────────

/// Wrap a UDP payload with a SOCKS5 UDP request header for sending through the
/// relay.  Only IPv4 destinations are supported (matching SA:MP's UDP usage).
///
/// Header layout (RFC 1928 §7):
/// ```text
/// +----+------+------+----------+----------+----------+
/// |RSV | FRAG | ATYP | DST.ADDR | DST.PORT |   DATA   |
/// +----+------+------+----------+----------+----------+
/// | 2  |  1   |  1   |    4     |    2     | variable |
/// +----+------+------+----------+----------+----------+
/// ```
pub fn wrap_packet(payload: &[u8], dest: SocketAddr) -> Vec<u8> {
    let mut out = Vec::with_capacity(10 + payload.len());
    out.extend_from_slice(&[0x00, 0x00]); // RSV
    out.push(0x00);                        // FRAG = 0 (no fragmentation)
    match dest.ip() {
        IpAddr::V4(v4) => {
            out.push(ATYP_IPV4);
            out.extend_from_slice(&v4.octets());
        }
        IpAddr::V6(_) => {
            // SA:MP only uses IPv4; fall back to a zeroed address to avoid panics.
            out.push(ATYP_IPV4);
            out.extend_from_slice(&[0u8; 4]);
        }
    }
    out.extend_from_slice(&dest.port().to_be_bytes());
    out.extend_from_slice(payload);
    out
}

/// Strip a SOCKS5 UDP header from a datagram received from the relay.
///
/// Returns `(source_ipv4, header_length)` on success, or `None` if the
/// datagram is malformed, fragmented, or uses an unsupported address type.
/// The caller should `buf.copy_within(header_length..n, 0)` to shift the
/// payload to the start of the buffer.
pub fn unwrap_packet(data: &[u8]) -> Option<(Ipv4Addr, usize)> {
    // Minimum for IPv4: 2(RSV) + 1(FRAG) + 1(ATYP) + 4(addr) + 2(port) = 10
    if data.len() < 10 { return None; }
    if data[2] != 0x00 { return None; } // fragmentation not supported
    match data[3] {
        ATYP_IPV4 => {
            let src = Ipv4Addr::new(data[4], data[5], data[6], data[7]);
            // data[8..10] = source port — we don't need it; server port is known
            Some((src, 10))
        }
        _ => None, // domain / IPv6 not expected from a game server
    }
}
