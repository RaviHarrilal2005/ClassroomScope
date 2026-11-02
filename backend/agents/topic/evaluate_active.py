"""Evaluate explicit reference articles locally; never reads/writes the database.

Reference JSON: [{"article_id": 123, "text": "full text", "label": "T001"}].
Raw articles and generated reports belong in ignored review/, not Git.
"""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--references', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--method', choices=['bertopic'], default='bertopic')
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Output exists; choose a new evaluation directory')
    rows = json.loads(args.references.read_text())
    labels = {'T001', 'T002', 'T003', 'T004', 'T005', 'U'}
    if not isinstance(rows, list) or not rows or any(not isinstance(r.get('text'), str) or not r['text'].strip() or r.get('label') not in labels for r in rows):
        raise ValueError('References require nonempty text and a valid label')
    if len({r['article_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate reference article IDs')
    import pandas as pd
    from .topic_model import analyze_topics, get_model_registration, DEFAULT_MODEL_PATH
    articles = pd.DataFrame([dict(id=r['article_id'], content_hash=None, clean_content=r['text'],
                                 is_relevant=True, llm_relevant=True, processing_status='success') for r in rows])
    results = analyze_topics(articles).set_index('article_id')
    provenance = get_model_registration(DEFAULT_MODEL_PATH)
    predictions = [{'prediction': results.loc[r['article_id'], 'stable_topic_id'] or 'U', 'status': 'completed'} for r in rows]
    details = [{**p, 'article_id': r['article_id'], 'reference': r['label'],
                'text_sha256': hashlib.sha256(r['text'].encode()).hexdigest()}
               for r, p in zip(rows, predictions)]
    report = {'method': args.method, 'provenance': provenance, 'articles': details,
              'sample_size': len(rows), 'matches': sum(r['reference'] == r['prediction'] for r in details),
              'failed': sum(r['status'] == 'failed' for r in details),
              'needs_review': sum(r['status'] == 'needs_review' for r in details),
              'reference_file_sha256': hashlib.sha256(args.references.read_bytes()).hexdigest(),
              'limits': 'Only independently selected and blind-labeled references support independent accuracy claims. Review/failure outcomes never count as correct Unassigned decisions.'}
    args.output.mkdir(parents=True)
    (args.output / 'evaluation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'articles'}, indent=2))


if __name__ == '__main__':
    main()
