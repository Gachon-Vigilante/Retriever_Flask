import typing
from datetime import datetime
from typing import Any, Literal, Annotated, Sequence, TypedDict, Optional

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_teddynote.models import get_model_name, LLMs
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field, Json
from weaviate.classes.query import Filter

from server.logger import logger
from .indications import generate_by_channel, generate_by_chats
from .memory import checkpointer
from .weaviate import WeaviateClientContext

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


class SearchCondition(BaseModel):
    """LLM이 생성할 Weaviate 벡터 검색 조건"""
    query: Optional[str] = Field(None, description="The search text to use for vector-based similarity.")
    channelId: Optional[int] = Field(None, description="Target Telegram channel ID for filtering.")
    after: Optional[str] = Field(None, description="ISO date string for filtering messages after a time.")
    before: Optional[str] = Field(None, description="ISO date string for filtering messages before a time.")
    keyword: Optional[str] = Field(None, description="A keyword that should appear in the document.")


# 에이전트 상태를 정의하는 타입 딕셔너리, 메시지 시퀀스를 관리하고 추가 동작 정의
class GraphState(TypedDict):
    # add_messages reducer 함수를 사용하여 메시지 시퀀스를 관리
    messages: Annotated[Sequence[BaseMessage], add_messages]
    question: Annotated[str, "Question"]  # 질문
    db_query: Annotated[Query, "Query"]  # 데이터베이스 쿼리
    answer: Annotated[str, "Answer"]  # 답변
    debug: Annotated[bool, "Debug"]
    type: Annotated[Literal["data", "others"], "Type"]
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

def extract_search_conditions(question: str) -> SearchCondition:
    llm = ChatOpenAI(model=MODEL_NAME, temperature=0).with_structured_output(SearchCondition)

    prompt = PromptTemplate.from_template(
        """Extract search conditions from the question for Weaviate. Return both the main query (if any) and filters.
        Question: {question}
        Only include filters that are clearly indicated.
        """
    )

    chain = prompt | llm
    return chain.invoke({"question": question})

def build_filter_from_condition(cond: SearchCondition, channel_ids: list[int]):
    filters = [
        Filter.any_of([
            Filter.by_property("channelId").equal(channel_id)
            for channel_id in channel_ids
        ])
    ]
    if cond.keyword:
        filters.append(Filter.by_property("text").like(f"*{cond.keyword}*"))
    if cond.after:
        filters.append(Filter.by_property("timestamp").greater_or_equal(cond.after))
    if cond.before:
        filters.append(Filter.by_property("timestamp").less_or_equal(cond.before))

    if len(filters) == 1:
        return filters[0]
    else:
        return Filter.all_of(filters)


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
    def classify(state: GraphState) -> Literal["data", "others"]:
        """
            사용자의 초기 질문을 바탕으로 데이터 기반 질문인지, 이전 답변 기반 질문인지를 AI가 판단해서
            이진 분류(Binary Classification)을 수행하는 함수.
            데이터 기반일 경우 'data', 이전 답변 기반일 경우 'others'를 반환한다.
        """

        # 데이터 모델 정의
        class Classification(BaseModel):
            """Classification result for user question."""
            question_classification: Literal["data", "others"] = Field(
                description="""Response 'data' if the question is based on data of telegram channel and chats(e.g. channel id, send time, views, sale contact, recruitment, drug product type, sale place, price, discount event, how to buy etc.),
                               'others' if the question is just only general question(e.g. greetings, questions based on ONLY previous chat history NOT telegram channel or chats...)"""
            )

        # LLM 모델 초기화 -> 구조화된 출력을 위한 LLM 설정
        llm_with_structured_output = ChatOpenAI(temperature=0, model=MODEL_NAME,
                                                streaming=True).with_structured_output(Classification)

        # 분류를 요구하는 프롬프트 템플릿 정의
        indication = """
            You are an AI assistant supporting an investigator monitoring illegal drug trafficking activities on Telegram channels.
            
            Your role is to classify the user's question into one of two categories: 'data' or 'others'.
            
            Instructions:
            - The user is an investigator asking questions to analyze data from Telegram channels and their chat messages.
            - Classify the question as 'data' if it pertains to specific information within a channel or its messages.
              This includes: channel ID, send time, number of views, drug product types, sale location, pricing, promotions, or any chat content.
            - Classify the question as 'others' **only if** it is a general question unrelated to Telegram channel or message data.
              For example: greetings, questions based solely on previous answers, or general AI interaction without requiring Telegram data.
            
            Output:
            Return either 'data' or 'others' based strictly on the content of the user's question.
            Be cautious and conservative — only return 'data' when the question clearly requires analysis of Telegram channel or chat message data.
        """

        # prompt + llm 바인딩 체인 생성
        prompt = ChatPromptTemplate.from_messages([
            ("system", indication),
            ("human", "classify this question: {question}"),
        ])
        chain = prompt | llm_with_structured_output

        # 최초 질문 추출
        question = state["question"]

        # 관련성 평가 실행
        classification_result = chain.invoke({"question": question})

        # 관련성 여부에 따른 결정
        if classification_result.question_classification == "data":
            if state.get("debug"):
                print("\n==== [DECISION: DATA RELEVANT] ====\n")
            return "data"
        else:
            if state.get("debug"):
                print("\n==== [DECISION: GENERAL QUESTION RELEVANT] ====\n")
            return "others"


    @staticmethod
    def execute_search(state: GraphState, channel_ids: list[int], index_name="TelegramMessages") -> GraphState:
        if state.get("debug"):
            print("\n=== NODE: execute_search ===\n")

        @tool
        def retriever_from_weaviate(
            query: Optional[str] = None,
            after: Optional[str] = None,
            before: Optional[str] = None,
            keyword: Optional[str] = None,
        ):
            """
            Retrieve relevant Telegram chat messages from a Weaviate vector database, using optional vector similarity search
            and structured metadata filters.

            This tool supports two modes:
            1. If a query string is provided, it performs a vector-based `near_text` similarity search.
            2. If no query is given, it falls back to a metadata-only object fetch using the specified filters.

            Parameters:
            - query (Optional[str]): The main semantic search string for vector similarity retrieval.
            - after (Optional[str]): ISO 8601 date string to filter messages sent after this time.
            - before (Optional[str]): ISO 8601 date string to filter messages sent before this time.
            - keyword (Optional[str]): A keyword that must be present in the message text.

            Returns:
            - A formatted string containing relevant documents in XML-like structure, each with context and metadata.

            Use this tool when you want to retrieve chat content relevant to a specific topic, timeframe, or channel
            from a large corpus of Telegram messages stored in Weaviate.
            """

            with WeaviateClientContext() as client:
                conditions = SearchCondition(
                    query=query,
                    after=after,
                    before=before,
                    keyword=keyword,
                )
                search_text = conditions.query
                weaviate_filter = build_filter_from_condition(conditions, channel_ids)

                collection = client.collections.get(index_name)

                # near_text or fetch_objects
                if search_text:
                    response = collection.query.near_text(
                        query=search_text,
                        filters=weaviate_filter,
                        limit=6
                    )
                else:
                    response = collection.query.fetch_objects(
                        filters=weaviate_filter,
                        limit=10
                    )

                # 결과를 LangChain Document로 변환
                documents = []
                for obj in response.objects:
                    page_content = obj.properties.get("text") or ""
                    metadata = {
                        "timestamp": obj.properties.get("timestamp"),
                        "url": obj.properties.get("url"),
                        "views": obj.properties.get("views"),
                    }
                    documents.append(Document(page_content=page_content, metadata=metadata))

            message = "\n\n".join(
                f"<document><context>{doc.page_content}</context><metadata>{doc.metadata}</metadata></document>"
                for doc in documents
            )

            return message

        llm_with_tools = ChatOpenAI(temperature=0,
                                    model=MODEL_NAME,
                                    streaming=True).bind_tools([retriever_from_weaviate],
                                                               tool_choice=retriever_from_weaviate.name)

        indication = """You are a query interpreter for a Weaviate-based vector search system.
            Your job is to extract a semantic search query (if any) and a set of structured filters from the user question.
            Note: 
            - now is {now}
            
            Instructions:
            - Determine 'query' string if there is a clear topic, subject, or keyword to search semantically.
            - Only include filters (e.g., channel_id, date range, keyword) **if the user explicitly mentions them** in the question.
            - DO NOT guess or infer filters that are not clearly and explicitly stated.
            - If any field is missing or ambiguous, leave it out (use null).
            
            Output format:
              "query": Optional[str],
              "after": Optional[str],
              "before": Optional[str],
              "keyword": Optional[str]
              
            Examples:
                1. question: "이 채널에서 거래되는 마약의 종류와 가격은?"
                -> "query": "마약 종류 가격", "after": null, "before": null, "keyword": null
                2. question: "'좌표'가 언급된 2025년 2월 이후의 채팅을 찾아줘"
                -> "query": null, "after": "2025-02-01T00:00:00.000Z", "before": null, "keyword": "좌표"
                3. question: "2025년 4월 2일과 27일 사이에 입고 관련 소식이 있었나?"
                -> "query": "입고", "after": "2025-04-02T00:00:00.000Z", "before": "2025-04-28T00:00:00.000Z", "keyword": null
            
            Only return values that are certain and clearly specified by the user.
            If the user did not mention a filter, DO NOT include it.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", indication),
            ("human", "{question}"),
        ])
        chain = prompt | llm_with_tools

        ai_msg = chain.invoke({"now": datetime.now(), "question": state["question"]})

        messages = [ai_msg]
        # 결과를 ToolMessage로 변환
        for tool_call in ai_msg.tool_calls:
            selected_tool = {"retriever_from_weaviate": retriever_from_weaviate}[tool_call["name"].lower()]
            tool_msg = selected_tool.invoke(tool_call)
            messages.append(tool_msg)

        return update_state(state,
                            node_name="execute_search",
                            messages=messages,
                            type="data",
                            collection="chats",
                            )


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
            context = state["messages"][-1].content # tool node의 결과를 context로 저장
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
            response = rag_chain.invoke({"context": context, "question": state.get("question", ""), })
        else:
            llm = ChatOpenAI(model_name=MODEL_NAME, temperature=0, streaming=True)
            # 답변 생성
            response = llm.invoke(state["messages"])

        return update_state(state, node_name="generate", messages=[response],)


    def build_graph(self: 'Watson') -> Optional[CompiledStateGraph]:
        if not self.chats:
            return None

        workflow = StateGraph(GraphState)

        workflow.add_node("ask_question", self.ask_question)
        workflow.add_node("classify", self.classify)
        workflow.add_node("search", lambda state: self.execute_search(state, self.channels))
        workflow.add_node("generate", self.generate)

        # 시작점 설정
        workflow.set_entry_point("ask_question")
        # 첫 분기(메타데이터 기반인지/데이터 기반인지 분류)
        workflow.add_conditional_edges(
            "ask_question",
            self.classify,
            {
                # 조건 출력을 그래프 노드에 매핑
                "data": "search",
                "others": "generate",
            }
        )
        workflow.add_edge("search", "generate")
        workflow.add_edge("generate", END)


        logger.debug("Built a new LangGraph Workflow.")
        return workflow.compile(
            checkpointer=checkpointer
        )

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
