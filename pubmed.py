"""
fetch_source() の実装例: PubMed（脳科学）
monad.py の fetch_source() をこれで差し替える
"""

import random
import requests
from xml.etree import ElementTree

PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

QUERIES = [
    "neural plasticity",
    "consciousness neuroscience",
    "predictive coding brain",
    "default mode network",
    "memory consolidation sleep",
]

def fetch_source() -> dict | None:
    query = random.choice(QUERIES)

    # 論文ID一覧を取得
    r = requests.get(PUBMED_SEARCH_URL, params={
        "db": "pubmed", "term": query, "retmax": 20,
        "sort": "relevance", "retmode": "json",
    }, timeout=10)
    ids = r.json()["esearchresult"]["idlist"]
    if not ids:
        return None

    pmid = random.choice(ids)

    # 論文本文を取得
    r = requests.get(PUBMED_FETCH_URL, params={
        "db": "pubmed", "id": pmid,
        "rettype": "abstract", "retmode": "xml",
    }, timeout=10)

    root = ElementTree.fromstring(r.text)
    title    = root.findtext(".//ArticleTitle") or ""
    abstract = root.findtext(".//AbstractText") or ""

    if not abstract:
        return None

    return {
        "summary": f"{title}",
        "raw": f"Title: {title}\n\nAbstract: {abstract}",
    }
