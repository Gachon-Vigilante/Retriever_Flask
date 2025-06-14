"""텔레그램 채널 모니터링 및 첩보 등록 기능을 제공하는 모듈."""
import asyncio
import typing
from datetime import datetime, timezone

from telethon import events
from telethon.errors import ChatForwardsRestrictedError as ChatForwardsRestrictedError1
from telethon.errors.rpcerrorlist import ChatForwardsRestrictedError as ChatForwardsRestrictedError2

from ai.telegram import get_reports_by_openai, Report
from server.db import Database
from .channelscraper import process_message
from .utils import *
from server.logger import logger

if typing.TYPE_CHECKING:
    from .manager import TelegramManager


# 채팅 로그 파일 경로
log_file_path = "channel_messages.log"

class ChannelContentMonitorMethods:
    """텔레그램 채널의 메시지 모니터링 및 이벤트 핸들러 관리 메서드를 제공하는 클래스입니다."""
    def __init__(self):
        self.monitoring_task_map, self.event_handlers_map = {}, {}
        super().__init__()

    async def periodic_message(self:'TelegramManager', user_id):
        """특정 user id로 정기적인 심장박동 메시지를 보내는 비동기 함수 (현재 미사용)."""
        while True:
            await self.client.send_message(user_id, 'Periodic status message')
            await asyncio.sleep(43200)
    
    async def monitor_channel(self:'TelegramManager', channel_key:typing.Union[int, str]):
        """특정 채널의 메시지를 실시간으로 모니터링하는 비동기 함수입니다.

        Args:
            channel_key (int|str): 모니터링할 채널의 ID 또는 키
        """
        # 새로운 이벤트 핸들러 정의 (채널별로 별도 핸들러를 생성하기 위해, 함수 내에서 동적으로 선언)
        async def event_handler(event):
            """메시지 발생 시 반응하는 이벤트 핸들러 비동기 함수."""
            chat = await event.get_chat()
            # 이벤트가 채팅방 이벤트이고, 메세지가 있고, 해당 메세지가 아직 수집되지 않은 것일 때에만
            if chat and event.message:
                message, sender = event.message, await event.get_sender()
                await process_message(chat, self.client, message)

                if message.text and entity.id and message.id:
                    reports = get_reports_by_openai(message.text)
                    register_reports(entity.id, message.id, reports)

                sender = extract_sender_info(sender)
                # 메세지를 나에게 포워딩
                try:
                    await self.client.forward_messages(self.my_user_id, event.message)
                except ChatForwardsRestrictedError1 and ChatForwardsRestrictedError2:
                    logger.warning("This chat has message forwarding restricted.")
                    if message.text:
                        await self.client.send_message(self.my_user_id, message.text)
                    if message.media:
                        await self.client.send_file(self.my_user_id, message.media)
                    if not message.text and not message.media:
                        await self.client.send_message(self.my_user_id, "[Unsupported message type]")

                logger.info(
                    f"Target(ID: {sender.get('id')}, name: {sender.get('name')}) spoke. time: {message.date.strftime('%Y-%m-%d %H:%M:%S')}")
    
        try:
            # 채널 엔티티 가져오기
            entity = await self.connect_channel(channel_key)
            if entity:
                logger.debug(f"Monitoring channel - Channel Name: {entity.title}, Channel ID: {entity.id}")  # https://t.me/<channel_username>의 채널 ID 출력

                # 이벤트 핸들러 저장 및 등록
                self.event_handlers_map[channel_key] = event_handler
                self.client.add_event_handler(event_handler, events.NewMessage(chats=entity.id))
        except asyncio.CancelledError:
            logger.info(f"Task for {channel_key} was cancelled. Cleaning up...")
        except Exception as e:
            logger.error(f"Error in monitor_channel(): {e}")
    
    
    def start_monitoring(self:'TelegramManager', channel_key:typing.Union[int, str]):
        """특정 채널 모니터링을 시작하는 동기 함수입니다.

        Args:
            channel_key (int|str): 모니터링할 채널의 ID 또는 키
        """
        try:
            if channel_key in self.monitoring_task_map:
                logger.warning(f"Already monitoring {channel_key}")
                return
            self.monitoring_task_map[channel_key] = asyncio.run_coroutine_threadsafe(
                self.monitor_channel(channel_key), self.loop)
            logger.info(f"Started monitoring {channel_key}")
        except Exception as e:
            logger.error(f"Error in start_monitoring(): {e}")
    
    
    def stop_monitoring(self:'TelegramManager', channel_key:typing.Union[int, str]):
        """특정 채널 모니터링을 중단하는 함수입니다.

        Args:
            channel_key (int|str): 모니터링을 중단할 채널의 ID 또는 키
        """
        if channel_key in self.monitoring_task_map:
            # 1. 모니터링 Task 취소(모니터링 시작 Task가 실행되고 있었을 경우에 대비하기 위함)
            self.monitoring_task_map[channel_key].cancel()

            # 2. 등록된 이벤트 핸들러 제거
            if channel_key in self.event_handlers_map:
                self.client.remove_event_handler(self.event_handlers_map[channel_key])
                del self.event_handlers_map[channel_key]
            
            # 3. 모니터링 Task 제거
            del self.monitoring_task_map[channel_key]
    
            logger.info(f"Stopped monitoring {channel_key}")
        else:
            logger.warning(f"No active monitoring found for {channel_key}")

    
# 메시지를 파일에 저장하는 비동기 함수
def save_message_to_file(sender_name, sender_id, message_text, timestamp):
    """메시지를 파일에 저장합니다.

    Args:
        sender_name (str): 발신자 이름
        sender_id (int|str): 발신자 ID
        message_text (str): 메시지 내용
        timestamp (str): 메시지 타임스탬프
    """
    with open(log_file_path, "a", encoding="utf-8") as file:
        log_entry = f"[{timestamp}] Sender: {sender_name} (ID: {sender_id}), Message: {message_text}\n"
        file.write(log_entry)


def register_reports(channel_id:int, chat_id:int, reports: list[Report]):
    """AI 분석 결과(첩보)를 DB에 저장합니다.

    Args:
        channel_id (int): 채널 ID
        chat_id (int): 채팅 ID
        reports (list[Report]): 첩보 리스트
    """
    for report in reports:
        Database.Collection.REPORTS.insert_one({
            "channelId": channel_id,
            "chatId": chat_id,
            "type": report.report_type,
            "content": report.report_content,
            "description": report.report_description,
            "timestamp": datetime.now(tz=timezone.utc),
        })
        logger.info(f"새로운 첩보를 입수, 데이터베이스에 저장했습니다. Channel ID: {channel_id}, Chat ID: {chat_id}, Report: {report}")
