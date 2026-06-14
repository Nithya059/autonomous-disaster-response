#!/usr/bin/env python3
"""
CLI seed script — populates the database with mock incidents and resources.

Usage (from backend/ directory):
    python scripts/seed_db.py
    python scripts/seed_db.py --reset   # drops and recreates all data
"""

import sys
import os
import json
import argparse

# Ensure `app` is importable when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, create_all_tables
from app.models.incident import Incident
from app.models.resource import Resource
from app.services.mock_data import get_mock_incidents, get_mock_resources


def seed(reset: bool = False) -> None:
    create_all_tables()
    db = SessionLocal()

    try:
        if reset:
            print("Resetting database — deleting all incidents and resources...")
            db.query(Resource).delete()
            db.query(Incident).delete()
            db.commit()
            print("  ✓ All rows deleted")

        # Seed incidents
        existing_incidents = db.query(Incident).count()
        if existing_incidents > 0 and not reset:
            print(f"  Incidents table already has {existing_incidents} rows — skipping.")
        else:
            mock_incidents = get_mock_incidents()
            for data in mock_incidents:
                db.add(Incident(
                    title=data["title"],
                    type=data["type"],
                    severity=data["severity"],
                    lat=data["lat"],
                    lng=data["lng"],
                    status="new",
                    confidence=0.0,
                    source=data.get("source"),
                    raw_data=json.dumps(data),
                ))
            db.commit()
            print(f"  ✓ Seeded {len(mock_incidents)} incidents")

        # Seed resources
        existing_resources = db.query(Resource).count()
        if existing_resources > 0 and not reset:
            print(f"  Resources table already has {existing_resources} rows — skipping.")
        else:
            mock_resources = get_mock_resources()
            for data in mock_resources:
                db.add(Resource(
                    name=data["name"],
                    type=data["type"],
                    status="available",
                    lat=data["lat"],
                    lng=data["lng"],
                    capacity=data["capacity"],
                ))
            db.commit()
            print(f"  ✓ Seeded {len(mock_resources)} resources")

        print("\nDatabase seeding complete.")

    except Exception as exc:
        db.rollback()
        print(f"  ✗ Seeding failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the disaster response database")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete all existing data before seeding",
    )
    args = parser.parse_args()
    seed(reset=args.reset)
