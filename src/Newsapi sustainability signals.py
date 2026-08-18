"""
Innovation Radar - Sustainability Signal Collector
====================================================
Pulls recent sustainability-related news articles from NewsAPI.ai (Event Registry)
and exports them as structured "external signals" for Step 1 of the
Opportunity Discovery Process:
    Signals -> Themes -> Opportunity spaces -> Scoring -> Radar

Each article is tagged with:
    - likely business vertical(s)
    - a rough signal type guess (regulation / market move / technology maturity /
      trend / unclassified)

Setup:
    pip install eventregistry --break-system-packages
    export NEWSAPI_AI_KEY="your-api-key"

Default behavior:
    - Restricts results to European sources
    - Excludes paywalled sources
    - Outputs JSON unless a .csv path is provided
"""

import os
import sys
import csv
import json
import argparse
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

try:
    from eventregistry import (
        EventRegistry, QueryArticlesIter, QueryItems,
        ReturnInfo, ArticleInfoFlags,
    )
except ImportError:
    sys.exit("Missing dependency. Run: pip install eventregistry --break-system-packages")


#===========================================================
# STEP 1 — CONFIGURATION & CONSTANTS (START)
#===========================================================

MAX_KEYWORDS = 15  # Provider keyword limit

VERTICAL_KEYWORDS = {
    "Manufacturing": ["manufacturing", "factory", "industrial", "supply chain", "forestry", "paper"],
    "Retail": ["retail", "consumer goods", "fmcg"],
    "Finance/Banking/Insurance": ["bank", "insurance", "finance", "insurer"],
    "Public/Gov": ["government", "public sector", "municipal", "eu regulation"],
    "Defense": ["defense", "defence", "military"],
    "Automotive": ["automotive", "vehicle", "ev ", "electric vehicle"],
    "Transportation & Construction": ["transportation", "logistics", "construction", "shipping"],
    "Lifesciences": ["pharma", "biotech", "life sciences"],
    "Energy": ["energy", "power grid", "renewable", "solar", "wind power"],
    "Wholesale": ["wholesale", "distribution"],
    "Media & Entertainment": ["media", "streaming", "entertainment"],
    "Healthcare": ["healthcare", "hospital", "medical"],
    "Natural Resources": ["mining", "natural resources", "extraction"],
    "Aerospace & Defense": ["aerospace", "aviation"],
}

DEFAULT_SUSTAINABILITY_KEYWORDS = [
    "sustainability", "ESG", "carbon emissions", "circular economy",
    "net zero", "decarbonization", "climate regulation",
    "supply chain traceability", "digital product passport", "carbon tax",
]

DEFAULT_DATA_TYPES = ["news", "pr"]

EUROPEAN_COUNTRIES = [
    "Belgium", "France", "Germany", "Netherlands", "United Kingdom",
    "Ireland", "Spain", "Italy", "Portugal", "Switzerland", "Austria",
    "Sweden", "Norway", "Denmark", "Finland", "Poland", "Czech Republic",
    "Luxembourg", "Greece", "Romania", "Hungary",
]

#===========================================================
# STEP 2 — SUPPORTING UTILITIES (START)
#===========================================================

def get_european_location_uris(er):
    """Resolve country names to Event Registry location URIs."""
    uris = []
    for country in EUROPEAN_COUNTRIES:
        uri = er.getLocationUri(country)
        if uri:
            uris.append(uri)
        else:
            print(f"Warning: could not resolve location URI for '{country}', skipping.")
    return uris


def extract_domain(article):
    """Extract domain from Event Registry source or fallback to URL parsing."""
    source_uri = (article.get("source") or {}).get("uri")
    if source_uri:
        return source_uri
    url = article.get("url") or ""
    netloc = urlparse(url).netloc
    return netloc[4:] if netloc.startswith("www.") else netloc


def tag_verticals(text):
    """Simple substring-based vertical tagging."""
    text_lower = text.lower()
    return [v for v, kws in VERTICAL_KEYWORDS.items() if any(k in text_lower for k in kws)]


def classify_signal_type(title, categories):
    """Heuristic signal-type classifier."""
    cat_text = " ".join(categories).lower()
    title_lower = (title or "").lower()
    combined = f"{title_lower} {cat_text}"

    if any(w in combined for w in ["regulation", "policy", "law", "directive", "compliance", "mandate"]):
        return "regulation"
    if any(w in combined for w in ["deal", "partnership", "acquire", "acquisition", "invest", "funding", "contract"]):
        return "market move"
    if any(w in combined for w in ["launch", "release", "unveil", "pilot", "rollout"]):
        return "technology maturity"
    if any(w in combined for w in ["survey", "report", "study", "forecast", "market size", "growing"]):
        return "trend"
    return "unclassified"


def cap_keywords(keywords, limit=MAX_KEYWORDS):
    """Ensure keyword list stays within provider word-count limits."""
    kept, dropped, total_words = [], [], 0
    for kw in keywords:
        word_count = len(kw.split())
        if total_words + word_count <= limit:
            kept.append(kw)
            total_words += word_count
        else:
            dropped.append(kw)
    if dropped:
        print(f"Warning: keyword limit exceeded. Dropped: {', '.join(dropped)}")
    return kept


#===========================================================
# STEP 3 — FETCH & ENRICH SIGNALS (START)
#===========================================================

def fetch_signals(api_key, keywords, days, lang, max_articles, domain_label,
                   europe_only=True, data_types=None, full_body=False):
    """
    STEP 3A — Keyword preparation
    STEP 3B — Event Registry initialization
    STEP 3C — Query construction
    STEP 3D — Article fetching
    STEP 3E — Article enrichment
    """

    # STEP 3A — Keyword preparation
    keywords = cap_keywords(keywords)

    # STEP 3B — Initialize Event Registry client
    er = EventRegistry(apiKey=api_key, allowUseOfArchive=True)
    date_start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    # STEP 3C — Build query parameters
    query_kwargs = dict(
        keywords=QueryItems.OR(keywords),
        lang=lang,
        dateStart=date_start,
        categoryUri=er.getCategoryUri("Environment"),
        isDuplicateFilter="skipDuplicates",
        ignoreSourceGroupUri="paywall/paywalled_sources",
        dataType=data_types or DEFAULT_DATA_TYPES,
    )

    if europe_only:
        location_uris = get_european_location_uris(er)
        if location_uris:
            query_kwargs["sourceLocationUri"] = location_uris

    q = QueryArticlesIter(**query_kwargs)

    # STEP 3D — Define return fields
    return_info = ReturnInfo(
        articleInfo=ArticleInfoFlags(
            bodyLen=-1 if full_body else 300,
            concepts=True,
            categories=True,
            sentiment=True,
            socialScore=False,
        )
    )

    # STEP 3E — Fetch & enrich articles
    signals = []
    for idx, art in enumerate(q.execQuery(er, sortBy="date", maxItems=max_articles, returnInfo=return_info)):
        categories = [c.get("label", "") for c in (art.get("categories") or [])]

        enriched = dict(art)
        enriched["id"] = idx
        enriched["domain"] = domain_label
        enriched["source_domain"] = extract_domain(art)
        enriched["verticals"] = tag_verticals(f"{art.get('title', '')} {art.get('body', '')}")
        enriched["signal_type_guess"] = classify_signal_type(art.get("title"), categories)

        signals.append(enriched)

    return signals


#===========================================================
# STEP 4 — SAVE OUTPUT (START)
#===========================================================

def save_signals(signals, output_path):
    """Write enriched signals to JSON or CSV."""

    # CSV OUTPUT
    if output_path.endswith(".csv"):
        fieldnames = [
            "id", "title", "date", "domain", "source", "source_domain", "url",
            "body_excerpt", "concepts", "categories", "sentiment",
            "verticals", "signal_type_guess",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for art in signals:
                source = art.get("source") or {}
                concept_labels = [(c.get("label") or {}).get("eng") for c in (art.get("concepts") or [])][:8]
                categories_labels = [c.get("label", "") for c in (art.get("categories") or [])]
                body = art.get("body") or ""

                writer.writerow({
                    "id": art.get("id"),
                    "title": art.get("title"),
                    "date": art.get("date"),
                    "domain": art.get("domain"),
                    "source": source.get("title"),
                    "source_domain": art.get("source_domain"),
                    "url": art.get("url"),
                    "body_excerpt": body[:300],
                    "concepts": "; ".join(c for c in concept_labels if c),
                    "categories": "; ".join(categories_labels),
                    "sentiment": art.get("sentiment"),
                    "verticals": "; ".join(art.get("verticals") or []),
                    "signal_type_guess": art.get("signal_type_guess"),
                })

    # JSON OUTPUT
    else:
        payload = {
            "articles": {
                "results": signals,
                "totalResults": len(signals),
                "page": 1,
                "count": len(signals),
                "pages": 1,
            }
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

#===========================================================
# STEP 5 — MAIN ENTRY POINT (START)
#===========================================================

def main():
    """CLI entry point: parse arguments → fetch signals → save output."""

    # STEP 5A — Parse CLI arguments
    parser = argparse.ArgumentParser(description="Collect sustainability signals from NewsAPI.ai")
    parser.add_argument("--keywords", type=str, default=",".join(DEFAULT_SUSTAINABILITY_KEYWORDS))
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--max-articles", type=int, default=200)
    parser.add_argument("--lang", type=str, default="eng")
    parser.add_argument("--output", type=str, default="sustainability_signals.json")
    parser.add_argument("--global", dest="global_scope", action="store_true")
    parser.add_argument("--domain", type=str, default="Sustainability")
    parser.add_argument("--data-types", type=str, default=",".join(DEFAULT_DATA_TYPES))
    parser.add_argument("--full-body", action="store_true")
    args = parser.parse_args()

    # STEP 5B — Load API key
    api_key = os.environ.get("NEWSAPI_AI_KEY")
    if not api_key:
        sys.exit("Set your API key first: export NEWSAPI_AI_KEY='your-key-here'")

    # STEP 5C — Prepare parameters
    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    data_types = [d.strip() for d in args.data_types.split(",") if d.strip()]

    # STEP 5D — Fetch signals
    signals = fetch_signals(
        api_key, keywords, args.days, args.lang, args.max_articles,
        domain_label=args.domain,
        europe_only=not args.global_scope,
        data_types=data_types,
        full_body=args.full_body,
    )

    # STEP 5E — Save output
    save_signals(signals, args.output)

    # STEP 5F — Final summary
    print(f"Saved {len(signals)} signals to {args.output}")


if __name__ == "__main__":
    main()
