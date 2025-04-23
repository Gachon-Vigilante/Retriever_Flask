from flask import Blueprint, request, jsonify
from typing import Optional
from utils import confirm_request
from . import crawler
from . import serpapi

crawl_bp = Blueprint('crawl', __name__, url_prefix='/crawl')
@crawl_bp.route('/links', methods=["POST"])
def crawl_web_links():
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
    data = request.json
    if not data or 'link' not in data:
        return jsonify({"error": "Please provide 'link' in the request arguments."}), 400

    try:

        result = crawler.get_html_from_url(data['link'])
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500