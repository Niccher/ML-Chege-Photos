from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from qdrant_client import QdrantClient

from app.config import settings
from app.database import get_qdrant
from app.ml import semantic_search

log = logging.getLogger("ml_chege_photos.api_search")
router = APIRouter(prefix="/api/v1/search", tags=["search"])

@router.get("/semantic")
def semantic_search_endpoint(
    query: str = Query(..., description="Natural language query"),
    limit: int = Query(20, ge=1, le=100),
    user_id: int | None = Query(None),
):
    try:
        query_vec = semantic_search.encode_text(query)
        qdrant = get_qdrant()
        
        query_filter = None
        if user_id is not None:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(value=user_id)
                    )
                ]
            )

        hits = qdrant.search(
            collection_name=settings.qdrant_photo_collection,
            query_vector=query_vec,
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
        )
        results = []
        for hit in hits:
            payload = hit.payload or {}
            photo_id = payload.get("photo_id")
            if photo_id is not None:
                results.append({
                    "score": hit.score,
                    "photo_id": int(photo_id),
                })
        return {
            "query": query,
            "results": results
        }
    except Exception as exc:
        log.error("Semantic search failed: %s", exc)
        raise HTTPException(500, f"Semantic search failed: {exc}")
