# Exceptions

## Connection exceptions

All connection exceptions inherit from `SAMPConnectionError`.

```
SAMPConnectionError
├── SAMPBanned
├── SAMPInvalidPassword
├── SAMPServerFull
├── SAMPRejected
├── SAMPHandshakeTimeout
├── SAMPConnectionTimeout
├── SAMPHostResolutionError
├── SAMPProxyError
└── SAMPSocketError
```

### `SAMPConnectionError`
Base class for all connection failures. Raised by `SAMPBot.start()`.

### `SAMPBanned`
The client's IP address is banned from the server.

### `SAMPInvalidPassword`
The server password supplied to `SAMPBot` is wrong.

### `SAMPServerFull`
The server has no free player slots.

### `SAMPRejected`
The server actively refused the connection attempt.

### `SAMPHandshakeTimeout`
The server did not complete the open-connection handshake within the timeout period.

### `SAMPConnectionTimeout`
The server did not accept the connection request within the timeout period.

### `SAMPHostResolutionError`
The server hostname could not be resolved.

### `SAMPProxyError`
The SOCKS5 proxy handshake failed.

### `SAMPSocketError`
The local UDP socket could not be bound.

---

## Dialog exceptions

::: pyraksamp.DialogAlreadyRespondedError
