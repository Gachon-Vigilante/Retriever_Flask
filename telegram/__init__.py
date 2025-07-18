from flask import Blueprint, request, jsonify

from server.logger import logger
from utils import confirm_request
from .Telegrasper.manager import TelegramManager
from .Telegrasper.catalog import update_catalog

import threading
import typing

singleton_ready = threading.Event()  # 이벤트 객체 생성
telegram_manager = TelegramManager()


def init_telegram_singleton():
    """ 백그라운드 스레드에서 실행되는 텔레그램 클라이언트 초기화 함수 """
    the_telegram_manager = TelegramManager() # 여기서는 백그라운드 호출이기 때문에, Singleton 객체에서
    singleton_ready.set()  # 이벤트 트리거: (백그라운드 스레드에서) 싱글톤의 준비가 완료되었음을 이벤트로 알림
    try:
        the_telegram_manager.loop.run_forever()  # 백그라운드에서 루프 계속 실행
    finally:
        the_telegram_manager.client.disconnect() # 루프가 종료될 때(run_forever이므로, 서버 종료 시) 연결 종료


# 별도의 스레드에서 실행
threading.Thread(target=init_telegram_singleton, daemon=True).start()
singleton_ready.wait()  # 싱글톤의 텔레그램 클라이언트가 전부 준비될 때까지 대기

telegram_bp = Blueprint('telegram', __name__, url_prefix='/telegram')

@telegram_bp.route('/channel/info', methods=['POST'])
def connect_channel():
    logger.info("텔레그램 채널 정보 조회 API 호출됨.")
    data = request.json
    if response_for_invalid_request := confirm_request(data,
                                                       {
                                                           'channel_key': typing.Union[int, str],
                                                       }):
        return response_for_invalid_request

    try:
        return jsonify(telegram_manager.get_channel_info(data['channel_key'])), 200
    except Exception as e:
        logger.error(f"{type(e)}: {str(e)}")
        return jsonify({"error": str(e)}), 500


@telegram_bp.route('/channel/disconnect', methods=['POST'])
def disconnect_channel():
    # TODO: 텔레그램 채널에의 참가를 해제하는 코드를 구현해야 함.
    pass


@telegram_bp.route('/channel/scrape', methods=['POST'])
def scrape_channel():
    logger.info("텔레그램 채널 스크랩 API 호출됨.")
    data = request.json
    if response_for_invalid_request := confirm_request(data, {'channel_key': typing.Union[int, str]}):
        return response_for_invalid_request

    channel_key = data['channel_key']
    try:
        return jsonify(telegram_manager.scrape(channel_key)), 200
    except Exception as e:
        logger.error(f"{type(e)}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@telegram_bp.route('/channel/check-suspicious', methods=['POST'])
def check_channel():
    logger.info("텔레그램 채널 검문 API 호출됨.")
    data = request.json
    if response_for_invalid_request := confirm_request(data, {'channel_key': typing.Union[int, str]}):
        return response_for_invalid_request

    channel_key = data['channel_key']
    check_result = telegram_manager.check(channel_key)
    try:
        return jsonify({"suspicious": check_result}), 200
    except Exception as e:
        logger.error(f"{type(e)}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@telegram_bp.route('/channel/monitoring', methods=['POST'])
def monitor_channel():
    logger.info("텔레그램 채널 모니터링 API 호출됨.")
    data = request.json
    if response_for_invalid_request := confirm_request(data, {
        'channel_key': typing.Union[int, str],
        'how': str
    }):
        return response_for_invalid_request

    try:
        channel_key = data['channel_key']
        how = data['how']
        if how == "start":
            telegram_manager.start_monitoring(channel_key)
        elif how == "stop":
            telegram_manager.stop_monitoring(channel_key)
        else:
            return jsonify({"error": "Invalid 'how'."}), 400

        return jsonify({"success": True}), 200
    except Exception as e:
        logger.error(f"{type(e)}: {str(e)}")
        return jsonify({"error": str(e)}), 500



@telegram_bp.route('/channel/catalog', methods=['POST'])
def write_catalog():
    """특정 채널의 가격 정보를 추가로 추출해서 저장한다."""
    data = request.json
    try:
        if response_for_invalid_request := confirm_request(data, {
            'channel_id': int,
        }):
            return response_for_invalid_request
        update_catalog(data['channel_id'])
        return jsonify({"success": True}), 200
    except Exception as e:
        logger.error(e)
        return jsonify({"error": e}), 500