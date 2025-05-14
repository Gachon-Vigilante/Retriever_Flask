"""Watson RAG 시스템에서 사용하는 상수 및 데이터베이스 컬렉션 정의 모듈.

Attributes:
    chatbot_collection: 챗봇 메타데이터 컬렉션
    chat_collection: 채널 대화 데이터 컬렉션
    channel_collection: 채널 정보 컬렉션
    checkpoints_collection: 챗봇 체크포인트 컬렉션
    checkpoint_writes_collection: 챗봇 체크포인트 기록 컬렉션
    dimension_size: 임베딩 차원 크기
    weaviate_index_name: Weaviate 인덱스 이름
    weaviate_headers: 외부 API 키 헤더
"""
import os

from server.db import Database

# 모든 챗봇의 메타데이터를 가져와서 초기화.
chatbot_collection = Database.Collection.CHATBOT
chat_collection = Database.Collection.Channel.DATA
channel_collection = Database.Collection.Channel.INFO
checkpoints_collection = Database.Collection.CHATBOT_CHECKPOINTS
checkpoint_writes_collection = Database.Collection.CHATBOT_CHECKPOINT_WRITES

dimension_size = 1536

weaviate_index_name = "TelegramMessages"
# weaviate_index_name = "TelegramMessagesInstructor"

weaviate_headers={
    "X-OpenAI-Api-Key": os.getenv("OPENAI_API_KEY"),
    "X-HuggingFace-Api-Key": os.getenv("HUGGINGFACE_API_KEY"),
    "X-Cohere-Api-Key": os.getenv("COHERE_APIKEY"),
}