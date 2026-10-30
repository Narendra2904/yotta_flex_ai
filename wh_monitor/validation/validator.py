"""Comprehensive validation engine covering PK uniqueness, FK integrity, enums, dates, and reconciliation."""

from typing import Dict, List, Any
from datetime import datetime
from wh_monitor.models import (
    Warehouse, Zone, StorageRequirement, Sensor, SensorReading,
    DoorEvent, InventoryLot, Alarm, AlarmAffectedLot, Inspection, Remediation, GroundTruth
)


class ValidationResult:
    def __init__(self):
        self.is_valid: bool = True
        self.total_checks: int = 0
        self.passed_checks: int = 0
        self.failed_checks: int = 0
        self.details: List[Dict[str, Any]] = []

    def record(self, check_name: str, passed: bool, message: str, meta: Dict[str, Any] = None):
        self.total_checks += 1
        if passed:
            self.passed_checks += 1
        else:
            self.failed_checks += 1
            self.is_valid = False
            
        self.details.append({
            "check": check_name,
            "status": "PASS" if passed else "FAIL",
            "message": message,
            "meta": meta or {}
        })

    def summary(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "total_checks": self.total_checks,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "details": self.details
        }


def validate_dataset(
    warehouses: List[Warehouse],
    zones: List[Zone],
    requirements: List[StorageRequirement],
    sensors: List[Sensor],
    readings: List[SensorReading],
    door_events: List[DoorEvent],
    lots: List[InventoryLot],
    alarms: List[Alarm],
    bridges: List[AlarmAffectedLot],
    inspections: List[Inspection],
    remediations: List[Remediation],
    ground_truth: List[GroundTruth]
) -> ValidationResult:
    """Execute all Step 8 validation rules across dataset."""
    res = ValidationResult()

    # 1. Primary Key Uniqueness
    def check_pk(items, key_fn, name):
        seen = set()
        duplicates = set()
        for it in items:
            k = key_fn(it)
            if k in seen:
                duplicates.add(k)
            seen.add(k)
        passed = len(duplicates) == 0
        res.record(
            f"PK Uniqueness: {name}",
            passed,
            f"{len(seen)} unique PKs, {len(duplicates)} duplicates detected."
            if passed else f"FAIL: Duplicates found: {list(duplicates)[:5]}",
            {"entity": name, "count": len(seen), "duplicates": len(duplicates)}
        )

    check_pk(warehouses, lambda x: x.warehouse_id, "Warehouse")
    check_pk(zones, lambda x: x.zone_id, "Zone")
    check_pk(requirements, lambda x: x.requirement_id, "StorageRequirement")
    check_pk(sensors, lambda x: x.sensor_id, "Sensor")
    check_pk(readings, lambda x: x.reading_id, "SensorReading")
    check_pk(door_events, lambda x: x.door_event_id, "DoorEvent")
    check_pk(lots, lambda x: x.lot_id, "InventoryLot")
    check_pk(alarms, lambda x: x.alarm_id, "Alarm")
    check_pk(bridges, lambda x: x.bridge_id, "AlarmAffectedLot")
    check_pk(inspections, lambda x: x.inspection_id, "Inspection")
    check_pk(remediations, lambda x: x.remediation_id, "Remediation")
    check_pk(ground_truth, lambda x: x.anomaly_id, "GroundTruth")

    # 2. Foreign Key Referential Integrity
    wh_ids = {w.warehouse_id for w in warehouses}
    zone_ids = {z.zone_id for z in zones}
    req_ids = {r.requirement_id for r in requirements}
    sensor_ids = {s.sensor_id for s in sensors}
    lot_ids = {l.lot_id for l in lots}
    alarm_ids = {a.alarm_id for a in alarms}
    ins_ids = {i.inspection_id for i in inspections}

    # Zone -> Warehouse
    orphan_zones = [z.zone_id for z in zones if z.warehouse_id not in wh_ids]
    res.record("FK Integrity: zones.warehouse_id", len(orphan_zones) == 0, f"{len(orphan_zones)} orphans")

    # Sensor -> Zone
    orphan_sensors = [s.sensor_id for s in sensors if s.zone_id not in zone_ids]
    res.record("FK Integrity: sensors.zone_id", len(orphan_sensors) == 0, f"{len(orphan_sensors)} orphans")

    # SensorReading -> Sensor
    orphan_readings = [r.reading_id for r in readings if r.sensor_id not in sensor_ids]
    res.record("FK Integrity: sensor_readings.sensor_id", len(orphan_readings) == 0, f"{len(orphan_readings)} orphans")

    # DoorEvent -> Zone
    orphan_doors = [d.door_event_id for d in door_events if d.zone_id not in zone_ids]
    res.record("FK Integrity: door_events.zone_id", len(orphan_doors) == 0, f"{len(orphan_doors)} orphans")

    # InventoryLot -> Zone & StorageRequirement
    orphan_lot_zones = [l.lot_id for l in lots if l.zone_id not in zone_ids]
    orphan_lot_reqs = [l.lot_id for l in lots if l.requirement_id not in req_ids]
    res.record("FK Integrity: inventory_lots.zone_id", len(orphan_lot_zones) == 0, f"{len(orphan_lot_zones)} orphans")
    res.record("FK Integrity: inventory_lots.requirement_id", len(orphan_lot_reqs) == 0, f"{len(orphan_lot_reqs)} orphans")

    # Alarm -> Zone
    orphan_alarms = [a.alarm_id for a in alarms if a.zone_id not in zone_ids]
    res.record("FK Integrity: alarms.zone_id", len(orphan_alarms) == 0, f"{len(orphan_alarms)} orphans")

    # AlarmAffectedLot -> Alarm & Lot
    orphan_bridge_alarms = [b.bridge_id for b in bridges if b.alarm_id not in alarm_ids]
    orphan_bridge_lots = [b.bridge_id for b in bridges if b.lot_id not in lot_ids]
    res.record("FK Integrity: alarm_affected_lots.alarm_id", len(orphan_bridge_alarms) == 0, f"{len(orphan_bridge_alarms)} orphans")
    res.record("FK Integrity: alarm_affected_lots.lot_id", len(orphan_bridge_lots) == 0, f"{len(orphan_bridge_lots)} orphans")

    # Inspection -> Alarm
    orphan_inspections = [i.inspection_id for i in inspections if i.alarm_id not in alarm_ids]
    res.record("FK Integrity: inspections.alarm_id", len(orphan_inspections) == 0, f"{len(orphan_inspections)} orphans")

    # Remediation -> Inspection
    orphan_remediations = [rem.remediation_id for rem in remediations if rem.inspection_id not in ins_ids]
    res.record("FK Integrity: remediations.inspection_id", len(orphan_remediations) == 0, f"{len(orphan_remediations)} orphans")

    # 3. Allowed Enums
    allowed_wh_status = {"ACTIVE", "MAINTENANCE", "DECOMMISSIONED"}
    invalid_wh = [w.warehouse_id for w in warehouses if w.operational_status not in allowed_wh_status]
    res.record("Enum Check: warehouses.operational_status", len(invalid_wh) == 0, f"{len(invalid_wh)} invalid status")

    allowed_lot_states = {"RECEIVED", "STORED", "QUARANTINED", "RELEASED", "CONDEMNED"}
    invalid_lots = [l.lot_id for l in lots if l.lifecycle_state not in allowed_lot_states]
    res.record("Enum Check: inventory_lots.lifecycle_state", len(invalid_lots) == 0, f"{len(invalid_lots)} invalid states")

    allowed_alarm_severities = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
    invalid_severities = [a.alarm_id for a in alarms if a.severity not in allowed_alarm_severities]
    res.record("Enum Check: alarms.severity", len(invalid_severities) == 0, f"{len(invalid_severities)} invalid severities")

    # 4. Date Ordering
    date_inversions = []
    for l in lots:
        if l.departure_time and l.departure_time < l.arrival_time:
            date_inversions.append(l.lot_id)
    res.record("Date Ordering: inventory_lots arrival <= departure", len(date_inversions) == 0, f"{len(date_inversions)} inversions")

    door_inversions = [d.door_event_id for d in door_events if d.closed_at < d.opened_at]
    res.record("Date Ordering: door_events opened_at <= closed_at", len(door_inversions) == 0, f"{len(door_inversions)} inversions")

    alarm_inversions = [a.alarm_id for a in alarms if a.end_time and a.end_time < a.start_time]
    res.record("Date Ordering: alarms start_time <= end_time", len(alarm_inversions) == 0, f"{len(alarm_inversions)} inversions")

    bridge_inversions = [b.bridge_id for b in bridges if b.overlap_end < b.overlap_start]
    res.record("Date Ordering: alarm_affected_lots overlap_start <= overlap_end", len(bridge_inversions) == 0, f"{len(bridge_inversions)} inversions")

    # 5. Arithmetic Reconciliation
    lot_math_errors = []
    for l in lots:
        expected_val = round(l.quantity * l.unit_price_usd, 2)
        if abs(l.total_value_usd - expected_val) > 0.05:
            lot_math_errors.append(l.lot_id)
    res.record("Arithmetic: inventory_lots total_value == qty * unit_price", len(lot_math_errors) == 0, f"{len(lot_math_errors)} errors")

    door_duration_errors = []
    for d in door_events:
        sec = int((d.closed_at - d.opened_at).total_seconds())
        if abs(d.duration_sec - sec) > 2:
            door_duration_errors.append(d.door_event_id)
    res.record("Arithmetic: door_events duration_sec reconciles to closed_at - opened_at", len(door_duration_errors) == 0, f"{len(door_duration_errors)} errors")

    # Alarm affected lot count reconciliation
    bridges_per_alarm: Dict[str, int] = {}
    for b in bridges:
        bridges_per_alarm[b.alarm_id] = bridges_per_alarm.get(b.alarm_id, 0) + 1
        
    alarm_lot_count_mismatches = []
    for a in alarms:
        expected_cnt = bridges_per_alarm.get(a.alarm_id, 0)
        if a.affected_lot_count != expected_cnt:
            alarm_lot_count_mismatches.append(a.alarm_id)
    res.record(
        "Arithmetic: alarm.affected_lot_count reconciles to bridges count",
        len(alarm_lot_count_mismatches) == 0,
        f"{len(alarm_lot_count_mismatches)} mismatches"
    )

    # 6. Required Edge Cases in Ground Truth
    gt_types = {gt.issue_type for gt in ground_truth}
    required_edge_cases = {
        "INCOMPATIBLE_ZONE_ASSIGNMENT",
        "AMBIGUOUS_SENSOR_ZONE_MAPPING",
        "SILENT_SENSOR_OUTAGE_GAP",
        "UNLINKED_ALARM_AFFECTED_LOTS"
    }
    missing_edge_cases = required_edge_cases - gt_types
    res.record(
        "Edge Case Coverage: All 4 prompt-required edge cases present in ground truth",
        len(missing_edge_cases) == 0,
        f"Present: {list(gt_types)}, Missing: {list(missing_edge_cases)}"
    )

    return res
