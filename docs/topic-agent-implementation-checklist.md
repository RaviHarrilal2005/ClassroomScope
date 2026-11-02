# BERTopic-primary release status - November 1, 2026

- [x] BERTopic restored as the default in the adapter, registry, local/example configuration, CLI and deployment.
- [x] Review-only suggestions retained; model outliers remain Unassigned.
- [x] Model and mapping provenance fields retained; historical database results preserved.
- [x] Discovery and LDA tools remain separate deliberate operations.
- [x] Language-model implementation archived locally; removed its active pipeline selection and imports.
- [x] Current operating/deployment guides updated.
- [ ] Repair verified extraction defects and compare a corrected training snapshot against unchanged inputs.
- [ ] Validate category quality independently; the existing mapping is provisional and mixed.
- [x] Verify live read-only API counts/filters and replay captured responses in isolated local Chrome; all five topic filters and clearing filters passed.
- Cloud/Linux deployment is outside the required scope, confirmed by the user; it is not a release blocker.

The semantic-runtime checklist below is historical experimental work, not the primary release requirements.

# Topic agent release checklist - November 1, 2026

Current architecture and operations: [topic-agent.md](topic-agent.md).

## Implemented

- [x] Five reviewed category definitions, including student-only T001.
- [x] Separate BERTopic discovery and LDA comparison tooling.
- [x] Primary in-process semantic assignment using pinned Qwen revision on CPU/CUDA; optional HTTP runtime.
- [x] Pipeline adapter, explicit legacy rollback and no automatic fallback on failures.
- [x] Full-text span evidence, strict category/reason contract and bounded input/output.
- [x] Three Unassigned reasons, explicit input-limit review handling and failed-stage routing for bad outputs/transport/storage errors.
- [x] Insert-only storage, mapping/definition and prompt/model provenance; historical results preserved.
- [x] Database migrations applied; earlier live stored-result preservation verified.
- [x] Portable deployment files, lean dependency manifest and operating guide.
- [x] Experimental code remains local, excluded from Git; new runtime has no imports from those files.

## Acceptance work remaining

- [ ] Full pinned-Qwen smoke inference with the portable runtime on adequate hardware. The Mac has 16 GB RAM; float32 weights alone approach that capacity.
- [ ] Linux container build/run and model-ready smoke check. Docker is not installed here.
- [ ] Measure peak memory and latency on representative long and short articles.
- [ ] Evaluate independent reference articles under this new prompt/runtime; do not inherit Mac MLX development scores.
- [ ] Verify a new semantic result through live Supabase and dashboard filtering/counts after runtime smoke acceptance. Earlier live checks used the historical BERTopic path.
- [ ] Record the release/activation acceptance decision with known accuracy limitations.

## Later enhancements

- Human review queue UI; review counts currently exist without such an interface.
- Reprocessing with retained version history; existing insert-only behavior intentionally preserves older assignments.
- Apply reviewed exclusion/copy manifests and repair extraction defects before future discovery training.

Final local functional evidence: topic-agent-local-release.md. Upstream extraction work is assigned to another team member; do not modify that component as part of topic-agent work.
