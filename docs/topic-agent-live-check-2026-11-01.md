# Live topic storage check - November 1, 2026

Verified Supabase exposes mapping_version and unassigned_reason. Selected article 54 from eligible records without existing topic results and ran the saved provisional-v2 model in offline model mode (no model download). It returned T002 with assignment method bertopic-single-document-v1.

Inserted exactly one new topic result. Read-back matched all emitted fields, including the mapping SHA-256 and null unassigned_reason for an assigned result. Repeating insert returned zero inserted rows and left the stored record unchanged. No historical result was replaced. This checks storage and preservation, not semantic correctness.

This article was assigned, so the live run did not exercise an Unassigned result or a qualifying review-only suggestion. Those paths have controlled offline test coverage and still require a suitable live example. No browser/dashboard demonstration was performed.

Detailed result is retained locally in review/live-provenance-check-2026-11-01/result.json, excluded from Git. The active model remains provisional.
