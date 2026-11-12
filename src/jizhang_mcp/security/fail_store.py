from dataclasses import dataclass
from datetime import datetime, timedelta

from jizhang_mcp.config import get_settings
from jizhang_mcp.exceptions import AuthRateLimitedError
from jizhang_mcp.util.time_util import utcnow


@dataclass
class FailRecord:
    count: int = 0
    lock_until: datetime | None = None


class FailStore:
    def __init__(self) -> None:
        self._auth: dict[str, FailRecord] = {}
        self._register_ip: dict[str, list[datetime]] = {}

    def _get(self, key: str) -> FailRecord:
        return self._auth.setdefault(key, FailRecord())

    def check_auth_locked(self, key: str) -> None:
        rec = self._get(key)
        if rec.lock_until and utcnow() < rec.lock_until:
            secs = int((rec.lock_until - utcnow()).total_seconds()) + 1
            raise AuthRateLimitedError(
                "尝试过于频繁，请稍后再试",
                retry_after_seconds=secs,
            )

    def record_auth_failure(self, key: str) -> None:
        settings = get_settings()
        rec = self._get(key)
        rec.count += 1
        if rec.count >= settings.auth_max_failures:
            rec.lock_until = utcnow() + timedelta(seconds=settings.auth_lockout_seconds)

    def clear_auth(self, key: str) -> None:
        self._auth.pop(key, None)

    def check_register_ip(self, ip: str) -> None:
        settings = get_settings()
        now = utcnow()
        window_start = now - timedelta(hours=1)
        hits = [t for t in self._register_ip.get(ip, []) if t >= window_start]
        self._register_ip[ip] = hits
        if len(hits) >= settings.register_rate_per_hour:
            raise AuthRateLimitedError(
                "注册过于频繁，请稍后再试",
                retry_after_seconds=300,
            )

    def record_register_ip(self, ip: str) -> None:
        self._register_ip.setdefault(ip, []).append(utcnow())


fail_store = FailStore()
