from langchain_openai import OpenAIEmbeddings

from server.db import Database

# 모든 챗봇의 메타데이터를 가져와서 초기화.
chatbot_collection = Database.Collection.CHATBOT
chat_collection = Database.Collection.Channel.DATA
checkpoints_collection = Database.Collection.CHATBOT_CHECKPOINTS
checkpoint_writes_collection = Database.Collection.CHATBOT_CHECKPOINT_WRITES

from os.path import join, dirname
from .local_vectorstore import __file__ as f
vectorstore_dir = join(dirname(f))

dimension_size = 1536

weaviate_index_name = "TelegramMessages"