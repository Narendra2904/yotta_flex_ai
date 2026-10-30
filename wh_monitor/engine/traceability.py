"""Traceability Engine: Spatiotemporal overlap linking, thermal dosage, and lot risk assessment."""

from datetime import datetime, timezone
from typing import List, Dict, Tuple, Set
from wh_monitor.models import Alarm, InventoryLot, StorageRequirement, AlarmAffectedLot, GroundTruth
from wh_monitor.generator.anomaly_injector import AnomalyManifest
from wh_monitor.config import SIMULATION_END


def link_alarms_to_affected_lots(
    alarms: List[Alarm],
    lots: List[InventoryLot],
    requirements: List[StorageRequirement],
    manifest: AnomalyManifest
) -> Tuple[List[Alarm], List[AlarmAffectedLot], List[InventoryLot]]:
    """
    Perform spatiotemporal joins between Alarms and InventoryLots.
    Calculate degree-hours, classify risk, update lot states, and inject the unlinked alarm edge case.
    """
    req_by_id = {r.requirement_id: r for r in requirements}
    lots_by_id = {lot.lot_id: lot for lot in lots}
    
    # Pre-index lots by zone
    lots_by_zone: Dict[str, List[InventoryLot]] = {}
    for lot in lots:
        lots_by_zone.setdefault(lot.zone_id, []).append(lot)

    bridge_records: List[AlarmAffectedLot] = []
    updated_alarms: List[Alarm] = []

    # Pick one critical/high alarm with dwelling lots to be the deliberate unlinked edge case
    candidate_unlinked_alarm_id = None
    for a in alarms:
        if a.severity in ["CRITICAL", "HIGH"] and a.zone_id in lots_by_zone:
            candidate_unlinked_alarm_id = a.alarm_id
            break

    anom_counter = len(manifest.ground_truth_records) + 1

    for alarm in alarms:
        zone_lots = lots_by_zone.get(alarm.zone_id, [])
        alarm_end = alarm.end_time or SIMULATION_END
        
        # Check if this alarm is the deliberate unlinked anomaly
        if alarm.alarm_id == candidate_unlinked_alarm_id:
            manifest.unlinked_alarm_ids.add(alarm.alarm_id)
            manifest.ground_truth_records.append(
                GroundTruth(
                    anomaly_id=f"ANOM-{anom_counter:05d}",
                    issue_type="UNLINKED_ALARM_AFFECTED_LOTS",
                    entity_type="Alarm",
                    entity_id=alarm.alarm_id,
                    zone_id=alarm.zone_id,
                    start_time=alarm.start_time,
                    end_time=alarm_end,
                    expected_detection=True,
                    expected_alarm_type="TRACEABILITY_GAP",
                    expected_severity="CRITICAL",
                    rationale=(
                        f"Alarm {alarm.alarm_id} occurred with {len(zone_lots)} active dwelling lots in "
                        f"zone {alarm.zone_id}, but affected lots were omitted from downstream bridge table."
                    )
                )
            )
            anom_counter += 1
            # Deliberately omit bridge creation to simulate traceability failure
            updated_alarms.append(
                alarm.model_copy(update={"affected_lot_count": 0, "total_loss_usd": 0.0})
            )
            continue

        linked_bridges = []
        alarm_loss = 0.0

        for lot in zone_lots:
            lot_dep = lot.departure_time or SIMULATION_END
            # Check temporal intersection: lot arrival < alarm_end AND lot departure > alarm_start
            if lot.arrival_time < alarm_end and lot_dep > alarm.start_time:
                overlap_start = max(alarm.start_time, lot.arrival_time)
                overlap_end = min(alarm_end, lot_dep)
                
                exp_seconds = max(0.0, (overlap_end - overlap_start).total_seconds())
                exp_hours = round(exp_seconds / 3600.0, 2)
                
                if exp_hours > 0.05:  # At least 3 minutes overlap
                    # Thermal dosage / degree hours
                    temp_delta = abs(alarm.peak_excursion - alarm.threshold_limit) if alarm.peak_excursion else 2.0
                    degree_hours = round(exp_hours * temp_delta, 2)
                    
                    req = req_by_id.get(lot.requirement_id)
                    max_dur_hours = (req.max_excursion_duration_min / 60.0) if req else 1.0
                    
                    # Risk evaluation
                    if exp_hours >= max_dur_hours or alarm.severity == "CRITICAL":
                        risk_cat = "CRITICAL_VIOLATION"
                        disposition = "CONDEMNED"
                        alarm_loss += lot.total_value_usd
                        lots_by_id[lot.lot_id] = lot.model_copy(update={"lifecycle_state": "CONDEMNED"})
                    elif exp_hours >= max_dur_hours * 0.5:
                        risk_cat = "MODERATE_EXPOSURE"
                        disposition = "QUARANTINED"
                        lots_by_id[lot.lot_id] = lot.model_copy(update={"lifecycle_state": "QUARANTINED"})
                    else:
                        risk_cat = "LOW_RISK"
                        disposition = "ASSESSED"

                    bridge_id = f"AFL-{alarm.alarm_id}-{lot.lot_id}"
                    bridge = AlarmAffectedLot(
                        bridge_id=bridge_id,
                        alarm_id=alarm.alarm_id,
                        lot_id=lot.lot_id,
                        overlap_start=overlap_start,
                        overlap_end=overlap_end,
                        exposure_hours=exp_hours,
                        degree_hours=degree_hours,
                        risk_category=risk_cat,
                        disposition_status=disposition
                    )
                    linked_bridges.append(bridge)

        bridge_records.extend(linked_bridges)
        updated_alarms.append(
            alarm.model_copy(
                update={
                    "affected_lot_count": len(linked_bridges),
                    "total_loss_usd": round(alarm_loss, 2)
                }
            )
        )

    updated_lots = list(lots_by_id.values())
    return updated_alarms, bridge_records, updated_lots
