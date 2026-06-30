# Interviewer Notes — CRM Platform (Salesforce)
**Date:** 2026-06-17

## Key Observations

- Salesforce is the CRM — enterprise SaaS, standard choice
- Marketo is primary lead source (near real-time native connector)
- ZoomInfo for account enrichment (scheduled, 2x/week via API)
- 40% of data is manual rep entry — significant governance gap
- Fivetran replicates to lakehouse every 6 hours
- NetSuite integration via Workato for invoicing on closed-won
- Support portal has direct real-time API dependency on Salesforce

## Concerns

- Support portal → Salesforce is a direct app-to-app dependency (degrades without it)
- ZoomInfo enrichment creates duplicates ~20% of the time — matching logic issue
- Fivetran silent schema drift failures — 2 weeks before discovery in one incident
- Data quality ownership is fragmented (nobody owns enrichment data)
- 15% duplicate account rate despite duplicate detection rules

## Positive Patterns

- Lakehouse pipeline established (Fivetran, 6-hour cadence)
- PII handled well — column-level controls, hashing for analytics
- Enterprise SaaS accessed via native APIs/connectors (not workarounds)

## Follow-up

- Get details on the HubSpot evaluation — would change lead architecture significantly
- Understand the support portal dependency — can it be decoupled via lakehouse?
- What's the plan for ZoomInfo matching logic improvement?
