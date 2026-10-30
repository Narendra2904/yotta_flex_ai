"""Master data generation for Warehouses, Zones, Storage Requirements, and Sensors."""

import random
from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Tuple
from wh_monitor.config import ScaleConfig, ZONE_PROFILES, STORAGE_REQUIREMENTS_DATA
from wh_monitor.models import Warehouse, Zone, StorageRequirement, Sensor


def generate_storage_requirements() -> List[StorageRequirement]:
    """Return catalog of standardized storage requirements."""
    return [StorageRequirement(**req) for req in STORAGE_REQUIREMENTS_DATA]


def generate_warehouses(scale: ScaleConfig, rng: random.Random, base_date: datetime) -> List[Warehouse]:
    """Generate deterministic warehouse master records."""
    warehouses = []
    regions = ["NA-EAST", "NA-WEST", "EU-CENTRAL", "APAC-SOUTH", "APAC-EAST"]
    metro_areas = [
        ("Chicago Hub", "742 Logistics Blvd, Chicago, IL 60601, USA"),
        ("Newark ColdVault", "12 ColdChain Way, Newark, NJ 07102, USA"),
        ("Rotterdam Port Gateway", "Havennummer 451, 3089 JK Rotterdam, Netherlands"),
        ("Frankfurt Biologics", "Industriepark Hoechst, 65926 Frankfurt, Germany"),
        ("Singapore Changi Hub", "9 Airline Rd, Singapore 819834"),
        ("Dallas Central Depot", "1000 Freight Ave, Dallas, TX 75201, USA"),
        ("Memphis Air Logistics", "2400 Democrat Rd, Memphis, TN 38132, USA"),
        ("Tokyo Bay Distribution", "2-1 Yashio, Shinagawa-ku, Tokyo 140-0003, Japan"),
        ("Los Angeles WestGate", "200 S Alameda St, Los Angeles, CA 90012, USA"),
        ("London Heathrow Terminal Hub", "Southern Perimeter Rd, Hounslow TW6 3PF, UK"),
    ]

    for i in range(1, scale.num_warehouses + 1):
        wh_id = f"WH-{i:03d}"
        metro_idx = (i - 1) % len(metro_areas)
        name, address = metro_areas[metro_idx]
        region = regions[(i - 1) % len(regions)]
        created_at = base_date - timedelta(days=365 + i * 10)

        warehouses.append(
            Warehouse(
                warehouse_id=wh_id,
                name=f"{name} ({wh_id})",
                region=region,
                address=address,
                total_zones=scale.zones_per_warehouse,
                operational_status="ACTIVE",
                created_at=created_at
            )
        )
    return warehouses


def generate_zones(warehouses: List[Warehouse], scale: ScaleConfig, rng: random.Random) -> List[Zone]:
    """Generate zone records for each warehouse adhering to profile distribution."""
    zones = []
    for wh in warehouses:
        for z_idx in range(1, scale.zones_per_warehouse + 1):
            zone_id = f"ZONE-{wh.warehouse_id}-{z_idx:03d}"
            # Rotate across zone profiles deterministically
            profile = ZONE_PROFILES[(z_idx - 1) % len(ZONE_PROFILES)]
            
            zone = Zone(
                zone_id=zone_id,
                warehouse_id=wh.warehouse_id,
                zone_name=f"{profile['name_prefix']} #{z_idx:02d}",
                zone_type=profile["type"],
                target_temp_c=float(profile["target_temp_c"]),
                temp_min_c=float(profile["temp_min_c"]),
                temp_max_c=float(profile["temp_max_c"]),
                target_humidity_pct=float(profile["target_humidity_pct"]),
                humidity_min_pct=float(profile["humidity_min_pct"]),
                humidity_max_pct=float(profile["humidity_max_pct"]),
                max_occupancy=profile["max_occupancy"],
                max_door_open_sec=profile["max_door_open_sec"],
                status="ACTIVE"
            )
            zones.append(zone)
    return zones


def generate_sensors(zones: List[Zone], scale: ScaleConfig, rng: random.Random, current_date: date) -> List[Sensor]:
    """Generate environmental sensors for each zone adhering to ID convention."""
    sensors = []
    # Standard sensor types per zone: TEMP, HUM, OCC
    sensor_types = ["TEMP", "HUM", "OCC"]
    sensor_type_full = {
        "TEMP": "TEMPERATURE",
        "HUM": "HUMIDITY",
        "OCC": "OCCUPANCY"
    }
    model_types = {
        "TEMP": "SENS-T2000-PRECISION",
        "HUM": "HUMID-S50-DUAL",
        "OCC": "PIR-RADAR-OCC-10"
    }

    for zone in zones:
        # Determine how many sensors to place in this zone
        count = scale.sensors_per_zone
        for s_idx in range(1, count + 1):
            type_code = sensor_types[(s_idx - 1) % len(sensor_types)]
            idx_for_type = ((s_idx - 1) // len(sensor_types)) + 1
            sensor_id = f"SNS-{zone.zone_id}-{type_code}-{idx_for_type:02d}"
            
            cal_offset_days = rng.randint(30, 180)
            cal_date = current_date - timedelta(days=cal_offset_days)
            cal_due = cal_date + timedelta(days=365)
            battery = round(rng.uniform(78.0, 99.8), 1)

            sensor = Sensor(
                sensor_id=sensor_id,
                zone_id=zone.zone_id,
                sensor_type=sensor_type_full[type_code],
                model_number=model_types[type_code],
                calibration_date=cal_date,
                calibration_due=cal_due,
                battery_level_pct=battery,
                drift_offset=0.0,
                status="ONLINE"
            )
            sensors.append(sensor)
    return sensors
