"""Show row counts and optional schema for Grafana's SQLite database."""

import argparse
import sqlite3


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", action="store_true")
    args = parser.parse_args()

    connection = sqlite3.connect(
        "file:/grafana-data/grafana.db?mode=ro", uri=True
    )
    try:
        tables = connection.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type = 'table' ORDER BY name"
        ).fetchall()
        for name, definition in tables:
            quoted_name = '"' + name.replace('"', '""') + '"'
            count = connection.execute(
                f"SELECT COUNT(*) FROM {quoted_name}"
            ).fetchone()[0]
            print(f"{name}: {count} rows")
            if args.schema and definition:
                print(definition)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
