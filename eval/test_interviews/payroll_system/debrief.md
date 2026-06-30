# Debrief — Payroll System Interview
**Date:** 2026-06-15
**Participants:** Shawn, BA

## Summary

Payroll is a critical system with two main data feeds (Workday API, Kronos flat file) and a direct write to SAP for GL. The Kronos integration is the weakest link — flat file, no schema, three incidents this year. The SAP integration is a known architectural debt (direct JDBC to staging tables) with a planned migration to API in Q1 next year.

## Key Takeaways

1. **Data flow is mostly hub-and-spoke but SAP integration breaks the pattern.** Workday and lakehouse interactions are clean, but the SAP direct write is an app-to-app dependency that should route through the lakehouse or at minimum use SAP's API.

2. **Kronos is a ticking time bomb.** Three incidents in one year from a flat file with no schema enforcement. Replacement is "planned" but timeline is soft.

3. **Manual processes are heavy.** Two-day monthly reconciliation between payroll and Workday. This screams automation opportunity.

4. **Security posture is mostly good** but the SFTP file-at-rest encryption gap is a real finding from their SOC 2 audit.

5. **Data quality ownership is clear** — Maria owns it, David's team monitors. That's actually better than most orgs.

## Follow-up Items

- Confirm SAP API migration timeline with SAP team
- Get Kronos replacement timeline from whoever owns that decision
- Ask finance about their direct DB access usage — how much of it has migrated to lakehouse?
