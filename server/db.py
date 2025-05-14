import os
from typing import Any, Mapping, Union

import pymongo
from dotenv import load_dotenv
from pymongo.synchronous.collection import Collection
from pymongo.synchronous.database import Database

load_dotenv()

def get_mongo_connection_string() -> str:
    return os.getenv("MONGO_CONNECTION_STRING")

mongo_client = pymongo.MongoClient(get_mongo_connection_string()) # MongoDB 클라이언트 생성

db_name = os.getenv('MONGO_DB_NAME')
db_object: Database = mongo_client[db_name]

class Database:
    class Collection:
        class Channel:
            INFO: Collection = db_object["channel_info"]
            DATA: Collection = db_object["channel_data"]
            SIMILARITY: Collection = db_object["channel_similarity"]
        DRUGS: Collection = db_object["drugs"]
        ARGOT: Collection = db_object["argot"]
        CHATBOT: Collection = db_object["chat_bot"]
        CHATBOT_CHECKPOINTS: Collection = db_object["chat_bot_checkpoints"]
        CHATBOT_CHECKPOINT_WRITES: Collection = db_object["chat_bot_checkpoint_writes"]
        POST: Collection = db_object["posts"]
        POST_HTML: Collection = db_object["post_html"]
        POST_CLUSTERS: Collection = db_object["post_clusters"]
        POST_SIMILARITY: Collection = db_object["post_similarity"]
        REPORTS: Collection = db_object["reports"]

    OBJECT = db_object
    NAME = db_name