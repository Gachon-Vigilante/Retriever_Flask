import numpy as np
import hdbscan
import umap.umap_ as umap
from sklearn.metrics import silhouette_score, silhouette_samples
from bs4 import BeautifulSoup
from tqdm import tqdm
from collections import Counter
from sentence_transformers import SentenceTransformer
from server.db import Database

# MongoDB 연결
collection = Database.Collection.POST

# Ko-SBERT 모델 불러오기
model = SentenceTransformer('snunlp/KR-SBERT-V40K-klueNLI-augSTS')

# HTML 정제 함수
def preprocess_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    return soup.get_text(separator=' ').strip()

# Ko-SBERT 임베딩 추출
def get_bert_embedding(text):
    return model.encode(text).astype(np.float64)

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.cm as cm


# 실루엣 플롯 함수
def plot_silhouette(embeddings, labels, silhouette_avg):
    unique_labels = np.unique(labels)
    unique_labels = [l for l in unique_labels if l != -1]
    n_clusters = len(unique_labels)

    if n_clusters == 0:
        print("No clusters to plot.")
        return

    silhouette_vals = silhouette_samples(embeddings, labels)
    y_lower = 10
    plt.figure(figsize=(10, 6))

    for i, cluster in enumerate(unique_labels):
        ith_vals = silhouette_vals[labels == cluster]
        ith_vals.sort()
        size_cluster = ith_vals.shape[0]
        y_upper = y_lower + size_cluster
        color = cm.nipy_spectral(float(i) / n_clusters)
        plt.fill_betweenx(np.arange(y_lower, y_upper), 0, ith_vals, facecolor=color, edgecolor=color, alpha=0.7)
        y_lower = y_upper + 10

    plt.axvline(x=silhouette_avg, color="red", linestyle="--")
    plt.title(f"Number of Clusters : {n_clusters} | Silhouette Score : {silhouette_avg:.3f}")
    plt.xlabel("Silhouette coefficient")
    plt.ylabel("Cluster")
    plt.show()

def perform_clustering_with_cosine(min_cluster_size=5, n_neighbors=15, n_components=15):
    documents = list(collection.find({}, {
        "_id": 1, "postId": 1, "content": 1, "promoSiteLink": 1
    }))

    if not documents:
        return {"error": "No documents found."}

    # promoSiteLink 목록
    promo_links = [
        doc.get("promoSiteLink", [])[0]
        for doc in documents
        if isinstance(doc.get("promoSiteLink", []), list) and doc["promoSiteLink"]
    ]
    link_counts = Counter(promo_links)

    # promoSiteLink 임베딩
    promo_embeddings = {}
    for link in link_counts:
        promo_embeddings[link] = get_bert_embedding(link)

    # 임베딩 생성
    embeddings = []
    for doc in tqdm(documents, desc="Generating embeddings with promo info"):
        text = preprocess_html(doc.get("content", ""))
        doc_emb = get_bert_embedding(text)

        promo = doc.get("promoSiteLink", [])
        promo_link = promo[0] if isinstance(promo, list) and promo else None
        promo_emb = promo_embeddings.get(promo_link)

        # 문서 + promo 링크 임베딩 결합
        if promo_emb is not None:
            combined_emb = 0.7 * doc_emb + 0.3 * promo_emb
        else:
            combined_emb = doc_emb

        embeddings.append(combined_emb)

    embeddings = np.array(embeddings)

    # UMAP 차원 축소 (코사인 거리 유지)
    umap_model = umap.UMAP(
        n_neighbors=n_neighbors,
        n_components=n_components,
        min_dist=0.0,
        metric='cosine',
        random_state=42
    )
    umap_embeddings = umap_model.fit_transform(embeddings)

    # HDBSCAN 클러스터링
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        metric='euclidean',
        cluster_selection_method='eom'
    )
    labels = clusterer.fit_predict(umap_embeddings)

    # 실루엣 스코어 평가
    mask = labels != -1
    if np.sum(mask) < 2:
        silhouette_avg = -1
    else:
        silhouette_avg = silhouette_score(umap_embeddings[mask], labels[mask], metric='euclidean')

    # 실루엣 플롯 출력
    plot_silhouette(umap_embeddings, labels, silhouette_avg)

    # DB 업데이트
    for idx, doc in enumerate(documents):
        update_fields = {
            "cluster_label": int(labels[idx]),
            "embedding": embeddings[idx].tolist(),
            "umap_embedding": umap_embeddings[idx].tolist()
        }
        collection.update_one({"_id": doc["_id"]}, {"$set": update_fields})

    return {
        "message": "UMAP + HDBSCAN Clustering 결과가 posts 컬렉션에 저장되었습니다.",
        "total_documents": len(documents),
        "noise_documents": list(labels).count(-1),
        "silhouette_score": silhouette_avg
    }


# 함수 호출 예시
result = perform_clustering_with_cosine(min_cluster_size=5)
print(result)
