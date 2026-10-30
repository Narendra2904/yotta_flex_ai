"""Test deterministic reproducibility (Step 10): two generations with same seed produce identical data."""

import os
import shutil
import pytest
from wh_monitor.config import STARTER_SCALE, DEFAULT_SEED
from wh_monitor.generator.orchestrator import run_pipeline


def test_reproducibility_checksums():
    dir_run1 = "tests_tmp_run1"
    dir_run2 = "tests_tmp_run2"

    try:
        # Run 1
        manifest1, val1 = run_pipeline(scale=STARTER_SCALE, seed=DEFAULT_SEED, export_dir=dir_run1)
        assert val1.is_valid, "Run 1 validation failed"

        # Run 2
        manifest2, val2 = run_pipeline(scale=STARTER_SCALE, seed=DEFAULT_SEED, export_dir=dir_run2)
        assert val2.is_valid, "Run 2 validation failed"

        # Compare row counts and SHA-256 checksums
        tables1 = manifest1["tables"]
        tables2 = manifest2["tables"]

        assert set(tables1.keys()) == set(tables2.keys()), "Table sets differ"

        for tbl in tables1:
            meta1 = tables1[tbl]
            meta2 = tables2[tbl]
            assert meta1["row_count"] == meta2["row_count"], f"Row counts differ for {tbl}: {meta1['row_count']} vs {meta2['row_count']}"
            assert meta1["sha256"] == meta2["sha256"], f"SHA-256 checksum mismatch for {tbl}: {meta1['sha256']} vs {meta2['sha256']}"

    finally:
        if os.path.exists(dir_run1):
            shutil.rmtree(dir_run1, ignore_errors=True)
        if os.path.exists(dir_run2):
            shutil.rmtree(dir_run2, ignore_errors=True)
