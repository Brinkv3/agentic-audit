# Payroll System Interview Transcript
**Date:** 2026-06-15
**Interviewees:** Maria Chen (Payroll Manager), David Park (Sr. Developer)
**Interviewer:** Consultant

---

**Consultant:** Can you walk me through how the payroll system gets its data?

**Maria Chen:** Sure. The primary source is Workday. We pull employee records, compensation data, and org hierarchy from Workday every night via their REST API. There's a batch job that runs at 2 AM ET. It pulls the delta — anything that changed since the last run.

**David Park:** That's the main feed, yes. We also get time and attendance data from Kronos. That one's a flat file export — Kronos drops a CSV into an SFTP folder every evening, and our ETL picks it up around midnight.

**Consultant:** So those are the two main sources?

**Maria Chen:** For regular payroll, yes. There's also a manual upload process for bonuses and one-time payments. HR sends us a spreadsheet and we load it through an admin screen.

**Consultant:** What other systems receive data from payroll?

**David Park:** We send payroll results to the general ledger — that's SAP. That's a direct database write actually. Our batch job writes the journal entries directly into the SAP staging tables after each payroll run.

**Maria Chen:** And we send a summary feed to the data lakehouse for reporting. That one's newer — we started that about six months ago. Before that, finance was pulling reports directly from our database.

**Consultant:** You mentioned a direct write to SAP. Is there an API or is it truly a direct database connection?

**David Park:** It's a direct JDBC connection to the SAP staging database. We have credentials that let us write to specific staging tables. SAP then processes those staging records on their side. I know it's not ideal, but it's been that way for years and it works.

**Consultant:** What data quality controls do you have?

**Maria Chen:** We have validation rules on the input side — if the Workday feed has an employee without a cost center, it gets flagged and held. We also reconcile total headcount after each payroll run. If the count doesn't match what HR reports, we investigate.

**David Park:** There's also a checksum on the Kronos file. If it doesn't match the expected row count in the header, the file gets rejected and we get an alert.

**Consultant:** Who owns data quality for this system?

**Maria Chen:** Ultimately that's me. If something goes wrong with payroll data, I'm the one getting the call. But David's team handles the technical monitoring.

**Consultant:** What happens if payroll goes down for 24 hours?

**Maria Chen:** That depends on when. If it's the day before a pay run, we're in serious trouble. People don't get paid on time, and that's a compliance issue. If it's mid-cycle, we have more buffer but the GL feed to SAP would be delayed and finance would notice.

**Consultant:** What are your biggest data pain points?

**David Park:** The Kronos flat file is a nightmare. No schema enforcement, the format changes without notice, and we've had three incidents this year where bad data got through because the file had extra columns that threw off our parser. I think Kronos is supposed to be replaced next year but I've been hearing that for a while.

**Maria Chen:** For me it's the reconciliation process. We spend two days every month manually checking numbers between our system and Workday because there's always edge cases — retroactive changes, mid-period transfers, that sort of thing.

**Consultant:** Any planned changes?

**David Park:** We're supposed to move the SAP integration to their API — the direct database write is a known risk. That's on the roadmap for Q1 next year. Also, there's talk about replacing the Kronos file with a real-time API feed, but that's dependent on the Kronos replacement happening.

**Maria Chen:** The reporting side is getting better with the lakehouse feed. We're hoping to retire the direct database access that finance has been using.

**Consultant:** How do you handle PII and sensitive data?

**Maria Chen:** SSNs are encrypted at rest and masked in the UI — only I and two other people can see full SSNs. Salary data is restricted by role. We had a SOC 2 audit last year and passed, but they flagged that our Kronos SFTP transfer isn't encrypted end-to-end. David's team is working on that.

**David Park:** Yeah, the SFTP itself is encrypted in transit, but the file sitting on the SFTP server isn't encrypted at rest. It's on my list.
