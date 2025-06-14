import numpy as np
import hdbscan
import umap.umap_ as umap
from sklearn.metrics import silhouette_score

from server.cypher import run_cypher
from server.db import Database

# MongoDB 연결
collection = Database.Collection.POST

# 전체 클러스터링 수행
def perform_clustering_with_HDBSCAN(min_cluster_size=5, n_neighbors=15, n_components=15):
    documents = list(collection.find({"embedding": {"$exists": True}}, {"_id": 1, "embedding": 1, "link": 1}))
    if not documents:
        return {"error": "No documents found with existing embeddings."}

    embeddings = np.array([doc["embedding"] for doc in documents], dtype=np.float64)
    ids = [doc["_id"] for doc in documents]
    links = [doc.get("link") for doc in documents]

    umap_model = umap.UMAP(n_neighbors=n_neighbors, n_components=n_components,
                           min_dist=0.0, metric='cosine', random_state=42)
    umap_embeddings = umap_model.fit_transform(embeddings)

    clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, metric='euclidean', cluster_selection_method='eom')
    labels = clusterer.fit_predict(umap_embeddings)

    mask = labels != -1
    silhouette_avg = silhouette_score(umap_embeddings[mask], labels[mask], metric='euclidean') if np.sum(mask) >= 2 else -1

    for idx, _id in enumerate(ids):
        cluster_label = int(labels[idx])
        collection.update_one({"_id": _id}, {"$set": {
            "cluster_label": cluster_label
        }})

        run_cypher("""
            MERGE (p:Post {link: $link})
            ON MATCH SET p.cluster = $cluster
            RETURN p
        """, parameters={"link": links[idx], "cluster": cluster_label})


    return {
        "message": "Clustering 완료.",
        "total_documents": len(documents),
        "noise_documents": int(list(labels).count(-1)),
        "silhouette_score": float(silhouette_avg)
    }