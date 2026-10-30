"""Domain Models and Validation Schemas for Warehouse Monitoring & Traceability."""

from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class Warehouse(BaseModel):
    warehouse_id: str = Field(..., pattern=r"^WH-\d{3}$")
    name: str = Field(..., min_length=3, max_length=128)
    region: str = Field(...)
    address: str
    total_zones: int = Field(..., ge=1, le=50)
    operational_status: str = Field(default="ACTIVE")
    created_at: datetime


class StorageRequirement(BaseModel):
    requirement_id: str = Field(..., pattern=r"^REQ-[A-Z0-9_-]+$")
    profile_name: str
    allowed_zone_types: str
    temp_crit_min_c: float
    temp_warn_min_c: float
    temp_warn_max_c: float
    temp_crit_max_c: float
    humidity_crit_min_pct: float
    humidity_crit_max_pct: float
    max_excursion_duration_min: int = Field(..., ge=1)
    status: str = Field(default="ACTIVE")


class Zone(BaseModel):
    zone_id: str = Field(..., pattern=r"^ZONE-WH-\d{3}-\d{3}$")
    warehouse_id: str = Field(..., pattern=r"^WH-\d{3}$")
    zone_name: str
    zone_type: str
    target_temp_c: float
    temp_min_c: float
    temp_max_c: float
    target_humidity_pct: float
    humidity_min_pct: float
    humidity_max_pct: float
    max_occupancy: int = Field(..., ge=0)
    max_door_open_sec: int = Field(..., ge=30)
    status: str = Field(default="ACTIVE")


class Sensor(BaseModel):
    sensor_id: str = Field(..., pattern=r"^SNS-ZONE-[A-Z0-9-]+-(TEMP|HUM|OCC)-\d{2}$")
    zone_id: str
    sensor_type: str  # TEMPERATURE, HUMIDITY, OCCUPANCY
    model_number: str
    calibration_date: date
    calibration_due: date
    battery_level_pct: float = Field(..., ge=0.0, le=100.0)
    drift_offset: float = Field(default=0.0)
    status: str = Field(default="ONLINE")


class SensorReading(BaseModel):
    reading_id: str
    sensor_id: str
    timestamp: datetime
    metric_type: str
    raw_value: float
    calibrated_value: float
    unit: str
    status_code: str = Field(default="NORMAL")


class DoorEvent(BaseModel):
    door_event_id: str
    zone_id: str
    door_identifier: str
    opened_at: datetime
    closed_at: datetime
    duration_sec: int = Field(..., ge=0)
    is_ajar_violation: bool
    actor: str


class InventoryLot(BaseModel):
    lot_id: str = Field(..., pattern=r"^LOT-2026-\d{6}$")
    product_code: str
    requirement_id: str
    zone_id: str
    arrival_time: datetime
    departure_time: Optional[datetime] = None
    dwell_hours: float = Field(..., ge=0.0)
    quantity: int = Field(..., ge=1)
    unit_price_usd: float = Field(..., ge=0.0)
    total_value_usd: float = Field(..., ge=0.0)
    lifecycle_state: str = Field(default="STORED")


class Alarm(BaseModel):
    alarm_id: str = Field(..., pattern=r"^ALM-ZONE-.*")
    zone_id: str
    sensor_id: Optional[str] = None
    door_event_id: Optional[str] = None
    alarm_type: str
    severity: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_minutes: Optional[float] = None
    trigger_value: float
    threshold_limit: float
    peak_excursion: Optional[float] = None
    affected_lot_count: int = Field(default=0, ge=0)
    total_loss_usd: float = Field(default=0.0, ge=0.0)
    status: str = Field(default="ACTIVE")


class AlarmAffectedLot(BaseModel):
    bridge_id: str
    alarm_id: str
    lot_id: str
    overlap_start: datetime
    overlap_end: datetime
    exposure_hours: float = Field(..., ge=0.0)
    degree_hours: float = Field(default=0.0, ge=0.0)
    risk_category: str
    disposition_status: str = Field(default="IDENTIFIED")


class Inspection(BaseModel):
    inspection_id: str
    alarm_id: str
    inspector_role: str
    inspector_id: str
    inspection_time: datetime
    findings: str
    physical_damage: bool = False
    recommended_action: str
    status: str = Field(default="COMPLETED")


class Remediation(BaseModel):
    remediation_id: str
    inspection_id: str
    action_type: str
    lot_id: Optional[str] = None
    sensor_id: Optional[str] = None
    executed_by: str
    approved_by: str
    completed_at: datetime
    financial_impact_usd: float = Field(default=0.0, ge=0.0)
    status: str = Field(default="VERIFIED")


class GroundTruth(BaseModel):
    anomaly_id: str
    issue_type: str
    entity_type: str
    entity_id: str
    zone_id: str
    start_time: datetime
    end_time: datetime
    expected_detection: bool = True
    expected_alarm_type: Optional[str] = None
    expected_severity: str
    rationale: str
