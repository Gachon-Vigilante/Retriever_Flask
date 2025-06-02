from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from bs4 import BeautifulSoup
import numpy as np
from collections import Counter

from server.db import Database
from server.cypher import run_cypher, Neo4j # 네오4j 쿼리 실행 함수


# MongoDB 컬렉션
collection = Database.Collection.POST
similarity_collection = Database.Collection.POST_SIMILARITY

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
    documents = collection.find({}, {
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
        "postId": str(doc["_id"]),
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
def post_similarity():
    documents = fetch_documents()
    if not documents:
        return {"message": "No documents found."}

    # promoSiteLink 추출
    promo_links = [
        doc.get("promoSiteLink", [])[0]
        for doc in documents
        if isinstance(doc.get("promoSiteLink", []), list) and doc["promoSiteLink"]
    ]
    link_counts = Counter(promo_links)

    # 링크 사용 빈도 기반 weight 계산 (0~1)
    max_count = max(link_counts.values()) if link_counts else 1
    link_weights = {link: count / max_count for link, count in link_counts.items()}

    # 링크 임베딩 사전 생성
    promo_embeddings = {link: get_bert_embedding(link) for link in link_counts}

    # 문서별 임베딩 생성
    embeddings = []
    for doc in documents:
        doc_emb = get_bert_embedding(doc["text"])

        promo = doc.get("promoSiteLink", [])
        promo_link = promo[0] if isinstance(promo, list) and promo else None
        promo_emb = promo_embeddings.get(promo_link)
        weight = 0.3

        # 가중 평균
        combined_emb = (1 - weight) * doc_emb + weight * promo_emb if promo_emb is not None else doc_emb
        embeddings.append(combined_emb)

    # 유사도 계산
    similarity_matrix = cosine_similarity(np.array(embeddings))

    # 기존 MongoDB 유사도 데이터 삭제
    similarity_collection.delete_many({})

    bulk_data = []
    for i, doc in enumerate(documents):
        similarities = []
        for j, score in enumerate(similarity_matrix[i]):
            if i == j:
                continue

            other_doc = documents[j]
            similarities.append({
                "similarPost": other_doc["postId"],
                "similarity": float(score)
            })

            # Neo4j 유사도 관계 삽입
            link1 = doc["link"]
            link2 = other_doc["link"]
            if score >= 0.7 and link1 < link2:
                run_cypher(Neo4j.QueryTemplate.Node.Post.MERGE, {
                    "link": link1,
                    "siteName": doc.get("siteName"),
                    "content": doc.get("content"),
                    "createdAt": doc.get("createdAt"),
                    "updatedAt": doc.get("updatedAt"),
                    "deleted": doc.get("deleted"),
                })
                run_cypher(Neo4j.QueryTemplate.Node.Post.MERGE, {
                    "link": link2,
                    "siteName": other_doc["source"],
                    "content": other_doc["content"],
                    "createdAt": other_doc["createdAt"],
                    "updatedAt": other_doc["updatedAt"],
                    "deleted": other_doc["deleted"]
                })
                insert_post_similarity(link1, link2, score)

        bulk_data.append({
            "postId": doc["postId"],
            "similarPosts": similarities,
            "updatedAt": doc["updatedAt"]
        })

    if bulk_data:
        similarity_collection.insert_many(bulk_data)

    return {"message": "Similarity calculations completed and stored in MongoDB & Neo4j."}
