import typing
from os.path import exists, join

import faiss
from bson import ObjectId
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.document_loaders import MongodbLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

from server.db import get_mongo_connection_string, Database
from server.logger import logger
from .constants import vectorstore_dir, dimension_size

if typing.TYPE_CHECKING:
    from rag.watson import Watson


class VectorStoreMethods:
    def initialize_vectorstore(self: 'Watson') -> FAISS:
        """
            데이터베이스에서 채팅 데이터가 변경되었는지 확인하고,
            현재 메모리에 로드된 채팅 데이터에서 변경된 사항이 있다면 메모리의 벡터스토어를 업데이트한다.
            또한, 메모리의 벡터스토어에 기반하는 그래프(LangGraph)도 다시 구축한다.
        """
        folder_path = self.get_vectorstore_folder_path()
        if exists(join(folder_path, 'index.faiss')) and exists(join(folder_path, 'index.pkl')):
            local_vectorstore: FAISS = self._load_vectorstore()
        else:
            local_vectorstore: FAISS = FAISS(
                embedding_function=self.embedding,
                index=faiss.IndexFlatL2(dimension_size),
                docstore=InMemoryDocstore(),
                index_to_docstore_id={}
            )

        return local_vectorstore

    def _load_vectorstore(self: 'Watson') -> FAISS:
        """
            Notice for allow_dangerous_deserialization parameters of FAISS.load_local():

            The de-serialization relies on loading a pickle file.
            Pickle files can be modified to deliver a malicious payload
            that results in execution of arbitrary code on your machine.
            You will need to set `allow_dangerous_deserialization` to `True` to enable deserialization.
            If you do this, make sure that you trust the source of the data.
            For example, if you are loading a file that you created, and know that no one else has modified the file,
            then this is safe to do.
            Do not set this to `True` if you are loading a file from an untrusted source
            (e.g., some random site on the internet.).
        """
        # load_vectorstore가 호출되었다면 변경사항이 없다는 뜻이므로, 객체에 저장된 vectorstore가 있다면 재사용 가능
        # 만약 객체에 저장된 vectorstore가 없다면, load_local로 불러오기 시도.
        return FAISS.load_local(folder_path=self.get_vectorstore_folder_path(),
                                embeddings=self.embedding,
                                allow_dangerous_deserialization=True)

    def save_vectorstore(self: 'Watson'):
        try:
            self.vectorstore.save_local(folder_path=self.get_vectorstore_folder_path())
        except Exception as e:
            logger.error(f"An error occurred while saving vectorstore to local: {e}")


    def update_vectorstore(self: 'Watson'):
        ##### 단계 1: 문서 로드(Load Documents) #####
        # vectorstore에 저장된 모든 _id(ObjectId) 확인
        ids_in_vectorstore = {
            doc.metadata.get("_id")
            for doc_id in self.vectorstore.index_to_docstore_id.values()
            for doc in [self.vectorstore.docstore.search(doc_id)]
            if "_id" in doc.metadata
        }

        # MongoDB에는 있지만 vectorstore에는 반영되지 않은 _id 확인
        missing_chats = [oid for oid in self.chats if oid not in ids_in_vectorstore]
        # 새로 넣어야 할 문서의 id로 loader를 생성하고 문서 로드
        loader = self.build_loader(missing_chats)
        docs = loader.load()
        if docs: # 문서 목록이 비어 있지 않을 때만 추가(비어 있을 경우 add_documents() 에서 오류 발생)
            ##### 단계 2: 문서 분할(Split Documents) #####
            logger.debug(
                f"Splitting loaded chat documents from MongoDB. Channel IDs: {self.channels}, scope: {self.scope}")
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=50)
            split_documents = text_splitter.split_documents(docs)

            # 단계 3: 임베딩(Embedding) 생성
            # 임베딩을 생성한다.
            # embedding = OpenAIEmbeddings()  # -> self.embedding 으로 저장한다음 바로 참조하기 때문에 생략됨

            # 단계 4: DB 생성(Create DB) 및 저장
            # 벡터스토어를 생성하고, 저장한다.

            logger.debug(f"Adding documents to the vectorstore. Channel IDs: {self.channels}, scope: {self.scope}")
            self.vectorstore.add_documents(documents=split_documents)
            self.save_vectorstore()

            # chatbot collection에서 chatIds를 수집된 채팅의 ID로 업데이트
            logger.debug(f"Updating chatbot metadata. Channel IDs: {self.channels}, scope: {self.scope}")
            self.update_db() # MongoDB에서 현재 챗봇의 정보 업데이트 (없을 경우 신규 생성)
            self._update_graph()


    @staticmethod
    def build_loader(ids: list[ObjectId]) -> MongodbLoader:
        return MongodbLoader(
            connection_string=get_mongo_connection_string(),
            db_name=Database.NAME,
            collection_name=Database.Collection.Channel.DATA.name,
            filter_criteria={"_id": {"$in": ids}, "text": {"$ne": ""}},  # 데이터베이스에서 조회할 기준 (쿼리). 빈 텍스트가 아닌 채팅만 읽음. 빈 텍스트도 불러올 경우 벡터화 과정에서 오류 발생
            field_names=("text",),
            metadata_names=("_id", "channelId", "id", "timestamp", "views", "url"),  # 메타데이터로 지정할 필드 목록
        )

    def get_vectorstore_folder_path(self: 'Watson'):
        return join(vectorstore_dir, str(self.id))
