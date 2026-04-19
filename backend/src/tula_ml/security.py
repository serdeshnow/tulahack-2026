from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac


@dataclass(slots=True)
class UrlSigner:
    secret: str

    def sign(self, *, method: str, path: str, expires: int) -> str:
        payload = f"{method.upper()}:{path}:{expires}".encode("utf-8")
        return hmac.new(self.secret.encode("utf-8"), payload, sha256).hexdigest()

    def verify(self, *, method: str, path: str, expires: int, signature: str) -> bool:
        expected = self.sign(method=method, path=path, expires=expires)
        return hmac.compare_digest(expected, signature)
