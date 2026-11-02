"""Dry-run one article using the selected topic method; no database writes."""
import argparse
import os
from pathlib import Path


def main():
    from ..config import load_env
    load_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--text-file', type=Path, required=True)
    parser.add_argument('--method', choices=['bertopic'], default=os.getenv('TOPIC_METHOD', 'bertopic'))
    args = parser.parse_args()
    text = args.text_file.read_text()
    import pandas as pd
    from .topic_model import analyze_topics
    row = dict(id=1, content_hash=None, clean_content=text, is_relevant=True, llm_relevant=True, processing_status='success')
    print(analyze_topics(pd.DataFrame([row])).to_json(orient='records', indent=2))


if __name__ == '__main__':
    main()
