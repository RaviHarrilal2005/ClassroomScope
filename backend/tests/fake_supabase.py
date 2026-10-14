"""
An in-memory stand-in for the Supabase tables the dashboard reads.

Implements just the PostgREST calls orchestrator/corpus.py makes, with
the server's habit of capping each response at `cap` rows. Records every
table opened and every ilike pattern, so tests can check what was asked.
"""
import re
from types import SimpleNamespace


class FakeQuery:
    def __init__(self, client, rows):
        self.client, self.rows, self.window, self.counting = client, list(rows), None, False

    def select(self, columns, count=None):
        self.counting = count == "exact"
        return self

    def eq(self, column, value):
        self.rows = [r for r in self.rows if r.get(column) == value]
        return self

    def in_(self, column, values):
        values = set(values)
        self.rows = [r for r in self.rows if r.get(column) in values]
        return self

    def ilike(self, column, pattern):
        self.client.patterns.append(pattern)
        assert pattern.startswith("%") and pattern.endswith("%"), pattern
        needle = re.sub(r"\\(.)", r"\1", pattern[1:-1]).lower()
        self.rows = [r for r in self.rows if needle in (r.get(column) or "").lower()]
        return self

    def order(self, column, desc=False):
        self.rows.sort(key=lambda r: r.get(column) or "", reverse=desc)
        return self

    def range(self, start, end):
        self.window = (start, min(end + 1, start + self.client.cap))
        return self

    def limit(self, size):
        self.window = (0, size)
        return self

    def execute(self):
        if self.client.error:
            raise self.client.error
        data = self.rows[slice(*self.window)] if self.window else self.rows
        return SimpleNamespace(data=data, count=len(self.rows) if self.counting else None)


class FakeSupabase:
    def __init__(self, cap=1000, error=None, **tables):
        self.tables, self.cap, self.error = tables, cap, error
        self.opened, self.patterns = [], []

    def table(self, name):
        self.opened.append(name)
        return FakeQuery(self, self.tables.get(name, []))
