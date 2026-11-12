"""Quick SQLite Database Inspector for TelemetryX."""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "telemetryx_dev.db"


def show_summary():
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row[0] for row in cur.fetchall()]

    print(f"\n=======================================================")
    print(f"  TelemetryX Database Inspector (SQLite)")
    print(f"  File: {DB_PATH}")
    print(f"=======================================================\n")
    print(f"{'Table Name':<32} | {'Row Count':>10}")
    print("-" * 47)

    for table in tables:
        if table.startswith("sqlite_"):
            continue
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            cnt = cur.fetchone()[0]
            print(f"{table:<32} | {cnt:>10,}")
        except Exception as e:
            print(f"{table:<32} | ERROR: {e}")

    print("\n" + "=" * 47)
    conn.close()


def query_table(table_name: str, limit: int = 5):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT * FROM {table_name} LIMIT ?", (limit,))
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        print(f"\n--- Previewing top {limit} rows from '{table_name}' ---")
        print("Columns:", columns)
        for r in rows:
            print(r)
    except Exception as e:
        print(f"Error querying table {table_name}: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        query_table(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 5)
    else:
        show_summary()
