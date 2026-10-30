"""Monitoring Engine: detects environmental excursions, door ajar risks, and sensor outages."""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple, Optional
from wh_monitor.models import Zone, Sensor, SensorReading, DoorEvent, Alarm
from wh_monitor.config import SIMULATION_START, SIMULATION_END


def detect_sensor_outage_alarms(
    sensors: List[Sensor],
    readings: List[SensorReading],
    max_gap_seconds: int = 7200  # 2 hours without reading is an outage
) -> List[Alarm]:
    """Identify silent sensor gaps / outages where heartbeat was lost."""
    alarms = []
    # Group readings by sensor_id
    readings_by_sensor: Dict[str, List[SensorReading]] = {}
    for r in readings:
        readings_by_sensor.setdefault(r.sensor_id, []).append(r)
        
    sensors_by_id = {s.sensor_id: s for s in sensors}

    for s_id, s_readings in readings_by_sensor.items():
        sensor = sensors_by_id.get(s_id)
        if not sensor:
            continue
            
        s_readings.sort(key=lambda r: r.timestamp)
        for i in range(len(s_readings) - 1):
            t_curr = s_readings[i].timestamp
            t_next = s_readings[i + 1].timestamp
            gap_sec = (t_next - t_curr).total_seconds()
            
            if gap_sec >= max_gap_seconds:
                # Sensor outage alarm
                start_ts_str = t_curr.strftime("%Y%m%dT%H%M%SZ")
                sensor_suffix = "-".join(sensor.sensor_id.split("-")[-2:])
                alarm_id = f"ALM-{sensor.zone_id}-{sensor_suffix}-OUTAGE-{start_ts_str}"
                duration_min = round(gap_sec / 60.0, 1)
                
                alarms.append(
                    Alarm(
                        alarm_id=alarm_id,
                        zone_id=sensor.zone_id,
                        sensor_id=sensor.sensor_id,
                        alarm_type="SENSOR_OUTAGE_GAP",
                        severity="HIGH" if gap_sec > 14400 else "MEDIUM",
                        start_time=t_curr,
                        end_time=t_next,
                        duration_minutes=duration_min,
                        trigger_value=float(gap_sec),
                        threshold_limit=float(max_gap_seconds),
                        peak_excursion=float(gap_sec),
                        affected_lot_count=0,
                        total_loss_usd=0.0,
                        status="RESOLVED"
                    )
                )
    return alarms


def detect_door_ajar_alarms(
    zones: List[Zone],
    door_events: List[DoorEvent]
) -> List[Alarm]:
    """Detect prolonged door open violations posing thermal integrity risks."""
    alarms = []
    zones_by_id = {z.zone_id: z for z in zones}

    for ev in door_events:
        if ev.is_ajar_violation:
            zone = zones_by_id.get(ev.zone_id)
            threshold = zone.max_door_open_sec if zone else 120
            ts_str = ev.opened_at.strftime("%Y%m%dT%H%M%SZ")
            alarm_id = f"ALM-{ev.zone_id}-{ev.door_identifier}-DOOR-{ts_str}"
            
            severity = "CRITICAL" if ev.duration_sec > threshold * 3 else "HIGH"
            duration_min = round(ev.duration_sec / 60.0, 1)

            alarms.append(
                Alarm(
                    alarm_id=alarm_id,
                    zone_id=ev.zone_id,
                    sensor_id=None,
                    door_event_id=ev.door_event_id,
                    alarm_type="DOOR_AJAR_EXTENDED",
                    severity=severity,
                    start_time=ev.opened_at,
                    end_time=ev.closed_at,
                    duration_minutes=duration_min,
                    trigger_value=float(ev.duration_sec),
                    threshold_limit=float(threshold),
                    peak_excursion=float(ev.duration_sec - threshold),
                    affected_lot_count=0,
                    total_loss_usd=0.0,
                    status="RESOLVED"
                )
            )
    return alarms


def detect_environmental_excursion_alarms(
    zones: List[Zone],
    sensors: List[Sensor],
    readings: List[SensorReading]
) -> List[Alarm]:
    """Detect thermal and humidity threshold excursions from calibrated time-series readings."""
    alarms = []
    zones_by_id = {z.zone_id: z for z in zones}
    sensors_by_id = {s.sensor_id: s for s in sensors}

    # Group readings by sensor
    readings_by_sensor: Dict[str, List[SensorReading]] = {}
    for r in readings:
        if r.metric_type in ["TEMPERATURE", "HUMIDITY"]:
            readings_by_sensor.setdefault(r.sensor_id, []).append(r)

    for s_id, s_readings in readings_by_sensor.items():
        sensor = sensors_by_id.get(s_id)
        if not sensor:
            continue
        zone = zones_by_id.get(sensor.zone_id)
        if not zone:
            continue

        s_readings.sort(key=lambda r: r.timestamp)
        in_excursion = False
        exc_start: Optional[datetime] = None
        exc_type = ""
        threshold = 0.0
        peak_val = 0.0
        trigger_val = 0.0

        for r in s_readings:
            val = r.calibrated_value
            is_breach = False
            curr_type = ""
            curr_thresh = 0.0

            if sensor.sensor_type == "TEMPERATURE":
                if val > zone.temp_max_c:
                    is_breach = True
                    curr_type = "TEMP_EXCURSION_HIGH"
                    curr_thresh = zone.temp_max_c
                elif val < zone.temp_min_c:
                    is_breach = True
                    curr_type = "TEMP_EXCURSION_LOW"
                    curr_thresh = zone.temp_min_c
            elif sensor.sensor_type == "HUMIDITY":
                if val > zone.humidity_max_pct:
                    is_breach = True
                    curr_type = "HUMIDITY_HIGH"
                    curr_thresh = zone.humidity_max_pct
                elif val < zone.humidity_min_pct:
                    is_breach = True
                    curr_type = "HUMIDITY_LOW"
                    curr_thresh = zone.humidity_min_pct

            if is_breach:
                if not in_excursion:
                    in_excursion = True
                    exc_start = r.timestamp
                    exc_type = curr_type
                    threshold = curr_thresh
                    trigger_val = val
                    peak_val = val
                else:
                    if curr_type == "TEMP_EXCURSION_HIGH" or curr_type == "HUMIDITY_HIGH":
                        peak_val = max(peak_val, val)
                    else:
                        peak_val = min(peak_val, val)
            else:
                if in_excursion and exc_start is not None:
                    # Excursion resolved
                    exc_end = r.timestamp
                    duration_min = round((exc_end - exc_start).total_seconds() / 60.0, 1)
                    
                    # Only register if excursion lasted at least 15 minutes to avoid single-point blips
                    if duration_min >= 15.0:
                        deviation = abs(peak_val - threshold)
                        severity = "CRITICAL" if deviation > 4.0 else ("HIGH" if deviation > 2.0 else "MEDIUM")
                        sensor_suffix = "-".join(sensor.sensor_id.split("-")[-2:])
                        ts_str = exc_start.strftime("%Y%m%dT%H%M%SZ")
                        alarm_id = f"ALM-{zone.zone_id}-{sensor_suffix}-EXC-{ts_str}"

                        alarms.append(
                            Alarm(
                                alarm_id=alarm_id,
                                zone_id=zone.zone_id,
                                sensor_id=sensor.sensor_id,
                                door_event_id=None,
                                alarm_type=exc_type,
                                severity=severity,
                                start_time=exc_start,
                                end_time=exc_end,
                                duration_minutes=duration_min,
                                trigger_value=trigger_val,
                                threshold_limit=threshold,
                                peak_excursion=round(peak_val, 2),
                                affected_lot_count=0,
                                total_loss_usd=0.0,
                                status="RESOLVED"
                            )
                        )
                    in_excursion = False
                    exc_start = None

        # If still in excursion at end
        if in_excursion and exc_start is not None:
            exc_end = s_readings[-1].timestamp
            duration_min = round((exc_end - exc_start).total_seconds() / 60.0, 1)
            if duration_min >= 15.0:
                deviation = abs(peak_val - threshold)
                severity = "CRITICAL" if deviation > 4.0 else "HIGH"
                sensor_suffix = "-".join(sensor.sensor_id.split("-")[-2:])
                ts_str = exc_start.strftime("%Y%m%dT%H%M%SZ")
                alarms.append(
                    Alarm(
                        alarm_id=f"ALM-{zone.zone_id}-{sensor_suffix}-EXC-{ts_str}",
                        zone_id=zone.zone_id,
                        sensor_id=sensor.sensor_id,
                        alarm_type=exc_type,
                        severity=severity,
                        start_time=exc_start,
                        end_time=exc_end,
                        duration_minutes=duration_min,
                        trigger_value=trigger_val,
                        threshold_limit=threshold,
                        peak_excursion=round(peak_val, 2),
                        affected_lot_count=0,
                        total_loss_usd=0.0,
                        status="ACTIVE"
                    )
                )

    alarms.sort(key=lambda a: a.start_time)
    
    # Guarantee primary key uniqueness
    seen_ids = set()
    unique_alarms = []
    for a in alarms:
        aid = a.alarm_id
        if aid in seen_ids:
            counter = 2
            while f"{aid}-{counter:02d}" in seen_ids:
                counter += 1
            aid = f"{aid}-{counter:02d}"
            a = a.model_copy(update={"alarm_id": aid})
        seen_ids.add(aid)
        unique_alarms.append(a)

    return unique_alarms
