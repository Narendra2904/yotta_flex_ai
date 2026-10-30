"""Unit tests for the validation engine and edge-case verification."""

import copy
from datetime import datetime, timezone
from wh_monitor.config import STARTER_SCALE, DEFAULT_SEED
from wh_monitor.generator.master_data import generate_storage_requirements, generate_warehouses, generate_zones, generate_sensors
from wh_monitor.generator.lot_generator import generate_inventory_lots
from wh_monitor.generator.anomaly_injector import inject_edge_cases_and_plan_anomalies
from wh_monitor.generator.telemetry_gen import generate_door_events, generate_sensor_readings_chunked
from wh_monitor.engine.monitor import detect_sensor_outage_alarms, detect_door_ajar_alarms, detect_environmental_excursion_alarms
from wh_monitor.engine.traceability import link_alarms_to_affected_lots
from wh_monitor.engine.workflow import generate_inspections_and_remediations
from wh_monitor.validation.validator import validate_dataset


def test_validator_detects_corrupted_foreign_keys():
    import random
    rng = random.Random(DEFAULT_SEED)
    reqs = generate_storage_requirements()
    whs = generate_warehouses(STARTER_SCALE, rng, datetime(2026, 10, 16, tzinfo=timezone.utc))
    zones = generate_zones(whs, STARTER_SCALE, rng)
    sensors = generate_sensors(zones, STARTER_SCALE, rng, datetime(2026, 10, 16).date())
    lots = generate_inventory_lots(zones, reqs, STARTER_SCALE, rng)
    manifest, lots, sensors = inject_edge_cases_and_plan_anomalies(zones, sensors, lots, reqs, rng)
    doors = generate_door_events(zones, STARTER_SCALE, manifest, rng)

    readings = []
    for chunk in generate_sensor_readings_chunked(sensors, zones, doors, manifest, STARTER_SCALE, DEFAULT_SEED):
        readings.extend(chunk)

    alarms = detect_environmental_excursion_alarms(zones, sensors, readings)
    alarms, bridges, lots = link_alarms_to_affected_lots(alarms, lots, reqs, manifest)
    ins, rem = generate_inspections_and_remediations(alarms, bridges, lots)

    # 1. Baseline dataset should pass validation
    res_clean = validate_dataset(
        whs, zones, reqs, sensors, readings, doors, lots, alarms, bridges, ins, rem, manifest.ground_truth_records
    )
    assert res_clean.is_valid is True

    # 2. Corrupt one lot's foreign key to point to non-existent zone
    corrupted_lots = [l.model_copy() for l in lots]
    corrupted_lots[0] = corrupted_lots[0].model_copy(update={"zone_id": "ZONE-NON-EXISTENT-999"})
    
    res_corrupt = validate_dataset(
        whs, zones, reqs, sensors, readings, doors, corrupted_lots, alarms, bridges, ins, rem, manifest.ground_truth_records
    )
    assert res_corrupt.is_valid is False
    assert any("orphans" in d["message"] for d in res_corrupt.details if d["status"] == "FAIL")


def test_validator_detects_duplicate_primary_keys():
    import random
    rng = random.Random(DEFAULT_SEED)
    reqs = generate_storage_requirements()
    whs = generate_warehouses(STARTER_SCALE, rng, datetime(2026, 10, 16, tzinfo=timezone.utc))
    zones = generate_zones(whs, STARTER_SCALE, rng)
    sensors = generate_sensors(zones, STARTER_SCALE, rng, datetime(2026, 10, 16).date())
    lots = generate_inventory_lots(zones, reqs, STARTER_SCALE, rng)
    manifest, lots, sensors = inject_edge_cases_and_plan_anomalies(zones, sensors, lots, reqs, rng)
    doors = generate_door_events(zones, STARTER_SCALE, manifest, rng)

    readings = []
    for chunk in generate_sensor_readings_chunked(sensors, zones, doors, manifest, STARTER_SCALE, DEFAULT_SEED):
        readings.extend(chunk)

    alarms = detect_environmental_excursion_alarms(zones, sensors, readings)
    alarms, bridges, lots = link_alarms_to_affected_lots(alarms, lots, reqs, manifest)
    ins, rem = generate_inspections_and_remediations(alarms, bridges, lots)

    # Inject duplicate warehouse
    dup_whs = whs + [whs[0].model_copy()]
    res_dup = validate_dataset(
        dup_whs, zones, reqs, sensors, readings, doors, lots, alarms, bridges, ins, rem, manifest.ground_truth_records
    )
    assert res_dup.is_valid is False
    assert any("PK Uniqueness: Warehouse" in d["check"] and d["status"] == "FAIL" for d in res_dup.details)
