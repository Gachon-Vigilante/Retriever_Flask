from server.db import DB

# 모든 챗봇의 메타데이터를 가져와서 초기화.
chatbot_collection = DB.COLLECTION.CHATBOT
chat_collection = DB.COLLECTION.CHANNEL.DATA