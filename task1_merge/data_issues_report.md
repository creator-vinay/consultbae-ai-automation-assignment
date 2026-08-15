# Data Issues Report

Found by running `merge_pipeline.py` over the 3 source files, plus manual review
of the raw CSVs. Full machine-generated log: `data_issues_log.csv`.

## 1. Structural issues (broken rows)
- **source3_cbnexus_contacts.csv**: the header row (`Name,Phone Number,City,Verified,Projects Completed`)
  is repeated in the middle of the file — looks like two separate exports were
  concatenated into one CSV. Dropped the repeated header line.
- **source2_gig_workers.csv**: one fully blank row. Dropped.
- **source2_gig_workers.csv**: one row has its columns shifted — the `skill_tags`
  text ended up in the `email_id` column and everything shifted over
  (`"react, javascript, mysql",ISHA.CHOPRA95@...,Isha Chopra,1406/hr,Pune,active`).
  Detected it because the first column contained a comma-separated skill list
  instead of an email, then realigned the 6 values into the correct columns.

## 2. Duplicate / near-duplicate people within a single file
- **source1**: "Nikhil Chopra" appears twice with the *same* phone number but two
  different emails (`nikhil.chopra70@example.com` and `alt.nikhil.chopra70@example.com`)
  — the `alt.` prefix is a strong signal it's the same person applying twice.
  Merged via matching phone number.
- **source1**: "Rohit Verma" and "R. Verma" are two rows with the *same* email
  and phone — same person, inconsistent name spelling. Merged via email.

## 3. Formatting inconsistencies (needed normalizing before matching)
- **Phone numbers** appear in 3 formats across files: `9000000XXX`,
  `09000000XXX`, `+919000000XXX` / `919000000XXX`. Normalized to the last 10
  digits everywhere before using phone as a match key.
- **City names**: casing/whitespace differs everywhere (`NOIDA`, `Noida `,
  `noida`), and the same real city is written multiple ways —
  `Gurgaon`/`Gurugram`/`gurugram`, `Bangalore`/`Bengaluru`, and
  `Delhi`/`New Delhi`/`Delhi NCR`. Lowercased, trimmed, and mapped known
  aliases to one canonical spelling. Note: "Delhi NCR" is technically a wider
  region than "Delhi" city, so this alias is an approximation — flagged in
  case it matters for downstream use.
- **Emails**: some rows in source2 are fully UPPERCASE
  (`ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG`). Lowercased before using as a match key
  — case differences would otherwise have created duplicate people.
- **Dates** (source1 `Applied Date`): 4 different formats in the same column —
  `24-07-2026`, `2026-08-08`, `7 Jul 2026`, `07/13/2026`. Parsed with a
  flexible date parser and normalized to `YYYY-MM-DD`.

## 4. Unit ambiguity (needed a judgment call)
- **source1 `Current CTC`**: mixes full annual rupee figures (e.g. `417964`)
  with what appear to be lakhs written as bare decimals (e.g. `4.2`, `11.9`).
  Assumption: any value under 100 is lakhs and gets multiplied by 100,000
  (so `4.2` -> Rs. 4,20,000). 21 rows affected. This is a guess based on the
  numbers looking too small to be a real annual salary — worth confirming
  with whoever generated the data in a real setting.
- **source2 `rate`**: mixes `<num>/hr` and `<num>k/month`. Converted monthly
  to hourly assuming 160 working hours/month (a standard full-time month).
  14 rows affected. This assumption directly changes the number, so it's
  called out rather than silently applied.
- **source2 `status`** and **source3 `Verified`**: inconsistent casing/values
  (`Active`/`ACTIVE`/`active`, `Y`/`yes`/`Yes`). Normalized to a single
  lowercase / boolean form.

## 5. Ambiguous duplicates — deliberately NOT auto-merged
13 records share a name with another resolved person but have **no matching
email or phone** to confirm they're the same human (full list in
`possible_duplicates_review.csv`). Examples:
- Two "Arjun Mehta" records in Noida with different phone numbers/emails —
  could be the same person with a second (unlisted) number, or two different
  people who happen to share a common Indian name in the same city.
- "Manish Bhatia" in source2 (email, no phone) and source3 (phone, no email) —
  very likely the same person, but nothing in the data proves it.

**Decision:** matching only on an exact normalized email or phone. Name+city
alone was intentionally *not* used to auto-merge, because a common name
colliding in the same city is a realistic false-positive risk (there are
multiple genuinely different people in this dataset who share a first+last
name). Under-merging (leaving a possible duplicate as 2 records) is safer
than over-merging (silently combining 2 different people into 1 record) —
so these are surfaced for manual review instead.

## Summary
| Category | Count |
|---|---|
| CTC unit conversions (lakhs -> rupees) | 21 |
| Rate unit conversions (monthly -> hourly) | 14 |
| Blank row dropped | 1 |
| Column-shifted row fixed | 1 |
| Duplicate header row dropped | 1 |
| Name-only collisions flagged for manual review | 13 |
| **Raw rows across all 3 files** | **103** |
| **Resolved unique people** | **60** |
