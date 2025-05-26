from flask import Blueprint, jsonify, Response
from .channel import calculate_and_store_channel_similarity
from .channel_come_in import calculate_similarity_for_new_channels
from .post import perform_clustering_with_cosine
from .post_come_in import clustering_for_new_posts
from .post_similarity import post_similarity
# Blueprint 설정
cluster_bp = Blueprint('cluster', __name__, url_prefix='/cluster')

# '/post.py' 엔드포인트
@cluster_bp.route('/post', methods=['POST'])
# def post_clustering():
#     try:
#         result = perform_clustering_with_cosine()
#         return jsonify(result), 200
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500
def post_clustering():
    try:
        result = perform_clustering_with_cosine()
        # 만약 결과가 Flask Response 객체면 (즉, 이미지 등 binary data)
        if isinstance(result, Response):
            return result
        # 아니면 JSON 응답으로 처리
        else:
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

# '/post_come_in.py' 엔드포인트
@cluster_bp.route('/post_update', methods=['POST'])
def update_new_post():
    result = clustering_for_new_posts()
    return jsonify(result), 200

