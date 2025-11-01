from datetime import timedelta

def clamp_title(s: str, max_len: int = 70) -> str:
    return s if len(s) <= max_len else s[:max_len-1] + "…"

def fmt_duration(seconds: int | None) -> str:
    if not seconds and seconds != 0:
        return "Unknown"
    return str(timedelta(seconds=int(seconds)))
