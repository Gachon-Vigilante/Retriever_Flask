"""Watson RAG 시스템의 메모리 관리 및 체크포인트 관련 기능 모듈.

Attributes:
    checkpointer: LangGraph MongoDBSaver 인스턴스
"""
import os
import typing
from server.db import mongo_client, db_name, Database
from langgraph.checkpoint.mongodb import MongoDBSaver
from .constants import checkpoints_collection, checkpoint_writes_collection

if typing.TYPE_CHECKING:
    from rag.watson import Watson


checkpointer = MongoDBSaver(mongo_client,
                            db_name=db_name,
                            checkpoint_collection_name="chat_bot_checkpoints",
                            writes_collection_name="chat_bot_checkpoint_writes",)


class MemoryMethods:
    """챗봇의 메모리(체크포인트) 관리 메서드를 제공하는 클래스입니다."""
    def clear_memory(self: 'Watson') -> None:
        """MongoDB에 저장된 챗봇의 기억을 제거하는 메서드.

        Returns:
            None
        """
        checkpoints_collection.delete_many({"thread_id": self.id})
        checkpoint_writes_collection.delete_many({"thread_id": self.id})
