"""
Connects to Postgres AS EACH ROLE with that role's own credentials and
checks two things per role:

    positive  can it do its own job?            (expect ALLOWED)
    negative  is it blocked outside its lane?   (expect DENIED)

NOTE this tests the POLICY LAYER. A pass here means the policies are correct, not that the
pipeline is constrained by them.

Every write is rolled back. Nothing is left in the database.

RUN
    python test_agent_db_access.py > role_access_report.txt
"""

import os
import sys
from collections import Counter

import psycopg2
from dotenv import load_dotenv

load_dotenv()

HOST = os.environ.get("PGHOST", "aws-0-us-east-1.pooler.supabase.com")
PORT = os.environ.get("PGPORT", "6543")
DB = os.environ.get("PGDATABASE", "postgres")
REF = os.environ.get("PROJECT_REF", "")

ROLES = [
    "collection_agent",
    "sentiment_agent",
    "stance_agent",
    "topic_agent",
    "classification_agent",
    "orchestrator",
    "aggregator_agent",
]

# (role, label, sql, params, expect)   expect: "allow" | "deny"
#
# Reads are plain selects. Writes are wrapped by the runner in a
# savepoint and rolled back, so nothing persists either way.
CHECKS = [
    # ---- collection_agent: owns the corpus and the quarantine log ----
    ("collection_agent", "select articles",
     "select id from public.articles limit 1", (), "allow"),
    ("collection_agent", "update articles.processing_status",
     "update public.articles set processing_status = processing_status "
     "where id = (select min(id) from public.articles)", (), "allow"),
    ("collection_agent", "insert comments",
     "insert into public.comments (comment_id, article_id, body_text) "
     "values ('isolation-probe', (select min(id) from public.articles), 'probe')", (), "allow"),
    ("collection_agent", "insert quarantined_content",
     "insert into public.quarantined_content (source_table, source_id, reason, excerpt) "
     "values ('articles', 'probe', 'prompt_injection_suspected', 'probe')", (), "allow"),
    ("collection_agent", "read sentiment_results (not its table)",
     "select 1 from public.sentiment_results limit 1", (), "deny"),
    ("collection_agent", "delete articles",
     "delete from public.articles where id = (select min(id) from public.articles)", (), "deny"),

    # ---- the four analysis agents: read corpus, write only their own ----
    ("sentiment_agent", "select articles",
     "select id from public.articles limit 1", (), "allow"),
    ("sentiment_agent", "insert sentiment_results",
     "insert into public.sentiment_results (article_id) "
     "values ((select min(id) from public.articles))", (), "allow"),
    ("sentiment_agent", "read topic_results (another agent's table)",
     "select 1 from public.topic_results limit 1", (), "deny"),
    ("sentiment_agent", "write topic_results (another agent's table)",
     "insert into public.topic_results (article_id) "
     "values ((select min(id) from public.articles))", (), "deny"),

    ("stance_agent", "select articles",
     "select id from public.articles limit 1", (), "allow"),
    ("stance_agent", "insert stance_results",
     "insert into public.stance_results (article_id) "
     "values ((select min(id) from public.articles))", (), "allow"),
    ("stance_agent", "read sentiment_results (another agent's table)",
     "select 1 from public.sentiment_results limit 1", (), "deny"),

    ("topic_agent", "select articles",
     "select id from public.articles limit 1", (), "allow"),
    ("topic_agent", "insert topic_results",
     "insert into public.topic_results (article_id) "
     "values ((select min(id) from public.articles))", (), "allow"),
    ("topic_agent", "write sentiment_results (another agent's table)",
     "insert into public.sentiment_results (article_id) "
     "values ((select min(id) from public.articles))", (), "deny"),

    ("classification_agent", "select articles",
     "select id from public.articles limit 1", (), "allow"),
    ("classification_agent", "insert classification_results",
     "insert into public.classification_results (article_id) "
     "values ((select min(id) from public.articles))", (), "allow"),
    ("classification_agent", "read stance_results (another agent's table)",
     "select 1 from public.stance_results limit 1", (), "deny"),

    # ---- orchestrator: run tracking only, no corpus writes ----
    ("orchestrator", "insert pipeline_runs",
     "insert into public.pipeline_runs (trigger_type, status) values ('manual','completed')", (), "allow"),
    ("orchestrator", "insert pipeline_stage_runs",
     "insert into public.pipeline_stage_runs (run_id, stage_name, attempt) "
     "values ((select min(id) from public.pipeline_runs), 'collection', 999)", (), "allow"),
    ("orchestrator", "insert articles (not its job)",
     "insert into public.articles (title) values ('probe')", (), "deny"),
    ("orchestrator", "insert sentiment_results (not its job)",
     "insert into public.sentiment_results (article_id) "
     "values ((select min(id) from public.articles))", (), "deny"),

    # ---- aggregator_agent: reads all four results, writes only analysis ----
    ("aggregator_agent", "read sentiment_results",
     "select 1 from public.sentiment_results limit 1", (), "allow"),
    ("aggregator_agent", "read topic_results",
     "select 1 from public.topic_results limit 1", (), "allow"),
    ("aggregator_agent", "read stance_results",
     "select 1 from public.stance_results limit 1", (), "allow"),
    ("aggregator_agent", "read classification_results",
     "select 1 from public.classification_results limit 1", (), "allow"),
    ("aggregator_agent", "insert article_analysis",
     "insert into public.article_analysis (article_id) "
     "values ((select min(id) from public.articles))", (), "allow"),
    ("aggregator_agent", "insert sentiment_results (not its table)",
     "insert into public.sentiment_results (article_id) "
     "values ((select min(id) from public.articles))", (), "deny"),
]


def password_for(role):
    return os.environ.get("PW_" + role.upper())


def connect(role):
    pw = password_for(role)
    if not pw:
        raise RuntimeError(f"no password in .env for PW_{role.upper()}")
    user = f"{role}.{REF}" if REF else role
    return psycopg2.connect(
        host=HOST, port=PORT, dbname=DB, user=user, password=pw, sslmode="require"
    )


def run_check(conn, sql, params):
    """Run one statement inside a savepoint and always roll it back.

    Returns (allowed, detail). A write that succeeds is undone, so the
    test tells you whether permission exists without changing anything.
    """
    with conn.cursor() as cur:
        cur.execute("savepoint probe")
        try:
            cur.execute(sql, params)
            cur.execute("rollback to savepoint probe")
            return True, ""
        except psycopg2.Error as e:
            cur.execute("rollback to savepoint probe")
            # sqlerrm matters, not just the code: 42501 is both "RLS
            # blocked this" and "no such privilege", and other codes
            # (42P01 undefined table, 23502 not-null) mean the test
            # itself is wrong, not the permissions.
            msg = (e.pgerror or str(e)).strip().splitlines()[0]
            return False, f"{e.pgcode}: {msg}"


def main():
    if not REF:
        print("warning: PROJECT_REF not set. The Supabase pooler needs the "
              "username as role.<project-ref>; without it, login will fail.\n")

    tally = Counter()
    problems = []

    for role in ROLES:
        print(f"\n=== {role} ===")
        checks = [c for c in CHECKS if c[0] == role]
        if not checks:
            continue
        try:
            conn = connect(role)
        except Exception as e:
            print(f"  CANNOT CONNECT: {e}")
            print(f"  -- skipped {len(checks)} checks")
            tally["unreachable"] += len(checks)
            problems.append((role, "connection", str(e).strip().splitlines()[0]))
            continue

        try:
            for _, label, sql, params, expect in checks:
                allowed, detail = run_check(conn, sql, params)
                got = "allow" if allowed else "deny"
                if got == expect:
                    tally["ok"] += 1
                    mark = "OK  "
                elif expect == "allow":
                    tally["blocked"] += 1
                    mark = "FAIL"
                    problems.append((role, label, f"should be allowed - {detail}"))
                else:
                    tally["leak"] += 1
                    mark = "LEAK"
                    problems.append((role, label, "should be denied but succeeded"))
                print(f"  {mark} [{expect:>5}] {label}" + (f"  -> {detail}" if detail else ""))
        finally:
            conn.rollback()
            conn.close()

    total = sum(tally.values())
    print(f"\n{'=' * 60}")
    print(f"TOTAL: {tally['ok']}/{total} as expected")
    print(f"  blocked (role cannot do its own job): {tally['blocked']}")
    print(f"  leaks (role reached outside its lane): {tally['leak']}")
    print(f"  unreachable (no credentials / login failed): {tally['unreachable']}")

    if problems:
        print("\nProblems:")
        for role, label, detail in problems:
            print(f"  - [{role}] {label}: {detail}")

    print("\nScope note: this tests the RLS/grant layer only. The pipeline "
          "connects over the Supabase REST API with the secret key, which "
          "bypasses RLS, so these roles are not used at runtime.")

    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
