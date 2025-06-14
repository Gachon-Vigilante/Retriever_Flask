import weaviate
from weaviate import WeaviateClient

from .constants import weaviate_headers


def connect_weaviate() -> WeaviateClient:
    return weaviate.connect_to_local(
        port=8888,
        headers=weaviate_headers,
    )


class WeaviateClientContext:
    def __enter__(self):
        self.client = connect_weaviate()
        return self.client

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self.client, "close"):
            self.client.close()