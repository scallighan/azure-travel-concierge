"""
Azure AI Search retrieval tool over the Visa documentation knowledge base.
Uses semantic (hybrid) search with Entra ID auth. Exposed to the supervisor as
a function tool so it can answer visa / payment questions with citations.
"""

import logging
from typing import Annotated

from azure.identity.aio import DefaultAzureCredential
from azure.search.documents.aio import SearchClient
from pydantic import Field

from config import config

logger = logging.getLogger("agent-search")


async def search_visa_documentation(
    query: Annotated[str, Field(description="Natural-language question about visa requirements, payments or travel documentation.")],
) -> str:
    """
    Search the Visa documentation knowledge base (Azure AI Search) and return the
    most relevant passages with their source titles. Use for questions about visa
    requirements, entry rules, and payment/tokenization documentation.
    """
    if not config.SEARCH_ENDPOINT:
        return "Knowledge base is not configured."

    credential = DefaultAzureCredential()
    try:
        client = SearchClient(
            endpoint=config.SEARCH_ENDPOINT,
            index_name=config.SEARCH_INDEX_NAME,
            credential=credential,
        )
        async with client:
            results = await client.search(
                search_text=query,
                query_type="semantic",
                semantic_configuration_name="default",
                top=4,
            )
            chunks = []
            async for r in results:
                title = r.get("title") or r.get("metadata_storage_name") or "document"
                content = (r.get("content") or "").strip().replace("\n", " ")
                if content:
                    chunks.append(f"[{title}] {content[:600]}")
        if not chunks:
            return f"No documentation found for: {query}"
        return "\n\n".join(chunks)
    except Exception as exc:  # pragma: no cover
        logger.warning("AI Search query failed: %s", exc)
        return f"Knowledge base lookup failed: {exc}"
    finally:
        await credential.close()
