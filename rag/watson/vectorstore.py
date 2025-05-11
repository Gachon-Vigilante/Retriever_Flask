import typing
from datetime import datetime
from typing import Optional

from bson import ObjectId
from langchain_community.document_loaders import MongodbLoader
from langchain_weaviate import WeaviateVectorStore
from weaviate.classes.config import Configure, Property, DataType
from weaviate.classes.query import Filter
from weaviate.client import WeaviateClient

from server.db import get_mongo_connection_string, Database
from server.logger import logger
from .constants import weaviate_index_name
from .weaviate import connect_weaviate, WeaviateClientContext

if typing.TYPE_CHECKING:
    from rag.watson import Watson

class VectorStoreMethods:
    @staticmethod
    def get_vectorstore(weaviate_client:Optional[WeaviateClient]=None):
        # 먼저 스키마 등록
        with WeaviateClientContext() as client:
            VectorStoreMethods.register_schema(client)

        return WeaviateVectorStore(
            client=weaviate_client if weaviate_client else connect_weaviate(),
            index_name=weaviate_index_name,
            text_key="text",
        )

    @staticmethod
    def register_schema(weaviate_client: WeaviateClient) -> None:
        # 먼저 클래스가 존재하는지 확인
        if weaviate_index_name in weaviate_client.collections.list_all().keys():
            logger.info("TelegramMessages already exists in Weaviate.")
            return

        weaviate_client.collections.create(
            weaviate_index_name,
            description="Telegram channel messages with metadata",
            reranker_config=Configure.Reranker.cohere(),
            vectorizer_config=Configure.Vectorizer.text2vec_openai(),
            properties=[  # properties configuration is optional
                Property(name="objectId", data_type=DataType.TEXT),
                Property(name="text", data_type=DataType.TEXT),
                Property(name="channelId", data_type=DataType.INT),
                Property(name="chatId", data_type=DataType.INT),
                Property(name="timestamp", data_type=DataType.DATE),
                Property(name="views", data_type=DataType.INT),
                Property(name="url", data_type=DataType.TEXT),
                Property(name="sender", data_type=DataType.OBJECT,
                         nested_properties=[
                             Property(name="type", data_type=DataType.TEXT, ),
                             Property(name="name", data_type=DataType.TEXT, ),
                             Property(name="senderId", data_type=DataType.INT),
                         ], ),
            ]
        )
        logger.info("TelegramMessages schema is created in Weaviate.")

    def update_vectorstore(self: 'Watson'):
        with WeaviateClientContext() as weaviate_client:
            weaviate_client.connect()
            ##### 1. Weaviate에서 channelId 필터로 모든 _id 가져오기 #####
            weaviate_ids: set[str] = set()

            for channel_id in self.channels:
                collection = weaviate_client.collections.get(weaviate_index_name)
                response = collection.query.fetch_objects(
                    filters=Filter.by_property("channelId").equal(channel_id),
                    limit=10000, # 10000이 최대인듯. 100000으로 하면 query maximum result exceeded 오류 발생
                )

                # 중복 제거용 dict: {(channelId, chatId): [uuid1, uuid2, ...]}
                duplicates: dict[int, list[str]] = {}

                for o in response.objects:
                    props = o.properties or {}
                    uuid = o.uuid
                    chat_id = props.get("chatId")
                    weaviate_ids.add(props.get("objectId"))

                    # 누락 방지
                    if channel_id is None or chat_id is None or uuid is None:
                        continue
                    
                    # channelId와 chatId가 중복되는 object의 uuid를 기록
                    duplicates.setdefault(chat_id, []).append(uuid)

                # 중복된 (channelId, chatId) 조합에서 첫 번째를 제외한 나머지를 삭제
                for chat_id, uuid_list in duplicates.items():
                    if len(uuid_list) > 1:
                        # 첫 번째는 유지, 나머지 삭제
                        to_delete = uuid_list[1:]
                        if to_delete:
                            logger.warning(
                                f"Deleting duplicate Weaviate object: "
                                f"channelId={channel_id}, "
                                f"chatId={chat_id}, "
                                f"uuid=(survived: {uuid_list[0]}, killed: {to_delete})")
                            collection.data.delete_many(
                                where=Filter.by_id().contains_any(to_delete)
                            )

            ##### 2. MongoDB에서 전체 _id 리스트 확보 #####
            mongo_ids = {str(chat_id) for chat_id in self.chats}

            ##### 3. 차집합: MongoDB에는 있고 Weaviate에는 없는 _id #####
            missing_chat_ids = [ObjectId(oid) for oid in (mongo_ids - weaviate_ids)]

            ##### 4. MongoDB에서 문서 로딩 후 Weaviate에 추가 #####
            if missing_chat_ids:
                with self.build_loader(missing_chat_ids) as loader:
                    if docs := loader.load(): # 문서 목록이 비어 있지 않을 때만 추가(비어 있을 경우 add_documents() 에서 오류 발생)
                        ##### 단계 2: 문서 분할(Split Documents) ##### -> 채팅 데이터가 크지 않아서 필요 없음.
                        # logger.debug(
                        #     f"Splitting loaded chat documents from MongoDB. Channel IDs: {self.channels}, scope: {self.scope}")
                        # text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=50)
                        # split_documents = text_splitter.split_documents(docs)

                        # 단계 3: 임베딩(Embedding) 생성
                        # 임베딩을 생성한다.
                        # embedding = OpenAIEmbeddings()  # -> self.embedding 으로 저장한다음 바로 참조하기 때문에 생략됨

                        # 단계 4: DB 생성(Create DB) 및 저장
                        # 벡터스토어를 생성하고, 저장한다.
                        logger.debug(f"Adding documents to the vectorstore. Channel IDs: {self.channels}, scope: {self.scope}")
                        self.vectorstore.add_documents(docs)

                        # chatbot collection에서 chatIds를 수집된 채팅의 ID로 업데이트
                        logger.debug(f"Updating chatbot metadata. Channel IDs: {self.channels}, scope: {self.scope}")
                        self._update_graph()

            if weaviate_client.batch.failed_objects:
                for failed in weaviate_client.batch.failed_objects:
                    logger.error(f"Failed to insert documents into weaviate: {failed}")

            self.update_db()  # MongoDB에서 현재 챗봇의 정보 업데이트 (없을 경우 신규 생성)


    @staticmethod
    def build_loader(ids: list[ObjectId]) -> MongodbLoader:
        return MappedMongodbLoader(
            connection_string=get_mongo_connection_string(),
            db_name=Database.NAME,
            collection_name=Database.Collection.Channel.DATA.name,
            filter_criteria={"_id": {"$in": ids}, "text": {"$ne": ""}},  # 데이터베이스에서 조회할 기준 (쿼리). 빈 텍스트가 아닌 채팅만 읽음. 빈 텍스트도 불러올 경우 벡터화 과정에서 오류 발생
            field_names=("text",),
            metadata_names=("_id", "text", "channelId", "id", "timestamp", "views", "sender", "url"),  # 메타데이터로 지정할 필드 목록
            metadata_mapping={
                "_id": "objectId",
                "id": "chatId",
            },
            include_db_collection_in_metadata=False, # weaviate의 properties에는 database, collection 필드를 지정하지 않았음. 즉 여기서도 제외해야 함.
        )


from bson import ObjectId
from typing import Dict, List, Optional, Sequence

from langchain_core.documents import Document

class MappedMongodbLoader(MongodbLoader):
    def __init__(
            self,
            connection_string: str,
            db_name: str,
            collection_name: str,
            *,
            filter_criteria: Optional[Dict] = None,
            field_names: Optional[Sequence[str]] = None,
            metadata_names: Optional[Sequence[str]] = None,
            metadata_mapping: Optional[Dict[str, str]] = None,
            include_db_collection_in_metadata: bool = True,
    ) -> None:
        self.metadata_mapping = metadata_mapping or {}

        super().__init__(
            connection_string=connection_string,
            db_name=db_name,
            collection_name=collection_name,
            filter_criteria=filter_criteria,
            field_names=field_names,
            metadata_names=metadata_names,
            include_db_collection_in_metadata=include_db_collection_in_metadata,
        )

    async def aload(self) -> List[Document]:
        """Asynchronously loads data into Document objects with renamed metadata."""
        result = []
        total_docs = await self.collection.count_documents(self.filter_criteria)
        projection = self._construct_projection()

        async for doc in self.collection.find(self.filter_criteria, projection):
            raw_metadata = self._extract_fields(doc, self.metadata_names, default="")

            # 필드명을 매핑된 키로 변환
            metadata = {}
            for k, v in raw_metadata.items():
                new_key = self.metadata_mapping.get(k, k)
                if k == "_id":
                    metadata[new_key] = str(v)
                elif isinstance(v, datetime):
                    # RFC3339 타입. weaviate에서는 date 속성에 대해 이 타입의 문자열을 기대하기 때문에, 이렇게 하지 않으면 에러 발생
                    metadata[new_key] = v.isoformat(timespec="seconds") + "Z"  
                else:
                    metadata[new_key] = v

            if self.include_db_collection_in_metadata:
                metadata.update(
                    {
                        "database": self.db_name,
                        "collection": self.collection_name,
                    }
                )

            if self.field_names is not None:
                fields = self._extract_fields(doc, self.field_names, default="")
                texts = [str(value) for value in fields.values()]
                text = " ".join(texts)
            else:
                text = str(doc)

            result.append(Document(page_content=text, metadata=metadata))

        if len(result) != total_docs:
            logger.warning(
                f"Only partial collection of documents returned. "
                f"Loaded {len(result)} docs, expected {total_docs}."
            )

        return result

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.client.close()
