import json
import os


def load_regulations() -> list[dict]:
    file_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "..",
        "data",
        "processed",
        "hcmus_regulations.json",
    )
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def search_regulations(query: str, top_k: int = 3) -> list[dict]:
    """
    Search regulations using simple keyword matching and return matches with provenance.
    """
    regulations = load_regulations()
    if not regulations or not query:
        return []

    query_lower = query.lower()
    query_words = set(query_lower.split())

    scored_results = []
    for reg in regulations:
        score = 0
        content_lower = reg.get("content", "").lower()

        # Simple term frequency
        for word in query_words:
            if word in content_lower:
                score += 1

        # Keyword bonus
        keywords = reg.get("keywords", [])
        for kw in keywords:
            if kw.lower() in query_lower:
                score += 2

        if score > 0:
            scored_results.append((score, reg))

    # Sort by score descending
    scored_results.sort(key=lambda x: x[0], reverse=True)

    # Return top_k with provenance metadata
    top_results = []
    for score, reg in scored_results[:top_k]:
        top_results.append(
            {
                "document": reg.get("document"),
                "article": reg.get("article"),
                "clause": reg.get("clause"),
                "page": reg.get("page"),
                "content": reg.get("content"),
            }
        )

    return top_results
