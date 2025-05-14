# import torch
# import numpy as np
# from sklearn.cluster import DBSCAN
# from sklearn.metrics.pairwise import cosine_similarity
# from transformers import AutoTokenizer, AutoModel
# from bs4 import BeautifulSoup
# from tqdm import tqdm
#
# from server.db import Database
#
#
# # MongoDB 연결
# collection = Database.Collection.POST
#
# # KoBERT 모델 불러오기
# model_name = "monologg/kobert"
# tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
# model = AutoModel.from_pretrained(model_name, trust_remote_code=True)
#
#
# # HTML 정제 함수
# def preprocess_html(html_content):
#     soup = BeautifulSoup(html_content, 'html.parser')
#     return soup.get_text(separator=' ').strip()
#
#
# # KoBERT 임베딩 추출
# def get_bert_embedding(text):
#     tokens = tokenizer(text, return_tensors="pt", truncation=True, max_length=512, padding="max_length")
#     with torch.no_grad():
#         output = model(**tokens)
#     return output.last_hidden_state[:, 0, :].squeeze().tolist()
#
#
# # 클러스터링 수행
# def dbscan_clustering(embeddings, eps=0.4, min_samples=2):
#     similarity_matrix = cosine_similarity(np.array(embeddings))
#     similarity_matrix = (similarity_matrix + 1) / 2  # 정규화: [-1, 1] → [0, 1]
#
#     distance_matrix = 1 - similarity_matrix
#     distance_matrix = np.clip(distance_matrix, 0, 1)  # 음수 방지
#
#     db = DBSCAN(metric="precomputed", eps=eps, min_samples=min_samples)
#     return db.fit_predict(distance_matrix)
#
#
# # 전체 클러스터링 프로세스
# def perform_clustering_with_cosine(eps=0.4, min_samples=2):
#     # 데이터 불러오기
#     documents = list(collection.find({}, {
#         "_id": 1, "postId": 1, "content": 1
#     }))
#
#     if not documents:
#         return {"error": "No documents found."}
#
#     # 임베딩 생성
#     embeddings = []
#     for doc in tqdm(documents, desc="Generating embeddings"):
#         text = preprocess_html(doc.get("content", ""))
#         embeddings.append(get_bert_embedding(text))
#
#     # 클러스터링
#     labels = dbscan_clustering(embeddings, eps, min_samples)
#
#     # posts 컬렉션에 결과 업데이트
#     for idx, doc in enumerate(documents):
#         update_fields = {
#             "cluster_label": int(labels[idx]),
#             "embedding": embeddings[idx]
#         }
#         collection.update_one(
#             {"_id": doc["_id"]},
#             {"$set": update_fields}
#         )
#
#     return {
#         "message": "Clustering 결과가 posts 컬렉션에 저장되었습니다.",
#         "total_documents": len(documents),
#         "noise_documents": list(labels).count(-1)
#     }

#-------------------------------------------------------------------------------
# from transformers import AutoTokenizer, AutoModel
# import torch
# import numpy as np
# from sklearn.cluster import DBSCAN
# from sklearn.metrics.pairwise import cosine_similarity
# from bs4 import BeautifulSoup
# from tqdm import tqdm
#
# from server.db import Database
#
# # MongoDB 연결
# collection = Database.Collection.POST
#
# # ✅ KLUE RoBERTa 모델 로드
# model_name = "klue/roberta-base"
# tokenizer = AutoTokenizer.from_pretrained(model_name)
# model = AutoModel.from_pretrained(model_name)
# model.eval()  # 평가모드
#
# # HTML 정제
# def preprocess_html(html_content):
#     soup = BeautifulSoup(html_content, 'html.parser')
#     return soup.get_text(separator=' ').strip()
#
# # ✅ 임베딩 함수 (pooler_output 사용)
# def get_bert_embedding(text):
#     tokens = tokenizer(text, return_tensors="pt", truncation=True, max_length=512, padding="max_length")
#     with torch.no_grad():
#         outputs = model(**tokens)
#         # pooler_output은 전체 문장 의미 요약
#         return outputs.pooler_output.squeeze().tolist()
#
# # DBSCAN 클러스터링
# def dbscan_clustering(embeddings, eps=0.4, min_samples=2):
#     similarity_matrix = cosine_similarity(np.array(embeddings))
#     similarity_matrix = (similarity_matrix + 1) / 2
#     distance_matrix = 1 - similarity_matrix
#     distance_matrix = np.clip(distance_matrix, 0, 1)
#     db = DBSCAN(metric="precomputed", eps=eps, min_samples=min_samples)
#     return db.fit_predict(distance_matrix)
#
# # 전체 클러스터링
# def perform_clustering_with_cosine(eps=0.4, min_samples=2):
#     documents = list(collection.find({}, {
#         "_id": 1, "postId": 1, "content": 1
#     }))
#     if not documents:
#         return {"error": "No documents found."}
#
#     embeddings = []
#     for doc in tqdm(documents, desc="Generating embeddings"):
#         text = preprocess_html(doc.get("content", ""))
#         embeddings.append(get_bert_embedding(text))
#
#     labels = dbscan_clustering(embeddings, eps, min_samples)
#
#     for idx, doc in enumerate(documents):
#         update_fields = {
#             "cluster_label": int(labels[idx]),
#             "embedding": embeddings[idx]
#         }
#         collection.update_one({"_id": doc["_id"]}, {"$set": update_fields})
#
#     return {
#         "message": "Clustering 결과가 posts 컬렉션에 저장되었습니다.",
#         "total_documents": len(documents),
#         "noise_documents": list(labels).count(-1)
#     }
# -----------------------------------------------------------------------
# import torch
# import numpy as np
# import hdbscan
# from sklearn.metrics.pairwise import cosine_similarity
# from transformers import AutoTokenizer, AutoModel
# from bs4 import BeautifulSoup
# from tqdm import tqdm
#
# from server.db import Database
#
#
# # MongoDB 연결
# collection = Database.Collection.POST
#
# # KoBERT 모델 불러오기
# model_name = "monologg/kobert"
# tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
# model = AutoModel.from_pretrained(model_name, trust_remote_code=True)
#
#
# # HTML 정제 함수
# def preprocess_html(html_content):
#     soup = BeautifulSoup(html_content, 'html.parser')
#     return soup.get_text(separator=' ').strip()
#
#
# # KoBERT 임베딩 추출
# def get_bert_embedding(text):
#     tokens = tokenizer(text, return_tensors="pt", truncation=True, max_length=512, padding="max_length")
#     with torch.no_grad():
#         output = model(**tokens)
#     return output.last_hidden_state[:, 0, :].squeeze().tolist()
#
#
# # HDBSCAN 클러스터링
# def hdbscan_clustering(embeddings, min_cluster_size=5):
#     similarity_matrix = cosine_similarity(np.array(embeddings))
#     similarity_matrix = (similarity_matrix + 1) / 2  # 정규화: [-1, 1] → [0, 1]
#
#     distance_matrix = 1 - similarity_matrix
#     distance_matrix = np.clip(distance_matrix, 0, 1)  # 음수 방지
#
#     # HDBSCAN 클러스터링
#     clusterer = hdbscan.HDBSCAN(metric="precomputed", min_cluster_size=min_cluster_size)
#     labels = clusterer.fit_predict(distance_matrix)
#
#     return labels
#
#
# # 전체 클러스터링 프로세스
# def perform_clustering_with_cosine(min_cluster_size=2):
#     # 데이터 불러오기
#     documents = list(collection.find({}, {
#         "_id": 1, "postId": 1, "content": 1
#     }))
#
#     if not documents:
#         return {"error": "No documents found."}
#
#     # 임베딩 생성
#     embeddings = []
#     for doc in tqdm(documents, desc="Generating embeddings"):
#         text = preprocess_html(doc.get("content", ""))
#         embeddings.append(get_bert_embedding(text))
#
#     # 클러스터링
#     labels = hdbscan_clustering(embeddings, min_cluster_size)
#
#     # posts 컬렉션에 결과 업데이트
#     for idx, doc in enumerate(documents):
#         update_fields = {
#             "cluster_label": int(labels[idx]),
#             "embedding": embeddings[idx]
#         }
#         collection.update_one(
#             {"_id": doc["_id"]},
#             {"$set": update_fields}
#         )
#
#     return {
#         "message": "Clustering 결과가 posts 컬렉션에 저장되었습니다.",
#         "total_documents": len(documents),
#         "noise_documents": list(labels).count(-1)
#     }
#-----------------------------------------------------------------------
import numpy as np
import hdbscan
from matplotlib import pyplot as plt
from sklearn.metrics.pairwise import cosine_similarity
from bs4 import BeautifulSoup
from tqdm import tqdm
from sentence_transformers import SentenceTransformer

from server.db import Database

# MongoDB 연결
collection = Database.Collection.POST

# ✔️ Ko-SBERT 모델 불러오기
model = SentenceTransformer('snunlp/KR-SBERT-V40K-klueNLI-augSTS')


# HTML 정제 함수
def preprocess_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    return soup.get_text(separator=' ').strip()


# ✔️ Ko-SBERT 임베딩 추출
def get_bert_embedding(text):
    return model.encode(text)


# HDBSCAN 클러스터링
def hdbscan_clustering(embeddings, min_cluster_size=5):
    similarity_matrix = cosine_similarity(np.array(embeddings))
    similarity_matrix = (similarity_matrix + 1) / 2  # 정규화: [-1, 1] → [0, 1]

    distance_matrix = 1 - similarity_matrix
    distance_matrix = np.clip(distance_matrix, 0, 1)  # 음수 방지

    clusterer = hdbscan.HDBSCAN(metric="precomputed", min_cluster_size=min_cluster_size)
    labels = clusterer.fit_predict(distance_matrix)

    # 📈 Minimum Spanning Tree 시각화
    clusterer.minimum_spanning_tree_.plot(edge_cmap='viridis', edge_alpha=0.6, node_size=20)
    plt.title("Minimum Spanning Tree of HDBSCAN")
    plt.show()

    return labels


# 전체 클러스터링 프로세스
def perform_clustering_with_cosine(min_cluster_size=2):
    documents = list(collection.find({}, {
        "_id": 1, "postId": 1, "content": 1
    }))

    if not documents:
        return {"error": "No documents found."}

    embeddings = []
    for doc in tqdm(documents, desc="Generating embeddings"):
        text = preprocess_html(doc.get("content", ""))
        embeddings.append(get_bert_embedding(text))

    labels = hdbscan_clustering(embeddings, min_cluster_size)

    for idx, doc in enumerate(documents):
        update_fields = {
            "cluster_label": int(labels[idx]),
            "embedding": embeddings[idx]
        }
        collection.update_one(
            {"_id": doc["_id"]},
            {"$set": update_fields}
        )

    return {
        "message": "Clustering 결과가 posts 컬렉션에 저장되었습니다.",
        "total_documents": len(documents),
        "noise_documents": list(labels).count(-1)
    }
