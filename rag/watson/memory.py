import os
import typing
from server.db import mongo_client, Database
from langgraph.checkpoint.mongodb import MongoDBSaver

if typing.TYPE_CHECKING:
    from rag.watson import Watson


checkpointer = MongoDBSaver(mongo_client,
                            db_name=os.getenv("DB_NAME"),
                            checkpoint_collection_name="chat_bot_checkpoints",
                            writes_collection_name="chat_bot_checkpoint_writes",)

def clear_checkpointer(thread_id: int) -> None:
    Database.Collection.CHATBOT_CHECKPOINTS.delete_many({"thread_id": thread_id})
    Database.Collection.CHATBOT_CHECKPOINT_WRITES.delete_many({"thread_id": thread_id})

class MemoryMethods:
    def clear_memory(self: 'Watson') -> None:
        clear_checkpointer(self.id)
