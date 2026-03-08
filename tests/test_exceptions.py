"""Tests for the SAMPConnectionError exception hierarchy."""

import pytest

from pyraksamp import (
    SAMPConnectionError,
    SAMPBanned,
    SAMPInvalidPassword,
    SAMPServerFull,
    SAMPRejected,
    SAMPHandshakeTimeout,
    SAMPConnectionTimeout,
    SAMPHostResolutionError,
    SAMPProxyError,
    SAMPSocketError,
)

ALL_SUBCLASSES = [
    SAMPBanned,
    SAMPInvalidPassword,
    SAMPServerFull,
    SAMPRejected,
    SAMPHandshakeTimeout,
    SAMPConnectionTimeout,
    SAMPHostResolutionError,
    SAMPProxyError,
    SAMPSocketError,
]


# ── Base class ─────────────────────────────────────────────────────────────────


def test_base_is_exception_subclass():
    assert issubclass(SAMPConnectionError, Exception)


def test_base_can_be_raised_and_caught():
    with pytest.raises(Exception):
        raise SAMPConnectionError("base error")


# ── Inheritance ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("cls", ALL_SUBCLASSES, ids=lambda c: c.__name__)
def test_subclass_inherits_base(cls):
    assert issubclass(cls, SAMPConnectionError)


@pytest.mark.parametrize("cls", ALL_SUBCLASSES, ids=lambda c: c.__name__)
def test_subclass_inherits_exception(cls):
    assert issubclass(cls, Exception)


def test_all_subclasses_distinct():
    assert len(set(id(c) for c in ALL_SUBCLASSES)) == len(ALL_SUBCLASSES)


# ── Raise / catch ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("cls", ALL_SUBCLASSES, ids=lambda c: c.__name__)
def test_catch_by_specific_class(cls):
    with pytest.raises(cls):
        raise cls("msg")


@pytest.mark.parametrize("cls", ALL_SUBCLASSES, ids=lambda c: c.__name__)
def test_catch_by_base_class(cls):
    with pytest.raises(SAMPConnectionError):
        raise cls("msg")


@pytest.mark.parametrize("cls", ALL_SUBCLASSES, ids=lambda c: c.__name__)
def test_message_preserved(cls):
    try:
        raise cls("specific message")
    except cls as e:
        assert "specific message" in str(e)


# ── Sibling isolation ──────────────────────────────────────────────────────────


def test_banned_not_caught_as_invalid_password():
    with pytest.raises(SAMPBanned):
        try:
            raise SAMPBanned("banned")
        except SAMPInvalidPassword:
            pytest.fail("SAMPBanned should not be caught as SAMPInvalidPassword")


def test_server_full_not_caught_as_timeout():
    with pytest.raises(SAMPServerFull):
        try:
            raise SAMPServerFull("full")
        except SAMPHandshakeTimeout:
            pytest.fail("SAMPServerFull should not be caught as SAMPHandshakeTimeout")
