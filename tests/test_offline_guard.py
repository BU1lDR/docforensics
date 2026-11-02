import socket

import pytest


def test_public_address_connect_is_blocked():
    with pytest.raises(OSError, match="blocked"):
        socket.create_connection(("93.184.216.34", 80), timeout=1)


def test_public_name_lookup_is_blocked():
    with pytest.raises(OSError, match="blocked"):
        socket.getaddrinfo("example.com", 80)


def test_loopback_connect_is_allowed():
    with socket.socket() as srv:
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        socket.create_connection(srv.getsockname(), timeout=2).close()
