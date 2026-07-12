from datetime import timedelta
from typing import Optional


def clamp_title(text: str, max_len: int = 70) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def fmt_duration(seconds: Optional[int]) -> str:
    if seconds is None:
        return "알 수 없음"
    return str(timedelta(seconds=int(seconds)))
