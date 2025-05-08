import os
import weaviate


class WeaviateClientContext:
    def __enter__(self):
        self.client = weaviate.connect_to_local(
            headers={
                "X-OpenAI-Api-Key": os.getenv("OPENAI_API_KEY")
            },
        )
        return self.client

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self.client, "close"):
            self.client.close()