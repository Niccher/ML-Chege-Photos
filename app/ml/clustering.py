from __future__ import annotations

import uuid
import logging

import numpy as np
from sklearn.cluster import HDBSCAN
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
