# ServiceTrack

A Python application for tracking vehicle servicing by mileage and date.

## Planned features

- Calculate the next service mileage and date.
- Identify overdue servicing.
- Store vehicles and service history in SQLite.
- Manage records through a command-line interface.

## Requirements

Python 3.10 or newer.

No third-party runtime dependencies.

## Run tests

python -m unittest discover -v

## Project purpose

This repository also documents an evaluation of Codzee's automated
pull request reviews. Findings will be verified against code and tests.

AI tools assist with implementation. The repository owner reviews,
tests, and takes responsibility for the submitted work.

## Command-line usage

Run commands from the repository root with the virtual environment active.

Create a vehicle:

    python -m servicetrack add-vehicle "Honda Activa"

Record a completed service using the returned vehicle ID:

    python -m servicetrack add-service 1 --date 2026-10-01 --km 12000 --notes "Engine oil changed"

Check the next service:

    python -m servicetrack status 1 --current-km 14500 --interval-km 3000 --interval-days 180

View service history:

    python -m servicetrack history 1

List vehicles:

    python -m servicetrack vehicles

Use a different database by placing --db before the command:

    python -m servicetrack --db demo.db vehicles

Display help:

    python -m servicetrack --help

## Output and errors

Successful commands print JSON and exit with code 0.
Invalid input and SQLite errors print a message to stderr and exit
with code 2.

## Service rules

- Service is due when either the mileage or date threshold is reached.
- Negative remaining values indicate overdue servicing.
- Status uses the most recent service date.
- Service intervals are supplied when checking status.
- Date intervals use fixed days, not calendar months.
- Service dates must use YYYY-MM-DD and cannot be in the future.
- Multiple services on the same date must have equal mileage.

## Limitations

- Local command-line application.
- No reminders, authentication, or cloud synchronization.
- No service editing or deletion.
- No odometer replacement or reset support.
- All service records are treated as resetting the supplied service interval.

## Run tests

    python -m unittest discover -v