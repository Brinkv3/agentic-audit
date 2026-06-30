# Interviewer Notes — Payroll System
**Date:** 2026-06-15

## Key Observations

- Workday is the primary source (REST API, nightly batch at 2 AM ET, delta pull)
- Kronos for time/attendance — **flat file via SFTP, no schema enforcement** — this is a significant risk
- Manual upload for bonuses (spreadsheet → admin screen) — no validation mentioned for this path
- Direct JDBC write to SAP staging tables for GL entries — David acknowledged this isn't ideal
- New lakehouse feed for reporting (6 months old), replacing direct DB access by finance
- Maria owns data quality operationally, David's team handles technical monitoring
- Monthly reconciliation with Workday takes 2 days — significant manual effort

## Concerns

- SAP direct DB write is a classic app-to-app dependency — violates lakehouse principle
- Kronos file has caused 3 incidents this year — brittle integration
- SFTP file not encrypted at rest (SOC 2 finding)
- Kronos replacement timeline sounds uncertain ("been hearing that for a while")
- Manual bonus upload path may lack validation controls

## Body Language / Tone

- David was visibly frustrated discussing Kronos integration
- Maria confident on controls but seemed resigned about the reconciliation burden
- Both aligned on the SAP API migration being necessary
