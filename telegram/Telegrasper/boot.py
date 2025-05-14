"""텔레그램 매니저의 부팅 시 실행되는 메서드를 정의하는 모듈."""
import typing

from server.logger import logger
from .channel import get_all_active_channels

if typing.TYPE_CHECKING:
    from .manager import TelegramManager

class OnBootMethods:
    """텔레그램 매니저가 시작될 때 실행되는 메서드를 제공하는 클래스입니다."""
    
    def __init__(self: 'TelegramManager'):
        """초기화 메서드입니다. 부팅 시 모니터링을 재개합니다."""
        self.resume_monitoring()

    def resume_monitoring(self: 'TelegramManager'):
        """데이터베이스에 저장된 모든 활성 채널에 대한 모니터링을 재개합니다."""
        all_channels = get_all_active_channels()
        logger.info(f"데이터베이스에 저장된 모든 채널에 대해 모니터링을 시작합니다. 채널 개수: {len(all_channels)}")
        for channel_id in all_channels:
            self.start_monitoring(channel_id)


