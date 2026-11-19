#!/usr/bin/env python3
"""Measure live MySQL train-search latency; no synthetic timings are reported."""

import argparse
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.train_search import search_trains  # noqa: E402


def percentile(values, fraction):
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * fraction + 0.999999)))
    return ordered[index]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Source station ID")
    parser.add_argument("--destination", required=True, help="Destination station ID")
    parser.add_argument("--date", required=True, help="Journey date (YYYY-MM-DD)")
    parser.add_argument("--class-id", default=None, help="Optional travel class ID")
    parser.add_argument("--warmup", type=int, default=2, help="Unreported warm-up searches")
    parser.add_argument("--iterations", type=int, default=10, help="Measured searches")
    parser.add_argument("--target-seconds", type=float, default=3.0, help="Expected maximum p95 latency")
    args = parser.parse_args()

    if args.warmup < 0 or args.iterations < 1 or args.target_seconds <= 0:
        parser.error("warmup must be >= 0, iterations and target-seconds must be > 0")

    search_args = (args.source, args.destination, args.date, args.class_id)
    for _ in range(args.warmup):
        search_trains(*search_args)

    durations = []
    result_count = 0
    for _ in range(args.iterations):
        started = time.perf_counter()
        results = search_trains(*search_args)
        durations.append(time.perf_counter() - started)
        result_count = len(results)

    median = statistics.median(durations)
    p95 = percentile(durations, 0.95)
    maximum = max(durations)
    print(f"Search: {args.source} -> {args.destination} on {args.date}")
    print(f"Results returned (last run): {result_count}")
    print(f"Measured iterations: {args.iterations} (warm-up: {args.warmup})")
    print(f"Median: {median:.3f}s")
    print(f"P95:    {p95:.3f}s")
    print(f"Max:    {maximum:.3f}s")
    print(f"Target: p95 <= {args.target_seconds:.3f}s")
    print("RESULT: PASS" if p95 <= args.target_seconds else "RESULT: NEEDS INVESTIGATION")
    print("Note: timings are from this live database/environment; repeat with representative data and load.")
    return 0 if p95 <= args.target_seconds else 2


if __name__ == "__main__":
    raise SystemExit(main())
