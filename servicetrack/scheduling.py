from dataclasses import dataclass
from datetime import date, timedelta


def require_integer(name: str, value: int, minimum: int = 0) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")


@dataclass(frozen=True)
class ServiceStatus:
    next_service_km: int
    next_service_date: date
    remaining_km: int
    remaining_days: int
    is_due: bool


def calculate_service_status(
    *,
    current_km: int,
    last_service_km: int,
    last_service_date: date,
    interval_km: int,
    interval_days: int,
    today: date | None = None,
) -> ServiceStatus:
    require_integer("current_km", current_km)
    require_integer("last_service_km", last_service_km)
    require_integer("interval_km", interval_km, 1)
    require_integer("interval_days", interval_days, 1)

    if type(last_service_date) is not date:
        raise ValueError("last_service_date must be a date")

    if today is not None and type(today) is not date:
        raise ValueError("today must be a date")

    reference_date = today if today is not None else date.today()

    if current_km < last_service_km:
        raise ValueError("current_km cannot be below last_service_km")

    if last_service_date > reference_date:
        raise ValueError("last_service_date cannot be in the future")

    next_km = last_service_km + interval_km

    try:
        next_date = last_service_date + timedelta(days=interval_days)
    except OverflowError as exc:
        raise ValueError("interval_days exceeds the supported date range") from exc

    remaining_km = next_km - current_km
    remaining_days = (next_date - reference_date).days

    return ServiceStatus(
        next_service_km=next_km,
        next_service_date=next_date,
        remaining_km=remaining_km,
        remaining_days=remaining_days,
        is_due=remaining_km <= 0 or remaining_days <= 0,
    )