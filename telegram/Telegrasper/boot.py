import typing

from .channel import get_all_active_channels

if typing.TYPE_CHECKING:
    from .manager import TelegramManager

class OnBootMethods:
    def __init__(self: 'TelegramManager'):
        self.resume_monitoring()

    def resume_monitoring(self: 'TelegramManager'):
        for channel_id in get_all_active_channels():
            self.start_monitoring(channel_id)


