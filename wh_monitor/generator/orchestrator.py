"""End-to-End Orchestrator: generates synthetic data, executes risk engine, validates and exports."""

import os
import json
import random
import sqlite3
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple
import pandas as pd

from wh_monitor.config import ScaleConfig, STARTER_SCALE, FULL_SCALE, DEFAULT_SEED, SIMULATION_START, SIMULATION_END
from wh_monitor.generator.master_data import generate_storage_requirements, generate_warehouses, generate_zones, generate_sensors
from wh_monitor.generator.lot_generator import generate_inventory_lots
from wh_monitor.generator.anomaly_injector import inject_edge_cases_and_plan_anomalies
from wh_monitor.generator.telemetry_gen import generate_door_events, generate_sensor_readings_chunked
from wh_monitor.engine.monitor import detect_sensor_outage_alarms, detect_door_ajar_alarms, detect_environmental_excursion_alarms
from wh_monitor.engine.traceability import link_alarms_to_affected_lots
from wh_monitor.engine.workflow import generate_inspections_and_remediations
from wh_monitor.validation.validator import validate_dataset, ValidationResult
from wh_monitor.models import (
    Warehouse, Zone, StorageRequirement, Sensor, SensorReading,
    DoorEvent, InventoryLot, Alarm, AlarmAffectedLot, Inspection, Remediation, GroundTruth
)


def run_pipeline(
    scale: ScaleConfig = STARTER_SCALE,
    seed: int = DEFAULT_SEED,
    export_dir: str = "data"
) -> Tuple[Dict[str, Any], ValidationResult]:
    """Execute complete generation, risk detection, validation and export workflow."""
    rng = random.Random(seed)
    base_date = SIMULATION_START

    # Step 1 & 2: Generate Master Data
    requirements = generate_storage_requirements()
    warehouses = generate_warehouses(scale, rng, base_date)
    zones = generate_zones(warehouses, scale, rng)
    sensors = generate_sensors(zones, scale, rng, base_date.date())

    # Step 3: Generate Inventory Lots
    lots = generate_inventory_lots(zones, requirements, scale, rng)

    # Step 4 & 5: Inject labeled edge cases and ground truth
    manifest, lots, sensors = inject_edge_cases_and_plan_anomalies(zones, sensors, lots, requirements, rng)

    # Step 6: Generate Door Events & Sensor Readings
    door_events = generate_door_events(zones, scale, manifest, rng)
    
    # Collect readings via generator
    all_readings: List[SensorReading] = []
    for chunk in generate_sensor_readings_chunked(sensors, zones, door_events, manifest, scale, seed):
        all_readings.extend(chunk)

    # Step 7: Execute Risk & Monitoring Engine
    outage_alarms = detect_sensor_outage_alarms(sensors, all_readings)
    door_alarms = detect_door_ajar_alarms(zones, door_events)
    excursion_alarms = detect_environmental_excursion_alarms(zones, sensors, all_readings)
    
    raw_alarms = excursion_alarms + door_alarms + outage_alarms
    # Guarantee strict global uniqueness across all alarm types
    seen_alarm_ids = set()
    deduped_alarms = []
    for a in raw_alarms:
        aid = a.alarm_id
        if aid in seen_alarm_ids:
            cnt = 2
            while f"{aid}-{cnt:02d}" in seen_alarm_ids:
                cnt += 1
            aid = f"{aid}-{cnt:02d}"
            a = a.model_copy(update={"alarm_id": aid})
        seen_alarm_ids.add(aid)
        deduped_alarms.append(a)

    # Step 8: Execute Traceability & Lot Impact Engine
    alarms, bridges, lots = link_alarms_to_affected_lots(deduped_alarms, lots, requirements, manifest)

    # Step 9: Execute Inspection & Remediation Workflow
    inspections, remediations = generate_inspections_and_remediations(alarms, bridges, lots)

    ground_truth = manifest.ground_truth_records

    # Step 10: Run Full Validation
    val_result = validate_dataset(
        warehouses, zones, requirements, sensors, all_readings,
        door_events, lots, alarms, bridges, inspections, remediations, ground_truth
    )

    # Step 11: Export Data to CSV, JSON, and SQLite
    csv_dir = os.path.join(export_dir, "csv")
    json_dir = os.path.join(export_dir, "json")
    db_path = os.path.join(export_dir, "sqlite", "warehouse_telemetry.db")
    gt_dir = os.path.join(export_dir, "ground_truth")

    os.makedirs(csv_dir, exist_ok=True)
    os.makedirs(json_dir, exist_ok=True)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    os.makedirs(gt_dir, exist_ok=True)

    datasets = {
        "warehouses": [w.model_dump(mode="json") for w in warehouses],
        "storage_requirements": [r.model_dump(mode="json") for r in requirements],
        "zones": [z.model_dump(mode="json") for z in zones],
        "sensors": [s.model_dump(mode="json") for s in sensors],
        "door_events": [d.model_dump(mode="json") for d in door_events],
        "inventory_lots": [l.model_dump(mode="json") for l in lots],
        "alarms": [a.model_dump(mode="json") for a in alarms],
        "alarm_affected_lots": [b.model_dump(mode="json") for b in bridges],
        "inspections": [i.model_dump(mode="json") for i in inspections],
        "remediations": [rem.model_dump(mode="json") for rem in remediations],
        "ground_truth": [gt.model_dump(mode="json") for gt in ground_truth],
    }

    # Sensor readings as dataframe for high efficiency
    readings_df = pd.DataFrame([r.model_dump(mode="json") for r in all_readings])

    # Export CSVs
    for name, data in datasets.items():
        df = pd.DataFrame(data)
        if name == "ground_truth":
            df.to_csv(os.path.join(gt_dir, "ground_truth.csv"), index=False)
        else:
            df.to_csv(os.path.join(csv_dir, f"{name}.csv"), index=False)
            
    readings_df.to_csv(os.path.join(csv_dir, "sensor_readings.csv"), index=False)

    # Export JSONs
    for name, data in datasets.items():
        if name == "ground_truth":
            with open(os.path.join(gt_dir, "ground_truth.json"), "w") as f:
                json.dump(data, f, indent=2)
        else:
            with open(os.path.join(json_dir, f"{name}.json"), "w") as f:
                json.dump(data, f, indent=2)

    # Export sample JSON for readings (full readings JSON can be huge)
    sample_readings = readings_df.head(1000).to_dict(orient="records")
    with open(os.path.join(json_dir, "sensor_readings_sample.json"), "w") as f:
        json.dump(sample_readings, f, indent=2)

    # Export SQLite Database
    schema_sql_path = os.path.join(export_dir, "sqlite", "schema.sql")
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA journal_mode = MEMORY")
    if os.path.exists(schema_sql_path):
        with open(schema_sql_path, "r") as f:
            conn.executescript(f.read())
            
    for name, data in datasets.items():
        df = pd.DataFrame(data)
        df.to_sql(name, conn, if_exists="append", index=False)
        
    readings_df.to_sql("sensor_readings", conn, if_exists="append", index=False, chunksize=50000)
    conn.commit()
    conn.close()

    # Calculate File Hashes and Row Counts for Manifest
    manifest_info = {
        "dataset_name": f"warehouse_monitoring_{scale.name}",
        "scale": scale.name,
        "seed": seed,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tables": {}
    }

    for name in list(datasets.keys()) + ["sensor_readings"]:
        path = os.path.join(gt_dir if name == "ground_truth" else csv_dir, f"{name}.csv")
        count = len(readings_df) if name == "sensor_readings" else len(datasets[name])
        
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
                
        manifest_info["tables"][name] = {
            "row_count": count,
            "sha256": hasher.hexdigest(),
            "csv_path": path
        }

    # Write Manifest
    manifest_path = os.path.join(export_dir, "source_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest_info, f, indent=2)

    # Write Validation Summary
    val_path = os.path.join(export_dir, "validation_summary.json")
    with open(val_path, "w") as f:
        json.dump(val_result.summary(), f, indent=2)

    return manifest_info, val_result
