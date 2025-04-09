import asyncio
import re
import typing
import os

from pymongo import MongoClient

from preprocess.extractor import argot_dictionary
from server.db import get_mongo_client, DB
from server.logger import logger
from server.google import *

from .utils import download_media, extract_sender_info, get_url_from_message

default_bucket_name = os.environ.get('GCS_BUCKET_NAME')

if typing.TYPE_CHECKING:
    from .manager import TelegramManager

class ChannelContentMethods:
    async def check_channel_content(self:'TelegramManager', channel_key:typing.Union[int, str]) -> bool:
        """채널의 데이터를 일부 수집해서, 마약 관련 채널로 강력히 의심되는지 확인하는 검문 메서드."""
        try:
            logger.debug(f"Connecting to channel: {channel_key}")
            entity = await self.connect_channel(channel_key)
            if entity is None:
                logger.warning("Failed to connect to the channel.")
                return False

            # 메시지 확인
            post_count = 0
            suspicious_count = 0
            async for post in self.client.iter_messages(entity):
                post_count += 1
                if post.text:
                    # 메세지에서 은어가 총 3개 이상 발견되면 활성 채널로 분류
                    suspicious_count += sum([len(re.findall(re.escape(keyword), post.text)) for keyword in argot_dictionary])
                    if suspicious_count >= 3:
                        return True
                    # 100개 이내의 채팅에 은어가 3개 이상 없을 경우 탐색을 종료하고 비활성 채널로 분류
                    if post_count > 100:
                        return False


        except Exception as e:
            logger.error(f"An error occurred in check_channel_content(): {e}")
            return False

        return False


    # 채널 내의 데이터를 스크랩하는 함수
    async def scrape_channel_content(self:'TelegramManager', channel_key:typing.Union[int, str]) -> dict:
        logger.debug(f"Connecting to channel: {channel_key}")
        try:
            entity = await self.connect_channel(channel_key)
            if entity is None:
                logger.warning("Failed to connect to the channel.")
                return {"status": "warning",
                        "message": "Failed to connect to the channel."}
            # 메시지 스크랩
            post_count = 0

            # GCS 버킷에 채팅방 ID로 폴더 생성
            create_folder(default_bucket_name, entity.id)

            # MongoDB client 생성
            mongo_client = get_mongo_client()

            async for message in self.client.iter_messages(entity):
                post_count += 1
                if post_count % 10 == 0:
                    logger.info(f"{post_count} Posts is scraped from {channel_key}")

                await process_message(entity, self.client, message, mongo_client)

        except Exception as e:
            msg = f"An error occurred in scrape_channel_content(): {e}"
            logger.error(msg)
            return {"status": "error",
                    "message": msg}

        else:
            msg = (f"Archived all chats for the channel(Channel key: {channel_key}) in MongoDB - "
                   f"DB: {DB.NAME}, collection: {DB.COLLECTION.CHANNEL.DATA}, channel ID: {entity.id}")
            logger.info(msg)
            return {"status": "success",
                    "message": msg}


    # 채널 데이터 수집을 동기적으로 실행하는 동기 래퍼(wrapper) 함수
    def scrape(self:'TelegramManager', channel_key: typing.Union[int, str]) -> dict:
        future = asyncio.run_coroutine_threadsafe(self.scrape_channel_content(channel_key), self.loop)
        return future.result()  # 블로킹 호출 (결과를 기다림)

    # 채널 데이터 의심도 검증을 동기적으로 실행하는 동기 래퍼(wrapper) 함수
    def check(self:'TelegramManager', channel_key: typing.Union[int, str]) -> bool:
        future = asyncio.run_coroutine_threadsafe(self.check_channel_content(channel_key), self.loop)
        return future.result()  # 블로킹 호출 (결과를 기다림)


async def process_message(entity, client, message, mongo_client:MongoClient) -> None:
    chat_collection = mongo_client[DB.NAME][DB.COLLECTION.CHANNEL.DATA]  # 채팅 컬렉션 선택
    argot_collection = mongo_client[DB.NAME][DB.COLLECTION.ARGOT] # 은어 컬렉션 선택
    drugs_collection = mongo_client[DB.NAME][DB.COLLECTION.DRUGS] # 마약류 컬렉션 선택

    # channelId 필드와 id 필드를 기준으로 이미 채팅이 수집되었는지 검사한 후, 아직 수집되지 않았을 경우에만 삽입
    if not chat_collection.find_one({"channelId": entity.id, "id": message.id}):
        media_data, media_type = await download_media(message, client)
        if media_data:
            try:
                media = {"url": upload_bytes_to_gcs(bucket_name=default_bucket_name,
                                                    folder_name=entity.id,
                                                    file_name=message.id,
                                                    file_bytes=media_data,
                                                    content_type=media_type),
                         "type": media_type}
            except Exception as e:
                logger.error(f"An error occurred in process_message(), while uploading media to Google Cloud Storage: {e}")
                media = None
            else:
                logger.debug(f"Successfully uploaded media to Google Cloud Storage. (Media type: {media_type})")
        else:
            media = None

        argot_list, drugs_list = [], []
        # 은어가 메세지에서 발견될 경우 해당 은어와 그 은어에 대응하는 마약류를 channel data로  같이 삽입
        for argot in argot_collection.find():
            if message.text and argot.get("name") in message.text:
                argot_list.append(argot["_id"])
                drugs_list.append(drugs_collection.find_one({"_id": argot.get("drugId")}).get("_id"))

        if argot_list:
            logger.debug(f"Argot and Drugs are found in chat(chat ID: {message.id}, channel ID: {entity.id}). Argot: {argot_list}, Drugs: {drugs_list}")

        post_data = {
            "channelId": entity.id,
            "timestamp": message.date,
            "text": message.text or "",
            "sender": extract_sender_info(message.sender),
            "views": message.views or None,
            "url": get_url_from_message(entity, message),
            "id": message.id,
            "media": media,
            "argot": argot_list,
            "drugs": drugs_list,
        }

        chat_collection.insert_one(post_data)
        
    else: # 이미 수집된 채팅일 경우 경고 출력
        logger.warning(
            f"MongoDB collection already has same unique index of a chat(channelId: {entity.id}, id: {message.id})")




