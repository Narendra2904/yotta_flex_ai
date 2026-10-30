#!/usr/bin/env python3
"""Interactive demo runner: inspect metrics, simulate live risk triage, or launch web console."""

import sys
import os
import argparse
import uvicorn
from wh_monitor.web.app import app, get_kpi_overview, list_alarms, get_alarm_affected_lots


def run_cli_summary():
    print("================================================================================")
    print("  Warehouse Environmental Monitoring & Traceability Engine - Operational Audit")
    print("================================================================================")
    
    kpis = get_kpi_overview()
    print(f"\n[1] Operational KPIs:")
    print(f"    - Facilities / Zones        : {kpis['total_warehouses']} Warehouses / {kpis['total_zones']} Zones")
    print(f"    - Sensor Fleet Telemetry    : {kpis['total_sensors']} Sensors ({kpis['sensor_availability_pct']}% Uptime)")
    print(f"    - Total Inventory Tracked   : {kpis['total_lots']:,} Lots (${kpis['total_inventory_value_usd']:,.2f} USD)")
    print(f"    - Active Alarms             : {kpis['active_alarms']} (Critical: {kpis['critical_alarms']})")
    print(f"    - Mean Excursion Duration   : {kpis['mean_excursion_duration_min']} minutes")
    print(f"    - Inventory Loss at Risk    : ${kpis['total_loss_usd']:,.2f} USD")
    print(f"    - Completed Remediations    : {kpis['total_remediations_completed']}")

    alarms = list_alarms()
    crit_high = [a for a in alarms if a["severity"] in ["CRITICAL", "HIGH"]]
    print(f"\n[2] Top Critical & High Severity Alarms (Sample of {min(5, len(crit_high))}):")
    for a in crit_high[:5]:
        print(f"    * [{a['severity']}] {a['alarm_id']}")
        print(f"      Zone: {a['zone_id']} | Type: {a['alarm_type']} | Trigger: {a['trigger_value']:.1f} vs Limit: {a['threshold_limit']:.1f}")
        print(f"      Duration: {a['duration_minutes']}m | Affected Lots: {a['affected_lot_count']} | Loss: ${a['total_loss_usd']:,.2f}")
        
        # Sample affected lots
        affected = get_alarm_affected_lots(a["alarm_id"])
        if affected:
            top_lot = affected[0]
            print(f"      -> Sample Lot {top_lot['lot_id']} ({top_lot['product_code']}): Dosage {top_lot['degree_hours']:.1f} degC*h [{top_lot['risk_category']}]")

    print("\n================================================================================")
    print("To launch the interactive executive dashboard, run:")
    print("    python run_demo.py --serve --port 8000")
    print("Then open your browser to: http://localhost:8000")
    print("================================================================================")


def main():
    parser = argparse.ArgumentParser(description="Warehouse Telemetry Console Runner")
    parser.add_argument("--serve", action="store_true", help="Launch interactive FastAPI web console")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    args = parser.parse_args()

    if args.serve:
        print(f"Starting Warehouse Telemetry Web Dashboard on http://{args.host}:{args.port}")
        uvicorn.run("wh_monitor.web.app:app", host=args.host, port=args.port, reload=False)
    else:
        run_cli_summary()


if __name__ == "__main__":
    main()
