from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from jizhang_mcp.config import get_settings


def get_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def utcnow() -> datetime:
    return datetime.now(tz=ZoneInfo("UTC"))


def now_local() -> datetime:
    return datetime.now(tz=get_tz())


WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def weekday_cn(dt: datetime | None = None) -> str:
    dt = dt or now_local()
    return WEEKDAY_CN[dt.weekday()]


def parse_occurred_at(raw: str | None) -> datetime:
    tz = get_tz()
    if raw is None or raw.strip() == "":
        return now_local()
    raw = raw.strip()
    if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        d = date.fromisoformat(raw)
        return datetime.combine(d, time(12, 0), tzinfo=tz)
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def parse_date_only(raw: str) -> date:
    raw = raw.strip()
    if len(raw) == 10:
        return date.fromisoformat(raw)
    dt = datetime.fromisoformat(raw)
    return dt.date()


def month_start_local(d: date | None = None) -> datetime:
    d = d or now_local().date()
    return datetime.combine(d.replace(day=1), time.min, tzinfo=get_tz())


def iso_local(dt: datetime) -> str:
    return dt.astimezone(get_tz()).isoformat(timespec="seconds")


def default_stats_range() -> tuple[datetime, datetime]:
    start = month_start_local()
    end = now_local()
    return start, end


def clamp_range_span(date_from: datetime, date_to: datetime, max_days: int = 366) -> None:
    if date_to < date_from:
        raise ValueError("date_to 不能早于 date_from")
    if (date_to - date_from) > timedelta(days=max_days):
        raise ValueError("统计区间不能超过 366 天")
