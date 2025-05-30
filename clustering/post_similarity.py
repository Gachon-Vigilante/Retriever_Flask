from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from bs4 import BeautifulSoup
import numpy as np

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
        "createdAt": 1,
        "updatedAt": 1,
        "deleted": 1
    })

    return [{
        "postId": str(doc["_id"]),
        "link": doc.get("link", ""),
        "siteName": doc.get("siteName", ""),
        "content": doc.get("content", ""),
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

    # 임베딩
    embeddings = [get_bert_embedding(doc["text"]) for doc in documents]
    similarity_matrix = cosine_similarity(np.array(embeddings))

    # MongoDB 기존 결과 초기화
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

            # Neo4j에 유사도 저장 (단방향 조건: link1 < link2, 그리고 0.7 이상)
            link1 = doc["link"]
            link2 = other_doc["link"]
            if score >= 0.7 and link1 < link2:
                # 두 노드 모두 MERGE
                run_cypher(Neo4j.QueryTemplate.Node.Post.MERGE, {
                    "link": link1,
                    "siteName": doc.get("source"),
                    "content": doc.get("content"),
                    "createdAt": doc.get("createdAt"),
                    "updatedAt": doc.get("updatedAt"),
                    "deleted": doc.get("deleted"),
                })
                run_cypher(Neo4j.QueryTemplate.Node.Post.MERGE, {
                    "link": link2,
                    "siteName": other_doc.get("source"),
                    "content": other_doc.get("content"),
                    "createdAt": other_doc.get("createdAt"),
                    "updatedAt": other_doc.get("updatedAt"),
                    "deleted": other_doc.get("deleted"),
                })
                insert_post_similarity(link1, link2, score)

        # MongoDB에 저장할 데이터
        bulk_data.append({
            "postId": doc["postId"],
            "similarPosts": similarities,
            "updatedAt": doc["updatedAt"]
        })

    # MongoDB 저장
    if bulk_data:
        similarity_collection.insert_many(bulk_data)

    return {"message": "Similarity calculations completed and stored in MongoDB & Neo4j."}
