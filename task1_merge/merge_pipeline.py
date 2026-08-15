"""
merge_pipeline.py  --  Task 1 (Merge) + feeds Task 4 (Data issues report)

Design decision (important, explain this in the video / stuck log):
  None of the 3 files share a common ID. Source1 (Naukri) has email + phone,
  Source2 (gig workers) has email only, Source3 (CBNexus) has phone only.
  So a person can only be tied together with 100% certainty through an
  EXACT normalized email match or an EXACT normalized phone match.

  I deliberately do NOT auto-merge two records just because the name (and
  maybe city) looks the same - "Arjun Mehta" and "Deepak Nair" each appear
  more than once across these files as clearly DIFFERENT people (different
  emails, different phones, sometimes different city). Auto-merging on name
  would silently combine two different humans into one record, which is a
  worse failure than leaving a duplicate name unmerged. Instead, every
  same-name collision that survives after exact matching gets written to
  possible_duplicates_review.csv so a human makes the final call.

Run: python3 merge_pipeline.py
Produces: people.db (SQLite) + data_issues_log.csv + possible_duplicates_review.csv
"""
import csv
import sqlite3
from pathlib import Path
import pandas as pd

from normalize import (
    normalize_email, normalize_phone, normalize_city, normalize_name,
    name_key, normalize_date, normalize_ctc, normalize_rate_to_hourly,
    normalize_status, normalize_verified,
)

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = Path(__file__).parent / "people.db"
ISSUES_LOG = []  # collect (source, issue_type, detail) tuples for Task 4 report


def log_issue(source, issue_type, detail):
    ISSUES_LOG.append({"source": source, "issue_type": issue_type, "detail": detail})


# ---------------------------------------------------------------------------
# 1. LOAD + CLEAN EACH SOURCE
# ---------------------------------------------------------------------------

def load_source1():
    df = pd.read_csv(DATA_DIR / "source1_naukri_applicants.csv")
    df.columns = [c.strip() for c in df.columns]
    records = []
    for i, row in df.iterrows():
        email = normalize_email(row.get("Email"))
        phone = normalize_phone(row.get("Phone"))
        name = normalize_name(row.get("Full Name"))
        city = normalize_city(row.get("City"))
        ctc = normalize_ctc(row.get("Current CTC"))
        date = normalize_date(row.get("Applied Date"))
        if ctc is not None and row.get("Current CTC") is not None and float(row["Current CTC"]) < 100:
            log_issue("source1", "ctc_unit_ambiguous",
                      f"Row {i} ({name}): CTC given as {row['Current CTC']} -> "
                      f"treated as lakhs, converted to Rs.{ctc:.0f}")
        records.append({
            "source": "source1", "name": name, "email": email, "phone": phone,
            "city": city, "experience_years": row.get("Experience (Years)"),
            "current_ctc": ctc, "applied_date": date, "skills": row.get("Skills"),
        })
    return records


def load_source2():
    raw_path = DATA_DIR / "source2_gig_workers.csv"
    good_rows, records = [], []
    with open(raw_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        for i, row in enumerate(reader, start=2):
            if all(c.strip() == "" for c in row):
                log_issue("source2", "blank_row", f"Raw line {i}: completely empty row, dropped")
                continue
            # detect the column-shifted row: skill text sitting in the email column
            if row and ("," in row[0] and "@" not in row[0] and not row[0].strip().startswith("http")):
                log_issue("source2", "shifted_columns",
                          f"Raw line {i}: columns shifted (skills text landed in email column) -> "
                          f"realigned using the email found later in the row")
                # shift: [skills, EMAIL, name, rate, city, status] -> realign
                if len(row) >= 6:
                    fixed = [row[1], row[2], row[3], row[4], row[5], row[0]]
                    row = fixed
                else:
                    continue
            good_rows.append(row)
    df = pd.DataFrame(good_rows, columns=[c.strip() for c in header])

    # duplicate rows referring to the exact same person (e.g. Isha Chopra appeared
    # once normally and once in the shifted row) get caught naturally by the
    # email-based union-find later, so no special handling needed here.

    for i, row in df.iterrows():
        email = normalize_email(row.get("email_id"))
        name = normalize_name(row.get("worker_name"))
        city = normalize_city(row.get("location"))
        status = normalize_status(row.get("status"))
        rate_hourly, rate_kind = normalize_rate_to_hourly(row.get("rate"))
        if rate_kind == "month":
            log_issue("source2", "rate_unit_mixed",
                      f"Row {i} ({name}): rate given as {row.get('rate')} (monthly) -> "
                      f"converted to Rs.{rate_hourly}/hr assuming 160 working hrs/month")
        records.append({
            "source": "source2", "name": name, "email": email, "phone": None,
            "city": city, "rate_hourly": rate_hourly, "status": status,
            "skill_tags": row.get("skill_tags"),
        })
    return records


def load_source3():
    raw_path = DATA_DIR / "source3_cbnexus_contacts.csv"
    good_rows, records = [], []
    with open(raw_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        for i, row in enumerate(reader, start=2):
            if row == header:
                log_issue("source3", "duplicate_header_row",
                          f"Raw line {i}: header row repeated mid-file (looks like 2 exports "
                          f"concatenated together) -> dropped")
                continue
            if all(c.strip() == "" for c in row):
                continue
            good_rows.append(row)
    df = pd.DataFrame(good_rows, columns=[c.strip() for c in header])

    for i, row in df.iterrows():
        name = normalize_name(row.get("Name"))
        phone = normalize_phone(row.get("Phone Number"))
        city = normalize_city(row.get("City"))
        verified = normalize_verified(row.get("Verified"))
        try:
            projects = int(row.get("Projects Completed"))
        except (TypeError, ValueError):
            projects = None
        records.append({
            "source": "source3", "name": name, "email": None, "phone": phone,
            "city": city, "verified": verified, "projects_completed": projects,
        })
    return records


# ---------------------------------------------------------------------------
# 2. ENTITY RESOLUTION (union-find on exact email / exact phone only)
# ---------------------------------------------------------------------------

class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def resolve_people(all_records):
    n = len(all_records)
    uf = UnionFind(n)
    email_index, phone_index = {}, {}

    for idx, rec in enumerate(all_records):
        if rec["email"]:
            if rec["email"] in email_index:
                uf.union(idx, email_index[rec["email"]])
            else:
                email_index[rec["email"]] = idx
        if rec["phone"]:
            if rec["phone"] in phone_index:
                uf.union(idx, phone_index[rec["phone"]])
            else:
                phone_index[rec["phone"]] = idx

    clusters = {}
    for idx in range(n):
        root = uf.find(idx)
        clusters.setdefault(root, []).append(idx)

    return clusters


# ---------------------------------------------------------------------------
# 3. BUILD PERSON ROWS FROM CLUSTERS + FLAG NAME-ONLY COLLISIONS
# ---------------------------------------------------------------------------

def build_people(all_records, clusters):
    people = []
    for cluster_idxs in clusters.values():
        recs = [all_records[i] for i in cluster_idxs]
        name = next((r["name"] for r in recs if r.get("name")), None)
        email = next((r["email"] for r in recs if r.get("email")), None)
        phone = next((r["phone"] for r in recs if r.get("phone")), None)
        city = next((r["city"] for r in recs if r.get("city")), None)
        sources = sorted(set(r["source"] for r in recs))
        people.append({
            "name": name, "email": email, "phone": phone, "city": city,
            "sources": ",".join(sources), "record_indexes": cluster_idxs,
        })

    # flag same-name collisions across DIFFERENT resolved people (not auto-merged)
    by_name = {}
    for pid, p in enumerate(people):
        k = name_key(p["name"])
        by_name.setdefault(k, []).append(pid)

    review_rows = []
    for k, pids in by_name.items():
        if len(pids) > 1:
            for pid in pids:
                p = people[pid]
                review_rows.append({
                    "name_key": k, "resolved_name": p["name"], "email": p["email"],
                    "phone": p["phone"], "city": p["city"], "sources": p["sources"],
                    "note": "Same name as another resolved person but email/phone did not "
                            "match -> kept as separate records, needs human review",
                })
    return people, review_rows


# ---------------------------------------------------------------------------
# 4. WRITE TO SQLITE
# ---------------------------------------------------------------------------

def write_db(all_records, people):
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE people (
        person_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, email TEXT, phone TEXT, city TEXT, sources TEXT
    );
    CREATE TABLE naukri_applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        person_id INTEGER REFERENCES people(person_id),
        experience_years REAL, current_ctc REAL, applied_date TEXT, skills TEXT
    );
    CREATE TABLE gig_worker_profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        person_id INTEGER REFERENCES people(person_id),
        rate_hourly REAL, status TEXT, skill_tags TEXT
    );
    CREATE TABLE cbnexus_profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        person_id INTEGER REFERENCES people(person_id),
        verified INTEGER, projects_completed INTEGER
    );
    CREATE TABLE audio_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        person_id INTEGER REFERENCES people(person_id),
        name TEXT, phone TEXT, filename TEXT,
        duration_sec REAL, sample_rate_khz REAL, bitrate_kbps REAL,
        loudness_db REAL, quality_estimate TEXT, submitted_at TEXT
    );
    """)

    idx_to_person_id = {}
    for p in people:
        cur.execute(
            "INSERT INTO people (name, email, phone, city, sources) VALUES (?,?,?,?,?)",
            (p["name"], p["email"], p["phone"], p["city"], p["sources"]),
        )
        person_id = cur.lastrowid
        for idx in p["record_indexes"]:
            idx_to_person_id[idx] = person_id

    for idx, rec in enumerate(all_records):
        pid = idx_to_person_id[idx]
        if rec["source"] == "source1":
            cur.execute(
                "INSERT INTO naukri_applications (person_id, experience_years, current_ctc, "
                "applied_date, skills) VALUES (?,?,?,?,?)",
                (pid, rec.get("experience_years"), rec.get("current_ctc"),
                 rec.get("applied_date"), rec.get("skills")),
            )
        elif rec["source"] == "source2":
            cur.execute(
                "INSERT INTO gig_worker_profile (person_id, rate_hourly, status, skill_tags) "
                "VALUES (?,?,?,?)",
                (pid, rec.get("rate_hourly"), rec.get("status"), rec.get("skill_tags")),
            )
        elif rec["source"] == "source3":
            cur.execute(
                "INSERT INTO cbnexus_profile (person_id, verified, projects_completed) "
                "VALUES (?,?,?)",
                (pid, rec.get("verified"), rec.get("projects_completed")),
            )

    conn.commit()
    conn.close()


def main():
    s1 = load_source1()
    s2 = load_source2()
    s3 = load_source3()
    all_records = s1 + s2 + s3

    clusters = resolve_people(all_records)
    people, review_rows = build_people(all_records, clusters)

    write_db(all_records, people)

    pd.DataFrame(ISSUES_LOG).to_csv(Path(__file__).parent / "data_issues_log.csv", index=False)
    pd.DataFrame(review_rows).to_csv(Path(__file__).parent / "possible_duplicates_review.csv", index=False)

    print(f"Source1 rows: {len(s1)} | Source2 rows: {len(s2)} | Source3 rows: {len(s3)}")
    print(f"Total raw records: {len(all_records)}")
    print(f"Resolved unique people: {len(people)}")
    print(f"Issues logged: {len(ISSUES_LOG)}")
    print(f"Possible-duplicate rows flagged for review: {len(review_rows)}")
    print(f"DB written to: {DB_PATH}")


if __name__ == "__main__":
    main()
