"""Configuration and Scale Profiles for Synthetic Data Generation & Risk Engine."""

from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Dict, Any

DEFAULT_SEED = 20261022

# Simulation Baseline Window: 14 days of operations in late October 2026
SIMULATION_START = datetime(2026, 10, 16, 0, 0, 0, tzinfo=timezone.utc)
SIMULATION_END = datetime(2026, 10, 30, 0, 0, 0, tzinfo=timezone.utc)


@dataclass
class ScaleConfig:
    name: str
    num_warehouses: int
    zones_per_warehouse: int
    sensors_per_zone: int
    num_readings: int
    num_lots: int
    num_door_events: int
    reading_interval_seconds: int


STARTER_SCALE = ScaleConfig(
    name="starter",
    num_warehouses=2,
    zones_per_warehouse=5,  # 10 zones total
    sensors_per_zone=3,     # 30 sensors total (TEMP, HUM, OCC per zone)
    num_readings=10_000,
    num_lots=200,
    num_door_events=120,
    reading_interval_seconds=300  # 5 min interval
)

FULL_SCALE = ScaleConfig(
    name="full",
    num_warehouses=10,
    zones_per_warehouse=10,  # 100 zones total
    sensors_per_zone=5,      # 500 sensors total
    num_readings=1_000_000,
    num_lots=10_000,
    num_door_events=2_500,
    reading_interval_seconds=60   # 1 min interval
)

# Standard Zone Profiles
ZONE_PROFILES = [
    {
        "type": "ULTRA_LOW_FREEZE",
        "name_prefix": "Ultra-Low Cryo Vault",
        "target_temp_c": -20.0,
        "temp_min_c": -25.0,
        "temp_max_c": -15.0,
        "target_humidity_pct": 25.0,
        "humidity_min_pct": 10.0,
        "humidity_max_pct": 40.0,
        "max_occupancy": 3,
        "max_door_open_sec": 60,
    },
    {
        "type": "COLD_STORAGE",
        "name_prefix": "Cold Chain Bio-Hold",
        "target_temp_c": 4.0,
        "temp_min_c": 2.0,
        "temp_max_c": 8.0,
        "target_humidity_pct": 45.0,
        "humidity_min_pct": 30.0,
        "humidity_max_pct": 60.0,
        "max_occupancy": 5,
        "max_door_open_sec": 90,
    },
    {
        "type": "CONTROLLED_ROOM_TEMP",
        "name_prefix": "Controlled Pharma Room",
        "target_temp_c": 20.0,
        "temp_min_c": 18.0,
        "temp_max_c": 24.0,
        "target_humidity_pct": 50.0,
        "humidity_min_pct": 35.0,
        "humidity_max_pct": 65.0,
        "max_occupancy": 8,
        "max_door_open_sec": 180,
    },
    {
        "type": "AMBIENT",
        "name_prefix": "General Ambient Staging",
        "target_temp_c": 22.0,
        "temp_min_c": 15.0,
        "temp_max_c": 30.0,
        "target_humidity_pct": 55.0,
        "humidity_min_pct": 20.0,
        "humidity_max_pct": 75.0,
        "max_occupancy": 15,
        "max_door_open_sec": 300,
    },
    {
        "type": "HUMIDITY_CONTROLLED",
        "name_prefix": "Dry Moisture Barrier Vault",
        "target_temp_c": 19.0,
        "temp_min_c": 16.0,
        "temp_max_c": 22.0,
        "target_humidity_pct": 30.0,
        "humidity_min_pct": 20.0,
        "humidity_max_pct": 38.0,
        "max_occupancy": 4,
        "max_door_open_sec": 75,
    },
    {
        "type": "LOADING_DOCK",
        "name_prefix": "Rapid Ingress Bay",
        "target_temp_c": 18.0,
        "temp_min_c": 10.0,
        "temp_max_c": 28.0,
        "target_humidity_pct": 60.0,
        "humidity_min_pct": 25.0,
        "humidity_max_pct": 85.0,
        "max_occupancy": 20,
        "max_door_open_sec": 600,
    },
]

# Master Storage Requirements Catalog
STORAGE_REQUIREMENTS_DATA = [
    {
        "requirement_id": "REQ-VACCINE-ULTRA",
        "profile_name": "mRNA Vaccines / Ultra-Cold Cryo (-25C to -15C)",
        "allowed_zone_types": "ULTRA_LOW_FREEZE",
        "temp_crit_min_c": -28.0,
        "temp_warn_min_c": -25.0,
        "temp_warn_max_c": -15.0,
        "temp_crit_max_c": -12.0,
        "humidity_crit_min_pct": 10.0,
        "humidity_crit_max_pct": 50.0,
        "max_excursion_duration_min": 30,
        "status": "ACTIVE"
    },
    {
        "requirement_id": "REQ-PHARMA-COLD",
        "profile_name": "Refrigerated Biologics & Insulin (+2C to +8C)",
        "allowed_zone_types": "COLD_STORAGE",
        "temp_crit_min_c": 1.5,
        "temp_warn_min_c": 2.0,
        "temp_warn_max_c": 8.0,
        "temp_crit_max_c": 9.5,
        "humidity_crit_min_pct": 25.0,
        "humidity_crit_max_pct": 65.0,
        "max_excursion_duration_min": 45,
        "status": "ACTIVE"
    },
    {
        "requirement_id": "REQ-PERISHABLE-FRESH",
        "profile_name": "Fresh Produce & Dairy (+1C to +6C)",
        "allowed_zone_types": "COLD_STORAGE,LOADING_DOCK",
        "temp_crit_min_c": 0.5,
        "temp_warn_min_c": 1.0,
        "temp_warn_max_c": 6.5,
        "temp_crit_max_c": 8.0,
        "humidity_crit_min_pct": 40.0,
        "humidity_crit_max_pct": 85.0,
        "max_excursion_duration_min": 60,
        "status": "ACTIVE"
    },
    {
        "requirement_id": "REQ-DRY-AMBIENT",
        "profile_name": "Dry Goods & Standard Tablets (+15C to +25C)",
        "allowed_zone_types": "CONTROLLED_ROOM_TEMP,AMBIENT",
        "temp_crit_min_c": 12.0,
        "temp_warn_min_c": 15.0,
        "temp_warn_max_c": 25.0,
        "temp_crit_max_c": 30.0,
        "humidity_crit_min_pct": 15.0,
        "humidity_crit_max_pct": 70.0,
        "max_excursion_duration_min": 180,
        "status": "ACTIVE"
    },
    {
        "requirement_id": "REQ-MOISTURE-SENSITIVE",
        "profile_name": "Active API & Moisture Sensitive Reagents",
        "allowed_zone_types": "HUMIDITY_CONTROLLED",
        "temp_crit_min_c": 15.0,
        "temp_warn_min_c": 18.0,
        "temp_warn_max_c": 22.0,
        "temp_crit_max_c": 26.0,
        "humidity_crit_min_pct": 10.0,
        "humidity_crit_max_pct": 40.0,
        "max_excursion_duration_min": 40,
        "status": "ACTIVE"
    }
]
