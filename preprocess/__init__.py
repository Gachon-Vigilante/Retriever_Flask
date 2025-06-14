from flask import Blueprint, request, jsonify
from utils import confirm_request

from . import extractor
from .ai_extractor import extract_promotion_by_openai

preprocess_bp = Blueprint('preprocess', __name__, url_prefix='/preprocess')

# 수집한 웹 홍보글 HTML에서 홍보글의 내용 부분을 추출하는 API
@preprocess_bp.route("/extract/web-promotion", methods=["POST"])
def extract_web_promotion_by_algorithm():
    """알고리즘을 사용하여 HTML에서 홍보 내용을 추출합니다.

    Request Body:
        html (str): 분석할 HTML 문서 문자열

    Returns:
        tuple: (JSON 응답, HTTP 상태 코드)
            - 성공 시: (추출된 내용 딕셔너리, 200)
            - 실패 시: (에러 메시지, 400 또는 500)
    """
    data = request.json
    if response_for_invalid_request := confirm_request(data, {
        'html': str
    }):
        return response_for_invalid_request

    try:
        # 요청에서 HTML 텍스트 가져오기
        html = request.get_json().get("html", "")

        # HTML에서 텍스트 블록 추출
        result = extractor.extract_promotion_content(html)
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@preprocess_bp.route("/extract/web-promotion/openai", methods=["POST"])
def extract_web_promotion_by_openai():
    """OpenAI API를 사용하여 HTML에서 홍보 내용을 추출합니다.

    Request Body:
        html (str): 분석할 HTML 문서 문자열

    Returns:
        tuple: (JSON 응답, HTTP 상태 코드)
            - 성공 시: (추출된 내용 딕셔너리, 200)
            - 실패 시: (에러 메시지, 400 또는 500)
    """
    data = request.json
    if response_for_invalid_request := confirm_request(data, {
        'html': str
    }):
        return response_for_invalid_request

    try:
        # 요청에서 HTML 텍스트 가져오기
        html = request.get_json().get("html", "")

        result = extract_promotion_by_openai(html) # HTML에서 홍보글 여부, 홍보글 내용, 링크까지 추출한 dictionary 얻기
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500