"""Gmail OAuth connector service for CITDS EvidenceUnit sync.

This module provides the production-oriented path beyond the import contract:
OAuth URL generation, callback token storage, and Gmail thread/message sync into
EvidenceUnit records. The sync is intentionally conservative: imported messages
become owned EvidenceUnits and then flow through the same policy/classifier/action
reconstruction pipeline as all other evidence.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

from sqlalchemy.orm import Session
from cryptography.fernet import Fernet, InvalidToken

import evidence_service
import models

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
PROVIDER = "gmail"
DEFAULT_APP_BASE_URL = "http://127.0.0.1:8000"
OAUTH_STATE_VERSION = "infobank-oauth-state-v1"
OAUTH_STATE_TTL_SECONDS = 600
OAUTH_STATE_COOKIE = "infobank_gmail_oauth_state"
TOKEN_CIPHERTEXT_PREFIX = "fernet:v1:"


def _app_base_url() -> str:
    return os.getenv("APP_BASE_URL", DEFAULT_APP_BASE_URL).rstrip("/")


def _redirect_uri() -> str:
    return os.getenv("GOOGLE_REDIRECT_URI") or f"{_app_base_url()}/api/connectors/gmail/callback"


def _allow_insecure_transport_for_localhost(redirect_uri: str) -> None:
    """Allow HTTP OAuth callbacks only for local development.

    oauthlib rejects plain HTTP by default. Google local testing commonly uses
    localhost/127.0.0.1 redirect URIs, so we opt in only for those hosts. Do not
    enable this for a deployed public URL.
    """

    parsed = urlparse(redirect_uri)
    if parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}:
        os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")


def _unix_time() -> int:
    return int(time.time())


def _derived_fernet(env_name: str, context: str) -> Fernet:
    secret = os.getenv(env_name) or os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError(f"{env_name} or JWT_SECRET_KEY must be configured.")
    digest = hashlib.sha256(f"{context}\0{secret}".encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _state_cipher() -> Fernet:
    return _derived_fernet("OAUTH_STATE_SECRET", OAUTH_STATE_VERSION)


def _token_cipher() -> Fernet:
    return _derived_fernet("CONNECTOR_TOKEN_ENCRYPTION_KEY", "infobank-connector-token-v1")


def _encode_state(user_id: str, code_verifier: str) -> str:
    now = _unix_time()
    payload = {
        "type": OAUTH_STATE_VERSION,
        "user_id": user_id,
        "code_verifier": code_verifier,
        "nonce": secrets.token_urlsafe(24),
        "issued_at": now,
        "expires_at": now + OAUTH_STATE_TTL_SECONDS,
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return "v1." + _state_cipher().encrypt(raw).decode("ascii")


def decode_state(state: str) -> Tuple[str, str]:
    """Validate and decrypt a short-lived Gmail OAuth state token."""

    if not state or not state.startswith("v1."):
        raise ValueError("Invalid OAuth state.")
    try:
        raw = _state_cipher().decrypt(state[3:].encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
        user_id = str(payload["user_id"])
        code_verifier = str(payload["code_verifier"])
        uuid.UUID(user_id)
        if payload.get("type") != OAUTH_STATE_VERSION:
            raise ValueError("Invalid OAuth state type.")
        if not payload.get("nonce"):
            raise ValueError("OAuth state nonce is missing.")
        if int(payload.get("expires_at", 0)) < _unix_time():
            raise ValueError("OAuth state has expired.")
        if not 43 <= len(code_verifier) <= 128:
            raise ValueError("Invalid OAuth PKCE verifier.")
        return user_id, code_verifier
    except (InvalidToken, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError("Invalid or expired OAuth state.") from exc


def state_cookie_binding(state: str) -> str:
    secret = os.getenv("OAUTH_STATE_SECRET") or os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError("OAUTH_STATE_SECRET or JWT_SECRET_KEY must be configured.")
    return hmac.new(
        secret.encode("utf-8"),
        f"{OAUTH_STATE_VERSION}\0{state}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def state_cookie_matches(state: str, cookie_value: str | None) -> bool:
    if not state or not cookie_value:
        return False
    return hmac.compare_digest(state_cookie_binding(state), cookie_value)


def encrypt_connector_token(token_json: str) -> str:
    parsed = json.loads(token_json)
    if not isinstance(parsed, dict):
        raise ValueError("Connector token payload must be a JSON object.")
    ciphertext = _token_cipher().encrypt(
        json.dumps(parsed, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).decode("ascii")
    return TOKEN_CIPHERTEXT_PREFIX + ciphertext


def decrypt_connector_token(stored_value: str) -> str:
    if not stored_value.startswith(TOKEN_CIPHERTEXT_PREFIX):
        raise RuntimeError("Legacy plaintext connector token detected; reconnect Gmail to replace it securely.")
    try:
        raw = _token_cipher().decrypt(stored_value[len(TOKEN_CIPHERTEXT_PREFIX):].encode("ascii"))
        parsed = json.loads(raw.decode("utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError("Connector token payload must be a JSON object.")
        return json.dumps(parsed, separators=(",", ":"), sort_keys=True)
    except (InvalidToken, json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError("Encrypted connector token is invalid or cannot be decrypted.") from exc


def connector_account_is_usable(account: models.ConnectorAccount | None) -> bool:
    return bool(
        account
        and account.status == "connected"
        and account.token_json.startswith(TOKEN_CIPHERTEXT_PREFIX)
    )


def _new_code_verifier() -> str:
    # RFC 7636: 43-128 chars from the unreserved URI set. token_urlsafe(64) is
    # usually 86 chars and accepted by google-auth-oauthlib/oauthlib.
    return secrets.token_urlsafe(64)


def _require_google_libs():
    try:
        from google.oauth2.credentials import Credentials  # noqa: F401
        from google_auth_oauthlib.flow import Flow  # noqa: F401
        from googleapiclient.discovery import build  # noqa: F401
    except Exception as exc:
        raise RuntimeError(
            "Google connector dependencies are missing. Run pip install -r requirements.txt."
        ) from exc


def _client_config() -> Dict[str, Any]:
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = _redirect_uri()
    if not client_id or not client_secret:
        raise RuntimeError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set for Gmail OAuth.")
    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }


def create_authorization_url(user_id: str) -> Dict[str, str]:
    _require_google_libs()
    from google_auth_oauthlib.flow import Flow

    redirect_uri = _redirect_uri()
    _allow_insecure_transport_for_localhost(redirect_uri)
    code_verifier = _new_code_verifier()
    state = _encode_state(user_id, code_verifier)
    flow = Flow.from_client_config(
        _client_config(),
        scopes=SCOPES,
        redirect_uri=redirect_uri,
        autogenerate_code_verifier=False,
    )
    flow.code_verifier = code_verifier
    auth_url, returned_state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return {"authorization_url": auth_url, "state": returned_state}


def store_callback_tokens(db: Session, user_id: str, authorization_response_url: str, code_verifier: str | None = None) -> models.ConnectorAccount:
    _require_google_libs()
    from google_auth_oauthlib.flow import Flow

    redirect_uri = _redirect_uri()
    _allow_insecure_transport_for_localhost(redirect_uri)
    flow = Flow.from_client_config(
        _client_config(),
        scopes=SCOPES,
        redirect_uri=redirect_uri,
        autogenerate_code_verifier=False,
    )
    if code_verifier:
        flow.code_verifier = code_verifier
    flow.fetch_token(authorization_response=authorization_response_url)
    credentials = flow.credentials

    existing = db.query(models.ConnectorAccount).filter(
        models.ConnectorAccount.user_id == user_id,
        models.ConnectorAccount.provider == PROVIDER,
    ).first()
    token_json = encrypt_connector_token(credentials.to_json())
    metadata_json = json.dumps({"scopes": SCOPES, "token_encryption": "fernet-v1"}, ensure_ascii=False)
    if existing:
        existing.token_json = token_json
        existing.metadata_json = metadata_json
        existing.status = "connected"
        db.commit()
        db.refresh(existing)
        return existing

    account = models.ConnectorAccount(
        id=str(uuid.uuid4()),
        user_id=user_id,
        provider=PROVIDER,
        status="connected",
        token_json=token_json,
        metadata_json=metadata_json,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def _credentials_from_account(account: models.ConnectorAccount):
    _require_google_libs()
    from google.oauth2.credentials import Credentials

    return Credentials.from_authorized_user_info(json.loads(decrypt_connector_token(account.token_json)), SCOPES)


def _gmail_service(account: models.ConnectorAccount):
    _require_google_libs()
    from googleapiclient.discovery import build

    return build("gmail", "v1", credentials=_credentials_from_account(account))


def _headers_to_dict(headers: List[Dict[str, str]]) -> Dict[str, str]:
    return {h.get("name", "").lower(): h.get("value", "") for h in headers or []}


def _extract_text_from_payload(payload: Dict[str, Any]) -> str:
    if not payload:
        return ""
    body = payload.get("body", {}) or {}
    data = body.get("data")
    if data:
        try:
            import base64 as b64
            return b64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="ignore")
        except Exception:
            return ""
    parts = payload.get("parts") or []
    texts = []
    for part in parts:
        mime = part.get("mimeType", "")
        if mime.startswith("text/"):
            texts.append(_extract_text_from_payload(part))
    return "\n".join(t for t in texts if t).strip()


def sync_gmail_messages(db: Session, user_id: str, max_results: int = 25, query: str = "") -> Dict[str, Any]:
    account = db.query(models.ConnectorAccount).filter(
        models.ConnectorAccount.user_id == user_id,
        models.ConnectorAccount.provider == PROVIDER,
        models.ConnectorAccount.status == "connected",
    ).first()
    if not account:
        raise RuntimeError("Gmail is not connected for this user.")

    service = _gmail_service(account)
    list_response = service.users().messages().list(userId="me", maxResults=max_results, q=query).execute()
    messages = list_response.get("messages", [])
    units = []

    for msg_ref in messages:
        message = service.users().messages().get(userId="me", id=msg_ref["id"], format="full").execute()
        payload = message.get("payload", {})
        headers = _headers_to_dict(payload.get("headers", []))
        subject = headers.get("subject") or "Gmail message"
        sender = headers.get("from")
        recipients = headers.get("to")
        sent_at = None
        internal_date = message.get("internalDate")
        if internal_date:
            try:
                import datetime
                sent_at = datetime.datetime.fromtimestamp(int(internal_date) / 1000).isoformat()
            except Exception:
                sent_at = None
        body = _extract_text_from_payload(payload) or message.get("snippet", "")
        labels = message.get("labelIds", [])
        direction = "outbound" if "SENT" in labels else "inbound"
        content = (
            f"Gmail message. Direction: {direction}. Subject: {subject}. "
            f"From: {sender or 'unknown'}. To: {recipients or ''}. "
            f"Labels: {', '.join(labels)}. Body: {body}"
        )
        units.append({
            "source_type": "Email",
            "title": subject,
            "content": content,
            "source_timestamp": sent_at,
            "thread_id": message.get("threadId") or message.get("id"),
            "relation_key": message.get("threadId") or message.get("id"),
            "metadata": {
                "connector": "gmail_oauth",
                "message_id": message.get("id"),
                "thread_id": message.get("threadId"),
                "sender": sender,
                "recipients": recipients,
                "direction": direction,
                "labels": labels,
                "snippet": message.get("snippet"),
            },
        })

    created = evidence_service.import_evidence_units(db, user_id, units)
    return {"imported": len(created), "ids": [unit.id for unit in created], "gmail_count": len(messages)}
