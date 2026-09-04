from __future__ import annotations

import ipaddress
import os
import socket
from typing import Any

import pytest


def _loopback_address(address: Any) -> bool:
    if not isinstance(address, tuple) or not address:
        return False
    host = address[0]
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(str(host)).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def no_external_network_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    if os.getenv("INFOBANK_TEST_NO_NETWORK") != "1":
        return

    original_connect = socket.socket.connect

    def guarded_connect(self: socket.socket, address: Any) -> Any:
        if _loopback_address(address):
            return original_connect(self, address)
        raise RuntimeError("External network access is disabled for offline tests")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
