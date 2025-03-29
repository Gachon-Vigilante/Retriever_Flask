from flask import Blueprint, request, jsonify
from . import post, post_similarity
from .channel import calculate_and_store_similarity
from .post import dbscan_clustering, collection, db, perform_clustering_with_cosine

# Blueprint 설정
cluster_bp = Blueprint('cluster', __name__, url_prefix='/cluster')

# '/post.py' 엔드포인트
@cluster_bp.route('/post', methods=['POST'])
def post_clustering():
    if not request.is_json:
        return jsonify({"error": "Request must be in JSON format"}), 400

    data = request.json
    eps = data.get('eps', 0.4)  # 기본값 수정
    min_samples = data.get('min_samples', 2)

    try:
        result = perform_clustering_with_cosine(eps, min_samples)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# '/post_similarity.py' 엔드포인트
@cluster_bp.route('/post_similarity', methods=['POST'])
def post_similarity_calculation():
    try:
        result = calculate_and_store_similarity()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# '/channel.py' 엔드포인트
@cluster_bp.route('/channels', methods=['POST'])
def analyze_channels():
    if not request.is_json:
        return jsonify({"error": "Request must be in JSON format"}), 400
    try:
        result = calculate_and_store_similarity()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500