from pymongo import MongoClient
import torch
from sklearn.metrics.pairwise import cosine_similarity
from transformers import AutoTokenizer, AutoModel
from bs4 import BeautifulSoup
import numpy as np

# MongoDB 연결 설정
client = MongoClient("mongodb://localhost:27017/")
db = client['local']
collection = db['train']
similarity_collection = db['post_similarity']  # 유사도 결과 저장 컬렉션

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

    # 평균 풀링 적용
    embedding = output.last_hidden_state.mean(dim=1).squeeze().tolist()
    return embedding

# 유사도 분석 및 저장
def calculate_and_store_similarity():
    documents = fetch_html_documents()
    embeddings = [get_bert_embedding(preprocess_html(doc["html"])) for doc in documents]

    similarity_matrix = cosine_similarity(np.array(embeddings))

    similarity_collection.delete_many({})  # 기존 데이터 초기화

    bulk_data = []  # MongoDB에 한 번에 저장할 리스트

    for idx, doc in enumerate(documents):
        similarities = [
            {"similarPost": documents[jdx]["postId"], "similarity": float(score)}
            for jdx, score in enumerate(similarity_matrix[idx]) if idx != jdx
        ]

        bulk_data.append({
            "postId": doc["postId"],  # `_id` 제거
            "similarPosts": similarities,
            "updatedAt": doc["updatedAt"]
        })

    # MongoDB에 한 번에 삽입
    if bulk_data:
        similarity_collection.insert_many(bulk_data)

    return {"message": "Similarity calculations stored successfully in MongoDB."}
