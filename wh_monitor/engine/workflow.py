"""Workflow Engine: Automates Inspection dispatch, actor triage, and Remediation execution."""

from datetime import datetime, timedelta
from typing import List, Tuple
from wh_monitor.models import Alarm, AlarmAffectedLot, Inspection, Remediation, InventoryLot


def generate_inspections_and_remediations(
    alarms: List[Alarm],
    bridges: List[AlarmAffectedLot],
    lots: List[InventoryLot]
) -> Tuple[List[Inspection], List[Remediation]]:
    """Create lifecycle Inspections and Remediations for triggered Alarms."""
    inspections: List[Inspection] = []
    remediations: List[Remediation] = []
    
    bridges_by_alarm = {}
    for b in bridges:
        bridges_by_alarm.setdefault(b.alarm_id, []).append(b)

    for alarm in alarms:
        # Generate inspection for critical, high, or medium alarms with affected lots
        linked_bridges = bridges_by_alarm.get(alarm.alarm_id, [])
        if alarm.severity not in ["CRITICAL", "HIGH"] and len(linked_bridges) == 0:
            continue

        ins_id = f"INS-{alarm.alarm_id}-01"
        ins_time = alarm.start_time + timedelta(minutes=20)
        
        # Actor role mapping
        if "TEMP" in alarm.alarm_type or "HUMIDITY" in alarm.alarm_type:
            role = "QUALITY_ENGINEER"
            inspector_id = "QA-SENIOR-104"
            findings = (
                f"Thermal excursion confirmed in {alarm.zone_id}. Peak deviation: {alarm.peak_excursion:.1f} vs limit {alarm.threshold_limit:.1f}. "
                f"Evaluated {len(linked_bridges)} inventory lots for temperature abuse."
            )
            has_damage = any(b.risk_category == "CRITICAL_VIOLATION" for b in linked_bridges)
            action = "CONDEMN_LOT" if has_damage else "QUARANTINE_LOT"
            rem_action = "LOT_CONDEMNATION" if has_damage else "LOT_QUARANTINE"
        elif "DOOR" in alarm.alarm_type:
            role = "PLANT_OPERATOR"
            inspector_id = "OPR-LEAD-202"
            findings = (
                f"Zone door left open for {alarm.trigger_value:.0f} seconds (limit {alarm.threshold_limit:.0f}s). "
                f"Physical inspection showed seal intact, door latch obstruction cleared."
            )
            has_damage = False
            action = "DOOR_SEAL_REPAIR"
            rem_action = "DOOR_SEAL_REPAIR"
        else:  # SENSOR
            role = "MAINTENANCE_ENGINEER"
            inspector_id = "TECH-OT-550"
            findings = (
                f"Sensor telemetry gap detected. Battery measured at nominal voltage, gateway connection reset. "
                f"Re-established RF packet transmission."
            )
            has_damage = False
            action = "REPLACE_SENSOR"
            rem_action = "SENSOR_RECALIBRATION"

        inspection = Inspection(
            inspection_id=ins_id,
            alarm_id=alarm.alarm_id,
            inspector_role=role,
            inspector_id=inspector_id,
            inspection_time=ins_time,
            findings=findings,
            physical_damage=has_damage,
            recommended_action=action,
            status="COMPLETED"
        )
        inspections.append(inspection)

        # Dual sign-off remediation
        rem_id = f"REM-{ins_id}-01"
        repair_overhead = 150.0 if not has_damage else 350.0
        total_rem_loss = round(alarm.total_loss_usd + repair_overhead, 2)
        
        remediation = Remediation(
            remediation_id=rem_id,
            inspection_id=ins_id,
            action_type=rem_action,
            lot_id=linked_bridges[0].lot_id if linked_bridges else None,
            sensor_id=alarm.sensor_id,
            executed_by=inspector_id,
            approved_by="PLANT-DIR-901",
            completed_at=ins_time + timedelta(hours=2),
            financial_impact_usd=total_rem_loss,
            status="VERIFIED"
        )
        remediations.append(remediation)

    return inspections, remediations
