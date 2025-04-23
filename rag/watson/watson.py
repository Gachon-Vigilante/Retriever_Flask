from server.logger import logger

from .constants import chatbot_collection
from .base import BaseWatson
from .graph import LangGraphMethods
from .memory import MemoryMethods
from .mongodb import MongoDBMethods
from .vectorstore import VectorStoreMethods


class AutoCreateInstances(type):
    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)
        cls._instances = {}
        for document in chatbot_collection.find():
            cls._instances[document.get('_id')] = cls(bot_id=document.get('_id'))

        logger.info(f"데이터베이스에 있는 챗봇을 모두 로드했습니다. 로드된 챗봇: {list(cls._instances.keys())}")

class Watson(BaseWatson, VectorStoreMethods, LangGraphMethods, MongoDBMethods, MemoryMethods, metaclass=AutoCreateInstances):
    pass