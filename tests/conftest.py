"""The tool must run offline, so every test runs with non-loopback sockets blocked."""
import ipaddress
import socket

import pytest


def _is_loopback(host) -> bool:
    if host in (None, "", b""):
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def block_non_loopback(monkeypatch):
    real_connect, real_connect_ex, real_getaddrinfo = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo

    def check(host):
        if not _is_loopback(host):
            raise OSError(f"blocked: tests may not reach {host!r}")

    def connect(self, address):
        if isinstance(address, tuple):  # AF_UNIX addresses are str/bytes
            check(address[0])
        return real_connect(self, address)

    def connect_ex(self, address):
        if isinstance(address, tuple):
            check(address[0])
        return real_connect_ex(self, address)

    def getaddrinfo(host, *args, **kwargs):
        check(host)
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
