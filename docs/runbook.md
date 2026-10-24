# CRM Health Check runbook

*[Leer en español](runbook.es.md)*

A plain-English guide for the sales or marketing manager who owns CRM data quality. It covers what the report shows, how to read it, and how to work the fix lists each week.

> Everything in this repo uses **Bayline Loop**, a fictional company, and generated data. Numbers in the report are sample data.

## 1. What the report answers

| Question | Page |
|---|---|
| Can we trust the CRM right now? | **Overview**: health score per object, issues by severity, top 5 fixes |
| What exactly is wrong, and why does it matter? | **Data Health**: one section per check with the affected records |
| What do I fix, and who fixes it? | **Fix List**: three CSV files, one per kind of fix |
| What's in the pipeline and what will close? | **Pipeline & Forecast** |
| Which marketing sources win deals? | **Attribution** |
| Why doesn't our ARR match what finance bills? | **Reconciliation** |
| How is each number defined? | **Methodology**, with a link to the SQL behind it |

## 2. Weekly routine (about 30 minutes)

1. **Run the audit** on the latest export: `chc generate` is only for the demo; with real exports, drop the CSV files into `data/` and run `chc build`.
2. **Open the Overview.** Note the three health scores and compare them with last week. A score going down means new bad data is coming in, so look for the cause (a form, an integration, a new rep) rather than only cleaning up.
3. **Work the Top 5 fixes** in order. High severity first: these break revenue numbers.
4. **Import `fixes.csv`** (section 4).
5. **Send `merge_candidates.csv`** to the person who owns merges (section 5).
6. **Send `needs_owner_review.csv`** to each record owner, filtered to their records (section 6).
7. **Check Reconciliation** and send any non-Matched accounts to finance or the deal owner (section 7).

## 3. Reading the checks

| ID | Check | Why it matters | Who fixes it |
|---|---|---|---|
| H01 | Duplicate contacts | One person's history is split; reps double-contact them | Merge owner (review) |
| H02 | Duplicate companies | Revenue and contacts are split across copies of one account | Merge owner (review) |
| H03 | Missing or invalid email | Can't email, dedupe or attribute the contact | Record owner |
| H04 | Lifecycle stage missing or wrong | Funnel and customer counts are off | Blank stages: automatic. "Customer" with no won deal: record owner |
| H05 | Deal missing company or contact | Deal drops out of account revenue and attribution | Deal owner |
| H06 | Stale open deal | Pipeline and forecast include money that isn't coming | Deal owner: update or close it |
| H07 | Closed-won deal incomplete | Revenue reports can't count it; CRM won't match billing | Deal owner, from the order form |
| H08 | Inactive or missing owner | Nobody follows up | Contacts/deals: automatic. Companies: sales manager |
| H09 | Non-canonical UTM value | One channel shows up as several, so it's undercounted | Known aliases: automatic. Unknown values: marketing ops |

Severity: **high** breaks revenue or reporting numbers, **medium** breaks follow-up or routing, **low** breaks attribution detail.

## 4. Importing `fixes.csv`

`fixes.csv` only holds changes a rule can make safely: a blank lifecycle stage filled from the company's deals, a record moved from a departed owner to the company's active owner, and a UTM alias rewritten to its canonical value.

The file has four columns: `Record ID`, `Object`, `Property`, `New Value`. HubSpot imports one object at a time and expects one column per property, so:

1. Filter the file to one **Object** and one **Property** (for example, contact + `utm_source`).
2. Rename the `New Value` column to the property's name.
3. In HubSpot, import the file as an update to existing records of that object, matching on **Record ID**.
4. Repeat for the next object/property pair.
5. Re-run the audit. Those issues should be gone.

Spot-check a few rows before every import. A rule is only as good as the data it reads.

## 5. Working merges (`merge_candidates.csv`)

Merges are **never automatic**. A HubSpot merge combines two records' history and can't be cleanly undone, and a wrong merge attaches deals and emails to the wrong customer.

For each row, open both records (`duplicate_record_id` and `keep_record_id`) and confirm they really are the same person or company:

- **Contacts:** same person, not a shared team inbox.
- **Companies:** same business, not a sister brand or a subsidiary that shares a domain.

If they match, merge the duplicate into the record to keep (the older one). If not, leave both and note why, so the pair isn't reviewed again.

## 6. Owner reviews (`needs_owner_review.csv`)

Everything that needs a person's judgment: missing or broken emails, "customer" contacts with no won deal, deals missing associations or values, stale deals, companies owned by someone who left, and unknown UTM values. Filter by owner and send each person their rows. Ask for fixes by the next weekly run.

For stale deals (H06), the owner either sets a real next step and a new close date, or closes the deal as lost. Moving the close date out without a next step only hides the problem.

## 7. Reconciliation follow-up

Each account that isn't **Matched** has a one-sentence explanation. Typical next steps:

| Category | What to do |
|---|---|
| CRM-only | Ask finance whether the customer is billed under another domain; if they churned, log it in the CRM |
| Billing-only | Create or find the company and log the won deal, or confirm it's a self-serve signup |
| Amount mismatch | Compare the order form with the subscription: discount, extra storefront, price change, or a missing amount (H07) |
| Term mismatch | Fix whichever side has a monthly value typed as annual (or the reverse) |
| Currency mismatch | Agree on the contract currency and correct the other system |

Remember that ARR here is contracted recurring value. It isn't revenue recognized by finance, so small timing differences are normal.

## 8. Definitions

- **Health score:** share of records of an object (contacts, companies, deals) with no issue from any check.
- **Weighted forecast:** sum over open deals of amount x stage probability (see `config/pipeline.yml`). It's only as good as stage hygiene, which is why H06 matters.
- **First touch / last touch:** the source of the earliest / latest tracked marketing touch of a won deal's primary contact before the deal was created.
- **Normalized domain:** lowercase, without `http(s)://`, `www.` or a path. Used to match billing to CRM, because the two systems don't share an ID.
