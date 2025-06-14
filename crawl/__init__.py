from flask import Blueprint, request, jsonify
from typing import Optional
from utils import confirm_request
from . import crawler
from . import serpapi

crawl_bp = Blueprint('crawl', __name__, url_prefix='/crawl')
@crawl_bp.route('/links', methods=["POST"])
def crawl_web_links():
    """웹 검색을 수행하고 결과를 반환합니다.

    Request Body:
        queries (list[str]): 검색할 쿼리 문자열 목록
        max_results (int): 각 쿼리당 가져올 최대 검색 결과 수

    Returns:
        tuple: (JSON 응답, HTTP 상태 코드)
            - 성공 시: (검색 결과 딕셔너리, 200)
            - 실패 시: (에러 메시지, 400 또는 500)
    """
    data = request.json
    if response_for_invalid_request := confirm_request(data, {
        'queries': list[str],
        'max_results': int,
    }):
        return response_for_invalid_request

    try:
        
        result = crawler.search_links(data['queries'], data['max_results'])
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@crawl_bp.route('/links/serpapi', methods=["GET"])
def crawl_web_links_by_serpapi():
    """SerpAPI를 사용하여 웹 검색을 수행하고 결과를 반환합니다.

    Query Parameters:
        q (list[str]): 검색할 쿼리 문자열 목록
        max_results (int, optional): 각 쿼리당 가져올 최대 검색 결과 수

    Returns:
        tuple: (JSON 응답, HTTP 상태 코드)
            - 성공 시: (검색 결과 딕셔너리, 200)
            - 실패 시: (에러 메시지, 400 또는 500)
    """
    queries:list[str] = request.args.getlist("q")
    max_results:Optional[int] = request.args.get("max_results")
    if max_results:
        try:
            max_results = int(request.args.get("max_results"))
        except ValueError:
            return jsonify({"error": "parameter 'max_results' must be convertable to integer."}), 400

    try:
        result = serpapi.search_links_by_serpapi(queries, max_results)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@crawl_bp.route('/html', methods=["POST"])
def link_to_html():
    """URL에서 HTML 내용을 가져와 반환합니다.

    Request Body:
        link (str): HTML을 가져올 URL

    Returns:
        tuple: (JSON 응답, HTTP 상태 코드)
            - 성공 시: (HTML 내용, 200)
            - 실패 시: (에러 메시지, 400 또는 500)
    """
    data = request.json
    if not data or 'link' not in data:
        return jsonify({"error": "Please provide 'link' in the request arguments."}), 400

    try:
        result = crawler.get_html_from_url(data['link'])
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500