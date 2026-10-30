"""Tests for master data and inventory lot generators."""

import random
from datetime import datetime, timezone
from wh_monitor.config import STARTER_SCALE
from wh_monitor.generator.master_data import (
    generate_storage_requirements, generate_warehouses, generate_zones, generate_sensors
)
from wh_monitor.generator.lot_generator import generate_inventory_lots


def test_master_data_hierarchy():
    rng = random.Random(42)
    base_date = datetime(2026, 10, 16, tzinfo=timezone.utc)
    
    reqs = generate_storage_requirements()
    assert len(reqs) >= 4

    whs = generate_warehouses(STARTER_SCALE, rng, base_date)
    assert len(whs) == STARTER_SCALE.num_warehouses
    for w in whs:
        assert w.warehouse_id.startswith("WH-")

    zones = generate_zones(whs, STARTER_SCALE, rng)
    assert len(zones) == STARTER_SCALE.num_warehouses * STARTER_SCALE.zones_per_warehouse
    for z in zones:
        assert z.zone_id.startswith(f"ZONE-{z.warehouse_id}")

    sensors = generate_sensors(zones, STARTER_SCALE, rng, base_date.date())
    assert len(sensors) == len(zones) * STARTER_SCALE.sensors_per_zone
    for s in sensors:
        assert s.sensor_id.startswith(f"SNS-{s.zone_id}")


def test_lot_generator_properties():
    rng = random.Random(42)
    base_date = datetime(2026, 10, 16, tzinfo=timezone.utc)
    reqs = generate_storage_requirements()
    whs = generate_warehouses(STARTER_SCALE, rng, base_date)
    zones = generate_zones(whs, STARTER_SCALE, rng)

    lots = generate_inventory_lots(zones, reqs, STARTER_SCALE, rng)
    assert len(lots) == STARTER_SCALE.num_lots

    for lot in lots:
        assert lot.lot_id.startswith("LOT-2026-")
        assert lot.quantity >= 1
        assert lot.unit_price_usd > 0.0
        # Check total value calculation
        expected = round(lot.quantity * lot.unit_price_usd, 2)
        assert abs(lot.total_value_usd - expected) < 0.05
