#!/usr/bin/env python3
"""CLI Command for Warehouse Monitoring Synthetic Dataset Generation and Risk Analysis."""

import argparse
import sys
import time
from wh_monitor.config import STARTER_SCALE, FULL_SCALE, DEFAULT_SEED
from wh_monitor.generator.orchestrator import run_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic warehouse environmental telemetry and evaluate risk conditions."
    )
    parser.add_argument(
        "--scale",
        type=str,
        choices=["starter", "full"],
        default="starter",
        help="Scale profile: 'starter' (fast, ~10k readings) or 'full' (1M readings, 10k lots, 10 WH, 100 zones, 500 sensors)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Deterministic random seed (default: {DEFAULT_SEED})"
    )
    parser.add_argument(
        "--outdir",
        type=str,
        default="data",
        help="Output directory path for data exports (default: 'data')"
    )

    args = parser.parse_args()

    scale_cfg = FULL_SCALE if args.scale == "full" else STARTER_SCALE

    print(f"================================================================================")
    print(f">> Starting Warehouse Telemetry Generator & Risk Engine")
    print(f"   Scale Profile : {scale_cfg.name.upper()}")
    print(f"   Target Volume : {scale_cfg.num_warehouses} Warehouses, {scale_cfg.num_warehouses * scale_cfg.zones_per_warehouse} Zones, {scale_cfg.num_readings:,} Readings, {scale_cfg.num_lots:,} Lots")
    print(f"   Random Seed   : {args.seed}")
    print(f"   Export Target : {args.outdir}/")
    print(f"================================================================================")

    t0 = time.time()
    manifest, val_result = run_pipeline(scale=scale_cfg, seed=args.seed, export_dir=args.outdir)
    elapsed = time.time() - t0

    print(f"\n[OK] Generation & Risk Evaluation Completed in {elapsed:.2f}s")
    print(f"--------------------------------------------------------------------------------")
    print(f"{'Table Name':<28} | {'Rows':<10} | {'SHA-256 (first 12 chars)':<24}")
    print(f"--------------------------------------------------------------------------------")
    for tbl, meta in manifest["tables"].items():
        print(f"{tbl:<28} | {meta['row_count']:<10} | {meta['sha256'][:24]}...")
    print(f"--------------------------------------------------------------------------------")

    print(f"\n[Validation Checks]: {val_result.passed_checks}/{val_result.total_checks} PASSED")
    for detail in val_result.details:
        status_icon = "PASS" if detail["status"] == "PASS" else "FAIL"
        print(f"  [{status_icon}] {detail['check']}: {detail['message']}")

    if not val_result.is_valid:
        print(f"\n[FAIL] Validation failed with {val_result.failed_checks} errors.")
        sys.exit(1)
    else:
        print(f"\n[SUCCESS] All integrity and domain constraints verified successfully!")


if __name__ == "__main__":
    main()
