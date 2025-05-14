import torch
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_similarity
from transformers import AutoTokenizer, AutoModel
from bs4 import BeautifulSoup
from tqdm import tqdm

from server.db import Database

# MongoDB 연결
collection = Database.Collection.POST

# KoBERT 모델 불러오기
model_name = "monologg/kobert"
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
model = AutoModel.from_pretrained(model_name, trust_remote_code=True)


# HTML 정제 함수
def preprocess_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    return soup.get_text(separator=' ').strip()


# KoBERT 임베딩 추출
def get_bert_embedding(text):
    tokens = tokenizer(text, return_tensors="pt", truncation=True, max_length=512, padding="max_length")
    with torch.no_grad():
        output = model(**tokens)
    return output.last_hidden_state[:, 0, :].squeeze().tolist()


# 신규 게시글 클러스터링
def clustering_for_new_posts(eps=0.4):
    new_posts = list(collection.find({"cluster_label": {"$exists": False}}, {"_id": 1, "html": 1}))
    if not new_posts:
        return {"message": "새 게시글 없음"}

    existing_docs = list(collection.find({"cluster_label": {"$ne": -1}}, {"embedding": 1, "cluster_label": 1}))

    if not existing_docs:
        existing_embeddings = []
        existing_labels = []
        next_label = 0
    else:
        existing_embeddings = [doc["embedding"] for doc in existing_docs]
        existing_labels = [doc["cluster_label"] for doc in existing_docs]
        next_label = max(existing_labels) + 1

    for post in tqdm(new_posts, desc="Incremental clustering"):
        text = preprocess_html(post["html"])
        new_embedding = get_bert_embedding(text)

        if existing_embeddings:
            similarities = cosine_similarity([new_embedding], existing_embeddings)[0]
            max_sim_idx = np.argmax(similarities)
            max_sim = similarities[max_sim_idx]

            if max_sim >= (1 - eps):
                new_label = existing_labels[max_sim_idx]
            else:
                new_label = next_label
                next_label += 1
        else:
            new_label = 0
            next_label += 1

        collection.update_one(
            {"_id": post["_id"]},
            {
                "$set": {
                    "embedding": new_embedding,
                    "cluster_label": new_label
                }
            }
        )

        existing_embeddings.append(new_embedding)
        existing_labels.append(new_label)

    return {
        "message": f"{len(new_posts)}개의 새 게시글 클러스터링 완료"
    }

