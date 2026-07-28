#!/usr/bin/env python3
"""Offline and online checks for cited BibTeX records."""
from __future__ import annotations

import difflib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable

USER_AGENT = "sudis-aaai-submission-reviewer/0.3 (citation verification)"
PLACEHOLDERS = {"todo", "tbd", "unknown", "placeholder", "xxx", "citation needed"}


def normalize(value: str) -> str:
    value = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^]]*\])?", " ", value)
    value = value.replace("{", " ").replace("}", " ").replace("~", " ")
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def citation_keys(source: str) -> list[str]:
    keys: set[str] = set()
    pattern = r"\\cite[a-zA-Z]*\*?(?:\s*\[[^]]*\]){0,2}\s*\{([^}]+)\}"
    for group in re.findall(pattern, source):
        for key in group.split(","):
            key = key.strip()
            if key and key != "*":
                keys.add(key)
    return sorted(keys)


def _entry_blocks(text: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    cursor = 0
    start_pattern = re.compile(r"@([a-zA-Z]+)\s*([\{\(])")
    while match := start_pattern.search(text, cursor):
        entry_type = match.group(1).lower()
        opener = match.group(2)
        closer = "}" if opener == "{" else ")"
        depth = 1
        quoted = False
        escaped = False
        index = match.end()
        while index < len(text) and depth:
            char = text[index]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = not quoted
            elif not quoted and char == opener:
                depth += 1
            elif not quoted and char == closer:
                depth -= 1
            index += 1
        if depth:
            cursor = match.end()
            continue
        blocks.append((entry_type, text[match.end():index - 1]))
        cursor = index
    return blocks


def _split_top_level(text: str, delimiter: str = ",") -> list[str]:
    parts: list[str] = []
    start = 0
    brace_depth = 0
    quoted = False
    escaped = False
    for index, char in enumerate(text):
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            quoted = not quoted
        elif not quoted and char == "{":
            brace_depth += 1
        elif not quoted and char == "}":
            brace_depth = max(0, brace_depth - 1)
        elif char == delimiter and not quoted and brace_depth == 0:
            parts.append(text[start:index])
            start = index + 1
    parts.append(text[start:])
    return parts


def _clean_value(value: str) -> str:
    value = value.strip().rstrip(",").strip()
    while len(value) >= 2 and ((value[0] == "{" and value[-1] == "}") or (value[0] == '"' and value[-1] == '"')):
        value = value[1:-1].strip()
    return value


def parse_bibtex(paths: list[Path]) -> tuple[dict[str, dict], list[str]]:
    entries: dict[str, dict] = {}
    duplicate_keys: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for entry_type, block in _entry_blocks(text):
            if entry_type in {"comment", "preamble", "string"}:
                continue
            parts = _split_top_level(block)
            key = parts[0].strip() if parts else ""
            if not key:
                continue
            fields: dict[str, str] = {}
            for part in parts[1:]:
                if "=" not in part:
                    continue
                name, value = part.split("=", 1)
                fields[name.strip().lower()] = _clean_value(value)
            record = {"key": key, "entry_type": entry_type, "source": str(path), **fields}
            if key in entries:
                duplicate_keys.append(key)
            else:
                entries[key] = record
    return entries, sorted(set(duplicate_keys))


def _doi(entry: dict) -> str | None:
    raw = entry.get("doi", "")
    if not raw:
        match = re.search(r"(?:doi\.org/|doi:)\s*(10\.\d{4,9}/[^\s}]+)", entry.get("url", ""), re.I)
        raw = match.group(1) if match else ""
    raw = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", raw.strip(), flags=re.I)
    return raw.rstrip(".,;)") or None


def _arxiv(entry: dict) -> str | None:
    candidates = [entry.get("eprint", ""), entry.get("url", ""), entry.get("note", "")]
    for raw in candidates:
        match = re.search(r"(?:arxiv[:./\s]|abs/)?(\d{4}\.\d{4,5}(?:v\d+)?)", raw, re.I)
        if match:
            return match.group(1)
    return None


def _record(key: str, status: str, check: str, evidence: str, gate_effect: str = "NONE") -> dict:
    return {"key": key, "status": status, "check": check, "evidence": evidence, "gate_effect": gate_effect}


def offline_audit(source: str, bib_paths: list[Path]) -> dict:
    cited = citation_keys(source)
    entries, duplicate_keys = parse_bibtex(bib_paths)
    items: list[dict] = []
    for key in cited:
        if key not in entries:
            items.append(_record(key, "MISMATCH", "missing-key", "Citation key is used in active source but absent from active BibTeX files.", "FAIL"))
    for key in duplicate_keys:
        effect = "BLOCK" if key in cited else "NONE"
        status = "UNVERIFIED" if key in cited else "MISMATCH"
        items.append(_record(key, status, "duplicate-key", "BibTeX key is defined more than once.", effect))

    doi_owners: dict[str, list[str]] = defaultdict(list)
    title_owners: dict[str, list[str]] = defaultdict(list)
    current_year = datetime.now().year
    for key, entry in entries.items():
        if key not in cited:
            continue
        title = entry.get("title", "")
        author = entry.get("author", "")
        year = entry.get("year", "")
        normalized_title = normalize(title)
        doi = _doi(entry)
        if doi:
            doi_owners[doi.lower()].append(key)
            if not re.fullmatch(r"10\.\d{4,9}/\S+", doi, re.I):
                items.append(_record(key, "UNVERIFIED", "malformed-doi", f"DOI has an invalid shape: {doi}", "BLOCK"))
        if normalized_title:
            title_owners[normalized_title].append(key)
        if not title or not author:
            items.append(_record(key, "UNVERIFIED", "missing-metadata", "Cited record lacks a title or author.", "BLOCK"))
        if any(token in normalize(title) for token in PLACEHOLDERS):
            items.append(_record(key, "UNVERIFIED", "placeholder-metadata", f"Title appears to contain placeholder text: {title}", "BLOCK"))
        if year and (not year.isdigit() or not 1800 <= int(year) <= current_year + 1):
            items.append(_record(key, "UNVERIFIED", "invalid-year", f"Year is outside the expected range: {year}", "BLOCK"))
        arxiv = _arxiv(entry)
        if entry.get("archiveprefix", "").lower() == "arxiv" and not arxiv:
            items.append(_record(key, "UNVERIFIED", "malformed-arxiv", "Record declares arXiv but has no valid arXiv identifier.", "BLOCK"))

    for doi, keys in doi_owners.items():
        if len(keys) > 1:
            for key in keys:
                items.append(_record(key, "UNVERIFIED", "duplicate-doi", f"DOI {doi} is shared by cited keys: {', '.join(keys)}.", "BLOCK"))
    for title, keys in title_owners.items():
        if title and len(keys) > 1:
            for key in keys:
                items.append(_record(key, "UNVERIFIED", "duplicate-title", f"Normalized title is shared by cited keys: {', '.join(keys)}.", "BLOCK"))

    return {
        "mode": "structural",
        "cited_keys": cited,
        "entries": entries,
        "items": items,
        "summary": _summary(items, cited),
    }


def _summary(items: list[dict], cited: list[str]) -> dict:
    return {
        "cited": len(cited),
        "verified": sum(item["status"] == "VERIFIED" for item in items),
        "mismatch": sum(item["status"] == "MISMATCH" for item in items),
        "unverified": sum(item["status"] == "UNVERIFIED" for item in items),
    }


def _request(url: str, accept: str, timeout: float = 8.0) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(0.5 * (2 ** attempt))
    raise RuntimeError("unreachable")


def _first_author(entry: dict) -> str:
    author = entry.get("author", "").split(" and ")[0]
    if "," in author:
        author = author.split(",", 1)[0]
    else:
        author = author.split()[-1] if author.split() else ""
    return normalize(author)


def _metadata_match(entry: dict, remote_title: str, remote_year: str, remote_author: str) -> tuple[str, str]:
    local_title = normalize(entry.get("title", ""))
    title_score = difflib.SequenceMatcher(None, local_title, normalize(remote_title)).ratio()
    local_year = re.sub(r"\D", "", entry.get("year", ""))
    year_ok = not local_year or not remote_year or abs(int(local_year) - int(remote_year)) <= 1
    local_author = _first_author(entry)
    author_ok = not local_author or not remote_author or local_author == normalize(remote_author)
    if title_score >= 0.86 and year_ok and author_ok:
        status = "VERIFIED"
    elif title_score < 0.55 or (title_score < 0.75 and not year_ok and not author_ok):
        status = "MISMATCH"
    else:
        status = "UNVERIFIED"
    return status, f"title_similarity={title_score:.2f}, year_match={year_ok}, first_author_match={author_ok}"


def _crossref(entry: dict, request_fn: Callable[[str, str], bytes]) -> tuple[str, str]:
    doi = _doi(entry)
    if doi:
        url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    else:
        title = entry.get("title", "")
        url = "https://api.crossref.org/works?" + urllib.parse.urlencode({"query.title": title, "rows": 3, "select": "title,author,issued,DOI"})
    payload = json.loads(request_fn(url, "application/json"))
    message = payload.get("message", {})
    candidates = [message] if doi else message.get("items", [])
    if not candidates:
        return "UNVERIFIED", "Crossref returned no candidate."
    best: tuple[float, dict] | None = None
    local_title = normalize(entry.get("title", ""))
    for candidate in candidates:
        title = (candidate.get("title") or [""])[0]
        score = difflib.SequenceMatcher(None, local_title, normalize(title)).ratio()
        if best is None or score > best[0]:
            best = (score, candidate)
    assert best is not None
    candidate = best[1]
    remote_title = (candidate.get("title") or [""])[0]
    date_parts = (candidate.get("issued") or {}).get("date-parts") or []
    remote_year = str(date_parts[0][0]) if date_parts and date_parts[0] else ""
    authors = candidate.get("author") or []
    remote_author = authors[0].get("family", "") if authors else ""
    match_status, detail = _metadata_match(entry, remote_title, remote_year, remote_author)
    if match_status == "VERIFIED":
        return "VERIFIED", f"Crossref metadata matched. {detail}"
    if doi and match_status == "MISMATCH":
        return "MISMATCH", f"DOI resolved but metadata did not match. {detail}; remote_title={remote_title}"
    return "UNVERIFIED", f"Crossref metadata was inconclusive. {detail}"


def _arxiv_lookup(entry: dict, request_fn: Callable[[str, str], bytes]) -> tuple[str, str]:
    identifier = _arxiv(entry)
    if not identifier:
        return "UNVERIFIED", "No arXiv identifier."
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"id_list": identifier})
    root = ET.fromstring(request_fn(url, "application/atom+xml"))
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    records = root.findall("atom:entry", namespace)
    if not records:
        return "UNVERIFIED", f"arXiv returned no record for {identifier}."
    record = records[0]
    remote_title = record.findtext("atom:title", default="", namespaces=namespace)
    published = record.findtext("atom:published", default="", namespaces=namespace)
    remote_year = published[:4] if published else ""
    author_node = record.find("atom:author/atom:name", namespace)
    remote_author = (author_node.text or "").split()[-1] if author_node is not None else ""
    match_status, detail = _metadata_match(entry, remote_title, remote_year, remote_author)
    if match_status == "VERIFIED":
        return "VERIFIED", f"arXiv metadata matched. {detail}"
    if match_status == "MISMATCH":
        return "MISMATCH", f"arXiv identifier resolved but metadata did not match. {detail}; remote_title={normalize(remote_title)}"
    return "UNVERIFIED", f"arXiv metadata was inconclusive. {detail}"


def full_audit(
    structural: dict,
    request_fn: Callable[[str, str], bytes] = _request,
    delay_seconds: float = 0.1,
) -> dict:
    items = list(structural["items"])
    structurally_failed = {item["key"] for item in items if item["gate_effect"] == "FAIL"}
    lookup_cache: dict[str, tuple[str, str]] = {}
    for key in structural["cited_keys"]:
        if key in structurally_failed:
            continue
        entry = structural["entries"].get(key)
        if not entry:
            continue
        identity = _doi(entry) or _arxiv(entry) or normalize(entry.get("title", ""))
        if identity in lookup_cache:
            status, evidence = lookup_cache[identity]
        else:
            try:
                if _arxiv(entry) and not _doi(entry):
                    status, evidence = _arxiv_lookup(entry, request_fn)
                else:
                    status, evidence = _crossref(entry, request_fn)
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, ET.ParseError, ValueError) as error:
                status, evidence = "UNVERIFIED", f"Online lookup could not complete: {type(error).__name__}: {error}"
            lookup_cache[identity] = (status, evidence)
            if delay_seconds:
                time.sleep(delay_seconds)
        effect = "FAIL" if status == "MISMATCH" else "BLOCK" if status == "UNVERIFIED" else "NONE"
        items.append(_record(key, status, "online-metadata", evidence, effect))
    return {
        "mode": "full",
        "cited_keys": structural["cited_keys"],
        "items": items,
        "summary": _summary(items, structural["cited_keys"]),
    }
