"""High-performance telemetry and door event generator with realistic physical dynamics."""

import random
import math
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple, Generator
import numpy as np
import pandas as pd
from wh_monitor.config import ScaleConfig, SIMULATION_START, SIMULATION_END
from wh_monitor.models import Zone, Sensor, SensorReading, DoorEvent
from wh_monitor.generator.anomaly_injector import AnomalyManifest


def generate_door_events(
    zones: List[Zone],
    scale: ScaleConfig,
    manifest: AnomalyManifest,
    rng: random.Random
) -> List[DoorEvent]:
    """Generate door opening and closing events across warehouse zones."""
    events = []
    total_sec = int((SIMULATION_END - SIMULATION_START).total_seconds())
    actors = ["OPR-701", "OPR-822", "AGV-04", "AGV-12", "QA-902", "MAINT-104"]

    # At least 10% of door events will be deliberate ajar violations
    num_events = scale.num_door_events

    for i in range(1, num_events + 1):
        zone = rng.choice(zones)
        door_num = (i % 3) + 1
        door_ident = f"DOOR-D{door_num:02d}"
        
        offset_sec = rng.randint(0, total_sec - 7200)
        opened_at = SIMULATION_START + timedelta(seconds=offset_sec)
        
        # Inject door ajar violations deterministically for ~8% of events
        is_violation = (i % 12 == 0) or (zone.zone_id in manifest.door_ajar_zones)
        if is_violation:
            # Extended open duration: between zone.max_door_open_sec + 60s and 3600s
            duration_sec = rng.randint(zone.max_door_open_sec + 45, max(zone.max_door_open_sec + 120, 2400))
        else:
            # Normal open duration: between 5 seconds and max_door_open_sec - 5
            duration_sec = rng.randint(5, max(10, zone.max_door_open_sec - 5))
            
        closed_at = opened_at + timedelta(seconds=duration_sec)
        ts_str = opened_at.strftime("%Y%m%dT%H%M%SZ")
        door_event_id = f"DOOR-{zone.zone_id}-D{door_num:02d}-{ts_str}"
        actor = rng.choice(actors)

        events.append(
            DoorEvent(
                door_event_id=door_event_id,
                zone_id=zone.zone_id,
                door_identifier=door_ident,
                opened_at=opened_at,
                closed_at=closed_at,
                duration_sec=duration_sec,
                is_ajar_violation=duration_sec > zone.max_door_open_sec,
                actor=actor
            )
        )
        
    events.sort(key=lambda e: e.opened_at)
    return events


def generate_sensor_readings_chunked(
    sensors: List[Sensor],
    zones: List[Zone],
    door_events: List[DoorEvent],
    manifest: AnomalyManifest,
    scale: ScaleConfig,
    seed: int
) -> Generator[List[SensorReading], None, None]:
    """
    Vectorized and chunked generation of sensor readings to support both starter and 1M full scale.
    Yields chunks of SensorReading objects (or lists of dicts) for high throughput.
    """
    np_rng = np.random.default_rng(seed)
    zone_by_id = {z.zone_id: z for z in zones}
    
    # Calculate timestamps
    num_target_readings = scale.num_readings
    num_sensors = len(sensors)
    
    # Determine readings per sensor to hit target volume
    readings_per_sensor = max(10, math.ceil(num_target_readings / num_sensors))
    
    # Simulation span
    total_span_sec = (SIMULATION_END - SIMULATION_START).total_seconds()
    time_step_sec = total_span_sec / readings_per_sensor
    
    base_epoch = SIMULATION_START.timestamp()
    
    # Pre-index door ajar violations by zone for thermal leakage effect
    ajar_events_by_zone: Dict[str, List[Tuple[float, float]]] = {}
    for de in door_events:
        if de.is_ajar_violation:
            ajar_events_by_zone.setdefault(de.zone_id, []).append(
                (de.opened_at.timestamp(), de.closed_at.timestamp())
            )
            
    # Process sensors in chunks of 50 sensors to balance memory and speed
    sensor_chunk_size = 50
    for s_start in range(0, len(sensors), sensor_chunk_size):
        sensor_chunk = sensors[s_start : s_start + sensor_chunk_size]
        chunk_readings: List[SensorReading] = []
        
        for sensor in sensor_chunk:
            zone = zone_by_id[sensor.zone_id]
            stype = sensor.sensor_type
            
            # Check outage window
            outage = manifest.sensor_outage_windows.get(sensor.sensor_id)
            outage_start_ts = outage[0].timestamp() if outage else None
            outage_end_ts = outage[1].timestamp() if outage else None
            
            drift_val = manifest.sensor_drifts.get(sensor.sensor_id, 0.0)
            
            # Time vector for this sensor
            # Add slight jitter per sensor so they don't all sample at identical microsecond
            sensor_jitter = (hash(sensor.sensor_id) % 30)
            timestamps_epoch = base_epoch + np.arange(readings_per_sensor) * time_step_sec + sensor_jitter
            
            # Filter timestamps beyond SIMULATION_END
            timestamps_epoch = timestamps_epoch[timestamps_epoch <= SIMULATION_END.timestamp()]
            
            # If outage exists, filter out readings falling into the silent gap
            if outage_start_ts and outage_end_ts:
                valid_mask = (timestamps_epoch < outage_start_ts) | (timestamps_epoch > outage_end_ts)
                timestamps_epoch = timestamps_epoch[valid_mask]
                
            n_samples = len(timestamps_epoch)
            if n_samples == 0:
                continue
                
            # Base diurnal cycle: 24h sine wave (peaks around 14:00 UTC)
            hours = (timestamps_epoch % 86400) / 3600.0
            diurnal_wave = np.sin((hours - 8.0) * (2.0 * np.pi / 24.0))
            
            # Physical parameters based on sensor type
            if stype == "TEMPERATURE":
                target = zone.target_temp_c
                # Ambient diurnal amplitude is ~1.5C, in sealed cold rooms ~0.3C
                amp = 1.2 if zone.zone_type in ["AMBIENT", "LOADING_DOCK"] else 0.35
                noise = np_rng.normal(0.0, 0.15, size=n_samples)
                values = target + amp * diurnal_wave + noise
                
                # Check for localized HVAC chiller failures
                for exc in manifest.excursion_windows:
                    if exc["zone_id"] == zone.zone_id:
                        e_start = exc["start_time"].timestamp()
                        e_end = exc["end_time"].timestamp()
                        exc_mask = (timestamps_epoch >= e_start) & (timestamps_epoch <= e_end)
                        if np.any(exc_mask):
                            # Spike temperature smoothly during excursion
                            progress = (timestamps_epoch[exc_mask] - e_start) / (e_end - e_start)
                            # Bell-shaped excursion spike
                            spike = exc["peak_delta_c"] * np.sin(progress * np.pi)
                            values[exc_mask] += spike
                            
                # Check door ajar thermal leakage
                if zone.zone_id in ajar_events_by_zone:
                    for d_start, d_end in ajar_events_by_zone[zone.zone_id]:
                        d_mask = (timestamps_epoch >= d_start) & (timestamps_epoch <= d_end + 600)
                        if np.any(d_mask):
                            values[d_mask] += 2.5
                            
                unit = "CELSIUS"
                
            elif stype == "HUMIDITY":
                target = zone.target_humidity_pct
                amp = 4.0 if zone.zone_type in ["AMBIENT", "LOADING_DOCK"] else 1.5
                noise = np_rng.normal(0.0, 0.8, size=n_samples)
                values = np.clip(target - amp * diurnal_wave + noise, 5.0, 99.0)
                unit = "PERCENT_RH"
                
            else:  # OCCUPANCY
                # Occupancy is higher during working shift (08:00 - 18:00)
                is_workshift = (hours >= 7.0) & (hours <= 19.0)
                occ_base = np_rng.integers(0, max(2, zone.max_occupancy // 2), size=n_samples)
                occ_base[~is_workshift] = np_rng.choice([0, 1], p=[0.9, 0.1], size=np.sum(~is_workshift))
                values = occ_base.astype(float)
                unit = "PERSON_COUNT"

            # Apply sensor drift to raw value
            if drift_val != 0.0:
                # Drift ramps up progressively
                drift_progress = (timestamps_epoch - base_epoch) / total_span_sec
                raw_values = values + (drift_val * drift_progress)
            else:
                raw_values = values.copy()
                
            calibrated_values = values  # Reconciled truth

            # Build SensorReading models
            for idx in range(n_samples):
                ts = datetime.fromtimestamp(timestamps_epoch[idx], tz=timezone.utc)
                ts_str = ts.strftime("%Y%m%dT%H%M%SZ")
                r_id = f"RDG-{sensor.sensor_id}-{ts_str}"
                
                val = float(round(raw_values[idx], 2))
                cal_val = float(round(calibrated_values[idx], 2))
                
                # Assign status code
                status_code = "NORMAL"
                if stype == "TEMPERATURE":
                    if cal_val > zone.temp_max_c or cal_val < zone.temp_min_c:
                        status_code = "EXCURSION"
                elif stype == "HUMIDITY":
                    if cal_val > zone.humidity_max_pct or cal_val < zone.humidity_min_pct:
                        status_code = "EXCURSION"
                elif stype == "OCCUPANCY":
                    if cal_val > zone.max_occupancy:
                        status_code = "EXCURSION"
                        
                chunk_readings.append(
                    SensorReading(
                        reading_id=r_id,
                        sensor_id=sensor.sensor_id,
                        timestamp=ts,
                        metric_type=stype,
                        raw_value=val,
                        calibrated_value=cal_val,
                        unit=unit,
                        status_code=status_code
                    )
                )
                
        yield chunk_readings
