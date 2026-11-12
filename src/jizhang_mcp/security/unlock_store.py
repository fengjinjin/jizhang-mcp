from dataclasses import dataclass
from datetime import datetime

from jizhang_mcp.config import get_settings
from jizhang_mcp.util.time_util import utcnow


@dataclass
class UnlockRecord:
    api_key_id: int
    session_key: str
    unlocked_at: datetime
    last_seen_at: datetime


class UnlockStore:
    def __init__(self) -> None:
        self._records: dict[tuple[int, str], UnlockRecord] = {}

    def is_unlocked(self, api_key_id: int, session_key: str) -> bool:
        key = (api_key_id, session_key)
        rec = self._records.get(key)
        if rec is None:
            return False
        ttl = get_settings().passphrase_ttl_seconds
        if (utcnow() - rec.last_seen_at).total_seconds() > ttl:
            del self._records[key]
            return False
        return True

    def unlock(self, api_key_id: int, session_key: str) -> None:
        now = utcnow()
        self._records[(api_key_id, session_key)] = UnlockRecord(
            api_key_id=api_key_id,
            session_key=session_key,
            unlocked_at=now,
            last_seen_at=now,
        )

    def touch(self, api_key_id: int, session_key: str) -> None:
        key = (api_key_id, session_key)
        rec = self._records.get(key)
        if rec is not None:
            rec.last_seen_at = utcnow()

    def lock(self, api_key_id: int, session_key: str) -> None:
        self._records.pop((api_key_id, session_key), None)

    def clear_user(self, user_id: int, api_key_ids: list[int]) -> None:
        for aid in api_key_ids:
            for key in list(self._records.keys()):
                if key[0] == aid:
                    del self._records[key]


unlock_store = UnlockStore()
