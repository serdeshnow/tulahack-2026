from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from urllib import error as urllib_error
from urllib import request as urllib_request
import hmac
import json
import time

from .config import AppConfig


@dataclass(slots=True)
class WebhookNotifier:
    config: AppConfig

    def notify(self, *, webhook_url: str | None, payload: dict[str, object]) -> dict[str, object]:
        if not webhook_url:
            return {"delivered": False, "reason": "webhook_not_configured", "attempts": 0}
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        signature = hmac.new(self.config.webhook_signing_secret.encode("utf-8"), body, sha256).hexdigest()
        last_error = None
        for attempt in range(self.config.webhook_max_retries + 1):
            request = urllib_request.Request(
                webhook_url,
                data=body,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "tula-ml-webhook/1.0",
                    "X-Tula-Signature-SHA256": signature,
                    "Idempotency-Key": str(payload.get("job_id", "unknown")),
                },
            )
            try:
                with urllib_request.urlopen(request, timeout=self.config.webhook_timeout_seconds) as response:
                    status_code = getattr(response, "status", 200)
                    if 200 <= status_code < 300:
                        return {
                            "delivered": True,
                            "attempts": attempt + 1,
                            "status_code": status_code,
                        }
                    last_error = f"HTTP {status_code}"
            except urllib_error.HTTPError as exc:
                last_error = f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:200]}"
                if exc.code < 500 and exc.code not in {408, 429}:
                    break
            except (urllib_error.URLError, TimeoutError) as exc:
                last_error = str(exc)
            if attempt < self.config.webhook_max_retries:
                time.sleep(0.2 * (attempt + 1))
        return {
            "delivered": False,
            "reason": "delivery_failed",
            "attempts": self.config.webhook_max_retries + 1,
            "last_error": last_error,
            "target": webhook_url,
        }
