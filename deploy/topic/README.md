# BERTopic-primary deployment

Routine assignment runs the existing saved BERTopic model inside the app. No separate inference host, model API key, Qwen weights or Apple MLX dependency is needed. Language-model sources are archived locally and cannot be selected by the active pipeline.

## Direct local/Linux setup

Use Python 3.12, install `backend/requirements.txt`, restore the model with `git lfs pull`, and configure the existing backend/.env credentials. Set `TOPIC_METHOD=bertopic` (also the default). Keep the exact runtime environment with the pickle; library changes may require compatibility checks. Dependencies are not a fully frozen cross-platform lockfile.

From backend/, dry-run a file without database access:

```sh
python -m agents.topic.assign --text-file /absolute/path/article.txt
```

The existing live pipeline and `python -m agents.topic.topic_model` can insert Supabase results. Existing article rows are preserved. Check required migrations before live use.

## Container package

From the repository root:

```sh
git lfs pull
docker compose -f deploy/topic/compose.yaml build
docker compose -f deploy/topic/compose.yaml up -d
```

The build includes only the active saved topic pickle from the model folder and rejects a Git LFS pointer. Raw corpora, experimental model directories and credentials are excluded. backend/.env is supplied at runtime. CPU PyTorch wheels and backend dependencies are installed; no Qwen model is provisioned. The named volume caches embedding assets; provision required assets before offline operation.

The API binds to loopback port 5000 for integration with the project's frontend/proxy. The frontend is not bundled in this backend image. Health checks test API reachability, not model readiness. Use a dry-run with a mounted article file to verify model loading before live pipeline execution. One worker avoids multiplying model memory; perform host-specific latency/memory checks before scaling.

Docker is unavailable in this workspace. Configuration syntax and software tests are checked, but no Linux image build/run has been performed. This is a deployment package, not a claim that a cloud service has been launched or certified.

## Discovery and limitations

Use train_auto.py in the same BERTopic-capable environment for deliberate candidate discovery and benchmark_discovery.py for an LDA comparison. Candidates remain inactive pending review. The current saved mapping mixes some reporting categories; current evidence does not establish reliable five-category accuracy. More-cluster experiments did not resolve the key boundary cases. See docs/topic-agent.md and docs/topic-agent-validation.md.
