import numpy as np
import hdbscan
import umap.umap_ as umap
from sklearn.metrics import silhouette_score, pairwise
from bs4 import BeautifulSoup
from tqdm import tqdm
from collections import Counter
from sentence_transformers import SentenceTransformer

from server.cypher import run_cypher
from server.db import Database
from server.logger import logger
from datetime import datetime
import pickle
import os
from dotenv import load_dotenv

load_dotenv()  # .env 파일 읽어 환경변수로 설정

UMAP_MODEL_PATH = os.path.join(os.path.dirname(__file__), "umap_model.pkl")

# MongoDB 연결
collection = Database.Collection.POST
centroid_collection = Database.Collection.CENTER

# Ko-SBERT 모델 로드
try:
    model = SentenceTransformer('snunlp/KR-SBERT-V40K-klueNLI-augSTS')
except Exception as e:
    print(f"Error loading SentenceTransformer model: {e}")
    raise

def preprocess_html(html_content: str) -> str:
    """HTML 콘텐츠를 텍스트로 정제"""
    soup = BeautifulSoup(html_content, 'html.parser')
    return soup.get_text(separator=' ').strip()

def get_bert_embedding(text: str) -> np.ndarray:
    """문자열 입력받아 Ko-SBERT 임베딩 벡터 반환"""
    return model.encode(text).astype(np.float64)

def save_umap_model(umap_model, path=UMAP_MODEL_PATH):
    """UMAP 모델을 지정 경로에 저장"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        pickle.dump(umap_model, f)

def load_umap_model(path=UMAP_MODEL_PATH):
    """저장된 UMAP 모델 불러오기"""
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'rb') as f:
            return pickle.load(f)
    except Exception as e:
        logger.error(f"Failed to load UMAP model: {e}")
        return None

def compute_centroids(embeddings: np.ndarray, labels: np.ndarray) -> dict:
    """클러스터별 중심(centroid) 계산"""
    centroids = {}
    for label in np.unique(labels):
        if label == -1:
            continue
        cluster_embs = embeddings[labels == label]
        centroids[label] = np.mean(cluster_embs, axis=0)
    return centroids

def save_centroids(centroid_dict: dict):
    """MongoDB에 클러스터 중심 저장 (기존 데이터 삭제 후 삽입)"""
    try:
        centroid_collection.delete_many({})
        docs = [{"cluster_label": int(k), "centroid": v.tolist(), "updatedAt": datetime.utcnow()}
                for k, v in centroid_dict.items()]
        if docs:
            centroid_collection.insert_many(docs)
    except Exception as e:
        print(f"Failed to save centroids: {e}")
        raise

def load_centroids() -> dict:
    """MongoDB에서 클러스터 중심 로딩"""
    try:
        docs = list(centroid_collection.find())
        return {doc["cluster_label"]: np.array(doc["centroid"]) for doc in docs}
    except Exception as e:
        print(f"Failed to load centroids: {e}")
        return {}

def assign_cluster(new_emb: np.ndarray, centroid_dict: dict, threshold=0.6) -> int:
    """
   새로운 문서의 UMAP 임베딩을 받아, UMAP 기반 centroid와 cosine 유사도 비교 후 클러스터 라벨 할당.
   threshold 미만이면 -1 (noise) 반환.
   """
    if not centroid_dict:
        return -1
    labels = list(centroid_dict.keys())
    centroids = np.array([centroid_dict[label] for label in labels])
    sims = pairwise.cosine_similarity([new_emb], centroids)[0]
    max_idx = np.argmax(sims)
    return labels[max_idx] if sims[max_idx] >= threshold else -1

def perform_clustering_with_HDBSCAN(min_cluster_size=5, n_neighbors=15, n_components=15):
    """전체 문서 대상 UMAP + HDBSCAN 클러스터링 수행 및 모델, 중심 저장"""
    documents = list(collection.find({}, {"_id": 1, "postId": 1, "content": 1, "promoSiteLink": 1}))
    if not documents:
        return {"error": "No documents found."}

    promo_links = [doc.get("promoSiteLink", [])[0] for doc in documents
                   if isinstance(doc.get("promoSiteLink", []), list) and doc["promoSiteLink"]]
    link_counts = Counter(promo_links)

    promo_embeddings = {link: get_bert_embedding(link) for link in link_counts}

    embeddings, ids = [], []
    for doc in tqdm(documents, desc="Generating embeddings"):
        text = preprocess_html(doc.get("content", ""))
        doc_emb = get_bert_embedding(text)

        promo = doc.get("promoSiteLink", [])
        promo_link = promo[0] if isinstance(promo, list) and promo else None
        promo_emb = promo_embeddings.get(promo_link)

        combined_emb = 0.7 * doc_emb + 0.3 * promo_emb if promo_emb is not None else doc_emb
        embeddings.append(combined_emb)
        ids.append(doc["_id"])

    embeddings = np.array(embeddings)

    umap_model = umap.UMAP(n_neighbors=n_neighbors, n_components=n_components,
                           min_dist=0.0, metric='cosine', random_state=42)
    umap_embeddings = umap_model.fit_transform(embeddings)

    save_umap_model(umap_model)

    clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, metric='euclidean', cluster_selection_method='eom')
    labels = clusterer.fit_predict(umap_embeddings)

    mask = labels != -1
    silhouette_avg = silhouette_score(umap_embeddings[mask], labels[mask], metric='euclidean') if np.sum(mask) >= 2 else -1

    # DB 업데이트
    for idx, _id in enumerate(ids):
        cluster_label = int(labels[idx])
        collection.update_one({"_id": _id}, {"$set": {
            "cluster_label": cluster_label,
            "embedding": embeddings[idx].tolist(),
            "umap_embedding": umap_embeddings[idx].tolist(),
            "assigned_by": "full"
        }})

        run_cypher(query="""
                             MERGE (p:Post {link: $link})
                             ON MATCH SET
                                 p.cluster = $cluster
                             RETURN p
                         """,
                   parameters={
                       "link": collection.find_one({"_id": _id}).get("link"),
                       "cluster": cluster_label
                   }
       )

    # 클러스터 중심 저장
    centroid_dict = compute_centroids(umap_embeddings, labels)  # 기존 embeddings 대신 umap_embeddings로 계산하는게 더 정확
    save_centroids(centroid_dict)

    return {
        "message": "Full clustering 완료.",
        "total_documents": len(documents),
        "noise_documents": int(list(labels).count(-1)),  # 안전하게 변환
        "silhouette_score": float(silhouette_avg)        # 여기만 float으로 변환
    }

def handle_new_posts(threshold=0.6):
    """
    새 문서(cluster_label 미존재)를 불러와 기존 UMAP 모델 및 클러스터 중심으로 클러스터 할당.
    """
    new_docs = list(collection.find({"cluster_label": {"$exists": False}}))
    if not new_docs:
        return {"message": "No new documents."}

    centroids = load_centroids()
    umap_model = load_umap_model()
    if umap_model is None:
        return {"error": "UMAP model not found. Please run full clustering first."}

    for doc in tqdm(new_docs, desc="Assigning new docs"):
        text = preprocess_html(doc.get("content", ""))
        emb = get_bert_embedding(text)

        # UMAP 차원 축소 적용
        try:
            emb_umap = umap_model.transform([emb])[0]
        except Exception as e:
            logger.warning(f"UMAP transform failed for doc {doc['_id']}: {e}")
            emb_umap = emb  # fallback: 원본 임베딩 사용

        label = assign_cluster(emb_umap, centroids, threshold)

        collection.update_one({"_id": doc["_id"]}, {"$set": {
            "cluster_label": int(label),
            "embedding": emb.tolist(),
            "umap_embedding": emb_umap.tolist() if isinstance(emb_umap, np.ndarray) else [],
            "assigned_by": "centroid"
        }})

    return {"message": f"{len(new_docs)} documents assigned to clusters."}

def maybe_recluster(threshold_count=100):
    """
    새로 centroid 할당된 문서 수가 threshold 이상이면 전체 재클러스터링 실행.
    """
    count = collection.count_documents({"assigned_by": "centroid"})
    if count >= threshold_count:
        logger.info("Reclustering triggered...")
        result = perform_clustering_with_HDBSCAN()
        # 재할당된 문서들은 assigned_by를 "full"로 변경
        collection.update_many({"assigned_by": "centroid"}, {"$set": {"assigned_by": "full"}})
        return result
    return {"message": f"Current new doc count: {count}"}
