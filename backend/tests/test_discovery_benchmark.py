import numpy as np
import pytest
from scipy.sparse import csr_matrix
from agents.topic.benchmark_discovery import topic_metrics


def test_cooccurrence_distinguishes_exclusive_from_associated_keywords():
    exclusive=csr_matrix([[1,0],[0,1],[1,0],[0,1]])
    associated=csr_matrix([[1,1],[1,1],[0,0],[0,0]])
    assert topic_metrics([['a','b']],exclusive,['a','b'],2)['mean_document_npmi']==-1
    result=topic_metrics([['a','b']],associated,['a','b'],2)
    assert result['mean_document_npmi']==pytest.approx(1)
    assert result['coverage']==.5
    assert result['unassigned']==2


def test_no_discovered_topics_does_not_claim_coherence():
    result=topic_metrics([],csr_matrix(np.ones((3,2))),['a','b'],0)
    assert result['topics']==0
    assert result['mean_document_npmi'] is None
    assert result['keyword_diversity'] is None
