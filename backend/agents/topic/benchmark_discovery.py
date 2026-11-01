"""Compare saved discovery outputs with an LDA baseline on the same corpus.

No training labels, model activation, API requests, or database writes.
"""
import argparse
import hashlib
import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer, ENGLISH_STOP_WORDS
from sklearn.metrics import adjusted_mutual_info_score


def topic_metrics(topics, matrix, vocabulary, assigned):
    """Document-level NPMI and keyword diversity; neither measures label accuracy."""
    index = {word: i for i, word in enumerate(vocabulary)}
    words = [list(dict.fromkeys(t))[:10] for t in topics if t]
    binary = (matrix > 0).astype(float)
    n = matrix.shape[0]
    scores = []
    for topic in words:
        pairs = []
        for a, b in combinations(topic, 2):
            if a not in index or b not in index:
                pairs.append(-1.0); continue
            pa = float(binary[:, index[a]].sum()) / n
            pb = float(binary[:, index[b]].sum()) / n
            joint = float(binary[:, index[a]].multiply(binary[:, index[b]]).sum()) / n
            if joint == 0:
                pairs.append(-1.0)
            elif joint == 1:
                pairs.append(0.0)  # ubiquitous terms provide no association information
            else:
                pairs.append(float(np.log(joint / (pa * pb)) / -np.log(joint)))
        if pairs:
            scores.append(float(np.mean(pairs)))
    total = sum(map(len, words))
    return dict(topics=len(words), assigned=int(assigned), unassigned=int(n-assigned),
                coverage=assigned/n, keyword_diversity=len({w for t in words for w in t})/total if total else None,
                mean_document_npmi=float(np.mean(scores)) if scores else None)


def benchmark(candidate, output, topic_count=5):
    if output.exists():
        raise ValueError('Output exists; choose a new directory')
    if isinstance(topic_count, bool) or not isinstance(topic_count, int) or topic_count < 2:
        raise ValueError('Topic count must be an integer of at least two')
    from .train_auto import read_snapshot, DOMAIN_STOP_WORDS
    snapshot = candidate/'articles.json'
    manifest = json.loads((candidate/'training.json').read_text())
    digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    if manifest['status'] != 'succeeded' or digest != manifest['input_snapshot_sha256']:
        raise ValueError('Candidate snapshot is not a verified successful training input')
    articles = read_snapshot(snapshot)
    assignments = pd.read_csv(candidate/'assignments.csv')
    if assignments.article_id.duplicated().any() or set(assignments.article_id) != set(articles.id):
        raise ValueError('Candidate assignment IDs differ from snapshot')
    assignments = assignments.set_index('article_id').loc[articles.id]
    info = pd.read_csv(candidate/'topics.csv').fillna('')
    if set(info.topic_id) != set(assignments.topic_id):
        raise ValueError('Candidate topic IDs differ from assignments')
    if any(int(row['count']) != int((assignments.topic_id==row['topic_id']).sum()) for _,row in info.iterrows()):
        raise ValueError('Candidate topic counts differ from assignments')
    if topic_count > len(articles):
        raise ValueError('Topic count exceeds articles')
    vectorizer = CountVectorizer(stop_words=sorted(ENGLISH_STOP_WORDS | DOMAIN_STOP_WORDS))
    matrix = vectorizer.fit_transform(articles.clean_content)
    vocabulary = vectorizer.get_feature_names_out()
    lda = LatentDirichletAllocation(n_components=topic_count, max_iter=20, learning_method='batch', random_state=42)
    probabilities = lda.fit_transform(matrix)
    lda_ids = probabilities.argmax(axis=1)
    lda_words = [[str(vocabulary[i]) for i in np.argsort(-weights)[:10]] for weights in lda.components_]
    discovered_words = [[w.strip() for w in row.keywords.split(';') if w.strip()] for row in info.itertuples() if row.topic_id!=-1]
    normalized = articles.clean_content.map(lambda t:' '.join(t.casefold().split()))
    report = dict(method='Same-corpus descriptive discovery comparison, not held-out accuracy. NPMI uses binary document co-occurrence over full bodies. LDA forces a topic; HDBSCAN may abstain. Adjusted mutual information measures grouping agreement, not correctness.',
                  candidate_version=manifest['version'],snapshot_sha256=digest,articles=len(articles),
                  compared_output_sha256={name:hashlib.sha256((candidate/name).read_bytes()).hexdigest() for name in ('topics.csv','assignments.csv')},
                  normalized_text_duplicates=int(normalized.duplicated().sum()),
                  configuration=dict(lda_topics=topic_count,lda_iterations=20,seed=42,top_keywords=10),
                  discovery=topic_metrics(discovered_words,matrix,vocabulary,int((assignments.topic_id!=-1).sum())),
                  lda=topic_metrics(lda_words,matrix,vocabulary,len(articles)),
                  adjusted_mutual_information=float(adjusted_mutual_info_score(assignments.topic_id,lda_ids)),
                  lda_keywords={str(i):words for i,words in enumerate(lda_words)},
                  limitations=['Corpus eligibility flags do not establish relevance or source quality.',
                               'Exact duplicates and syndicated stories can inflate apparent coherence.',
                               'Saved BERTopic output uses its recorded representation; LDA reads full bodies.',
                               'Higher coverage, coherence, diversity, or cross-model agreement does not prove semantic correctness.',
                               'Saved candidate model binaries may have been removed; this compares retained training outputs.'])
    output.mkdir(parents=True)
    (output/'comparison.json').write_text(json.dumps(report,indent=2)+'\n')
    pd.DataFrame(dict(article_id=articles.id,discovery_topic=assignments.topic_id.to_numpy(),lda_topic=lda_ids)).to_csv(output/'assignments.csv',index=False)
    print(json.dumps({k:v for k,v in report.items() if k not in {'lda_keywords','limitations'}},indent=2))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--topic-count',type=int,default=5)
    args=parser.parse_args()
    benchmark(args.candidate,args.output,args.topic_count)


if __name__=='__main__':
    main()
