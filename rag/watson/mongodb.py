import typing
from typing import Any
from datetime import datetime, timezone
from server.logger import logger
from .constants import chatbot_collection, channel_collection

if typing.TYPE_CHECKING:
    from . import Watson

class MongoDBMethods:
    """Watson 챗봇의 MongoDB 관련 메서드를 제공하는 클래스입니다."""
    def update_db(self: 'Watson'):
        """현재 챗봇의 정보(참조 중인 채팅 목록, 범위, 마지막 업데이트 일시)를 MongoDB에 갱신하거나 신규 생성합니다.

        Returns:
            None
        """
        try:
            chatbot_collection.update_one({"_id": self.id},
                                          {"$set": {
                                              "updatedAt": datetime.now(),
                                              "channels": list(self.channels),
                                              "chats": list(self.chats),
                                              "scope": self.scope,
                                          }}, upsert=True) # upsert=True -> 없을 경우 신규 생성
        except Exception as e:
            logger.error(f"An error occurred while updating chatbot metadata at MongoDB: {e}")

    def get_channel_info(self: 'Watson') -> dict[str, dict[str, Any]]:
        """챗봇이 참조하는 채널들의 정보를 반환합니다.

        Returns:
            dict: 채널 정보 딕셔너리
        """
        return {
            f"Channel #{i}": {
                "channel id": doc["_id"],
                "channel title": doc["title"],
                "this channel is created at": doc["startedAt"].replace(tzinfo=timezone.utc).isoformat(),
                "we discovered this channel at": doc["discoveredAt"].replace(tzinfo=timezone.utc).isoformat(),
            }
            for i, doc in enumerate(channel_collection.find({"_id": {"$in": self.channels}}))
        }