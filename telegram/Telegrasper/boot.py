import typing

from server.logger import logger
from .channel import get_all_active_channels

if typing.TYPE_CHECKING:
    from .manager import TelegramManager

class OnBootMethods:
    def __init__(self: 'TelegramManager'):
        self.resume_monitoring()

    def resume_monitoring(self: 'TelegramManager'):
        all_channels = get_all_active_channels()
        logger.info(f"데이터베이스에 저장된 모든 채널에 대해 모니터링을 시작합니다. 채널 개수: {len(all_channels)}")
        for channel_id in all_channels:
            self.start_monitoring(channel_id)


