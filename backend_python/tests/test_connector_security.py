from __future__ import annotations

import json

import pytest

import gmail_connector


USER_ID = "00000000-0000-0000-0000-000000000301"


def test_oauth_state_is_confidential_tamper_evident_and_expiring(monkeypatch) -> None:
    monkeypatch.setenv("OAUTH_STATE_SECRET", "isolated-oauth-state-secret")
    monkeypatch.setattr(gmail_connector, "_unix_time", lambda: 1_900_000_000)
    verifier = "v" * 64
    state = gmail_connector._encode_state(USER_ID, verifier)

    assert USER_ID not in state
    assert verifier not in state
    assert gmail_connector.decode_state(state) == (USER_ID, verifier)
    with pytest.raises(ValueError, match="Invalid or expired OAuth state"):
        gmail_connector.decode_state(state[:-1] + ("A" if state[-1] != "A" else "B"))
    with pytest.raises(ValueError, match="Invalid OAuth state"):
        gmail_connector.decode_state(USER_ID)

    monkeypatch.setattr(
        gmail_connector,
        "_unix_time",
        lambda: 1_900_000_000 + gmail_connector.OAUTH_STATE_TTL_SECONDS + 1,
    )
    with pytest.raises(ValueError, match="Invalid or expired OAuth state"):
        gmail_connector.decode_state(state)


def test_oauth_state_requires_matching_browser_cookie(monkeypatch) -> None:
    monkeypatch.setenv("OAUTH_STATE_SECRET", "isolated-oauth-state-secret")
    monkeypatch.setattr(gmail_connector, "_unix_time", lambda: 1_900_000_000)
    state = gmail_connector._encode_state(USER_ID, "p" * 64)
    binding = gmail_connector.state_cookie_binding(state)

    assert gmail_connector.state_cookie_matches(state, binding) is True
    assert gmail_connector.state_cookie_matches(state, None) is False
    assert gmail_connector.state_cookie_matches(state + "x", binding) is False


def test_connector_tokens_are_encrypted_and_legacy_plaintext_is_refused(monkeypatch) -> None:
    monkeypatch.setenv("CONNECTOR_TOKEN_ENCRYPTION_KEY", "isolated-connector-token-secret")
    token = json.dumps({"token": "access-secret", "refresh_token": "refresh-secret"})
    encrypted = gmail_connector.encrypt_connector_token(token)

    assert encrypted.startswith(gmail_connector.TOKEN_CIPHERTEXT_PREFIX)
    assert "access-secret" not in encrypted
    assert "refresh-secret" not in encrypted
    assert json.loads(gmail_connector.decrypt_connector_token(encrypted)) == json.loads(token)
    with pytest.raises(RuntimeError, match="Legacy plaintext connector token"):
        gmail_connector.decrypt_connector_token(token)
