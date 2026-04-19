from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from hashlib import sha256
from typing import Any
import hmac
import json
import time

from .models import AccessLevel


class AuthError(RuntimeError):
    pass


def _encode_b64url(data: bytes) -> str:
    return urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _decode_b64url(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return urlsafe_b64decode(data + padding)


@dataclass(slots=True)
class ClaimsAuth:
    secret: str
    allow_legacy_role_header: bool = True

    def issue_token(self, *, access_levels: list[AccessLevel] | list[str], subject: str = "internal", expires_in_seconds: int = 3600) -> str:
        payload = {
            "sub": subject,
            "exp": int(time.time()) + expires_in_seconds,
            "access_levels": [level.value if isinstance(level, AccessLevel) else str(level) for level in access_levels],
        }
        encoded_payload = _encode_b64url(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        signature = hmac.new(self.secret.encode("utf-8"), encoded_payload.encode("utf-8"), sha256).hexdigest()
        return f"{encoded_payload}.{signature}"

    def decode_token(self, token: str) -> dict[str, Any]:
        try:
            encoded_payload, signature = token.split(".", 1)
        except ValueError as exc:
            raise AuthError("Bearer token format is invalid") from exc
        expected = hmac.new(self.secret.encode("utf-8"), encoded_payload.encode("utf-8"), sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise AuthError("Bearer token signature is invalid")
        payload = json.loads(_decode_b64url(encoded_payload).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise AuthError("Bearer token has expired")
        return payload

    def resolve_access_levels(self, *, authorization: str | None, legacy_role: str | None) -> set[AccessLevel]:
        if authorization and authorization.lower().startswith("bearer "):
            payload = self.decode_token(authorization.split(" ", 1)[1].strip())
            levels = payload.get("access_levels") or []
            try:
                resolved = {AccessLevel(level) for level in levels}
            except ValueError as exc:
                raise AuthError("Bearer token contains an unknown access level") from exc
            if not resolved:
                raise AuthError("Bearer token does not grant any access levels")
            return resolved
        if self.allow_legacy_role_header and legacy_role:
            return self._legacy_role_to_access_levels(legacy_role)
        raise AuthError("Authorization is required")

    def _legacy_role_to_access_levels(self, role: str) -> set[AccessLevel]:
        role = role.lower()
        permissions = {
            "viewer": {AccessLevel.REDACTED},
            "auditor": {AccessLevel.REDACTED, AccessLevel.AUDIT},
            "privileged": {AccessLevel.REDACTED, AccessLevel.AUDIT, AccessLevel.RESTRICTED, AccessLevel.INTERNAL},
        }
        if role not in permissions:
            raise AuthError(f"Unknown legacy role: {role}")
        return permissions[role]
