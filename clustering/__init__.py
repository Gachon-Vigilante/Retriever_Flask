from flask import Blueprint, request, jsonify
from . import post, post_similarity
from .channel import calculate_and_store_channel_similarity
from .drug_stat import drug_time, drug_type
from .post import dbscan_clustering, collection, perform_clustering_with_cosine
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

@cluster_bp.route('/drug-type', methods=['GET'])
def drug_usage_by_type():
    data = drug_type()
    return jsonify(data)

@cluster_bp.route('/drug-time', methods=['GET'])
def drug_usage_over_time():
    period = request.args.get('period', 'monthly')  # 'weekly' or 'monthly'
    data = drug_time(period=period)
    return jsonify(data)