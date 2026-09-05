# Vector Databases and Machine Learning Stacks

Guidelines for documenting machine learning pipelines, vector similarity search, and embedding stores in polyglot systems.

---

## 1. Core Concepts

Modern AI-driven systems frequently augment relational databases (MySQL, PostgreSQL) with dedicated **Vector Databases** (Qdrant, Milvus, Chroma, pgvector). When documenting an ML stack:

| Component | Purpose | Examples | Key Metadata to Document |
|---|---|---|---|
| **Feature Extractor** | Converts raw media/text into numerical arrays | InsightFace (ArcFace), OpenAI CLIP, Sentence-Transformers | Backbone (ResNet-100, ViT-B/32), input dimensions, weights path |
| **Vector Database** | Indexes high-dimensional vectors for low-latency similarity | Qdrant, Milvus, pgvector | Distance metric (Cosine, Euclidean), dimensions, indexing algorithm |
| **Object Detector** | Classifies bounding boxes and labels in images | YOLOv8, Faster R-CNN, DETR | Confidence thresholds, label count, hardware acceleration |
| **Clustering Engine** | Discovers unsupervised groupings of vectors | HDBSCAN, DBSCAN, Agglomerative | Distance metric, `min_cluster_size`, centroid calculation strategy |

---

## 2. Documenting Vector Collections

Every vector collection must be documented in `docs/architecture/data-and-storage.md` or `docs/services/ml.md` using this standard schema:

| Collection Name | Vector Dimensions | Distance Metric | Index Type | Payload Attributes | Purpose |
|---|---|---|---|---|---|
| `face_embeddings` | 512 | Cosine | HNSW | `photo_id`, `user_id`, `face_id` | Individual detected faces. Used for 1:N face search. |
| `face_centroids` | 512 | Cosine | HNSW | `person_id`, `user_id` | Arithmetic mean vector of all faces in a cluster. |
| `clip_embeddings` | 512 | Cosine | HNSW | `photo_id`, `user_id` | Full-image visual embedding for semantic text search. |

### Index Configuration (HNSW Parameters)
Document HNSW (Hierarchical Navigable Small World) settings when relevant for production scaling:
- **`m`** (number of edges per node, default: 16): Controls connectivity. Higher values improve recall at the cost of RAM.
- **`ef_construct`** (search depth during build, default: 100): Trade-off between indexing time and search accuracy.
- **On-Disk vs In-RAM**: Specify whether vector vectors or payloads are stored in memory or memory-mapped on disk (`on_disk: true`).

---

## 3. Mathematical Foundations & Algorithms

When documenting algorithms in `docs/architecture/` or `docs/services/ml.md`:

### Additive Angular Margin Loss (ArcFace)
Explain why ArcFace is chosen over Euclidean distance for biometric face matching:
- ArcFace introduces an additive angular penalty $m = 0.5$ directly into the target cosine angle:
  $$\mathcal{L}_{\text{ArcFace}} = -\log \frac{e^{s \cos(\theta_{y_i} + m)}}{e^{s \cos(\theta_{y_i} + m)} + \sum_{j \neq y_i} e^{s \cos \theta_j}}$$
- Vectors are $L_2$-normalized onto a unit hypersphere ($\|\mathbf{v}\|_2 = 1$), meaning cosine similarity corresponds directly to geodesic angle distance:
  $$S = \cos(\theta) = \mathbf{u} \cdot \mathbf{v}$$

### Density-Based Clustering (HDBSCAN)
- **Mutual Reachability Distance**: Protects against noise by transforming distances using local density:
  $$d_{\text{mrd}}(a, b) = \max \left( \text{core}_k(a), \text{core}_k(b), d(a, b) \right)$$
- **Centroid Computation**: Arithmetic mean of cluster vectors normalized to unit length:
  $$\mathbf{c} = \frac{\sum_{i \in C} \mathbf{v}_i}{\left\| \sum_{i \in C} \mathbf{v}_i \right\|_2}$$

---

## 4. Hardware Sizing & OOM Prevention

Always include production memory sizing tables in user and engineer documentation:

| Model / Network | Disk Footprint | Peak RAM Footprint | Inference Mode |
|---|---|---|---|
| **InsightFace Buffalo-L** | ~300 MB | ~450 MB | CPU / PyTorch ONNX Runtime |
| **OpenAI CLIP (ViT-B/32)** | ~588 MB | ~650 MB | CPU / PyTorch TorchScript |
| **YOLOv8 Nano** | ~12 MB | ~80 MB | CPU / PyTorch Ultralytics |

> **OOM Prevention Rule**: When multiple deep learning models load concurrently during batch scans, memory momentarily spikes by ~1.2x. Container limits below 2048 MB trigger Linux OOM kills (`SIGKILL 137`). Document minimum container limits in `docs/user/configuration.md`.

---

## 5. Graceful Degradation Patterns

Document how the broader system behaves when the ML service or Vector DB is unavailable:
1. **Asynchronous Non-Blocking Scans**: Web/mobile photo uploads must never fail if the ML service is down (use non-blocking cURL with short connection timeouts $\le 100\text{ms}$).
2. **Search Fallback**: If CLIP vector search fails, the search router must catch the exception and fall back to SQL string matching on metadata and EXIF tags.
3. **Health Status Probes**: `/health` should distinguish between `status: ok` (fully functional) and `status: degraded` (e.g. relational DB connected, but vector DB disconnected).
