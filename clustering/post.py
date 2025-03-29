from pymongo import MongoClient
import torch
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_similarity
from transformers import AutoTokenizer, AutoModel
from bs4 import BeautifulSoup
import numpy as np

# MongoDB 연결 설정
client = MongoClient("mongodb://localhost:27017/")
db = client['local']
collection = db['train']
cluster_collection = db['post_clusters']  # 클러스터링 결과 저장 컬렉션

# KoBERT 모델 및 토크나이저 로드
model_name = "monologg/kobert"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModel.from_pretrained(model_name)

# HTML 문서 불러오기
def fetch_html_documents():
    documents = collection.find({}, {"_id": 1, "postId": 1, "html": 1, "createdAt": 1, "updatedAt": 1})
    return [{
        "_id": str(doc["_id"]),
        "postId": doc["postId"],
        "html": doc["html"],
        "createdAt": doc["createdAt"],
        "updatedAt": doc["updatedAt"]
    } for doc in documents if "html" in doc]

# HTML 전처리
def preprocess_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    return soup.get_text(separator=' ').strip()

# KoBERT 임베딩 생성
def get_bert_embedding(text):
    tokens = tokenizer(text, return_tensors="pt", truncation=True, max_length=512, padding="max_length")
    with torch.no_grad():
        output = model(**tokens)
    return output.last_hidden_state[:, 0, :].squeeze().tolist()

# DBSCAN 클러스터링
def dbscan_clustering(similarity_matrix, eps=0.4, min_samples=2):
    distance_matrix = 1 - similarity_matrix  # 코사인 유사도를 거리로 변환
    db = DBSCAN(metric="precomputed", eps=eps, min_samples=min_samples)
    return db.fit_predict(distance_matrix)

# 클러스터링 실행 및 MongoDB 저장
def perform_clustering_with_cosine(eps=0.4, min_samples=2):
    documents = fetch_html_documents()
    embeddings = [get_bert_embedding(preprocess_html(doc["html"])) for doc in documents]

    similarity_matrix = cosine_similarity(np.array(embeddings))
    labels = dbscan_clustering(similarity_matrix, eps, min_samples)

    # 클러스터링 결과를 MongoDB에 저장
    cluster_collection.delete_many({})  # 기존 데이터 초기화

    for idx, doc in enumerate(documents):
        cluster_collection.insert_one({
            "postId": doc["postId"],
            "cluster_label": int(labels[idx]),
            "embedding": embeddings[idx],
            "createdAt": doc["createdAt"],
            "updatedAt": doc["updatedAt"]
        })

    # 클러스터 통계 정보 저장
    cluster_collection.insert_one({
        "_id": "cluster_stats",
        "total_documents": len(documents),
        "noise_documents": list(labels).count(-1)
    })

    return {"message": "Clustering results stored successfully in MongoDB."}
