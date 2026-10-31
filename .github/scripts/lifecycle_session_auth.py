#!/usr/bin/env python3
"""Sign and validate coordinator-issued lifecycle session capabilities."""

from __future__ import annotations

import hashlib
import hmac
import re
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo


UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
SESSION_PATTERN = re.compile(r"^(hml|prd)-(\d{4}-\d{2}-\d{2})$")
TOKEN_PATTERN = re.compile(r"^[0-9a-f]{64}$")
EMERGENCY_REQUEST_PATTERN = re.compile(r"^emergency-[1-9][0-9]*$")
BRT = ZoneInfo("America/Sao_Paulo")


class LifecycleSessionAuthError(ValueError):
    """Raised when session signing inputs or capability are invalid."""


def _validated_material(session_mode: str, session_id: str, started_at: str) -> bytes:
    match = SESSION_PATTERN.fullmatch(session_id)
    if match is None:
        raise LifecycleSessionAuthError("The lifecycle session ID is malformed.")
    expected_mode = "hml" if match.group(1) == "hml" else "prd-window"
    if session_mode != expected_mode:
        raise LifecycleSessionAuthError("The lifecycle session mode does not match its stage.")

    try:
        parsed_start = datetime.strptime(started_at, UTC_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise LifecycleSessionAuthError("The lifecycle start must use canonical UTC format.") from error
    if parsed_start.strftime(UTC_FORMAT) != started_at:
        raise LifecycleSessionAuthError("The lifecycle start must use canonical UTC format.")
    if parsed_start.astimezone(BRT).date().isoformat() != match.group(2):
        raise LifecycleSessionAuthError("The lifecycle start date does not match its BRT session ID.")

    local_start = parsed_start.astimezone(BRT)
    if session_mode == "prd-window" and local_start.strftime("%H:%M:%S") != "06:00:00":
        raise LifecycleSessionAuthError("PRD sessions must be signed for a 06:00 BRT start.")
    local_start_time = local_start.time().replace(tzinfo=None)
    if session_mode == "hml" and not time(7, 0) <= local_start_time <= time(17, 0):
        raise LifecycleSessionAuthError("HML sessions must start between 07:00 and 17:00 BRT.")

    return f"{session_mode}|{session_id}|{started_at}".encode("utf-8")


def sign_lifecycle_session(
    signing_key: str, session_mode: str, session_id: str, started_at: str
) -> str:
    key = signing_key.encode("utf-8")
    if len(key) < 32:
        raise LifecycleSessionAuthError("LIFECYCLE_SESSION_SIGNING_KEY must contain at least 32 UTF-8 bytes.")
    material = _validated_material(session_mode, session_id, started_at)
    return hmac.new(key, material, hashlib.sha256).hexdigest()


def verify_lifecycle_session(
    signing_key: str,
    token: str,
    session_mode: str,
    session_id: str,
    started_at: str,
) -> None:
    if not TOKEN_PATTERN.fullmatch(token):
        raise LifecycleSessionAuthError("A valid coordinator session capability is required.")
    expected = sign_lifecycle_session(signing_key, session_mode, session_id, started_at)
    if not hmac.compare_digest(token, expected):
        raise LifecycleSessionAuthError("The coordinator session capability does not match this session.")


def sign_emergency_hml_cleanup(
    signing_key: str, session_id: str, started_at: str, close_request_id: str
) -> str:
    key = signing_key.encode("utf-8")
    if len(key) < 32:
        raise LifecycleSessionAuthError("LIFECYCLE_SESSION_SIGNING_KEY must contain at least 32 UTF-8 bytes.")
    if not EMERGENCY_REQUEST_PATTERN.fullmatch(close_request_id):
        raise LifecycleSessionAuthError("Emergency cleanup requires its unique emergency close request ID.")
    material = _validated_material("hml", session_id, started_at)
    purpose_bound_material = b"emergency-cleanup|" + material + b"|" + close_request_id.encode("utf-8")
    return hmac.new(key, purpose_bound_material, hashlib.sha256).hexdigest()


def verify_emergency_hml_cleanup(
    signing_key: str, token: str, session_id: str, started_at: str, close_request_id: str
) -> None:
    if not TOKEN_PATTERN.fullmatch(token):
        raise LifecycleSessionAuthError("A valid emergency HML cleanup capability is required.")
    expected = sign_emergency_hml_cleanup(signing_key, session_id, started_at, close_request_id)
    if not hmac.compare_digest(token, expected):
        raise LifecycleSessionAuthError("The emergency cleanup capability does not match this close request.")
