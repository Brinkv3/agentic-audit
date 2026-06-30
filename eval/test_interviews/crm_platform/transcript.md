# CRM Platform Interview Transcript
**Date:** 2026-06-17
**Interviewees:** Rachel Torres (CRM Admin), James Liu (Data Engineer)
**Interviewer:** Consultant

---

**Consultant:** Let's start with data sources. What feeds into your CRM?

**Rachel Torres:** Salesforce is our CRM. The main data source is our marketing automation platform — Marketo. Leads come in from Marketo via the native Salesforce-Marketo connector. That sync is near real-time, maybe a 5-minute delay.

**James Liu:** We also pull account firmographic data from ZoomInfo. That's a scheduled enrichment job — runs twice a week, Tuesdays and Fridays. It hits the ZoomInfo API and updates account records in Salesforce.

**Rachel Torres:** And then there's the manual entry side. Sales reps enter activity, notes, and opportunity data directly in Salesforce. That's a significant portion of our data — probably 40% of what's in the system comes from manual rep entry.

**Consultant:** What about data going out of Salesforce?

**James Liu:** We have a Salesforce-to-lakehouse pipeline. We use Fivetran to replicate Salesforce data into the lakehouse every 6 hours. That's how analytics and data science access CRM data.

**Rachel Torres:** We also send closed-won opportunity data to our finance system — NetSuite — through a Workato integration. That triggers invoicing.

**James Liu:** There's one more — we have a direct API call from our customer support portal. When a customer submits a ticket, the portal hits the Salesforce API to pull their account info and recent interactions. That's real-time.

**Consultant:** Are there any direct dependencies between Salesforce and other applications?

**James Liu:** The support portal one I mentioned is essentially an app-to-app dependency. The portal can't function without live access to Salesforce. If Salesforce goes down, the support portal shows degraded data — just name and email from their local cache, none of the account context.

**Rachel Torres:** And honestly, the Marketo sync is another one. If Salesforce is down, Marketo can't sync leads. They queue up on the Marketo side, but it means lead routing stops until the sync catches up.

**Consultant:** What data quality controls exist?

**Rachel Torres:** We have required fields on lead and opportunity records — company name, email, source, stuff like that. We also have duplicate detection rules. They're not perfect — we still find duplicates quarterly, especially from the ZoomInfo enrichment.

**James Liu:** On the pipeline side, Fivetran handles schema drift automatically, which is nice. But we've had issues where custom fields got deleted in Salesforce and the pipeline just stopped syncing those fields silently. We didn't catch it for two weeks.

**Consultant:** Who owns data quality?

**Rachel Torres:** That's a gray area. I own the Salesforce configuration — validation rules, page layouts, duplicate rules. But the data itself? Sales ops owns pipeline data, marketing owns lead data, and nobody really owns the enrichment data from ZoomInfo. James monitors the pipeline but that's just technical — he wouldn't know if the data content was wrong.

**Consultant:** What would break if Salesforce went down for 24 hours?

**Rachel Torres:** Lead routing stops completely. Reps can't see their pipeline. Forecast meetings don't happen. And the support portal goes into degraded mode.

**James Liu:** The lakehouse would have stale data — up to 30 hours old depending on timing. Any dashboards or models consuming CRM data would be working off old data. The NetSuite integration would also fail, so any closed deals wouldn't trigger invoicing.

**Consultant:** Biggest pain points?

**Rachel Torres:** Duplicate records. We have maybe 15% duplicate accounts despite the rules. The ZoomInfo enrichment creates new records instead of updating existing ones about 20% of the time. It's a matching logic issue.

**James Liu:** For me it's the Fivetran silent failures. Schema changes in Salesforce don't always propagate cleanly. I've built custom monitoring but it's still reactive — I find out something broke after someone complains their dashboard is wrong.

**Consultant:** Any planned changes?

**Rachel Torres:** We're evaluating moving from Marketo to HubSpot. That would change the entire lead flow architecture. It's still in the evaluation phase — probably Q3 decision, Q1 next year implementation if we go.

**James Liu:** I'd like to add a data quality layer between Salesforce and the lakehouse — validate records before they land in the lakehouse rather than after. But that's my wish list, not an approved project.

**Consultant:** How is PII handled?

**Rachel Torres:** Standard Salesforce field-level security. Contact email and phone are visible to all users but exportable only by admins. We don't store SSNs or financial data in Salesforce — that lives in NetSuite.

**James Liu:** In the lakehouse, CRM data lands in a governed zone with column-level access controls. PII fields are hashed for analytics use cases. The Fivetran pipeline handles that transformation.
