"""SA:MP connection and protocol exception hierarchy."""

__all__ = [
    "SAMPConnectionError",
    "SAMPBanned",
    "SAMPInvalidPassword",
    "SAMPServerFull",
    "SAMPRejected",
    "SAMPHandshakeTimeout",
    "SAMPConnectionTimeout",
    "SAMPHostResolutionError",
    "SAMPProxyError",
    "SAMPSocketError",
]


class SAMPConnectionError(Exception):
    """Base class for all SA:MP connection errors.

    Raised by :meth:`SAMPBot.start` when the connection attempt fails.
    Catch this to handle any connection failure regardless of cause.
    """


class SAMPBanned(SAMPConnectionError):
    """The client's IP address is banned from the server."""


class SAMPInvalidPassword(SAMPConnectionError):
    """The server password supplied to :class:`SAMPBot` is incorrect."""


class SAMPServerFull(SAMPConnectionError):
    """The server has no free player slots."""


class SAMPRejected(SAMPConnectionError):
    """The server actively refused the connection attempt."""


class SAMPHandshakeTimeout(SAMPConnectionError):
    """The server did not complete the open-connection handshake in time."""


class SAMPConnectionTimeout(SAMPConnectionError):
    """The server did not accept the connection request in time."""


class SAMPHostResolutionError(SAMPConnectionError):
    """The server hostname could not be resolved."""


class SAMPProxyError(SAMPConnectionError):
    """The SOCKS5 proxy handshake failed."""


class SAMPSocketError(SAMPConnectionError):
    """The local UDP socket could not be bound."""
