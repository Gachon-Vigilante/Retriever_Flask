"""텔레그램 API 인증 정보를 관리하는 모듈입니다.

이 모듈은 환경 변수에서 텔레그램 API ID, API Hash, 전화번호 등의 인증 정보를 로드합니다.
"""
import os
from dotenv import load_dotenv

load_dotenv()

apiID = os.environ["TELEGRAM_API_ID"]
apiHash = os.environ["TELEGRAM_API_HASH"]
number = os.environ["PHONE_NUMBER"]
