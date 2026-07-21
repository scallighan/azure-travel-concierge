"""
Ingest the Visa documentation into Azure AI Search.

Creates (or updates) a semantic-search index named after ``SEARCH_INDEX_NAME``
and uploads chunked markdown from ./visa-documentation. Uses Entra ID auth — the
principal running this needs "Search Service Contributor" + "Search Index Data
Contributor" on the search service (granted by Terraform to the deploying user).

Usage:
    export SEARCH_ENDPOINT="https://<svc>.search.windows.net"
    export SEARCH_INDEX_NAME="visa-documentation"
    python ingest.py
"""

import glob
import hashlib
import os

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchableField,
    SearchIndex,
    SimpleField,
    SearchFieldDataType,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
)

ENDPOINT = os.environ["SEARCH_ENDPOINT"]
INDEX_NAME = os.getenv("SEARCH_INDEX_NAME", "visa-documentation")
DOCS_DIR = os.path.join(os.path.dirname(__file__), "visa-documentation")

credential = DefaultAzureCredential()


def build_index() -> None:
    client = SearchIndexClient(ENDPOINT, credential)
    index = SearchIndex(
        name=INDEX_NAME,
        fields=[
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SearchableField(name="title", type=SearchFieldDataType.String),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SimpleField(name="source", type=SearchFieldDataType.String, filterable=True),
        ],
        semantic_search=SemanticSearch(
            configurations=[
                SemanticConfiguration(
                    name="default",
                    prioritized_fields=SemanticPrioritizedFields(
                        title_field=SemanticField(field_name="title"),
                        content_fields=[SemanticField(field_name="content")],
                    ),
                )
            ]
        ),
    )
    client.create_or_update_index(index)
    print(f"Index '{INDEX_NAME}' created/updated.")


def chunk(text: str, size: int = 1200, overlap: int = 150) -> list[str]:
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunks.append(" ".join(words[i : i + size]))
        i += size - overlap
    return chunks or [text]


def upload_docs() -> None:
    client = SearchClient(ENDPOINT, INDEX_NAME, credential)
    docs = []
    for path in glob.glob(os.path.join(DOCS_DIR, "*.md")):
        name = os.path.basename(path)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        title = text.splitlines()[0].lstrip("# ").strip() if text else name
        for idx, part in enumerate(chunk(text)):
            doc_id = hashlib.sha1(f"{name}:{idx}".encode()).hexdigest()
            docs.append({"id": doc_id, "title": title, "content": part, "source": name})
    if docs:
        client.upload_documents(docs)
    print(f"Uploaded {len(docs)} document chunk(s).")


if __name__ == "__main__":
    build_index()
    upload_docs()
