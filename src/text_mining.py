import re
from collections import Counter
from typing import Dict, Iterable, List


def _tokenize(text: str) -> Iterable[str]:
    for token in re.split(r"[\s,.;!?]", text):
        token = token.strip().lower()
        if token:
            yield token


def extract_keywords(text: str, top_k: int = 5) -> List[str]:
    if not text:
        return []
    tokens = list(_tokenize(text))
    stopwords = {"i", "the", "and", "to", "a", "is", "it", "of", "for", "my", "in", "this", "with", "but"}
    tokens = [t for t in tokens if t not in stopwords]
    counts = Counter(tokens)
    return [w for w, _ in counts.most_common(top_k)]


def extract_topics(text: str) -> List[str]:
    ''' simple rule-based topic extraction '''
    text_lower = text.lower()
    topics = []
    rules = {
        "pricing": ["price", "expensive", "cost", "cheap", "subscription", "money", "pay"],
        "ui_ux": ["ui", "design", "interface", "screen", "button", "color", "look", "app"],
        "content": ["song", "track", "artist", "album", "music", "jazz", "pop", "rock"],
        "recommendation": ["recommend", "suggest", "algorithm", "guess", "playlist", "accurate"],
        "performance": ["slow", "bug", "crash", "lag", "loading", "error"],
    }
    for topic, keywords in rules.items():
        for k in keywords:
            if k in text_lower:
                topics.append(topic)
                break
    return topics


def predict_mbti(text: str) -> str:
    text = text.lower()
    scores = {"E": 0, "I": 0, "N": 0, "S": 0, "T": 0, "F": 0, "J": 0, "P": 0}

    keywords = {
        "E": ["social", "friend", "party", "share", "talk", "together", "group"],
        "I": ["alone", "quiet", "private", "myself", "peace", "book", "solo"],
        "N": ["imagine", "idea", "future", "dream", "concept", "theory", "why"],
        "S": ["fact", "detail", "experience", "step", "real", "actual", "past"],
        "T": ["logic", "analyze", "efficient", "system", "think", "mind", "objective"],
        "F": ["feel", "love", "happy", "sad", "mood", "value", "heart"],
        "J": ["plan", "schedule", "goal", "rule", "deadline", "order", "list"],
        "P": ["random", "flow", "change", "maybe", "open", "adapt", "options"]
    }

    for dim, words in keywords.items():
        for w in words:
            if w in text:
                scores[dim] += 1

    e_i = "E" if scores["E"] >= scores["I"] else "I"
    n_s = "N" if scores["N"] >= scores["S"] else "S"
    t_f = "T" if scores["T"] >= scores["F"] else "F"
    j_p = "J" if scores["J"] >= scores["P"] else "P"

    return f"{e_i}{n_s}{t_f}{j_p}"


def classify_user_segment(features: Dict[str, float]) -> str:
    play_count = features.get("play_count", 0)
    duration = features.get("total_duration", 0)
    avg_rating = features.get("avg_rating", 0)

    if play_count > 100 or duration > 20000:
        return "heavy_user"
    if avg_rating > 0 and avg_rating < 3:
        return "at_risk_user" 
    if play_count < 10:
        return "new_or_inactive"
    return "steady_user"
