from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from bs4 import BeautifulSoup
import numpy as np
from collections import Counter
from pymongo import UpdateOne
from server.db import Database
from server.cypher import run_cypher, Neo4j # 네오4j 쿼리 실행 함수


# MongoDB 컬렉션
collection = Database.Collection.POST

# Ko-SBERT 모델 로드
try:
    model = SentenceTransformer('snunlp/KR-SBERT-V40K-klueNLI-augSTS')
except Exception as e:
    print(f"Error loading SentenceTransformer model: {e}")
    raise

def preprocess_text(text):
    soup = BeautifulSoup(text, 'html.parser')
    return soup.get_text(separator=' ').strip()

def get_bert_embedding(text: str) -> np.ndarray:
    """문자열 입력받아 Ko-SBERT 임베딩 벡터 반환"""
    return model.encode(text).astype(np.float64)

# Neo4j에 유사도 관계 삽입
def insert_post_similarity(link1: str, link2: str, score: float):
    query = """
    MATCH (a:Post {link: $link1}), (b:Post {link: $link2})
    MERGE (a)-[r:SIMILAR]->(b)
    SET r.score = $score
    """
    run_cypher(query, {"link1": link1, "link2": link2, "score": score})

# 문서 가져오기
def fetch_documents():
    documents = collection.find({"embedding": {"$exists": False}}, {
        "_id": 1,
        "link": 1,
        "siteName": 1,
        "content": 1,
        "promoSiteLink": 1,  # 추가
        "createdAt": 1,
        "updatedAt": 1,
        "deleted": 1
    })

    return [{
        "_id": str(doc["_id"]),
        "link": doc.get("link", ""),
        "siteName": doc.get("siteName", ""),
        "content": doc.get("content", ""),
        "promoSiteLink": doc.get("promoSiteLink", []),  # 추가
        "text": preprocess_text(doc.get("content", "")),
        "createdAt": doc.get("createdAt"),
        "updatedAt": doc.get("updatedAt", doc.get("createdAt")),
        "deleted": doc.get("deleted", False)
    } for doc in documents if doc.get("content", "").strip()]

# 전체 파이프라인 실행
def embeddings():
    documents = fetch_documents()
    if not documents:
        return {"message": "No documents found or embeddings already exist."}

    promo_links = [
        str(doc.get("promoSiteLink", [])[0])
        for doc in documents
        if isinstance(doc.get("promoSiteLink", []), list) and doc["promoSiteLink"]
    ]
    link_counts = Counter(promo_links)
    promo_embeddings = {link: get_bert_embedding(link) for link in link_counts}

    bulk_ops = []
    for doc in documents:
        doc_emb = get_bert_embedding(doc["content"])
        promo = doc.get("promoSiteLink", [])
        promo_link = promo[0] if isinstance(promo, list) and promo else None
        promo_emb = promo_embeddings.get(promo_link)
        weight = 0.3
        combined_emb = (1 - weight) * doc_emb + weight * promo_emb if promo_emb is not None else doc_emb

        bulk_ops.append(UpdateOne(
            {"_id": doc["_id"]},
            {"$set": {"embedding": combined_emb.tolist(), "updatedAt": doc["updatedAt"]}}
        ))

    if bulk_ops:
        collection.bulk_write(bulk_ops)

    return {"message": f"Embeddings generated and stored for {len(bulk_ops)} documents."}


def similarity(threshold=0.7):
    documents = list(collection.find({"embedding": {"$exists": True}}, {
        "_id": 1, "link": 1, "siteName": 1, "content": 1,
        "createdAt": 1, "updatedAt": 1, "deleted": 1, "embedding": 1
    }))

    if len(documents) < 2:
        return {"message": "Not enough documents with embeddings to calculate similarity."}

    embeddings = np.array([doc["embedding"] for doc in documents])
    similarity_matrix = cosine_similarity(embeddings)

    bulk_ops = []
    for i, doc in enumerate(documents):
        similarities = []
        for j, score in enumerate(similarity_matrix[i]):
            if i == j:
                continue

            other_doc = documents[j]
            similarities.append({
                "similarPost": str(other_doc["_id"]),
                "similarity": float(score)
            })

            if score >= threshold and doc["link"] < other_doc["link"]:
                run_cypher(Neo4j.QueryTemplate.Node.Post.MERGE, {
                    "link": doc["link"],
                    "siteName": doc.get("siteName"),
                    "content": doc.get("content"),
                    "createdAt": doc.get("createdAt"),
                    "updatedAt": doc.get("updatedAt"),
                    "deleted": doc.get("deleted")
                })
                run_cypher(Neo4j.QueryTemplate.Node.Post.MERGE, {
                    "link": other_doc["link"],
                    "siteName": other_doc.get("siteName"),
                    "content": other_doc.get("content"),
                    "createdAt": other_doc.get("createdAt"),
                    "updatedAt": other_doc.get("updatedAt"),
                    "deleted": other_doc.get("deleted")
                })
                insert_post_similarity(doc["link"], other_doc["link"], score)

        bulk_ops.append(UpdateOne(
            {"_id": doc["_id"]},
            {"$set": {"similarPosts": similarities, "updatedAt": doc["updatedAt"]}}
        ))

    if bulk_ops:
        collection.bulk_write(bulk_ops)

    return {"message": "Similarity calculations completed and stored in MongoDB & Neo4j."}