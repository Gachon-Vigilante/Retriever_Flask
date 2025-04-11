import os
from typing import Any, Mapping, Union

import pymongo
from dotenv import load_dotenv
from pymongo.synchronous.collection import Collection
from pymongo.synchronous.database import Database

load_dotenv()

def get_mongo_connection_string() -> str:
    return (f"mongodb://{os.environ.get('DB_USERNAME')}"
            f":{os.environ.get('DB_PASSWORD')}"
            f"@{os.environ.get('DB_IP')}"
            f":{os.environ.get('DB_PORT')}/")

mongo_client = pymongo.MongoClient(get_mongo_connection_string()) # MongoDB 클라이언트 생성

db_name = os.environ.get('DB_NAME')
db_object: Database = mongo_client[os.environ.get('DB_NAME')]

class Database:
    class Collection:
        class Channel:
            INFO: Collection = db_object["channel_info"]
            DATA: Collection = db_object["channel_data"]
            SIMILARITY: Collection = db_object["channel_similarity"]
        CHANNEL: Collection = Channel
        DRUGS: Collection = db_object["drugs"]
        ARGOT: Collection = db_object["argot"]
        CHATBOT: Collection = db_object["chat_bot"]
        POST: Collection = db_object["posts"]
        POST_SIMILARITY: Collection = db_object["post_similarity"]

    COLLECTION = Collection
    OBJECT = db_object
    NAME = db_name

DB = Database