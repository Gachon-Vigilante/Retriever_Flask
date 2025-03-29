from pymongo import MongoClient
import torch
from sklearn.metrics.pairwise import cosine_similarity
from transformers import AutoTokenizer, AutoModel
import numpy as np

# MongoDB 연결 설정
client = MongoClient("mongodb://localhost:27017/")
db = client['local']
collection = db['train']
similarity_collection = db['channel_similarity']  # 유사도 결과 저장 컬렉션

# KoBERT 모델 및 토크나이저 로드
model_name = "monologg/kobert"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModel.from_pretrained(model_name)

drug_keywords = {
    '코카인': 3.0,
    '메스암페타민': 3.0,
    '펜타닐': 3.0,
    'LSD': 3.0,
    '엑스터시': 3.0,
    '순도': 2.0
}

# HTML 문서 불러오기
def fetch_html_documents():
    documents = collection.find({}, {"_id": 1, "channelId": 1, "timestamp": 1, "text": 1, "sender": 1, "views": 1, "url": 1, "id": 1, "media": 1, "argot": 1, "drugs": 1})
    return [{
        "_id": doc["_id"],
        "channelId": doc["channelId"],
        "timestamp": doc["timestamp"],
        "text": doc.get("text", ""),
        "sender": doc.get("sender", {}),
        "views": doc.get("views", 0),
        "url": doc.get("url", ""),
        "id": doc.get("id", 0),
        "media": doc.get("media", {}),
        "argot": doc.get("argot", []),
        "drugs": doc.get("drugs", [])
    } for doc in documents]

# 텍스트 전처리
def preprocess_text(text):
    return ' '.join(text.split()).strip()

# 가중치 적용 텍스트 전처리 (단어 가중치 적용)
def apply_keyword_weight(text):
    words = text.split()
    weighted_words = []
    for word in words:
        weight = drug_keywords.get(word, 1.0)
        weighted_words.extend([word] * int(weight))  # 최적화된 방식
    return ' '.join(weighted_words)

# KoBERT 임베딩 생성
def get_bert_embedding(text):
    tokens = tokenizer(text, return_tensors="pt", truncation=True, max_length=512, padding="max_length")
    with torch.no_grad():
        output = model(**tokens)
    return output.last_hidden_state[:, 0, :].squeeze().tolist()

# 유사도 분석 및 저장
def calculate_and_store_similarity():
    documents = fetch_html_documents()

    # 가중치 적용된 텍스트로 임베딩 생성
    weighted_embeddings = [get_bert_embedding(apply_keyword_weight(preprocess_text(doc["text"]))) for doc in documents]

    similarity_matrix = cosine_similarity(np.array(weighted_embeddings))

    similarity_collection.delete_many({})  # 기존 데이터 초기화

    similarity_data = []

    for idx, doc in enumerate(documents):
        similarities = []
        for jdx, score in enumerate(similarity_matrix[idx]):
            if idx != jdx:
                similarities.append({
                    "similarPost": documents[jdx]["channelId"],
                    "similarity": float(score)
                })

        similarity_data.append({
            "_id": doc["_id"],
            "channelId": doc["channelId"],
            "timestamp": doc["timestamp"],
            "text": doc["text"],
            "sender": doc["sender"],
            "views": doc["views"],
            "url": doc["url"],
            "id": doc["id"],
            "media": doc["media"],
            "argot": doc["argot"],
            "drugs": doc["drugs"],
            "similarChannels": similarities
        })

    # 최적화된 MongoDB 삽입
    for doc in similarity_data:
        doc.pop("_id", None)  # 기존 _id 제거
    similarity_collection.insert_many(similarity_data)

    return {"message": "Channel similarity calculations stored successfully in MongoDB."}
