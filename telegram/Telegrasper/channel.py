import asyncio
import typing
import datetime
from pymongo.errors import DuplicateKeyError

from server.db import Database
from server.logger import logger
from server.cypher import run_cypher, Neo4j
from .channelscraper import ChannelContentMethods
from .monitor import ChannelContentMonitorMethods

if typing.TYPE_CHECKING:
    from .manager import TelegramManager

class ChannelMethods(ChannelContentMethods, ChannelContentMonitorMethods):
    def get_channel_info(self:'TelegramManager',
                         channel_key:typing.Union[int, str],
                         ) -> dict:
        collection = Database.Collection.Channel.INFO  # 컬렉션 선택
        entity = asyncio.run_coroutine_threadsafe(self.connect_channel(channel_key), self.loop).result()

        if not entity:
            return {}

        channel_info = {
            "_id": entity.id,
            "title": entity.title,
            "username": entity.username,
            "restricted": entity.restricted, # 채널에 제한이 있는지 여부 (boolean)
            "startedAt": entity.date, # 채널이 생성된 일시 (datetime.datetime)
            "discoveredAt": datetime.datetime.now(), # 채널이 처음으로 발견된 일시
            "status": "active" if self.check(entity) else "inactive",
        }

        ##### Neo4j #####
        if channel_info["status"] == "active":
            # 채널 노드가 데이터베이스에 없을 경우 추가
            summary = run_cypher(query=Neo4j.QueryTemplate.Node.Channel.MERGE,
                                 parameters={
                                     "id": channel_info["_id"],
                                     "title": channel_info["title"],
                                     "username": channel_info["username"],
                                     "status": channel_info["status"],
                                 }).consume()
            if summary.counters.nodes_created > 0:
                logger.info(f"새로운 마약 판매 채널이 발견되어 Neo4j 데이터베이스에 추가되었습니다. 발견된 채널의 ID: {entity.id}, 제목: `{entity.title}`")

        ##### MongoDB #####
        try:
            collection.insert_one(channel_info.copy())  # 데이터 삽입. copy()를 하지 않으면 mongoClient가 channel_info 원본 딕셔너리에 ObjectId를 삽입함.
        except DuplicateKeyError:
            logger.warning(f"Tried to archive a channel which is already archived. Channel ID: {entity.id}, title: {entity.title}, ")
            # collection.update_one({"_id": entity.id},
            #                       channel_info.copy()) # <- 아카이브 정책을 어떻게 할지 고민해 봐야 함.
        except Exception as exception:
            logger.error(f"Error occurred while inserting data into MongoDB: {exception}")
        else:
            logger.info(f"Archived a new channel metadata in MongoDB - DB: {Database.NAME}, collection: channel_info")

        return channel_info


def is_channel_empty(channel_id) -> bool:
    """채널 ID에 해당하는 채널의 채팅 데이터가 있는지 여부를 조사하는 함수. 데이터가 없을 때 True 반환."""
    chat_collection = Database.Collection.Channel.DATA
    # 채널 ID를 기준으로 모든 채팅을 찾아서 각 채팅의 채팅 ID를 리스트로 생성
    return False if chat_collection.find_one({"channelId": channel_id}) else True

def get_all_active_channels() -> list[int]:
    """현재 status: active인 모든 채널의 ID를 불러오는 함수."""
    channel_collection = Database.Collection.Channel.INFO
    return [channel_info["_id"] for channel_info in channel_collection.find({"status": "active"})]