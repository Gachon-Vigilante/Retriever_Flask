"""텔레그램 매니저의 메인 클래스를 정의하는 모듈."""
import asyncio
import typing

from . import (ConnectMethods, ChannelMethods, TelegramBaseManager, OnBootMethods)


class TelegramManager(ConnectMethods, ChannelMethods, TelegramBaseManager, OnBootMethods):
    """텔레그램 채널 관리의 핵심 기능을 제공하는 메인 클래스입니다.
    
    MRO(Method Resolution Order)에 따라 TelegramBaseManager로 초기화 후 OnBootMethods가 실행됩니다.
    이 순서가 뒤집히면 OnBootMethods에서 오류가 발생할 수 있습니다.
    """
    # MRO에 따라 TelegramBaseManager로 초기화 후 -> OnBootMethods가 실행됨. 이 순서가 뒤집히면 OnBootMethods에서 오류 발생.
    def __init__(self):
        super().__init__()