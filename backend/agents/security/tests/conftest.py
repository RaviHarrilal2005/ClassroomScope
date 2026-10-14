"""
test_agent_db_access.py is a script, not a pytest test: it logs in to
Postgres as each agent role and needs psycopg2 and the roles' passwords.
Run it as `python test_agent_db_access.py`; pytest must not import it.
"""
collect_ignore = ["test_agent_db_access.py"]
