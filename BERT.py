import re
from fastapi import FastAPI, Form
from pydantic import BaseModel #json형식으로 받을때 필요한 import
from transformers import AutoTokenizer, AutoModel
import torch
from sklearn.metrics.pairwise import cosine_similarity

# FastAPI 애플리케이션 생성
app = FastAPI()

# BERT 모델과 토크나이저 로드
tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
model = AutoModel.from_pretrained("bert-base-uncased")

def preprocess_text(text):
    """
    입력 텍스트를 전처리
    - 조사, 따옴표, 특수문자 제거
    """
    # 특수문자 제거
    text = re.sub(r'[^\w\s]', '', text)
    # 공백 여러 개를 하나로 축소
    text = re.sub(r'\s+', ' ', text)
    # 소문자로 변환
    text = text.lower()
    return text.strip()

def get_bert_embedding(text, model, tokenizer):
    """
    입력 텍스트를 BERT 임베딩으로 변환
    """
    # 전처리된 텍스트 사용
    text = preprocess_text(text)
    # 토크나이징
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
    with torch.no_grad():
        outputs = model(**inputs)
    # CLS 토큰의 벡터를 사용 (첫 번째 벡터)
    return outputs.last_hidden_state[:, 0, :].numpy()

def calculate_similarity(text1, text2):
    """
    두 텍스트 간의 코사인 유사도 계산
    """
    # 텍스트 임베딩 생성
    embedding1 = get_bert_embedding(text1, model, tokenizer)
    embedding2 = get_bert_embedding(text2, model, tokenizer)

    # 코사인 유사도 계산
    similarity = cosine_similarity(embedding1, embedding2)
    # numpy.float32를 일반 float로 변환하여 반환
    return float(similarity[0][0])

# 유사도 계산 API 엔드포인트
@app.post("/calculate_similarity/")
async def calculate_text_similarity(
        text1: str = Form(...),
        text2: str = Form(...),
):
    similarity_score = calculate_similarity(text1, text2)
    return {"similarity_score": similarity_score}

# json형식으로 받기
# class Texts(BaseModel):
#     text1: str
#     text2: str
# @app.post("/calculate_similarity/")
# async def calculate_text_similarity(texts: Texts):
#     similarity_score = calculate_similarity(texts.text1, texts.text2)
#     return {"similarity_score": similarity_score}
