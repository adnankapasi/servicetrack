import argparse
import json
import sqlite3
from datetime import date

from servicetrack.scheduling import calculate_service_status
from servicetrack.storage import ServiceStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Track vehicle servicing by mileage and date."
    )

    parser.add_argument(
        "--db",
        default="servicetrack.db",
        help="SQLite database path. Default: servicetrack.db",
    )

    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    vehicle = commands.add_parser(
        "add-vehicle",
        help="Create a vehicle.",
    )
    vehicle.add_argument("name", help="Vehicle name.")

    commands.add_parser(
        "vehicles",
        help="List all vehicles.",
    )

    service = commands.add_parser(
        "add-service",
        help="Record a completed service.",
    )
    service.add_argument("vehicle_id", type=int)
    service.add_argument(
        "--date",
        required=True,
        help="Service date in YYYY-MM-DD format.",
    )
    service.add_argument("--km", type=int, required=True)
    service.add_argument("--notes", default="")

    history = commands.add_parser(
        "history",
        help="Show service history, newest first.",
    )
    history.add_argument("vehicle_id", type=int)

    status = commands.add_parser(
        "status",
        help="Calculate when the next service is due.",
    )
    status.add_argument("vehicle_id", type=int)
    status.add_argument("--current-km", type=int, required=True)
    status.add_argument("--interval-km", type=int, required=True)
    status.add_argument("--interval-days", type=int, required=True)

    return parser


def parse_service_date(value: str) -> date:
    """Require an explicit YYYY-MM-DD date."""
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            "Service date must be a valid date in YYYY-MM-DD format"
        ) from exc

    if parsed.isoformat() != value:
        raise ValueError(
            "Service date must be a valid date in YYYY-MM-DD format"
        )

    return parsed


def execute_command(args: argparse.Namespace, store: ServiceStore):
    if args.command == "add-vehicle":
        return {"vehicle_id": store.add_vehicle(args.name)}

    if args.command == "vehicles":
        return store.list_vehicles()

    if args.command == "add-service":
        service_id = store.add_service(
            vehicle_id=args.vehicle_id,
            service_date=parse_service_date(args.date),
            odometer_km=args.km,
            notes=args.notes,
        )
        return {"service_id": service_id}

    if args.command == "history":
        return store.service_history(args.vehicle_id)

    if args.command == "status":
        history = store.service_history(args.vehicle_id)

        if not history:
            raise ValueError(
                "Record a service before checking service status"
            )

        latest = history[0]

        status = calculate_service_status(
            current_km=args.current_km,
            last_service_km=latest["odometer_km"],
            last_service_date=date.fromisoformat(
                latest["service_date"]
            ),
            interval_km=args.interval_km,
            interval_days=args.interval_days,
        )

        return {
            "next_service_km": status.next_service_km,
            "next_service_date": status.next_service_date.isoformat(),
            "remaining_km": status.remaining_km,
            "remaining_days": status.remaining_days,
            "is_due": status.is_due,
        }

    raise ValueError(f"Unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        with ServiceStore(args.db) as store:
            result = execute_command(args, store)
    except (ValueError, sqlite3.Error) as exc:
        parser.exit(2, f"Error: {exc}\n")

    print(json.dumps(result, indent=2))
    return 0