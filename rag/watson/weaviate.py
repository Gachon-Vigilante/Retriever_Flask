"""Weaviate 벡터스토어 연결 및 컨텍스트 관리 유틸리티 모듈."""
import weaviate
from weaviate import WeaviateClient

from .constants import weaviate_headers


def connect_weaviate() -> WeaviateClient:
    """로컬 Weaviate 인스턴스에 연결합니다.

    Returns:
        WeaviateClient: 연결된 Weaviate 클라이언트
    """
    return weaviate.connect_to_local(
        port=8888,
        headers=weaviate_headers,
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