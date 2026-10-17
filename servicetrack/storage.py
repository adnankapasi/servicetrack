import sqlite3
from datetime import date

from servicetrack.scheduling import require_integer

SQLITE_MAX_INTEGER = (2**63) - 1


def require_sqlite_integer(
    name: str,
    value: int,
    minimum: int = 0,
) -> None:
    require_integer(name, value, minimum)

    if value > SQLITE_MAX_INTEGER:
        raise ValueError(
            f"{name} must be at most {SQLITE_MAX_INTEGER}"
        )


class ServiceStore:
    """Store vehicles and service records in a local SQLite database."""

    def __init__(self, path: str):
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row

        try:
            self.connection.execute("PRAGMA foreign_keys = ON")
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS vehicles (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL
                        CHECK (length(trim(name)) > 0)
                );

                CREATE TABLE IF NOT EXISTS services (
                    id INTEGER PRIMARY KEY,
                    vehicle_id INTEGER NOT NULL
                        REFERENCES vehicles(id) ON DELETE RESTRICT,
                    service_date TEXT NOT NULL,
                    odometer_km INTEGER NOT NULL
                        CHECK (odometer_km >= 0),
                    notes TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS services_vehicle_date
                ON services(vehicle_id, service_date, id);
                """
            )
        except BaseException:
            self.connection.close()
            raise

    def close(self) -> None:
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def _require_vehicle(self, vehicle_id: int) -> None:
        require_sqlite_integer("vehicle_id", vehicle_id, 1)

        vehicle = self.connection.execute(
            "SELECT id FROM vehicles WHERE id = ?",
            (vehicle_id,),
        ).fetchone()

        if vehicle is None:
            raise ValueError("Vehicle does not exist")

    def add_vehicle(self, name: str) -> int:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Vehicle name must be non-empty text")

        with self.connection:
            cursor = self.connection.execute(
                "INSERT INTO vehicles(name) VALUES (?)",
                (name.strip(),),
            )
            vehicle_id = cursor.lastrowid

        return vehicle_id

    def list_vehicles(self) -> list[dict]:
        rows = self.connection.execute(
            "SELECT id, name FROM vehicles ORDER BY id"
        ).fetchall()

        return [dict(row) for row in rows]

    def add_service(
        self,
        vehicle_id: int,
        service_date: date,
        odometer_km: int,
        notes: str = "",
    ) -> int:
        require_sqlite_integer("vehicle_id", vehicle_id, 1)
        require_sqlite_integer("odometer_km", odometer_km)

        if type(service_date) is not date:
            raise ValueError("service_date must be a date")

        if service_date > date.today():
            raise ValueError("service_date cannot be in the future")

        if not isinstance(notes, str):
            raise ValueError("notes must be text")

        new_date = service_date.isoformat()

        with self.connection:
            # Keep mileage validation and insertion in one write transaction.
            self.connection.execute("BEGIN IMMEDIATE")

            self._require_vehicle(vehicle_id)

            conflict = self.connection.execute(
                """
                SELECT id
                FROM services
                WHERE vehicle_id = ?
                  AND (
                      (service_date <= ? AND odometer_km > ?)
                      OR
                      (service_date >= ? AND odometer_km < ?)
                  )
                LIMIT 1
                """,
                (
                    vehicle_id,
                    new_date,
                    odometer_km,
                    new_date,
                    odometer_km,
                ),
            ).fetchone()

            if conflict is not None:
                raise ValueError(
                    "Mileage conflicts with existing service history"
                )

            cursor = self.connection.execute(
                """
                INSERT INTO services(
                    vehicle_id,
                    service_date,
                    odometer_km,
                    notes
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    vehicle_id,
                    new_date,
                    odometer_km,
                    notes.strip(),
                ),
            )
            service_id = cursor.lastrowid

        return service_id

    def service_history(self, vehicle_id: int) -> list[dict]:
        self._require_vehicle(vehicle_id)

        rows = self.connection.execute(
            """
            SELECT id, vehicle_id, service_date, odometer_km, notes
            FROM services
            WHERE vehicle_id = ?
            ORDER BY service_date DESC, id DESC
            """,
            (vehicle_id,),
        ).fetchall()

        return [dict(row) for row in rows]