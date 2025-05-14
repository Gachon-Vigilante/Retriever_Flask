import asyncio
import typing

from . import (ConnectMethods, ChannelMethods, TelegramBaseManager, OnBootMethods)


class TelegramManager(ConnectMethods, ChannelMethods, TelegramBaseManager, OnBootMethods):
    # MRO에 따라 TelegramBaseManager로 초기화 후 -> OnBootMethods가 실행됨. 이 순서가 뒤집히면 OnBootMethods에서 오류 발생.
    def __init__(self):
        super().__init__()