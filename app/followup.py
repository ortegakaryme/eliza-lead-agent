"""Follow-up commitment: when will a human contact this lead?

The backend computes this (not the LLM) so the promise made on the call always
matches real business hours. The rule:

  * If the lead arrives on a business day at least CUTOFF_HOURS before closing,
    a person calls back today before closing time.
  * Otherwise, a person calls back on the next business day before NEXT_DAY_DEADLINE.

Edit BUSINESS_HOURS to change the schedule (weekday: 0 = Monday ... 6 = Sunday).
"""
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

BUSINESS_HOURS = {
    0: (time(9), time(18)),
    1: (time(9), time(18)),
    2: (time(9), time(18)),
    3: (time(9), time(18)),
    4: (time(9), time(18)),
    5: (time(10), time(14)),
    # Sunday closed
}
CUTOFF_HOURS = 2
NEXT_DAY_DEADLINE = time(12)

WEEKDAYS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


@dataclass(frozen=True)
class FollowUp:
    deadline: datetime   # timezone-aware, stored in Notion "Follow-up by"
    message: str         # spoken to the lead by the agent


def _spoken_time(t: time) -> str:
    if t.hour == 12 and t.minute == 0:
        return "el mediodía"
    hour12 = t.hour % 12 or 12
    period = "de la mañana" if t.hour < 12 else "de la tarde"
    if t.hour >= 19:
        period = "de la noche"
    article = "la" if hour12 == 1 else "las"
    return f"{article} {hour12}:{t.minute:02d} {period}"


def _next_business_day(day: datetime) -> datetime:
    candidate = day + timedelta(days=1)
    while candidate.weekday() not in BUSINESS_HOURS:
        candidate += timedelta(days=1)
    return candidate


def compute_follow_up(tz_name: str, now: Optional[datetime] = None) -> FollowUp:
    tz = ZoneInfo(tz_name)
    now = now.astimezone(tz) if now else datetime.now(tz)

    hours = BUSINESS_HOURS.get(now.weekday())
    if hours:
        _, close = hours
        cutoff = datetime.combine(now.date(), close, tz) - timedelta(hours=CUTOFF_HOURS)
        if now <= cutoff:
            deadline = datetime.combine(now.date(), close, tz)
            message = f"Un asesor se pondrá en contacto con usted hoy antes de {_spoken_time(close)}."
            return FollowUp(deadline=deadline, message=message)

    next_day = _next_business_day(now)
    open_time, _ = BUSINESS_HOURS[next_day.weekday()]
    due = max(NEXT_DAY_DEADLINE, open_time)
    deadline = datetime.combine(next_day.date(), due, tz)

    when = "mañana" if (next_day.date() - now.date()).days == 1 else f"el {WEEKDAYS_ES[next_day.weekday()]}"
    preposition = "antes del" if due == time(12) else "antes de"
    spoken = "mediodía" if due == time(12) else _spoken_time(due)
    message = f"Un asesor se pondrá en contacto con usted {when} {preposition} {spoken}."
    return FollowUp(deadline=deadline, message=message)
