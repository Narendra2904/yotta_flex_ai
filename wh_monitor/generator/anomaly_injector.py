"""Anomaly and Edge-case injector to generate labeled synthetic scenarios."""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Set
from wh_monitor.models import Zone, Sensor, InventoryLot, StorageRequirement, GroundTruth
from wh_monitor.config import SIMULATION_START, SIMULATION_END


class AnomalyManifest:
    def __init__(self):
        self.incompatible_lots: List[InventoryLot] = []
        self.ambiguous_sensors: List[Dict[str, str]] = []
        self.sensor_outage_windows: Dict[str, Tuple[datetime, datetime]] = {}
        self.sensor_drifts: Dict[str, float] = {}
        self.door_ajar_zones: Set[str] = set()
        self.excursion_windows: List[Dict] = []
        self.unlinked_alarm_ids: Set[str] = set()
        self.ground_truth_records: List[GroundTruth] = []


def inject_edge_cases_and_plan_anomalies(
    zones: List[Zone],
    sensors: List[Sensor],
    lots: List[InventoryLot],
    requirements: List[StorageRequirement],
    rng: random.Random
) -> Tuple[AnomalyManifest, List[InventoryLot], List[Sensor]]:
    """Inject required negative edge cases into the dataset and record ground truth labels."""
    manifest = AnomalyManifest()
    anom_counter = 1
    req_map = {r.requirement_id: r for r in requirements}
    zones_by_id = {z.zone_id: z for z in zones}

    # 1. Edge Case 1: Lot assigned to incompatible zone
    # Deliberately modify ~3% of lots to be placed in completely incompatible zones
    num_incompatible = max(2, int(len(lots) * 0.03))
    incompatible_candidate_indices = rng.sample(range(len(lots)), num_incompatible)
    
    for idx in incompatible_candidate_indices:
        lot = lots[idx]
        req = req_map[lot.requirement_id]
        allowed = set(req.allowed_zone_types.split(","))
        
        # Find definitely incompatible zones
        incompat_zones = [z for z in zones if z.zone_type not in allowed]
        if incompat_zones:
            target_zone = rng.choice(incompat_zones)
            # Update lot zone
            lots[idx] = lot.model_copy(update={"zone_id": target_zone.zone_id})
            manifest.incompatible_lots.append(lots[idx])
            
            manifest.ground_truth_records.append(
                GroundTruth(
                    anomaly_id=f"ANOM-{anom_counter:05d}",
                    issue_type="INCOMPATIBLE_ZONE_ASSIGNMENT",
                    entity_type="InventoryLot",
                    entity_id=lot.lot_id,
                    zone_id=target_zone.zone_id,
                    start_time=lot.arrival_time,
                    end_time=lot.departure_time or SIMULATION_END,
                    expected_detection=True,
                    expected_alarm_type="COMPATIBILITY_VIOLATION",
                    expected_severity="CRITICAL",
                    rationale=(
                        f"Lot {lot.lot_id} requiring profile {req.profile_name} placed in "
                        f"incompatible zone type {target_zone.zone_type}."
                    )
                )
            )
            anom_counter += 1

    # 2. Edge Case 2: Sensor mapped to multiple zones without rationale
    # Select 2 sensors and inject duplicate mapping entry or secondary zone link
    num_ambiguous = min(2, len(sensors))
    selected_sensors = rng.sample(sensors, num_ambiguous)
    for s in selected_sensors:
        alt_zone = rng.choice([z for z in zones if z.zone_id != s.zone_id])
        manifest.ambiguous_sensors.append({
            "sensor_id": s.sensor_id,
            "primary_zone_id": s.zone_id,
            "conflicting_zone_id": alt_zone.zone_id
        })
        manifest.ground_truth_records.append(
            GroundTruth(
                anomaly_id=f"ANOM-{anom_counter:05d}",
                issue_type="AMBIGUOUS_SENSOR_ZONE_MAPPING",
                entity_type="Sensor",
                entity_id=s.sensor_id,
                zone_id=s.zone_id,
                start_time=SIMULATION_START,
                end_time=SIMULATION_END,
                expected_detection=True,
                expected_alarm_type="TOPOLOGY_INCONSISTENCY",
                expected_severity="HIGH",
                rationale=(
                    f"Sensor {s.sensor_id} is concurrently referenced by primary zone {s.zone_id} "
                    f"and conflicting zone {alt_zone.zone_id} without zoning rationale."
                )
            )
        )
        anom_counter += 1

    # 3. Edge Case 3: Reading gap / Silent sensor outage treated as normal
    # Select sensors to have a 4 to 8 hour silent outage window
    temp_sensors = [s for s in sensors if s.sensor_type == "TEMPERATURE"]
    num_gaps = max(1, min(4, len(temp_sensors)))
    gap_sensors = rng.sample(temp_sensors, num_gaps)
    for s in gap_sensors:
        outage_start = SIMULATION_START + timedelta(days=rng.randint(2, 8), hours=rng.randint(1, 12))
        outage_end = outage_start + timedelta(hours=rng.randint(4, 7))
        manifest.sensor_outage_windows[s.sensor_id] = (outage_start, outage_end)
        
        manifest.ground_truth_records.append(
            GroundTruth(
                anomaly_id=f"ANOM-{anom_counter:05d}",
                issue_type="SILENT_SENSOR_OUTAGE_GAP",
                entity_type="Sensor",
                entity_id=s.sensor_id,
                zone_id=s.zone_id,
                start_time=outage_start,
                end_time=outage_end,
                expected_detection=True,
                expected_alarm_type="SENSOR_OUTAGE_GAP",
                expected_severity="HIGH",
                rationale=(
                    f"Sensor {s.sensor_id} stopped publishing readings between {outage_start.isoformat()} "
                    f"and {outage_end.isoformat()} (missing heartbeat gap)."
                )
            )
        )
        anom_counter += 1

    # 4. Sensor Drift
    # Select 2 sensors to have gradual positive/negative decalibration drift
    drift_candidates = [s for s in sensors if s.sensor_type in ["TEMPERATURE", "HUMIDITY"] and s.sensor_id not in manifest.sensor_outage_windows]
    num_drifts = min(2, len(drift_candidates))
    for s in rng.sample(drift_candidates, num_drifts):
        drift_val = round(rng.choice([-3.8, +4.2]), 2)
        manifest.sensor_drifts[s.sensor_id] = drift_val
        manifest.ground_truth_records.append(
            GroundTruth(
                anomaly_id=f"ANOM-{anom_counter:05d}",
                issue_type="SENSOR_DRIFT_EXCESSIVE",
                entity_type="Sensor",
                entity_id=s.sensor_id,
                zone_id=s.zone_id,
                start_time=SIMULATION_START + timedelta(days=3),
                end_time=SIMULATION_END,
                expected_detection=True,
                expected_alarm_type="SENSOR_DRIFT_EXCESSIVE",
                expected_severity="MEDIUM",
                rationale=f"Sensor {s.sensor_id} exhibits continuous uncalibrated drift of {drift_val} units."
            )
        )
        anom_counter += 1

    # 5. Localized Chiller Excursions & Door Ajar Events
    # Inject 3 localized thermal excursions in cold zones
    cold_zones = [z for z in zones if z.zone_type in ["COLD_STORAGE", "ULTRA_LOW_FREEZE"]]
    if not cold_zones:
        cold_zones = zones[:2]
        
    num_excursions = min(3, len(cold_zones))
    excursion_zones = rng.sample(cold_zones, num_excursions)
    for z in excursion_zones:
        exc_start = SIMULATION_START + timedelta(days=rng.randint(3, 9), hours=rng.randint(2, 14))
        exc_duration_hours = rng.randint(2, 6)
        exc_end = exc_start + timedelta(hours=exc_duration_hours)
        peak_delta = rng.uniform(8.0, 16.0)
        
        manifest.excursion_windows.append({
            "zone_id": z.zone_id,
            "start_time": exc_start,
            "end_time": exc_end,
            "peak_delta_c": peak_delta,
            "cause": "HVAC_CHILLER_FAIL"
        })
        
        manifest.ground_truth_records.append(
            GroundTruth(
                anomaly_id=f"ANOM-{anom_counter:05d}",
                issue_type="THERMAL_EXCURSION_CHILLER_FAIL",
                entity_type="Zone",
                entity_id=z.zone_id,
                zone_id=z.zone_id,
                start_time=exc_start,
                end_time=exc_end,
                expected_detection=True,
                expected_alarm_type="TEMP_EXCURSION_HIGH",
                expected_severity="CRITICAL",
                rationale=(
                    f"Refrigeration failure in zone {z.zone_id} causing thermal runaway (+{peak_delta:.1f}°C) "
                    f"for {exc_duration_hours} hours."
                )
            )
        )
        anom_counter += 1

    # 6. Edge Case 4: Alarm not linked to affected lots
    # We mark one future alarm ID to deliberately drop affected lots during bridge generation
    # To be populated when alarms are generated
    
    return manifest, lots, sensors
