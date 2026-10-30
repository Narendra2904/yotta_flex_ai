"""Tests for Risk Engine: Excursion, Door Ajar, Outage, Traceability & Workflow."""

import random
from datetime import datetime, timezone
from wh_monitor.config import STARTER_SCALE, DEFAULT_SEED
from wh_monitor.generator.master_data import generate_storage_requirements, generate_warehouses, generate_zones, generate_sensors
from wh_monitor.generator.lot_generator import generate_inventory_lots
from wh_monitor.generator.anomaly_injector import inject_edge_cases_and_plan_anomalies
from wh_monitor.generator.telemetry_gen import generate_door_events, generate_sensor_readings_chunked
from wh_monitor.engine.monitor import detect_sensor_outage_alarms, detect_door_ajar_alarms, detect_environmental_excursion_alarms
from wh_monitor.engine.traceability import link_alarms_to_affected_lots
from wh_monitor.engine.workflow import generate_inspections_and_remediations


def test_end_to_end_engine_flow():
    rng = random.Random(DEFAULT_SEED)
    reqs = generate_storage_requirements()
    whs = generate_warehouses(STARTER_SCALE, rng, datetime(2026, 10, 16, tzinfo=timezone.utc))
    zones = generate_zones(whs, STARTER_SCALE, rng)
    sensors = generate_sensors(zones, STARTER_SCALE, rng, datetime(2026, 10, 16).date())
    lots = generate_inventory_lots(zones, reqs, STARTER_SCALE, rng)
    manifest, lots, sensors = inject_edge_cases_and_plan_anomalies(zones, sensors, lots, reqs, rng)
    door_events = generate_door_events(zones, STARTER_SCALE, manifest, rng)

    readings = []
    for chunk in generate_sensor_readings_chunked(sensors, zones, door_events, manifest, STARTER_SCALE, DEFAULT_SEED):
        readings.extend(chunk)

    # 1. Monitoring detection
    outages = detect_sensor_outage_alarms(sensors, readings)
    door_alarms = detect_door_ajar_alarms(zones, door_events)
    excursions = detect_environmental_excursion_alarms(zones, sensors, readings)

    total_alarms = outages + door_alarms + excursions
    assert len(total_alarms) > 0, "Monitoring should produce alarms"

    # 2. Traceability linking
    updated_alarms, bridges, updated_lots = link_alarms_to_affected_lots(total_alarms, lots, reqs, manifest)
    assert len(bridges) > 0, "Bridges should link alarms to lots"

    # Check unlinked edge case was captured in manifest
    assert len(manifest.unlinked_alarm_ids) >= 1

    # 3. Workflow inspections and remediations
    inspections, remediations = generate_inspections_and_remediations(updated_alarms, bridges, updated_lots)
    assert len(inspections) > 0
    assert len(remediations) == len(inspections)

    for ins in inspections:
        assert ins.inspector_role in ["QUALITY_ENGINEER", "PLANT_OPERATOR", "MAINTENANCE_ENGINEER"]
