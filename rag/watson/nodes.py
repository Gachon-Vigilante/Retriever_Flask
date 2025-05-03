from datetime import datetime
from typing import Literal, Optional

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_teddynote.models import get_model_name, LLMs
from weaviate.classes.query import Filter

from .datamodel import GraphState, SearchCondition, Classification
from .indications import Indications
from .weaviate import WeaviateClientContext

# 최신 모델이름 가져오기
MODEL_NAME = get_model_name(LLMs.GPT4o)

def update_state(state: GraphState, node_name: str, **updates) -> GraphState:
    """Graph의 State를 입력받고, 입력받은 State에서 **updates로 받은 딕셔너리를 반영해서 수정된 State를 반환하는 함수."""
    new_state: GraphState = state.copy()
    new_state.update(**updates)
    return new_state

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

class LangGraphNodes:
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

        # LLM 모델 초기화 -> 구조화된 출력을 위한 LLM 설정
        llm_with_structured_output = ChatOpenAI(temperature=0, model=MODEL_NAME,
                                                streaming=True).with_structured_output(Classification)

        # 분류를 요구하는 프롬프트 템플릿 정의
        indication = Indications.Classify.QUESTION

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

        indication = Indications.Interpret.WEAVIATE
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
            context = state["messages"][-1].content  # tool node의 결과를 context로 저장
            if state.get("collection") == "channel":
                indication = Indications.Generate.BY_CHANNEL
            else:
                indication = Indications.Generate.BY_CHATS  # type이 "chats"일 때

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

        return update_state(state, node_name="generate", messages=[response], )