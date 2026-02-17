import json
import html
from pathlib import Path

import requests

ORCID = "0000-0001-5374-6410"
EMAIL = "alberto.jaramilloj@udea.edu.co"
API_URL = "https://api.crossref.org/works"
TIMEOUT_SECONDS = 15
MAX_ROWS = 200

PLACEHOLDER_ITEM = {
    "name": (
        "No publications found via Crossref (yet). Tip: ensure your ORCID is connected in publisher metadata."
    ),
    "link": "#",
    "description": "",
}


def _safe_text(value) -> str:
    """Strip + HTML-unescape any string-ish value."""
    return html.unescape((value or "").strip())


def _pick_year(item):
    for key in ("published-print", "published-online", "created", "issued"):
        date_parts = item.get(key, {}).get("date-parts")
        if date_parts and isinstance(date_parts, list) and date_parts[0]:
            year = date_parts[0][0]
            if year:
                return str(year)
    return ""


def _author_list(item):
    authors = []
    for author in item.get("author", []):
        given = _safe_text(author.get("given"))
        family = _safe_text(author.get("family"))
        name = " ".join(part for part in (given, family) if part)
        if name:
            authors.append(name)

    if not authors:
        return ""
    if len(authors) > 8:
        return ", ".join(authors[:8]) + ", et al."
    return ", ".join(authors)


def _venue(item):
    container = item.get("container-title") or []
    if container and isinstance(container, list) and container:
        return _safe_text(container[0])
    return ""


def _title(item):
    titles = item.get("title") or []
    if titles and isinstance(titles, list) and titles:
        return _safe_text(titles[0])
    return ""


def _link(item):
    doi = _safe_text(item.get("DOI"))
    if doi:
        return f"https://doi.org/{doi}"

    url = _safe_text(item.get("URL"))
    if url:
        return url

    return "#"


def build_publications():
    params = {
        "filter": f"orcid:{ORCID}",
        "rows": MAX_ROWS,
        "sort": "published",
        "order": "desc",
        "mailto": EMAIL,
    }

    response = requests.get(API_URL, params=params, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    items = response.json().get("message", {}).get("items", [])

    publications = []
    for item in items:
        title = _title(item)
        if not title:
            continue

        authors = _author_list(item)
        year = _pick_year(item)
        venue = _venue(item)

        description_parts = [part for part in (authors, year, venue) if part]
        description = " — ".join(description_parts)

        publications.append(
            {
                "name": title,
                "link": _link(item),
                "description": description,
            }
        )

    return publications


def main():
    repo_root = Path(__file__).resolve().parents[1]
    output_path = repo_root / "publications.json"

    try:
        publications = build_publications()
    except Exception:
        publications = []

    if not publications:
        publications = [PLACEHOLDER_ITEM]

    output_path.write_text(
        json.dumps(publications, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(publications)} items to {output_path}")


if __name__ == "__main__":
    main()
