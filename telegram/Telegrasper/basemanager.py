"""텔레그램 클라이언트의 기본 관리자 클래스를 정의하는 모듈."""
import asyncio
import threading

from telethon import TelegramClient

from . import details as ds
from server.logger import logger

# details 모듈에서 가져오기
api_id = ds.apiID
api_hash = ds.apiHash
phone = ds.number


class TelegramBaseManager:
    """텔레그램 클라이언트를 백그라운드 스레드에서 생성하고 관리하는 싱글톤 클래스입니다.

    이 클래스는 다음과 같은 특징을 가집니다:

    1. 단 하나의 인스턴스
    - 싱글톤 클래스는 인스턴스를 하나만 생성하며, 동일한 인스턴스가 여러 번 호출되더라도 동일한 객체를 반환합니다.
    - 이를 통해 메모리 낭비를 방지하고, 프로그램의 여러 부분에서 같은 객체를 일관되게 사용할 수 있습니다.

    2. 전역적 접근
    - 싱글톤 인스턴스는 어디서든지 접근이 가능하며, 보통 애플리케이션 전체에서 공유됩니다.
    - 데이터베이스 연결, 로그 파일, 애플리케이션 설정 등을 다룰 때 아주 유용합니다.

    3. 지연 초기화 (Lazy Initialization)
    - 싱글톤 객체는 필요할 때(즉, 처음 호출될 때)만 인스턴스를 생성하는 방식으로 초기화되며, 초기화가 늦춰지는 경우가 많습니다.
    - 때문에 메모리 자원을 절약하는 데 유리합니다.

    Telethon 라이브러리의 TelegramClient 객체는 비동기 작업을 수행하기 위해 자체적으로 Event Loop를 이용합니다.
    Asyncio의 구조상 Event Loop는 Thread-specific하기 때문에 새로운 스레드에서 비동기 작업을 Asyncio로 실행하려면
    그 스레드에서 새로운 Event Loop를 생성하고 실행해야 합니다.
    Flask 서버는 새로운 요청이 들어올 때마다 Thread를 새로 생성해서 대응하므로, 각 Thread에서 Telethon의 비동기 작업을 수행하려면
    그 Thread에서 따로 Event Loop를 생성한 후 생성된 Event Loop에서 작업을 수행해야 합니다.
    그러나, Telethon 라이브러리에서는 Deadlock 현상을 방지하기 위해
    TelegramClient이 생성 및 연결되었을 당시의 Thread와 Event Loop과 현재 작업을 수행하는 Thread와 Event Loop이
    완벽히 똑같지 않으면 오류를 내도록 구현되어 있습니다.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """싱글톤 객체의 핵심 구현 메서드입니다.

        Returns:
            TelegramBaseManager: 싱글톤 인스턴스
        """
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(TelegramBaseManager, cls).__new__(cls)

        return cls._instance

    def __init__(self):
        """싱글톤 객체의 초기화 메서드입니다.
        
        백그라운드 스레드에서는 새로운 이벤트 루프를 생성하고 클라이언트를 초기화하며,
        메인 스레드에서는 기존 값을 유지하거나 None으로 초기화합니다.
        """
        with self._lock:
            # 현재 실행 흐름이 백그라운드 스레드일 경우, 루프를 만들고 클라이언트를 초기화한다.
            if threading.current_thread() is not threading.main_thread():
                background_loop = asyncio.new_event_loop()  # 백그라운드 스레드에서 새 이벤트 루프 생성
                asyncio.set_event_loop(background_loop)  # 새 루프를 설정

                self.loop = background_loop
                background_loop.run_until_complete(self.start_client())
                self.my_user_id = background_loop.run_until_complete(self.get_me())
                super().__init__()
            else:
                # 만약 현재 실행 흐름이 백그라운드 스레드가 아닐 경우(메인 스레드일 경우), 기존 값이 있으면 그대로 두고 없으면 None으로 초기화한다.
                self.client = getattr(self, "client", None)
                self.my_user_id = getattr(self, "my_user_id", None)
                self.loop = getattr(self, "loop", None)

    async def start_client(self) -> None:
        """텔레그램 클라이언트를 초기화하고 시작하는 비동기 메서드입니다.

        Raises:
            RuntimeWarning: 메인 스레드에서 실행될 경우
            ValueError: 이벤트 루프가 없는 경우
            TypeError: 이벤트 루프가 올바른 타입이 아닌 경우
        """
        if threading.current_thread() is threading.main_thread():
            message = "Telegram Singleton을 메인 스레드에서 실행하고 있습니다. Flask 서버가 제대로 실행되지 않을 수 있습니다."
            logger.warning(message)
            raise RuntimeWarning(message)
        if not self.loop:
            message = "Loop를 생성하지 않은 상태로 텔레그램 클라이언트를 시작하려고 시도했습니다."
            logger.critical(message)
            raise ValueError(message)
        elif not isinstance(self.loop, asyncio.AbstractEventLoop):
            message = "Loop가 이벤트 루프 객체(AbstractEventLoop)가 아닌 상태로 텔레그램 클라이언트를 시작하려고 시도했습니다."
            logger.critical(message)
            raise TypeError(message)

        # 세션 파일 경로 설정 (Docker 환경에서도 작동하도록)
        session_name = f"/app/telegram_session_{ds.number}"
        self.client = TelegramClient(session_name, ds.apiID, ds.apiHash, loop=self.loop)
        
        # 비대화형 모드로 시작 (Docker 환경에서 필요)
        await self.client.start(phone=lambda: ds.number)

        logger.info("Telegram Client started.")

    async def get_me(self):
        """현재 클라이언트의 사용자 정보를 가져오는 비동기 메서드입니다.

        Returns:
            int: 현재 클라이언트의 사용자 ID

        Raises:
            ValueError: 클라이언트가 초기화되지 않은 경우
        """
        if self.client is None:
            error_message = "텔레그램 클라이언트가 아직 초기화되지 않은 상태에서 클라이언트의 유저 정보를 가져오려고 시도했습니다."
            logger.critical(error_message)
            raise ValueError(error_message)

        me = await self.client.get_me()
        logger.info(f"Your Telegram Client Name: {me.first_name}")
        logger.info(f"Your Telegram Client User ID: {me.id}")
        self.my_user_id = me.id
        return me.id