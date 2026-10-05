import csv
import re
from transformers import pipeline, AutoTokenizer
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# news-trained model (matched the hand-checked labels best in our 10-article test)
model_name = "Jean-Baptiste/roberta-large-financial-news-sentiment-en"
method_name = "roberta_news"

# extra copies of articles that were saved more than once
# (the first copy is kept: 53, 47, 356, 492) - same ones the topic agent leaves out
duplicates = ["54", "322", "357", "358", "493"]

sentiment_model = pipeline(
    "text-classification",
    model=model_name
)

tokenizer = AutoTokenizer.from_pretrained(model_name)

vader = SentimentIntensityAnalyzer()

print("Sentiment models loaded")


def analyze_sentiment(text):
    # stop if the article has no text (dividing by 0 chunks would crash)
    if text.strip() == "":
        raise ValueError("Article has no text to analyze")

    tokens = tokenizer.encode(text, add_special_tokens=False)

    chunk_size = 500
    chunks = []

    for i in range(0, len(tokens), chunk_size):
        chunk_tokens = tokens[i:i + chunk_size]
        chunk_text = tokenizer.decode(
            chunk_tokens,
            skip_special_tokens=True
        )
        # save the chunk text and how long it is
        chunks.append((chunk_text, len(chunk_tokens)))

    scores = {
        "positive": 0,
        "neutral": 0,
        "negative": 0
    }
    total_tokens = 0

    for chunk_text, chunk_length in chunks:
        results = sentiment_model(chunk_text, top_k=None, truncation=True)

        for result in results:
            label = result["label"].lower()
            # longer chunks count more than short ones
            scores[label] += result["score"] * chunk_length

        total_tokens += chunk_length

    for label in scores:
        scores[label] = scores[label] / total_tokens

    final_sentiment = max(scores, key=scores.get)
    confidence = scores[final_sentiment]

    return final_sentiment, confidence, scores


def vader_sentiment(text):
    # our adaptation of VADER for full articles:
    # score each sentence, then average the sentence scores
    if text.strip() == "":
        raise ValueError("Article has no text to analyze")

    sentences = re.split(r"[.!?]+", text)
    sentences = [s for s in sentences if s.strip() != ""]

    total = 0
    for sentence in sentences:
        total += vader.polarity_scores(sentence)["compound"]

    average = total / len(sentences)

    # standard VADER cutoffs
    if average >= 0.05:
        label = "positive"
    elif average <= -0.05:
        label = "negative"
    else:
        label = "neutral"

    return label, average


# read the articles file downloaded from Supabase
csv.field_size_limit(10000000)

articles = []
skipped_duplicates = []
with open("articles_rows.csv", encoding="utf-8") as file:
    reader = csv.DictReader(file)
    for row in reader:
        # same rule as Juan's code: relevant AND successfully cleaned
        if (
            row["is_relevant"].strip().lower() == "true"
            and row["processing_status"].strip().lower() == "success"
            and row["clean_content"].strip() != ""
        ):
            if row["id"] in duplicates:
                skipped_duplicates.append(row["id"])
                continue
            articles.append(row)

print("Relevant articles found:", len(articles))
print("Duplicates skipped:", skipped_duplicates)

# run every article and keep the results
results = []
failed = []
agree = 0

for number, article in enumerate(articles, start=1):
    try:
        roberta_label, roberta_confidence, roberta_scores = analyze_sentiment(article["clean_content"])
        vader_label, vader_score = vader_sentiment(article["clean_content"])
    except Exception as error:
        # skip this article but remember it, so one bad article doesn't stop everything
        failed.append(article["id"])
        print(number, "of", len(articles), "| Article", article["id"], "| FAILED:", error)
        continue

    match = roberta_label == vader_label
    if match:
        agree += 1

    results.append({
        "article_id": article["id"],
        "title": article["title"],
        "roberta_sentiment": roberta_label,
        "roberta_confidence": roberta_confidence,
        "positive": roberta_scores["positive"],
        "neutral": roberta_scores["neutral"],
        "negative": roberta_scores["negative"],
        "vader_sentiment": vader_label,
        "vader_score": vader_score,
        "match": match
    })

    print(number, "of", len(articles), "| Article", article["id"],
          "| RoBERTa:", roberta_label, round(roberta_confidence, 3),
          "| VADER:", vader_label, round(vader_score, 3))

if results:
    # file 1: all results, for checking and for the report (full numbers, not rounded)
    with open("sentiment_results_final.csv", "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    # file 2: only the columns the Supabase sentiment_results table has
    with open("sentiment_upload.csv", "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["article_id", "sentiment", "confidence", "method"])
        writer.writeheader()
        for r in results:
            writer.writerow({
                "article_id": r["article_id"],
                "sentiment": r["roberta_sentiment"],
                "confidence": r["roberta_confidence"],
                "method": method_name
            })

    print("\nSaved sentiment_results_final.csv and sentiment_upload.csv")
else:
    print("\nNo results to save")

# summary
print("\n----------------------------")
print("Articles analyzed:", len(results))
print("Articles failed:", len(failed), failed)

for label in ["positive", "neutral", "negative"]:
    roberta_count = sum(1 for r in results if r["roberta_sentiment"] == label)
    vader_count = sum(1 for r in results if r["vader_sentiment"] == label)
    print(label, "| RoBERTa:", roberta_count, "| VADER:", vader_count)

if results:
    print("RoBERTa and VADER agreed on", agree, "out of", len(results), "articles")
