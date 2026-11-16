"""Small local scalability measurements, not production capacity certification."""

import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from test_industrial import asset, points, registered


def test_local_ingestion_scaling_and_concurrent_reads() -> None:
    client, _, base = registered()
    machine, _ = asset(client, base)
    batches = []
    for size in (1, 10, 100, 500):
        payload = points(machine, [50.0] * size, offset=100000 + size * 1000)
        started = time.perf_counter()
        response = client.post(f"{base}/telemetry", json=payload)
        elapsed = (time.perf_counter() - started) * 1000
        assert response.status_code == 200, response.text
        assert response.json()["accepted"] == size
        batches.append({"readings": size, "milliseconds": round(elapsed, 2)})

    def read(_: int) -> float:
        started = time.perf_counter()
        response = client.get(f"{base}/summary")
        assert response.status_code == 200
        assert response.json()["machine_count"] == 1
        return (time.perf_counter() - started) * 1000

    # Three local rounds with five callers and twenty requests per round.
    rounds = []
    for iteration in range(1, 4):
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=5) as executor:
            latencies = list(executor.map(read, range(20)))
        elapsed = time.perf_counter() - started
        rounds.append(
            {
                "iteration": iteration,
                "requests": 20,
                "concurrency": 5,
                "median_ms": round(statistics.median(latencies), 2),
                "p95_ms": round(sorted(latencies)[18], 2),
                "requests_per_second": round(20 / elapsed, 2),
                "errors": 0,
            }
        )
    evidence = Path(__file__).resolve().parents[3] / "output/testing/evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "local-performance.json").write_text(
        json.dumps(
            {
                "environment": "in-process TestClient and temporary SQLite",
                "ingestion": batches,
                "summary_reads": rounds,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
