from pymongo import MongoClient
import torch
from sklearn.metrics.pairwise import cosine_similarity
from transformers import AutoTokenizer, AutoModel
from bs4 import BeautifulSoup
import numpy as np

from server.db import Database

# MongoDB 연결
collection = Database.Collection.POST
similarity_collection = Database.Collection.POST_SIMILARITY  # 유사도 결과 저장 컬렉션

# KoBERT 모델 및 토크나이저 로드
model_name = "monologg/kobert"
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
model = AutoModel.from_pretrained(model_name, trust_remote_code=True)

# 텍스트 데이터 불러오기
def fetch_documents():
    documents = collection.find({}, {
        "_id": 1,
        "content": 1,
        "createdAt": 1,
        "updatedAt": 1
    })

    return [{
        "_id": str(doc["_id"]),
        "postId": str(doc["_id"]),  # _id를 postId로 사용
        "text": doc.get("content", "").strip(),
        "createdAt": doc.get("createdAt"),
        "updatedAt": doc.get("updatedAt", doc.get("createdAt"))
    } for doc in documents if doc.get("content", "").strip()]

# 텍스트 전처리
def preprocess_text(text):
    soup = BeautifulSoup(text, 'html.parser')  # 혹시 HTML 태그 포함된 경우 제거
    return soup.get_text(separator=' ').strip()

# KoBERT 임베딩 생성
def get_bert_embedding(text):
    tokens = tokenizer(text, return_tensors="pt", truncation=True, max_length=512, padding="max_length")
    with torch.no_grad():
        output = model(**tokens)
    embedding = output.last_hidden_state.mean(dim=1).squeeze().tolist()
    return embedding

# 유사도 분석 및 MongoDB 저장
def post_similarity():
    documents = fetch_documents()
    if not documents:
        return {"message": "No documents found."}

    # 텍스트 전처리 및 임베딩
    embeddings = []
    for doc in documents:
        clean_text = preprocess_text(doc["text"])
        embedding = get_bert_embedding(clean_text)
        embeddings.append(embedding)

    # 코사인 유사도 계산
    similarity_matrix = cosine_similarity(np.array(embeddings))

    # 기존 결과 초기화
    similarity_collection.delete_many({})

    # 유사도 결과 저장 준비
    bulk_data = []
    for idx, doc in enumerate(documents):
        similarities = [
            {"similarPost": documents[jdx]["postId"], "similarity": float(score)}
            for jdx, score in enumerate(similarity_matrix[idx]) if idx != jdx
        ]

        bulk_data.append({
            "postId": doc["postId"],
            "similarPosts": similarities,
            "updatedAt": doc["updatedAt"]
        })

    if bulk_data:
        similarity_collection.insert_many(bulk_data)

    return {"message": "Similarity calculations stored successfully in MongoDB."}


