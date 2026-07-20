from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone

import numpy as np
from sqlalchemy.orm import Session
from qdrant_client.models import PointStruct

from app.config import settings
from app.database import get_db, get_qdrant, FaceEncoding, Person
from app.models.db import FaceCluster
from app.ml import clustering as ml_clustering

log = logging.getLogger("ml_chege_photos.face")


def reclassify_face(face_id: int, db: Session) -> dict:
    fe = db.query(FaceEncoding).filter(FaceEncoding.id == face_id).first()
    if not fe:
        raise ValueError(f"Face {face_id} not found")

    previous_cluster_id = fe.person_id

    qdrant = get_qdrant()
    vectors, point_ids = ml_clustering.scroll_all_vectors(qdrant, settings.qdrant_collection)

    if len(vectors) < 2:
        if fe.person_id:
            fe.person_id = None
            db.commit()
            return {
                "face_id": face_id,
                "previous_cluster_id": previous_cluster_id,
                "new_cluster_id": None,
                "message": "Not enough faces to reclassify — unassigned",
            }
        return {
            "face_id": face_id,
            "previous_cluster_id": None,
            "new_cluster_id": None,
            "message": "Not enough faces to reclassify",
        }

    result = ml_clustering.run_hdbscan(vectors)
    labels = result["labels"]

    face_idx = None
    for i, pid in enumerate(point_ids):
        if pid == fe.qdrant_point_id:
            face_idx = i
            break

    if face_idx is None:
        raise ValueError(f"Face {face_id} has no Qdrant point")

    new_label = labels[face_idx]

    if new_label == -1:
        fe.person_id = None
        db.commit()
        return {
            "face_id": face_id,
            "previous_cluster_id": previous_cluster_id,
            "new_cluster_id": None,
            "message": "Face classified as noise — unassigned",
        }

    unique_labels = set(labels) - {-1}
    label_to_person = {}

    persons = db.query(Person).filter(Person.cluster_label.isnot(None)).all()
    for p in persons:
        label_to_person[p.cluster_label] = p.id

    existing_person = label_to_person.get(new_label)
    if existing_person is not None:
        fe.person_id = existing_person
        db.commit()
        return {
            "face_id": face_id,
            "previous_cluster_id": previous_cluster_id,
            "new_cluster_id": existing_person,
            "message": f"Face reassigned to existing person {existing_person}",
        }

    person = Person(cluster_label=int(new_label))
    db.add(person)
    db.flush()

    for pid, lbl in zip(point_ids, labels):
        if lbl == new_label:
            f = db.query(FaceEncoding).filter(FaceEncoding.qdrant_point_id == pid).first()
            if f:
                f.person_id = person.id
    db.commit()

    centroids = ml_clustering.compute_centroids(vectors, labels)
    ml_clustering.store_centroids(centroids, {new_label: person.id})

    return {
        "face_id": face_id,
        "previous_cluster_id": previous_cluster_id,
        "new_cluster_id": person.id,
        "message": f"Face reassigned to new person {person.id}",
    }


def merge_clusters(source_cluster_id: int, target_cluster_id: int, db: Session) -> dict:
    source = db.query(FaceCluster).filter(FaceCluster.id == source_cluster_id).first()
    if not source:
        raise ValueError(f"FaceCluster {source_cluster_id} not found")

    target = db.query(FaceCluster).filter(FaceCluster.id == target_cluster_id).first()
    if not target:
        raise ValueError(f"FaceCluster {target_cluster_id} not found")

    db.query(FaceEncoding).filter(
        FaceEncoding.person_id == source.person_id
    ).update({"person_id": target.person_id})

    merged = list(source.merged_from or []) + [source_cluster_id]
    target.merged_from = merged

    db.delete(source)
    db.commit()

    qdrant = get_qdrant()
    vectors, point_ids = ml_clustering.scroll_all_vectors(qdrant, settings.qdrant_collection)
    persons = db.query(Person).filter(Person.id == target.person_id).first()
    if persons and vectors:
        face_indices = [i for i, pid in enumerate(point_ids) if any(
            db.query(FaceEncoding).filter(
                FaceEncoding.qdrant_point_id == pid,
                FaceEncoding.person_id == target.person_id,
            ).first()
        )]
        if face_indices:
            cluster_vecs = [vectors[i] for i in face_indices]
            centroid = np.mean(cluster_vecs, axis=0).tolist()
            cid = str(uuid.uuid4())
            qdrant.upsert(
                collection_name=ml_clustering.centroid_collection(),
                points=[PointStruct(id=cid, vector=centroid, payload={
                    "cluster_label": persons.cluster_label,
                    "person_id": target.person_id,
                    "is_centroid": True,
                })],
            )
            target.centroid_point_id = cid
            db.commit()

    return {
        "source_cluster_id": source_cluster_id,
        "target_cluster_id": target_cluster_id,
        "merged_into": target.person_id,
    }


def split_cluster(cluster_id: int, db: Session) -> dict:
    cluster = db.query(FaceCluster).filter(FaceCluster.id == cluster_id).first()
    if not cluster:
        raise ValueError(f"FaceCluster {cluster_id} not found")

    person = db.query(Person).filter(Person.id == cluster.person_id).first()
    if not person:
        raise ValueError(f"Person {cluster.person_id} not found")

    faces = db.query(FaceEncoding).filter(
        FaceEncoding.person_id == cluster.person_id
    ).all()

    if len(faces) < 2:
        raise ValueError("Need at least 2 faces to split")

    qdrant = get_qdrant()
    vectors, point_ids = ml_clustering.scroll_all_vectors(qdrant, settings.qdrant_collection)

    face_vectors = []
    face_point_ids = []
    for fe in faces:
        for pid, vec in zip(point_ids, vectors):
            if pid == fe.qdrant_point_id:
                face_vectors.append(vec)
                face_point_ids.append(pid)
                break

    if len(face_vectors) < 2:
        raise ValueError("Could not find enough vectors for this person's faces")

    result = ml_clustering.run_hdbscan(face_vectors)
    labels = result["labels"]
    unique = set(labels) - {-1}

    if len(unique) < 2:
        raise ValueError("HDBSCAN did not find sub-clusters — this cluster is cohesive")

    label_to_person = {}
    for lbl in unique:
        new_person = Person(cluster_label=int(lbl))
        db.add(new_person)
        db.flush()
        label_to_person[lbl] = new_person.id

    noise_faces = []
    for fe, lbl in zip(faces, labels):
        if lbl == -1:
            noise_faces.append(fe.id)
            continue
        fe.person_id = label_to_person[lbl]

    db.delete(cluster)
    db.commit()

    centroids = ml_clustering.compute_centroids(face_vectors, labels)
    label_to_person_for_centroids = {}
    for lbl, pid in label_to_person.items():
        label_to_person_for_centroids[lbl] = pid
    if centroids and label_to_person_for_centroids:
        ml_clustering.store_centroids(centroids, label_to_person_for_centroids)

    return {
        "original_cluster_id": cluster_id,
        "new_clusters": len(unique),
        "noise_faces": len(noise_faces),
        "noise_face_ids": noise_faces,
    }
