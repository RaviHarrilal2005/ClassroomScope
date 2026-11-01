"""Evaluate the active agent against existing human reviews, without DB access."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Output exists; choose a new evaluation directory')
    from .reviewed_candidate import read_reviews, metrics
    from .topic_model import analyze_topics, get_model_registration, DEFAULT_MODEL_PATH
    import pandas as pd
    root = Path(__file__).resolve().parents[3]
    rows = read_reviews(root)
    articles = pd.DataFrame([dict(id=i, content_hash=r['group'], clean_content=r['text'],
                                  is_relevant=True, llm_relevant=True, processing_status='success')
                             for i, r in enumerate(rows)])
    results = analyze_topics(articles).set_index('article_id')
    registration = get_model_registration(DEFAULT_MODEL_PATH)
    original, final, details = [], [], []
    for i, row in enumerate(rows):
        # Exact duplicate text shares a prediction, matching production deduplication.
        representative = next(j for j, other in enumerate(rows) if other['group'] == row['group'])
        result = results.loc[representative]
        raw = int(result['original_topic_id'])
        before = 'U' if raw == -1 else registration['topic_mapping'][str(raw)]
        after = result['stable_topic_id'] if pd.notna(result['stable_topic_id']) else 'U'
        original.append(before)
        final.append(after)
        details.append(dict(review_set=row['review_set'], review_id=row['review_id'],
                            article_id=row['article_id'], human_label=row['label'],
                            original_prediction=before, final_prediction=after))
    report = dict(method='Replay of previously reviewed development examples; not fresh or independent validation.',
                  model_version=registration['version'], model_sha256=registration['sha256'],
                  inference_policy='bertopic-single-document-v1',
                  fallback_policy='topic-cosine-0.85-gap-0.03-single-document-v2',
                  unique_articles=len(results), reviewed_examples=len(rows),
                  original_model=metrics(rows, original), with_fallback=metrics(rows, final),
                  fallback_changed=sum(a != b for a, b in zip(original, final)), articles=details)
    args.output.mkdir(parents=True)
    (args.output / 'evaluation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'articles'}, indent=2))


if __name__ == '__main__':
    main()
