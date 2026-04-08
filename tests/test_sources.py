# Feature: monad-template, Property 3: fetch_source()の戻り値型契約
"""
Property 3 tests: fetch_source() return value type contract.

For any fetch_source() call (with mocked HTTP responses), the return value is either:
- None, OR
- A dict with keys "summary" and "raw", both with string values

Validates: Requirements 2.2
"""

from __future__ import annotations

import sys
import os
import json
from unittest.mock import patch, MagicMock
from xml.etree import ElementTree

import pytest
import respx
import httpx
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Ensure sources/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sources import arxiv, pubmed, rss


# ---------------------------------------------------------------------------
# Helper: assert the return value satisfies the type contract
# ---------------------------------------------------------------------------

def _assert_type_contract(result):
    assert result is None or (
        isinstance(result, dict)
        and "summary" in result
        and "raw" in result
        and isinstance(result["summary"], str)
        and isinstance(result["raw"], str)
    ), f"Type contract violated: {result!r}"


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=" -_.,:()/"),
    min_size=1,
    max_size=200,
)

_http_error_status = st.integers(min_value=400, max_value=599)


# ===========================================================================
# Property 3 – sources/arxiv.py
# ===========================================================================

def _make_arxiv_atom(entries: list[tuple[str, str]]) -> str:
    """Build a minimal Atom XML response with the given (title, summary) pairs."""
    NS = "http://www.w3.org/2005/Atom"
    root = ElementTree.Element(f"{{{NS}}}feed")
    for title, summary in entries:
        entry = ElementTree.SubElement(root, f"{{{NS}}}entry")
        t = ElementTree.SubElement(entry, f"{{{NS}}}title")
        t.text = title
        s = ElementTree.SubElement(entry, f"{{{NS}}}summary")
        s.text = summary
    return ElementTree.tostring(root, encoding="unicode")


@settings(max_examples=100)
@given(title=_safe_text, abstract=_safe_text)
def test_arxiv_successful_response_returns_dict(title: str, abstract: str):
    """Successful ArXiv response with valid title+abstract → returns dict."""
    assume(title.strip() and abstract.strip())
    atom_xml = _make_arxiv_atom([(title, abstract)])

    with respx.mock:
        respx.get(arxiv.ARXIV_API_URL).mock(
            return_value=httpx.Response(200, text=atom_xml)
        )
        result = arxiv.fetch_source()

    _assert_type_contract(result)
    assert result is not None
    assert isinstance(result["summary"], str)
    assert isinstance(result["raw"], str)


@settings(max_examples=100)
@given(status_code=_http_error_status)
def test_arxiv_http_error_returns_none(status_code: int):
    """HTTP error responses (4xx, 5xx) from ArXiv → returns None."""
    with respx.mock:
        respx.get(arxiv.ARXIV_API_URL).mock(
            return_value=httpx.Response(status_code, text="error")
        )
        result = arxiv.fetch_source()

    _assert_type_contract(result)
    assert result is None


@settings(max_examples=100)
@given(dummy=st.just(None))
def test_arxiv_empty_entries_returns_none(dummy):
    """ArXiv response with no entries → returns None."""
    atom_xml = _make_arxiv_atom([])

    with respx.mock:
        respx.get(arxiv.ARXIV_API_URL).mock(
            return_value=httpx.Response(200, text=atom_xml)
        )
        result = arxiv.fetch_source()

    _assert_type_contract(result)
    assert result is None


@settings(max_examples=100)
@given(dummy=st.just(None))
def test_arxiv_network_error_returns_none(dummy):
    """Network error for ArXiv → returns None."""
    with respx.mock:
        respx.get(arxiv.ARXIV_API_URL).mock(side_effect=httpx.ConnectError("timeout"))
        result = arxiv.fetch_source()

    _assert_type_contract(result)
    assert result is None


# ===========================================================================
# Property 3 – sources/pubmed.py
# ===========================================================================

def _make_pubmed_search_json(ids: list[str]) -> str:
    return json.dumps({"esearchresult": {"idlist": ids}})


def _make_pubmed_fetch_xml(title: str, abstract: str) -> str:
    root = ElementTree.Element("PubmedArticleSet")
    article = ElementTree.SubElement(root, "PubmedArticle")
    medline = ElementTree.SubElement(article, "MedlineCitation")
    art = ElementTree.SubElement(medline, "Article")
    t = ElementTree.SubElement(art, "ArticleTitle")
    t.text = title
    ab = ElementTree.SubElement(art, "Abstract")
    abt = ElementTree.SubElement(ab, "AbstractText")
    abt.text = abstract
    return ElementTree.tostring(root, encoding="unicode")


@settings(max_examples=100)
@given(title=_safe_text, abstract=_safe_text)
def test_pubmed_successful_response_returns_dict(title: str, abstract: str):
    """Successful PubMed response with valid title+abstract → returns dict."""
    assume(abstract.strip())
    search_json = _make_pubmed_search_json(["12345678"])
    fetch_xml = _make_pubmed_fetch_xml(title, abstract)

    with respx.mock:
        respx.get(pubmed.PUBMED_SEARCH_URL).mock(
            return_value=httpx.Response(200, text=search_json)
        )
        respx.get(pubmed.PUBMED_FETCH_URL).mock(
            return_value=httpx.Response(200, text=fetch_xml)
        )
        result = pubmed.fetch_source()

    _assert_type_contract(result)
    assert result is not None


@settings(max_examples=100)
@given(status_code=_http_error_status)
def test_pubmed_search_http_error_returns_none(status_code: int):
    """HTTP error on PubMed search request → returns None."""
    with respx.mock:
        respx.get(pubmed.PUBMED_SEARCH_URL).mock(
            return_value=httpx.Response(status_code, text="error")
        )
        result = pubmed.fetch_source()

    _assert_type_contract(result)
    assert result is None


@settings(max_examples=100)
@given(status_code=_http_error_status)
def test_pubmed_fetch_http_error_returns_none(status_code: int):
    """HTTP error on PubMed fetch request → returns None."""
    search_json = _make_pubmed_search_json(["12345678"])

    with respx.mock:
        respx.get(pubmed.PUBMED_SEARCH_URL).mock(
            return_value=httpx.Response(200, text=search_json)
        )
        respx.get(pubmed.PUBMED_FETCH_URL).mock(
            return_value=httpx.Response(status_code, text="error")
        )
        result = pubmed.fetch_source()

    _assert_type_contract(result)
    assert result is None


@settings(max_examples=100)
@given(dummy=st.just(None))
def test_pubmed_empty_id_list_returns_none(dummy):
    """PubMed search returns empty id list → returns None."""
    search_json = _make_pubmed_search_json([])

    with respx.mock:
        respx.get(pubmed.PUBMED_SEARCH_URL).mock(
            return_value=httpx.Response(200, text=search_json)
        )
        result = pubmed.fetch_source()

    _assert_type_contract(result)
    assert result is None


@settings(max_examples=100)
@given(dummy=st.just(None))
def test_pubmed_network_error_returns_none(dummy):
    """Network error for PubMed → returns None."""
    with respx.mock:
        respx.get(pubmed.PUBMED_SEARCH_URL).mock(
            side_effect=httpx.ConnectError("timeout")
        )
        result = pubmed.fetch_source()

    _assert_type_contract(result)
    assert result is None


# ===========================================================================
# Property 3 – sources/rss.py
# ===========================================================================

def _make_feed_mock(entries: list[dict]):
    """Build a mock feedparser result with the given entries."""
    mock_feed = MagicMock()
    mock_feed.entries = entries
    return mock_feed


@settings(max_examples=100)
@given(title=_safe_text, description=_safe_text)
def test_rss_successful_feed_returns_dict(title: str, description: str):
    """RSS feed with valid title+description → returns dict."""
    assume(title.strip())
    entry = {"title": title, "summary": description}
    mock_feed = _make_feed_mock([entry])

    with patch("sources.rss.feedparser.parse", return_value=mock_feed):
        result = rss.fetch_source()

    _assert_type_contract(result)
    assert result is not None


@settings(max_examples=100)
@given(dummy=st.just(None))
def test_rss_empty_entries_returns_none(dummy):
    """RSS feed with no entries → returns None."""
    mock_feed = _make_feed_mock([])

    with patch("sources.rss.feedparser.parse", return_value=mock_feed):
        result = rss.fetch_source()

    _assert_type_contract(result)
    assert result is None


@settings(max_examples=100)
@given(description=_safe_text)
def test_rss_missing_title_returns_none(description: str):
    """RSS entry with empty/missing title → returns None."""
    entry = {"title": "", "summary": description}
    mock_feed = _make_feed_mock([entry])

    with patch("sources.rss.feedparser.parse", return_value=mock_feed):
        result = rss.fetch_source()

    _assert_type_contract(result)
    assert result is None


@settings(max_examples=100)
@given(dummy=st.just(None))
def test_rss_parse_exception_returns_none(dummy):
    """feedparser.parse raising an exception → returns None."""
    with patch("sources.rss.feedparser.parse", side_effect=Exception("network error")):
        result = rss.fetch_source()

    _assert_type_contract(result)
    assert result is None


@settings(max_examples=100)
@given(title=_safe_text)
def test_rss_entry_with_no_description_returns_dict(title: str):
    """RSS entry with title but no description → still returns dict (description defaults to empty string)."""
    assume(title.strip())
    entry = {"title": title}  # no summary/description key
    mock_feed = _make_feed_mock([entry])

    with patch("sources.rss.feedparser.parse", return_value=mock_feed):
        result = rss.fetch_source()

    _assert_type_contract(result)
    assert result is not None


# ===========================================================================
# Unit tests: monad.py main loop – fetch_source() returns None
# Validates: Requirements 2.5
# ===========================================================================

import monad as monad_module


def test_fetch_source_none_skips_telos_search_and_write():
    """When fetch_source() returns None, telos.search and telos.write are NOT called."""

    class _BreakLoop(BaseException):
        pass

    def fake_sleep(_):
        raise _BreakLoop  # BaseException bypasses the broad except Exception in run()

    with (
        patch.object(monad_module, "fetch_source", return_value=None),
        patch.object(monad_module.telos, "search") as mock_search,
        patch.object(monad_module.telos, "write") as mock_write,
        patch("monad.time.sleep", side_effect=fake_sleep),
    ):
        try:
            monad_module.run()
        except _BreakLoop:
            pass

    mock_search.assert_not_called()
    mock_write.assert_not_called()


def test_fetch_source_none_calls_sleep():
    """When fetch_source() returns None, time.sleep is still called (loop continues)."""
    call_count = {"sleep": 0}

    class _BreakLoop(BaseException):
        pass

    def fake_sleep(_):
        call_count["sleep"] += 1
        raise _BreakLoop  # BaseException bypasses the broad except Exception in run()

    with (
        patch.object(monad_module, "fetch_source", return_value=None),
        patch.object(monad_module.telos, "search"),
        patch.object(monad_module.telos, "write"),
        patch("monad.time.sleep", side_effect=fake_sleep),
    ):
        try:
            monad_module.run()
        except _BreakLoop:
            pass

    assert call_count["sleep"] == 1
