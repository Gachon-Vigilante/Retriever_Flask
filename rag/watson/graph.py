import typing
from typing import Any, Literal, Annotated, Sequence, TypedDict, Union, Optional

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, BaseMessage
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import create_retriever_tool, Tool
from langchain_openai import ChatOpenAI
from langchain_teddynote.models import get_model_name, LLMs
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field, Json

from server.db import Database
from server.logger import logger
from .indications import generate_by_channel, generate_by_others, generate_by_chats
from .memory import checkpointer

load_dotenv()

if typing.TYPE_CHECKING:
    from rag.watson import Watson

# 최신 모델이름 가져오기
MODEL_NAME = get_model_name(LLMs.GPT4o)
LIGHT_MODEL_NAME = get_model_name(LLMs.GPT4o_MINI)

DB_INFORMATION = """The MongoDB database contains information about Telegram channels and all chat messages sent and received within each channel.
The database contains two collections: `"channel_info"` for storing metadata of channel and `"channel_data"` for storing chat messages within channels. The schema for each collection is as follows:  
### **`channel_info` Collection**  
- **`_id`**: Integer. The unique ID of the channel.  
- **`title`**: String. The name of the channel.  
- **`username`**: String. The `@username` of the channel.  
- **`startedAt`**: Datetime. The date and time when the channel was created.  
- **`discoveredAt`**: Datetime. The date and time when the channel was discovered by this system.  
- **`updatedAt`**: Datetime. The date and time when the last chat message was updated.  

### **`channel_data` Collection**  
- **`channelId`**: Integer. The ID of the channel the chat belongs to. Linked to the `"id"` field in the `"channel_info"` collection.  
- **`text`**: String. The content of the chat message.  
- **`views`**: Integer. The number of views the chat message has received.  
- **`url`**: String. The URL of the chat message.  
- **`id`**: Integer. A unique ID that distinguishes each chat message within the channel."""


class Query(BaseModel):
    """JSON for database request"""
    collection: Literal["channel_info", "channel_data"] = Field(
        description="""Determine which collection to query. 
        If you need metadata of channel to answer the question(e.g. createdAt, discoveredAt, title), answer "channel_info".
        If you need chat data of channel to answer the question(e.g. recent chats, views), answer "channel_data". 
        """
    )
    pipeline: Json[list[dict[str, Any]]] = Field(
        description="The best aggregation pipeline of query to answer user question.")


# 에이전트 상태를 정의하는 타입 딕셔너리, 메시지 시퀀스를 관리하고 추가 동작 정의
class GraphState(TypedDict):
    # add_messages reducer 함수를 사용하여 메시지 시퀀스를 관리
    messages: Annotated[Sequence[BaseMessage], add_messages]
    question: Annotated[str, "Question"]  # 질문
    context: Annotated[Union[str, Sequence[BaseMessage]], "Context"]  # 문서의 검색 결과
    db_query: Annotated[Query, "Query"]  # 데이터베이스 쿼리
    answer: Annotated[str, "Answer"]  # 답변
    debug: Annotated[bool, "Debug"]
    type: Annotated[Literal["metadata", "data", "others"], "Type"]
    collection: Annotated[Literal["channel", "chats"], "Type"]


def update_state(state: GraphState, node_name: str, **updates) -> GraphState:
    """Graph의 State를 입력받고, 입력받은 State에서 **updates로 받은 딕셔너리를 반영해서 수정된 State를 반환하는 함수."""
    new_state: GraphState = state.copy()
    new_state.update(**updates)
    return new_state


def load_from_dict(data: dict, content_key: str, metadata_keys=None) -> Document:
    if metadata_keys is None:
        metadata_keys = []
    return Document(page_content=data[content_key],
                    metadata={key: data[key] for key in data.keys() if key in metadata_keys})


class LangGraphMethods:
    # Root Nodes
    @staticmethod
    def ask_question(state: GraphState) -> GraphState:
        if state.get("debug"):
            print("\n=== NODE: question ===\n")
        question = state["messages"][-1].content
        return update_state(state,
                            node_name="question",
                            question=question,
                            type="others")

    @staticmethod
    def classify_question(state: GraphState) -> Literal["metadata", "data", "others"]:
        """
            사용자의 초기 질문을 바탕으로 메타데이터 기반 질문인지, 데이터 기반 질문인지, 이전 답변 기반 질문인지를 AI가 판단해서
            이진 분류(Binary Classification)을 수행하는 함수.
            메타데이터 기반일 경우 'metadata', 데이터 기반일 경우 'data'를 반환한다.
        """

        # 데이터 모델 정의
        class Classification(BaseModel):
            """Classification result for user question."""
            question_classification: Literal["metadata", "data", "others"] = Field(
                description="""Response 'metadata' if the question is based on chat metadata(e.g. channel id, send time, views etc.), 
                            'data' if it is based on chat data(e.g. sale contact, recruitment, drug product type, sale place, price, discount event, how to buy etc.),
                            'others' if it is general question(e.g. greetings, questions based on previous chat history...)"""
            )

        # LLM 모델 초기화 -> 구조화된 출력을 위한 LLM 설정
        llm_with_structured_output = ChatOpenAI(temperature=0, model=MODEL_NAME,
                                                streaming=True).with_structured_output(Classification)

        # 분류를 요구하는 프롬프트 템플릿 정의
        prompt = PromptTemplate(
            template="""You are a classifier responsible for categorizing user questions. \n 
                The user asks you about chat data from messanger application.
                Here is the user question: {question} \n
                If it is necessary to use metadata to answer the question, classify it as 'metadata'.\n
                Give a classification 'metadata', 'data' or 'others' to indicate whether the document is based on.
                Response 'metadata' if the question is based on chat metadata(e.g. channel id, send time, views etc.), 
                'data' if it is based on chat data(e.g. drug type, sale place, price etc.),
                'others' if it is general question(e.g. greetings, questions based on previous chat history...)""",
            input_variables=["question"],
        )

        # prompt + llm 바인딩 체인 생성
        chain = prompt | llm_with_structured_output

        # 최초 질문 추출
        question = state["question"]

        # 관련성 평가 실행
        classification_result = chain.invoke({"question": question})

        # 관련성 여부에 따른 결정
        if classification_result.question_classification == "metadata":
            if state.get("debug"):
                print("\n==== [DECISION: METADATA RELEVANT] ====\n")
            return "metadata"

        elif classification_result.question_classification == "data":
            if state.get("debug"):
                print("\n==== [DECISION: DATA RELEVANT] ====\n")
            return "data"
        else:
            if state.get("debug"):
                print("\n==== [DECISION: GENERAL QUESTION RELEVANT] ====\n")
            return "others"

    # 메타데이터 기반 질문에 대응하는 Graph Branch
    @staticmethod
    def generate_db_query(state: GraphState, channel_ids: list[int]) -> GraphState:
        if state.get("debug"):
            print("\n=== NODE: generate db query ===\n")
        # LLM 모델 초기화
        llm = ChatOpenAI(temperature=0, model=MODEL_NAME, streaming=True).with_structured_output(Query)

        # SQL Query 프롬프트 템플릿 정의. 기본적으로 PromptTemplate에서 {}는 사용자 입력으로 인식되기 때문에, {{}}로 escape해야 한다.
        system_message = """You are a MongoDB manager responsible for answering user questions. 
            # Database Information: 
            {database_information}
            
            # Your Primary Mission:
            To retrieve the necessary information from the database to answer a user's question, determine which collection to query and construct the best aggregation pipeline. 
            Then, provide the result like the following:
            collection: <collection_name>, 
            pipeline: [{{appropriate_query}}, {{appropriate_conditions}}, ...]
            
            If the user question is asked without specifying a channel ID or any identifying information for a channel, assume that the data should be retrieved from all channels by default.
            The collection should be only string, which is the name of the collection to query.
            The aggregation pipeline should be list of JSON, which is directly convertible to JSON. 
            Both collection and pipeline should be without any Markdown formatting or other unnecessary text.  
            
            # Example:
            For example, if a user asks:
            "Show me the most viewed chat message in the channels after January 1, 2025."
            Then your exact response should be:
            
            collection: channel_data
            pipeline: [
              {{
                "$match": {{
                  "timestamp": {{ "$gte": ISODate("2025-01-01T00:00:00Z") }}
                }}
              }},
              {{ "$sort": {{ "views": -1 }} }},
              {{ "$limit": 1 }}
            ]
            """

        prompts = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("user", "{question}"),
        ])

        # prompt + llm 바인딩 체인 생성
        chain = prompts | llm

        # 최초 질문 추출
        question = state["question"]

        # 데이터베이스 쿼리 받기
        query = chain.invoke({"database_information": DB_INFORMATION, "question": question})

        if query.collection == "channel_info":
            query.pipeline.insert(0, {
                "$match": {
                    "_id": {
                        "$in": channel_ids
                    }
                }
            })
        else:
            query.pipeline.insert(0, {
                "$match": {
                    "text": {
                        "$ne": ""
                    }
                }
            })
            query.pipeline.insert(0, {
                "$match": {
                    "channelId": {
                        "$in": channel_ids
                    }
                }
            })

        return update_state(state,
                            node_name="generate_db_query",
                            db_query=query,
                            type="metadata",
                            collection="channel" if query.collection == "channel_info" else "chats")

    @staticmethod
    def execute_db_query(state: GraphState) -> GraphState:
        if state.get("debug"):
            print("\n=== NODE: execute db query ===\n")
        collection_name, pipeline = state["db_query"].collection, state["db_query"].pipeline
        cursor = Database.OBJECT[collection_name].aggregate(
            pipeline)  # state["db_query"].pipeline 은 Pydantic 의 Json 형식으로 지정되었으므로 바로 사용 가능
        context = [load_from_dict(doc, content_key="text", metadata_keys=["views", "url", "id", "timestamp"]) for doc in
                   cursor] if collection_name == "channel_data" else list(cursor)

        return update_state(state, node_name="execute_db_query", context=context)

    # 데이터 기반 질문에 대응하는 Graph Branch
    @staticmethod
    def execute_retriever(state: GraphState, retriever_tool: Tool) -> GraphState:
        if state.get("debug"):
            print("\n=== NODE: execute retriever ===\n")
        # rewrite_question에서 넘어온 경우에 원래 질문에서 바뀐 다른 새로운 질문을 입력해야 하므로, 현재 상태에서 마지막 메시지(질문) 추출.
        question = state["messages"][-1].content

        # LLM 모델 초기화
        model = ChatOpenAI(temperature=0, streaming=True, model=LIGHT_MODEL_NAME)

        # retriever tool 바인딩 & 도구를 호출하는 것을 강제
        model = model.bind_tools([retriever_tool], tool_choice=retriever_tool.name)

        # 에이전트 응답 생성
        response = model.invoke(question)

        return update_state(state,
                            node_name="execute_retriever",
                            messages=[response],
                            type="data",
                            collection="chats",)

    @staticmethod
    def handle_error(state: GraphState) -> GraphState:
        if state.get("debug"):
            print("\n=== NODE: handle error ===\n")
        return update_state(state, node_name="handle_error")

    # 모든 것이 검증된 후 context를 기반으로 답변을 생성하는 Graph Branch
    @staticmethod
    def generate(state: GraphState) -> GraphState:
        if state.get("debug"):
            print("\n=== NODE: generate ===\n")

        if state.get("type") != "others":
            if state.get("type") == "data":
                state["context"] = state["messages"][-1].content # retriever tool node의 결과를 context로 저장
            if state.get("collection") == "channel":
                indication = generate_by_channel
            else:
                indication = generate_by_chats # type이 "chats"일 때

            # 기존 state["messages"]에 새로운 지시와 질문을 더해서 같이 제공한다.
            # memory를 설정하면 state["messages"]에 계속해서 대화 기록이 저장되기 때문에,
            # 이를 AI가 받아서 이전 채팅 기록에 근거한 답변을 생성할 수 있게 된다.
            prompt = ChatPromptTemplate.from_messages([
                *state["messages"],
                ("system", indication),
                ("human", "{question}"),
            ])

            # RAG 체인 구성.
            # StrOutParser()를 사용하면 결과가 문자열이 되어서 state["messages"]에 추가될 때 자동으로 HumanMessage로 타입이 변환되기 때문에,
            # Memory에 저장 후 AI에게 제공해도 AI가 이를 AI의 응답으로 인식하지 못한다.
            # 따라서 StrOutputParser는 사용하지 말자.
            rag_chain = prompt | ChatOpenAI(model_name=MODEL_NAME, temperature=0, streaming=True)

            # 답변 생성
            response = rag_chain.invoke({"context": state.get("context", ""), "question": state.get("question", ""), })
        else:
            llm = ChatOpenAI(model_name=MODEL_NAME, temperature=0, streaming=True)
            # 답변 생성
            response = llm.invoke(state["messages"])

        return update_state(state, node_name="generate", messages=[response],
                            context="")  # 이전 질문에서 얻어낸 context가 다음 historical 질문에 영향을 주지 않도록 context 초기화

    def build_graph(self: 'Watson') -> Optional[CompiledStateGraph]:
        if not self.chats:
            return None

        # 도구 초기화
        retriever_tool = create_retriever_tool(
            retriever=self.vectorstore.as_retriever(search_kwargs={"k": 6}),  # 6개의 문서 검색,
            name="retrieve_chats_in_telegram_channel",
            description="Searches and returns a few chat messages from the Telegram channel that are most relevant to the question.",
            document_prompt=PromptTemplate.from_template(
                "<document><context>{page_content}</context><metadata><timestamp>{timestamp}</timestamp><url>{url}</url><views>{views}</views></metadata></document>"
            ),
        )

        retriever_tool_node = ToolNode([retriever_tool])

        workflow = StateGraph(GraphState)

        workflow.add_node("ask_question", self.ask_question)
        workflow.add_node("generate_db_query", lambda state: self.generate_db_query(state, self.channels))
        workflow.add_node("execute_db_query", self.execute_db_query)
        workflow.add_node("execute_retriever", lambda state: self.execute_retriever(state, retriever_tool))
        workflow.add_node("retrieve", retriever_tool_node)
        workflow.add_node("generate", self.generate)
        # workflow.add_node("handle_error", handle_error)

        # 시작점 설정
        workflow.set_entry_point("ask_question")
        # 첫 분기(메타데이터 기반인지/데이터 기반인지 분류)
        workflow.add_conditional_edges(
            "ask_question",
            self.classify_question,
            {
                # 조건 출력을 그래프 노드에 매핑
                "metadata": "generate_db_query",
                "data": "execute_retriever",
                "others": "generate",
            }
        )

        # 메타데이터 기반일 경우 Branch
        workflow.add_edge("generate_db_query", "execute_db_query")
        workflow.add_edge("execute_db_query", "generate")

        # 데이터 기반일 경우의 Branch
        workflow.add_edge("execute_retriever", "retrieve")
        workflow.add_edge("retrieve", "generate")

        # 그래프 종료
        workflow.add_edge("generate", END)

        logger.debug("Built a new LangGraph Workflow.")
        return workflow.compile(checkpointer=checkpointer)

    def _update_graph(self: 'Watson'):
        self.graph = self.build_graph()

    # 체인 실행(Run Chain)
    # 문서에 대한 질의를 입력하고, 답변을 출력한다.
    def ask(self: 'Watson', question: str):
        # chain이 있으면 chain을 실행하고 답변을 반환. chain이 없으면 에러 메세지 반환.
        inputs = {
            "messages": [
                ("user", question),
            ]
        }

        # config 설정(재귀 최대 횟수, thread_id)
        config = RunnableConfig(recursion_limit=10, configurable={"thread_id": self.id})

        # 그래프를 스트리밍하려면:
        # stream_graph(self.graph, inputs, config, list(self.graph.nodes.keys()))
        # RecursionError에 대비해서 미리 상태 백업

        if self.graph:
            saved_state = self.graph.get_state(config)
            try:
                answer = self.graph.invoke(
                    inputs,  # 질문 입력
                    # 세션 ID 기준으로 대화를 기록. 현재는 세션 ID가 고정이라서 bot 하나당 하나의 세션만 유지됨.
                    config=config
                )["messages"][-1].content
            except RecursionError as e:
                # RecursionError 발생 시, answer에 대응 메세지를 대입하고 graph를 안전한 상태로 롤백
                answer = "답변을 생성하지 못했습니다. 질문이 이해하기 어렵거나, 마약 텔레그램 채널과 관련 없는 내용인 것 같습니다. 질문을 바꿔서 다시 입력해 보세요."
                self.graph.update_state(config, saved_state.values)

            logger.info(f"Chatbot answered to a question. Q: '{question}', A: '{answer}'")
            return answer
        else:
            return self.error_msg_for_empty_data
