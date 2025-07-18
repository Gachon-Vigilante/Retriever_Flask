"""Weaviate 벡터스토어 연결 및 컨텍스트 관리 유틸리티 모듈."""
from dotenv import load_dotenv
import os
import weaviate
from weaviate import WeaviateClient

from .constants import weaviate_headers
load_dotenv()

weaviate_http_host=os.getenv("WEAVIATE_HTTP_HOST")
weaviate_http_port=int(os.getenv("WEAVIATE_HTTP_PORT"))
weaviate_grpc_host=os.getenv("WEAVIATE_GRPC_HOST")
weaviate_grpc_port=int(os.getenv("WEAVIATE_GRPC_PORT"))

def connect_weaviate() -> WeaviateClient:
    """로컬 Weaviate 인스턴스에 연결합니다.

    Returns:
        WeaviateClient: 연결된 Weaviate 클라이언트
    """
    return weaviate.connect_to_custom(
        http_host=weaviate_http_host,
        http_port=weaviate_http_port,
        http_secure=False,
        grpc_host=weaviate_grpc_host,
        grpc_port=weaviate_grpc_port,
        headers=weaviate_headers,
        grpc_secure=False,
    )


class WeaviateClientContext:
    """with 문에서 Weaviate 클라이언트 연결을 관리하는 컨텍스트 매니저 클래스입니다."""
    def __enter__(self):
        """컨텍스트 진입 시 Weaviate 클라이언트 연결을 반환합니다."""
        self.client = connect_weaviate()
        return self.client

    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 종료 시 클라이언트 연결을 닫습니다."""
        if hasattr(self.client, "close"):
            self.client.close()