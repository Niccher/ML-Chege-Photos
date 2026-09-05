from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, Header, HTTPException, Query
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


@router.get("/similar/{photo_id}")
def similar_photos_endpoint(
    photo_id: int,
    limit: int = Query(20, ge=1, le=100),
    user_id: int | None = Query(None),
    x_webapp_url: str | None = Header(None, alias="X-Webapp-Url"),
):
    """Find visually and semantically similar photos using CLIP embeddings."""
    try:
        qdrant = get_qdrant()
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        # 1. Attempt to fetch pre-computed CLIP vector from Qdrant
        photo_filter = Filter(
            must=[FieldCondition(key="photo_id", match=MatchValue(value=photo_id))]
        )
        scroll_res = qdrant.scroll(
            collection_name=settings.qdrant_photo_collection,
            scroll_filter=photo_filter,
            limit=1,
            with_vectors=True,
        )

        query_vec = None
        points = scroll_res[0] if scroll_res and len(scroll_res) > 0 else []
        if points and points[0].vector:
            query_vec = points[0].vector

        # 2. If vector is not yet in Qdrant, compute on the fly
        if query_vec is None:
            from app.database import get_db
            from sqlalchemy import text
            from pathlib import Path
            import uuid
            from qdrant_client.models import PointStruct

            db = next(get_db())
            photo_row = db.execute(
                text(f"SELECT id, path, user_id FROM `{settings.effective_db_name}`.tbl_photos WHERE id = :pid"),
                {"pid": photo_id}
            ).fetchone()
            db.close()

            if not photo_row:
                raise HTTPException(404, f"Photo {photo_id} not found")

            rel = photo_row.path.strip().lstrip("/").removeprefix("uploads/").lstrip("/")
            photo_path = Path(settings.uploads_dir) / rel

            active_webapp = (
                x_webapp_url.strip().rstrip("/") if x_webapp_url else None
            ) or settings.effective_webapp_url
            if active_webapp and not active_webapp.startswith(("http://", "https://")):
                active_webapp = "https://" + active_webapp

            # Download from WebApp if missing or empty on disk
            if (not photo_path.exists() or photo_path.stat().st_size == 0) and active_webapp:
                import urllib.request

                candidate_urls = [
                    f"{active_webapp}/uploads/{rel}",
                ]
                if "railway" in (active_webapp or "").lower():
                    candidate_urls.insert(0, f"http://chege-photos-webapp.railway.internal/uploads/{rel}")

                photo_path.parent.mkdir(parents=True, exist_ok=True)
                for dl_url in candidate_urls:
                    try:
                        req = urllib.request.Request(
                            dl_url,
                            headers={"User-Agent": "Mozilla/5.0 (compatible; ChegePhotosML/1.0)"},
                        )
                        with urllib.request.urlopen(req, timeout=15) as resp:
                            if resp.status == 200:
                                content = resp.read()
                                if len(content) > 100:
                                    with open(photo_path, "wb") as f:
                                        f.write(content)
                                    break
                    except Exception:
                        pass

            if not photo_path.exists() or photo_path.stat().st_size == 0:
                raise HTTPException(404, f"Photo file not available on disk for embedding")

            query_vec = semantic_search.encode_image(str(photo_path))

            # Store in Qdrant for next time
            owner_id = photo_row.user_id if hasattr(photo_row, "user_id") else (photo_row[2] if len(photo_row) > 2 else None)
            qdrant.upsert(
                collection_name=settings.qdrant_photo_collection,
                points=[PointStruct(
                    id=str(uuid.uuid4()),
                    vector=query_vec,
                    payload={
                        "photo_id": photo_id,
                        "user_id": int(owner_id) if owner_id is not None else None,
                    }
                )]
            )

        # 3. Query nearest neighbors
        query_filter = None
        if user_id is not None:
            query_filter = Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
            )

        # Fetch extra results to allow excluding the query photo itself
        hits = qdrant.search(
            collection_name=settings.qdrant_photo_collection,
            query_vector=query_vec,
            limit=limit + 5,
            query_filter=query_filter,
            with_payload=True,
        )

        results = []
        for hit in hits:
            payload = hit.payload or {}
            hit_pid = payload.get("photo_id")
            if hit_pid is not None and int(hit_pid) != photo_id:
                results.append({
                    "score": round(float(hit.score), 4),
                    "photo_id": int(hit_pid),
                })
            if len(results) >= limit:
                break

        return {
            "photo_id": photo_id,
            "results": results,
            "count": len(results)
        }
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Visual similarity search failed for photo %d: %s", photo_id, exc)
        raise HTTPException(500, f"Similarity search failed: {exc}")

