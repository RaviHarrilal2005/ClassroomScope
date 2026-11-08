// Run with `npm test` (Node's built-in runner; no dependency).
import assert from "node:assert/strict";
import { test } from "node:test";
import { articlesCsv, exportFileName } from "./csv.js";

const article = {
  id: 7, title: "AI tutors, \"cheating\" and you", url: "https://example.com/a", source: "Example News",
  published_date: "2026-09-01T10:00:00+00:00", source_type: "news_outlet", stakeholder: "students",
  stable_topic_id: "T004", topic: "Academic integrity", sentiment: "negative", snippet: "…cheating…",
};
const lines = (csv) => csv.slice(1).split("\r\n");

test("starts with a byte-order mark and ends rows with CRLF, so Excel reads UTF-8", () => {
  const csv = articlesCsv([article]);
  assert.equal(csv[0], "﻿");
  assert.equal(lines(csv).length, 3); // header, one row, trailing newline
});

test("one row per article, quoting commas and doubling quotes", () => {
  const [header, row] = lines(articlesCsv([article]));
  assert.equal(header, "id,title,url,source,published_date,source_type,stakeholder,topic_id,topic,sentiment");
  assert.equal(row, '7,"AI tutors, ""cheating"" and you",https://example.com/a,Example News,'
    + "2026-09-01T10:00:00+00:00,news_outlet,students,T004,Academic integrity,negative");
});

test("missing values are empty cells, not dashes", () => {
  const [, row] = lines(articlesCsv([{ id: 1, title: "Untopiced" }]));
  assert.equal(row, "1,Untopiced,,,,,,,,");
});

test("a cell that would start a formula gets a leading apostrophe", () => {
  const [, row] = lines(articlesCsv([{ id: 2, title: "=HYPERLINK(\"http://x\")", source: "-5 reasons", url: "@x" }]));
  assert.equal(row, '2,"\'=HYPERLINK(""http://x"")",\'@x,\'-5 reasons,,,,,,');
});

test("line breaks inside a cell are quoted", () => {
  const [, row] = lines(articlesCsv([{ id: 3, title: "two\nlines" }]));
  assert.equal(row, '3,"two\nlines",,,,,,,,');
});

test("the snippet column is added only when a search is active", () => {
  assert.ok(lines(articlesCsv([article], { withSnippet: true }))[0].endsWith(",sentiment,snippet"));
  assert.ok(lines(articlesCsv([article], { withSnippet: true }))[1].endsWith(",negative,…cheating…"));
});

test("the file name says which filters made it", () => {
  const day = new Date("2026-10-25T12:00:00Z");
  assert.equal(exportFileName({}, day), "classroomscope-articles_2026-10-25.csv");
  assert.equal(exportFileName({ stakeholder: "students", q: "AI tutor!", from: "2026-01-01", to: "" }, day),
    "classroomscope-articles_from-2026-01-01_stakeholder-students_q-ai-tutor_2026-10-25.csv");
});
