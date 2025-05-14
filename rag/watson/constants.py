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