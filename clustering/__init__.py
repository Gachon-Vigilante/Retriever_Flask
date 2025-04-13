from flask import Blueprint, request, jsonify
from .channel import calculate_and_store_channel_similarity
from .channel_come_in import calculate_similarity_for_new_channels
from .post import perform_clustering_with_cosine
from .post_similarity import post_similarity
# Blueprint 설정
cluster_bp = Blueprint('cluster', __name__, url_prefix='/cluster')

# '/post.py' 엔드포인트
@cluster_bp.route('/post', methods=['POST'])
def post_clustering():
    if not request.is_json:
        return jsonify({"error": "Request must be in JSON format"}), 400

    data = request.json
    eps = data.get('eps', 0.4)  # 기본값은 0.4
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
        result = post_similarity()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# '/channel.py' 엔드포인트
@cluster_bp.route('/channels', methods=['POST'])
def calculate_similarity():
    result = calculate_and_store_channel_similarity()
    return jsonify(result), 200

# '/channel_come_in.py' 엔드포인트
@cluster_bp.route('/channel_update', methods=['POST'])
def update_new_channel():
    result = calculate_similarity_for_new_channels()
    return jsonify(result), 200

