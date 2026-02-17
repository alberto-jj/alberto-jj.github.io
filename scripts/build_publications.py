import json
import html
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

# -------------------------
# Config
# -------------------------
ORCID = "0000-0001-5374-6410"
EMAIL = "alberto.jaramilloj@udea.edu.co"

ORCID_API_BASE = "https://pub.orcid.org/v3.0"
CROSSREF_API_BASE = "https://api.crossref.org/works"

TIMEOUT_SECONDS = 20
USER_AGENT = f"alberto-jj.github.io publications bot (mailto:{EMAIL})"

PLACEHOLDER_ITEM = {
    "name": (
        "No publications found via ORCID (yet). Tip: check that your works are Public on ORCID, "
        "or use ORCID Member API to read limited items."
    ),
    "link": "#",
    "description": "",
}


# -------------------------
# Helpers
# -------------------------
def _safe_text(value) -> str:
    """Strip + HTML-unescape any string-ish value."""
    return html.unescape((value or "").strip())


def _http_get(url: str, *, params: Optional[dict] = None, headers: Optional[dict] = None) -> dict:
    h = {"User-Agent": USER_AGENT, **(headers or {})}
    r = requests.get(url, params=params, headers=h, timeout=TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.json()


def _normalize_doi(doi: str) -> str:
    doi = _safe_text(doi)
    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
    doi = doi.replace("https://dx.doi.org/", "").replace("http://dx.doi.org/", "")
    return doi.strip().lower()


def _first_nonempty(*vals: str) -> str:
    for v in vals:
        v = _safe_text(v)
        if v:
            return v
    return ""


def _join_nonempty(parts: List[str], sep: str = " — ") -> str:
    return sep.join([p for p in parts if p])


def _is_real_doi_link(link: str) -> bool:
    link = (link or "").strip().lower()
    return link.startswith("https://doi.org/") and len(link) > len("https://doi.org/")


def _title_key(title: str) -> str:
    t = _safe_text(title).lower()
    t = re.sub(r"\s+", " ", t).strip()
    return t


# -------------------------
# ORCID parsing
# -------------------------
def _orcid_headers() -> dict:
    return {"Accept": "application/json"}


def _extract_doi_from_external_ids(external_ids_container: dict) -> str:
    ext_ids = (external_ids_container or {}).get("external-id") or []
    for ex in ext_ids:
        if _safe_text(ex.get("external-id-type")).lower() == "doi":
            val = _safe_text(ex.get("external-id-value"))
            if val:
                return _normalize_doi(val)
    return ""


def _pick_year_from_orcid_work(work: dict) -> str:
    pub = work.get("publication-date") or {}
    year = (pub.get("year") or {}).get("value")
    return _safe_text(year)


def _extract_title_from_orcid_work(work: dict) -> str:
    title = (
        (((work.get("title") or {}).get("title") or {}).get("value"))
        if isinstance(work.get("title"), dict)
        else ""
    )
    return _safe_text(title)


def _extract_doi_from_orcid_work(work: dict) -> str:
    return _extract_doi_from_external_ids(work.get("external-ids") or {})


def _orcid_get_one_putcode_per_group() -> List[int]:
    """
    ORCID /works returns 'groups'. Each group may contain multiple 'work-summary' entries
    for the same work (different sources). The ORCID UI typically shows one per group.

    Select ONE representative put-code per group:
      - prefer a summary that has a DOI (better Crossref enrichment)
      - otherwise fall back to the first summary in the group
    """
    url = f"{ORCID_API_BASE}/{ORCID}/works"
    data = _http_get(url, headers=_orcid_headers())

    putcodes: List[int] = []
    groups = data.get("group") or []

    for g in groups:
        summaries = g.get("work-summary") or []
        if not summaries:
            continue

        def _summary_has_doi(summary: dict) -> bool:
            doi = _extract_doi_from_external_ids(summary.get("external-ids") or {})
            return bool(doi)

        chosen = next((s for s in summaries if _summary_has_doi(s)), summaries[0])
        pc = chosen.get("put-code")
        if isinstance(pc, int):
            putcodes.append(pc)

    return sorted(set(putcodes))


def _orcid_get_work(put_code: int) -> dict:
    url = f"{ORCID_API_BASE}/{ORCID}/work/{put_code}"
    return _http_get(url, headers=_orcid_headers())


# -------------------------
# Crossref enrichment
# -------------------------
def _pick_year_from_crossref(item: dict) -> str:
    for key in ("published-print", "published-online", "created", "issued"):
        date_parts = item.get(key, {}).get("date-parts")
        if date_parts and isinstance(date_parts, list) and date_parts[0]:
            year = date_parts[0][0]
            if year:
                return str(year)
    return ""


def _title_from_crossref(item: dict) -> str:
    titles = item.get("title") or []
    if titles and isinstance(titles, list) and titles:
        return _safe_text(titles[0])
    return ""


def _venue_from_crossref(item: dict) -> str:
    container = item.get("container-title") or []
    if container and isinstance(container, list) and container:
        return _safe_text(container[0])
    return ""


def _author_list_from_crossref(item: dict) -> str:
    authors: List[str] = []
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


def _crossref_lookup_by_doi(doi: str) -> Optional[dict]:
    doi = _normalize_doi(doi)
    if not doi:
        return None
    try:
        data = _http_get(
            f"{CROSSREF_API_BASE}/{doi}",
            params={"mailto": EMAIL},
        )
        return (data or {}).get("message") or None
    except Exception:
        return None


# -------------------------
# Build publications
# -------------------------
def build_publications() -> List[Dict[str, str]]:
    putcodes = _orcid_get_one_putcode_per_group()
    publications: List[Dict[str, str]] = []

    for pc in putcodes:
        try:
            work = _orcid_get_work(pc)
        except Exception:
            continue

        doi = _extract_doi_from_orcid_work(work)
        if not doi:
            # MUST have DOI
            continue

        # Enrich with Crossref (required for journal name)
        cr = _crossref_lookup_by_doi(doi)
        if not cr:
            continue

        journal = _venue_from_crossref(cr)
        if not journal:
            # MUST have journal name
            continue

        title = _first_nonempty(_title_from_crossref(cr), _extract_title_from_orcid_work(work))
        if not title:
            continue

        authors = _author_list_from_crossref(cr)
        year = _first_nonempty(_pick_year_from_crossref(cr), _pick_year_from_orcid_work(work))

        link = f"https://doi.org/{_normalize_doi(doi)}"  # canonical

        description_parts: List[str] = []
        if authors:
            description_parts.append(authors)
        if year:
            description_parts.append(year)
        description_parts.append(journal)  # journal is required so always include

        publications.append(
            {
                "name": title,
                "link": link,
                "description": _join_nonempty(description_parts),
            }
        )

    # Sort: prefer year desc if available (keeps "best" candidate first for each title)
    def _sort_key(pub: Dict[str, str]) -> Tuple[int, str]:
        m = re.search(r"\b(19\d{2}|20\d{2})\b", pub.get("description", ""))
        year_int = int(m.group(1)) if m else 0
        return (year_int, pub.get("name", "").lower())

    publications.sort(key=_sort_key, reverse=True)

    # De-dup by title: if repeated, keep first (all have DOI+journal already)
    by_title: Dict[str, Dict[str, str]] = {}
    for pub in publications:
        tkey = _title_key(pub.get("name", ""))
        if not tkey:
            continue
        if tkey not in by_title:
            by_title[tkey] = pub

    return list(by_title.values())


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
