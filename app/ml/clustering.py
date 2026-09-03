from __future__ import annotations

import uuid
import logging

import numpy as np
from sklearn.cluster import HDBSCAN
from sklearn.metrics import silhouette_score
from qdrant_client.models import PointStruct, VectorParams, Distance

from app.config import settings
from app.database import get_qdrant

log = logging.getLogger("ml_chege_photos.clustering")

CENTROID_COLLECTION_SUFFIX = "_centroids"


def centroid_collection() -> str:
    return settings.qdrant_collection + CENTROID_COLLECTION_SUFFIX


def ensure_collections():
    qdrant = get_qdrant()
    cols = {c.name for c in qdrant.get_collections().collections}
    main = settings.qdrant_collection
    if main not in cols:
        qdrant.create_collection(
            collection_name=main,
            vectors_config=VectorParams(size=512, distance=Distance.COSINE),
        )
    cent = centroid_collection()
    if cent not in cols:
        qdrant.create_collection(
            collection_name=cent,
            vectors_config=VectorParams(size=512, distance=Distance.COSINE),
        )


def scroll_all_vectors(qdrant, collection: str):
    offset: int | None = None
    vectors = []
    point_ids = []
    while True:
        points, next_offset = qdrant.scroll(
            collection_name=collection,
            limit=100,
            offset=offset,
            with_vectors=True,
            with_payload=False,
        )
        for p in points:
            vectors.append(p.vector)
            point_ids.append(p.id)
        if next_offset is None:
            break
        offset = next_offset
    return vectors, point_ids


def run_hdbscan(vectors: list, min_cluster_size: int | None = None, min_samples: int | None = None) -> dict:
    n = len(vectors)
    mcs = min_cluster_size if min_cluster_size is not None else settings.hdbscan_min_cluster_size
    ms = min_samples if min_samples is not None else settings.hdbscan_min_samples

    if n < mcs:
        return {
            "labels": [-1] * n,
            "n_clusters": 0,
            "noise": n,
        }

    X = np.array(vectors)
    clusterer = HDBSCAN(
        min_cluster_size=mcs,
        min_samples=ms,
        metric=settings.cluster_metric,
    )
    labels = clusterer.fit_predict(X)
    unique = set(labels) - {-1}

    return {
        "labels": labels.tolist(),
        "n_clusters": len(unique),
        "noise": int((labels == -1).sum()),
    }


def evaluate_clustering_quality(vectors: list, labels: list) -> dict:
    X = np.array(vectors)
    lbls = np.array(labels)
    n = len(X)
    if n == 0:
        return {
            "silhouette_score": 0.0,
            "n_clusters": 0,
            "noise": 0,
            "noise_ratio": 0.0,
            "total_points": 0,
        }

    non_noise = lbls != -1
    unique_clusters = set(lbls[non_noise])
    n_clusters = len(unique_clusters)
    noise_count = int((lbls == -1).sum())
    noise_ratio = round(float(noise_count / n), 3)

    score = 0.0
    if n_clusters >= 2 and int(non_noise.sum()) > n_clusters:
        try:
            score = round(float(silhouette_score(X[non_noise], lbls[non_noise], metric=settings.cluster_metric)), 3)
        except Exception as exc:
            log.warning("Silhouette score calculation error: %s", exc)
            score = 0.0

    return {
        "silhouette_score": score,
        "n_clusters": n_clusters,
        "noise": noise_count,
        "noise_ratio": noise_ratio,
        "total_points": n,
    }


def autotune_hdbscan(vectors: list, candidate_mcs: list[int] | None = None, candidate_ms: list[int] | None = None) -> dict:
    n = len(vectors)
    if n < 4:
        return {
            "status": "insufficient_data",
            "message": f"Only {n} face vector(s) found. Need at least 4 vectors for hyperparameter optimization.",
            "recommended_min_cluster_size": settings.hdbscan_min_cluster_size,
            "recommended_min_samples": settings.hdbscan_min_samples,
            "silhouette_score": 0.0,
            "n_clusters": 0,
            "noise_ratio": 0.0,
            "total_vectors_analyzed": n,
            "candidates": [],
        }

    mcs_candidates = candidate_mcs or [2, 3, 4, 5]
    ms_candidates = candidate_ms or [1, 2, 3]

    candidates = []
    best_candidate = None
    best_score = -999.0

    X = np.array(vectors)

    for mcs in mcs_candidates:
        if mcs > n:
            continue
        for ms in ms_candidates:
            if ms > mcs:
                continue
            try:
                clusterer = HDBSCAN(
                    min_cluster_size=mcs,
                    min_samples=ms,
                    metric=settings.cluster_metric,
                )
                labels = clusterer.fit_predict(X)
                quality = evaluate_clustering_quality(vectors, labels.tolist())
                sil = quality["silhouette_score"]
                noise_r = quality["noise_ratio"]
                k = quality["n_clusters"]

                # Composite score: reward high silhouette and cluster formation, penalize high noise
                if k < 2:
                    composite = -1.0 + (k * 0.1) - noise_r
                else:
                    composite = sil * (1.0 - (noise_r * 0.6))
                    # Favor min_samples >= 2 to avoid single-point bridge bleeding
                    if ms > 1:
                        composite += 0.02

                candidate_info = {
                    "min_cluster_size": mcs,
                    "min_samples": ms,
                    "silhouette_score": sil,
                    "n_clusters": k,
                    "noise": quality["noise"],
                    "noise_ratio": noise_r,
                    "composite_score": round(float(composite), 4),
                }
                candidates.append(candidate_info)

                if composite > best_score:
                    best_score = composite
                    best_candidate = candidate_info
            except Exception as exc:
                log.warning("HDBSCAN grid test failed for mcs=%d, ms=%d: %s", mcs, ms, exc)

    candidates.sort(key=lambda c: c["composite_score"], reverse=True)

    if not best_candidate:
        best_candidate = {
            "min_cluster_size": settings.hdbscan_min_cluster_size,
            "min_samples": settings.hdbscan_min_samples,
            "silhouette_score": 0.0,
            "n_clusters": 0,
            "noise": n,
            "noise_ratio": 1.0,
        }

    return {
        "status": "success",
        "recommended_min_cluster_size": best_candidate["min_cluster_size"],
        "recommended_min_samples": best_candidate["min_samples"],
        "silhouette_score": best_candidate["silhouette_score"],
        "n_clusters": best_candidate["n_clusters"],
        "noise_ratio": best_candidate["noise_ratio"],
        "rationale": f"Optimal configuration discovered: {best_candidate['n_clusters']} Person cluster(s) with a Silhouette score of {best_candidate['silhouette_score']} and {best_candidate['noise_ratio']*100:.1f}% noise.",
        "top_candidates": candidates[:5],
        "total_vectors_analyzed": n,
    }


def compute_centroids(vectors: list, labels: list) -> dict[int, list[float]]:
    arr = np.array(vectors)
    unique = set(labels) - {-1}
    centroids = {}
    for lbl in unique:
        mask = np.array(labels) == lbl
        centroids[int(lbl)] = arr[mask].mean(axis=0).tolist()
    return centroids


def store_centroids(centroids: dict[int, list[float]], label_to_person: dict[int, int]):
    qdrant = get_qdrant()
    col = centroid_collection()

    qdrant.delete_collection(collection_name=col)
    qdrant.create_collection(
        collection_name=col,
        vectors_config=VectorParams(size=512, distance=Distance.COSINE),
    )

    points = []
    for lbl, person_id in label_to_person.items():
        vec = centroids.get(lbl)
        if vec is not None:
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=vec,
                payload={
                    "cluster_label": lbl,
                    "person_id": person_id,
                    "is_centroid": True,
                },
            ))
    if points:
        qdrant.upsert(collection_name=col, points=points)
        log.info("Stored %d centroid vectors", len(points))


def clear_centroids():
    qdrant = get_qdrant()
    col = centroid_collection()
    try:
        qdrant.delete_collection(collection_name=col)
    except Exception:
        pass
    qdrant.create_collection(
        collection_name=col,
        vectors_config=VectorParams(size=512, distance=Distance.COSINE),
    )
    log.info("Cleared centroid collection")


# ── Incremental clustering helpers ──────────────────────────────

def count_unassigned(qdrant) -> int:
    """Return number of face vectors in the centroid collection — used
    to decide when to trigger a full HDBSCAN sweep."""
    try:
        info = qdrant.get_collection(collection_name=centroid_collection())
        return info.points_count or 0
    except Exception:
        return 0


def assign_new_faces(
    qdrant,
    new_vectors: list[list[float]],
    new_point_ids: list[str],
    confidence_threshold: float = 0.80,
) -> dict[str, int | None]:
    """Fast centroid-based assignment for newly scanned face embeddings.

    For each new face vector, the nearest centroid in the centroid collection
    is searched. If the cosine similarity score exceeds *confidence_threshold*
    the face is immediately assigned to that centroid's ``person_id``; otherwise
    it is left unassigned (returns ``None``) to be picked up by the next full
    HDBSCAN run.

    Returns a mapping of ``{qdrant_point_id: person_id | None}``.
    """
    col = centroid_collection()
    assignments: dict[str, int | None] = {}

    try:
        centroid_count = qdrant.get_collection(collection_name=col).points_count or 0
    except Exception:
        centroid_count = 0

    if centroid_count == 0:
        # No centroids yet — nothing to assign against
        return {pid: None for pid in new_point_ids}

    for vec, pid in zip(new_vectors, new_point_ids):
        hits = qdrant.search(
            collection_name=col,
            query_vector=vec,
            limit=1,
            with_payload=True,
        )
        if hits and hits[0].score >= confidence_threshold:
            assignments[pid] = hits[0].payload.get("person_id")
        else:
            assignments[pid] = None

    assigned = sum(1 for v in assignments.values() if v is not None)
    log.info(
        "Incremental assignment: %d/%d faces matched centroid (threshold=%.2f)",
        assigned, len(new_point_ids), confidence_threshold,
    )
    return assignments

