# Debrief — CRM Platform (Salesforce) Interview
**Date:** 2026-06-17
**Participants:** Shawn, BA

## Summary

Salesforce is well-integrated into the data ecosystem via Fivetran → lakehouse pipeline, with appropriate SaaS API usage. Main concerns are the support portal's real-time dependency on Salesforce (app-to-app), ZoomInfo enrichment creating duplicates (~20% of the time), and fragmented data quality ownership.

## Key Takeaways

1. **Lakehouse pattern is established** — Fivetran replicates Salesforce to lakehouse every 6 hours. This is the right direction. PII handling is solid with hashing in the governed zone.

2. **Support portal dependency is architectural debt.** The portal makes live API calls to Salesforce for account context. If Salesforce is down, support goes to degraded mode. This should route through the lakehouse or a caching layer.

3. **ZoomInfo duplicate problem is significant.** 15% duplicate account rate, with enrichment contributing ~20% match failure rate. This corrupts downstream analytics and reporting.

4. **Data quality ownership gap.** Rachel owns config, sales ops owns pipeline data, marketing owns leads, nobody owns enrichment data. Classic "everybody's responsible = nobody's responsible" pattern.

5. **Fivetran silent failures are a monitoring gap.** Custom monitoring exists but is reactive. Two-week detection delay on a schema change is too long.

## Cross-Application Notes

- NetSuite integration via Workato is clean — event-driven on closed-won. Good pattern.
- The lakehouse receives data from both payroll (Workday) and CRM (Salesforce) — coverage is growing.
- Support portal dependency mirrors the payroll → SAP direct write: both are app-to-app patterns that bypass the central data layer.
