"""Lightweight lexicon-based sentiment analysis for product reviews (no external model needed).
Replace `score_text` with a transformer (e.g. Hugging Face) or a managed cloud NLP API for production."""
import re

from database import query_df

POS = {"excellent", "love", "great", "good", "amazing", "perfect", "fresh", "recommend", "worth", "fast",
       "enjoyed", "value", "best", "happy", "nice"}
NEG = {"poor", "terrible", "bad", "disappointed", "broken", "damaged", "late", "overpriced", "worst",
       "stopped", "waste", "cheap"}
NEGATORS = {"not", "never", "no", "hardly"}


def score_text(text: str) -> float:
    """Returns a score in [-1, 1]."""
    words = re.findall(r"[a-z']+", text.lower())
    score = 0
    for i, w in enumerate(words):
        polarity = 1 if w in POS else -1 if w in NEG else 0
        if polarity and i > 0 and words[i - 1] in NEGATORS:
            polarity *= -1
        score += polarity
    return max(-1.0, min(1.0, score / 3))


def label(score: float) -> str:
    return "positive" if score > 0.15 else "negative" if score < -0.15 else "neutral"


def sentiment_report() -> list[dict]:
    df = query_df(
        "SELECT r.product_id, p.name, p.category, r.text, r.rating FROM reviews r JOIN products p ON p.id = r.product_id"
    )
    df["score"] = df["text"].map(score_text)
    df["label"] = df["score"].map(label)
    out = []
    for (pid, name, cat), g in df.groupby(["product_id", "name", "category"]):
        share = g["label"].value_counts(normalize=True)
        out.append({
            "product_id": int(pid), "name": name, "category": cat, "reviews": int(len(g)),
            "avg_rating": round(float(g["rating"].mean()), 2), "sentiment_score": round(float(g["score"].mean()), 2),
            "positive_pct": round(float(share.get("positive", 0)) * 100, 1),
            "negative_pct": round(float(share.get("negative", 0)) * 100, 1),
        })
    out.sort(key=lambda r: r["sentiment_score"])
    return out
