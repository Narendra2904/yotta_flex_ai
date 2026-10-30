"""Executive REST API and Operational Dashboard for Warehouse Environmental Monitoring."""

import os
import json
import sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(
    title="Warehouse Environmental Monitoring & Traceability API",
    version="1.0.0",
    description="Operational workflow engine for multi-zone environmental telemetry, risk alerts, and lot traceability."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "sqlite", "warehouse_telemetry.db")


def get_db():
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=503, detail="Database not initialized. Please run dataset generator first.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/api/kpi/overview")
def get_kpi_overview() -> Dict[str, Any]:
    """Return high-level operational KPIs and risk metrics."""
    conn = get_db()
    cursor = conn.cursor()

    total_warehouses = cursor.execute("SELECT COUNT(*) FROM warehouses").fetchone()[0]
    total_zones = cursor.execute("SELECT COUNT(*) FROM zones").fetchone()[0]
    total_sensors = cursor.execute("SELECT COUNT(*) FROM sensors").fetchone()[0]
    total_lots = cursor.execute("SELECT COUNT(*) FROM inventory_lots").fetchone()[0]
    
    total_inventory_value = cursor.execute("SELECT COALESCE(SUM(total_value_usd), 0.0) FROM inventory_lots").fetchone()[0]
    total_alarms = cursor.execute("SELECT COUNT(*) FROM alarms").fetchone()[0]
    critical_alarms = cursor.execute("SELECT COUNT(*) FROM alarms WHERE severity = 'CRITICAL'").fetchone()[0]
    active_alarms = cursor.execute("SELECT COUNT(*) FROM alarms WHERE status = 'ACTIVE'").fetchone()[0]
    
    total_loss = cursor.execute("SELECT COALESCE(SUM(total_loss_usd), 0.0) FROM alarms").fetchone()[0]
    total_remediations = cursor.execute("SELECT COUNT(*) FROM remediations").fetchone()[0]

    # Calculate Sensor Availability %
    online_sensors = cursor.execute("SELECT COUNT(*) FROM sensors WHERE status = 'ONLINE'").fetchone()[0]
    sensor_availability_pct = round((online_sensors / max(1, total_sensors)) * 100.0, 1)

    # Calculate Mean Time to Detect / Average Excursion Duration
    avg_duration = cursor.execute("SELECT COALESCE(AVG(duration_minutes), 0.0) FROM alarms").fetchone()[0]

    conn.close()
    return {
        "total_warehouses": total_warehouses,
        "total_zones": total_zones,
        "total_sensors": total_sensors,
        "sensor_availability_pct": sensor_availability_pct,
        "total_lots": total_lots,
        "total_inventory_value_usd": round(total_inventory_value, 2),
        "total_alarms": total_alarms,
        "critical_alarms": critical_alarms,
        "active_alarms": active_alarms,
        "mean_excursion_duration_min": round(avg_duration, 1),
        "total_loss_usd": round(total_loss, 2),
        "total_remediations_completed": total_remediations
    }


@app.get("/api/zones")
def list_zones(warehouse_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """List zones with current status and operational thresholds."""
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM zones"
    params = []
    if warehouse_id:
        query += " WHERE warehouse_id = ?"
        params.append(warehouse_id)
    query += " ORDER BY zone_id"
    rows = cursor.execute(query, params).fetchall()
    zones = [dict(r) for r in rows]
    conn.close()
    return zones


@app.get("/api/alarms")
def list_alarms(
    severity: Optional[str] = None,
    zone_id: Optional[str] = None,
    status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Query alarms with filtering by severity, zone, and lifecycle status."""
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM alarms WHERE 1=1"
    params = []
    if severity:
        query += " AND severity = ?"
        params.append(severity)
    if zone_id:
        query += " AND zone_id = ?"
        params.append(zone_id)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY start_time DESC"
    rows = cursor.execute(query, params).fetchall()
    alarms = [dict(r) for r in rows]
    conn.close()
    return alarms


@app.get("/api/alarms/{alarm_id}/affected-lots")
def get_alarm_affected_lots(alarm_id: str) -> List[Dict[str, Any]]:
    """Get all inventory lots exposed to an alarm with degree-hours and risk classification."""
    conn = get_db()
    cursor = conn.cursor()
    query = """
        SELECT 
            b.bridge_id,
            b.alarm_id,
            b.lot_id,
            b.overlap_start,
            b.overlap_end,
            b.exposure_hours,
            b.degree_hours,
            b.risk_category,
            b.disposition_status,
            l.product_code,
            l.requirement_id,
            l.quantity,
            l.unit_price_usd,
            l.total_value_usd,
            l.lifecycle_state
        FROM alarm_affected_lots b
        JOIN inventory_lots l ON b.lot_id = l.lot_id
        WHERE b.alarm_id = ?
        ORDER BY b.degree_hours DESC
    """
    rows = cursor.execute(query, [alarm_id]).fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results


@app.get("/api/sensors")
def list_sensors(zone_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """List sensors with health, drift offset, and battery status."""
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM sensors"
    params = []
    if zone_id:
        query += " WHERE zone_id = ?"
        params.append(zone_id)
    query += " ORDER BY sensor_id"
    rows = cursor.execute(query, params).fetchall()
    sensors = [dict(r) for r in rows]
    conn.close()
    return sensors


@app.get("/api/ground-truth")
def list_ground_truth() -> List[Dict[str, Any]]:
    """Retrieve injected ground truth anomalies for evaluation."""
    conn = get_db()
    cursor = conn.cursor()
    rows = cursor.execute("SELECT * FROM ground_truth ORDER BY anomaly_id").fetchall()
    anomalies = [dict(r) for r in rows]
    conn.close()
    return anomalies


class RemediationSignOffRequest(BaseModel):
    alarm_id: str
    inspector_role: str
    action_type: str
    executed_by: str
    approved_by: str
    findings: str


@app.post("/api/remediations/execute")
def execute_remediation(req: RemediationSignOffRequest) -> Dict[str, Any]:
    """Plant operator / Quality engineer sign-off to execute and resolve an alarm."""
    conn = get_db()
    cursor = conn.cursor()

    # Check if alarm exists
    alarm = cursor.execute("SELECT * FROM alarms WHERE alarm_id = ?", [req.alarm_id]).fetchone()
    if not alarm:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Alarm {req.alarm_id} not found.")

    ts_now = datetime.now(timezone.utc).isoformat()
    ins_id = f"INS-{req.alarm_id}-LIVE"
    rem_id = f"REM-{ins_id}-01"

    # Insert live inspection
    cursor.execute("""
        INSERT INTO inspections (inspection_id, alarm_id, inspector_role, inspector_id, inspection_time, findings, physical_damage, recommended_action, status)
        VALUES (?, ?, ?, ?, ?, ?, 0, ?, 'COMPLETED')
    """, [ins_id, req.alarm_id, req.inspector_role, req.executed_by, ts_now, req.findings, req.action_type])

    # Insert live remediation
    cursor.execute("""
        INSERT INTO remediations (remediation_id, inspection_id, action_type, executed_by, approved_by, completed_at, financial_impact_usd, status)
        VALUES (?, ?, ?, ?, ?, ?, 0.0, 'VERIFIED')
    """, [rem_id, ins_id, req.action_type, req.executed_by, req.approved_by, ts_now])

    # Update alarm status to RESOLVED
    cursor.execute("UPDATE alarms SET status = 'RESOLVED' WHERE alarm_id = ?", [req.alarm_id])
    conn.commit()
    conn.close()

    return {
        "status": "SUCCESS",
        "message": f"Remediation {rem_id} executed and alarm {req.alarm_id} resolved.",
        "inspection_id": ins_id,
        "remediation_id": rem_id
    }


# Static web dashboard mount
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
def index_page():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Warehouse Environmental Monitoring System</h1><p>API is active. Visit /docs for Swagger UI.</p>"
