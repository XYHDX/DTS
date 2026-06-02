"""Standalone background workers for DamascusTransit.

These run as their own processes (not inside the serverless FastAPI app):

  python -m api.workers.mqtt_consumer    # Phase S2.2 — MQTT → ingest pipeline

See Scale_100k_Roadmap.md and PROJECT_STATUS.md.
"""
