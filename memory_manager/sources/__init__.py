"""Read-only real data sources for Hermes (Home Assistant, InfluxDB 3).

The model never reaches a source directly: a host-side reader on VM103 builds
every request from validated arguments (fixed method, fixed paths, no free URL,
no free query language), summarizes the answer, and records it as a canonical
`measurement` event so that each read is citable (`source.ref`) and receipted.
Credentials stay in the private sources config (0600); they never enter memory,
results or logs. No reader exposes a write, service call or actuator path.
"""
