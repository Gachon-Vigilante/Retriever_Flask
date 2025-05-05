from datetime import datetime, timezone
from typing import Literal, Optional

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_teddynote.models import get_model_name, LLMs
from weaviate.classes.query import Filter, Sort

from server.db import Database
from utils import dict_to_xml
from .constants import weaviate_index_name
from .datamodel import GraphState, Classification
from .indications import Indications
from .weaviate import WeaviateClientContext

# 최신 모델이름 가져오기
MODEL_NAME = get_model_name(LLMs.GPT4o)

def update_state(state: GraphState, node_name: str, **updates) -> GraphState:
    """Graph의 State를 입력받고, 입력받은 State에서 **updates로 받은 딕셔너리를 반영해서 수정된 State를 반환하는 함수."""
    new_state: GraphState = state.copy()
    new_state.update(**updates)
    return new_state

def parse_filter_node(node: dict):
    if "and" in node:
        return Filter.all_of([parse_filter_node(sub) for sub in node["and"]])
    if "or" in node:
        return Filter.any_of([parse_filter_node(sub) for sub in node["or"]])
    if "field" in node and "op" in node:
        field = node["field"]
        op = node["op"]
        value = node["value"]
        base = Filter.by_property(field)

        match op:
            case "eq": return base.equal(value)
            case "neq": return base.not_equal(value)
            case "gt": return base.greater_than(value)
            case "gte": return base.greater_or_equal(value)
            case "lt": return base.less_than(value)
            case "lte": return base.less_or_equal(value)
            case "like": return base.like(value)
            case "contains_any": return base.contains_any(value)
            case "contains_all": return base.contains_all(value)
            case "isnull": return base.is_none(value)
            case _: raise ValueError(f"Unsupported operator: {op}")

    raise ValueError("Invalid filter node structure")

def parse_sort_list(sort_json: list[dict]):
    """
        Converts a list of sort conditions into a chained Sort object.

        Each element in sort_json must be a dict like:
            { "field": "views", "direction": "desc" }

        Returns:
            Sort object with multiple fields chained via .by_property()
    """
    sort_obj = None
    for i, item in enumerate(sort_json):
        if i == 0:
            sort_obj = Sort.by_property(
                name=item["field"],
                ascending=(item["direction"] == "asc")
            )
        else:
            sort_obj = sort_obj.by_property(
                name=item["field"],
                ascending=(item["direction"] == "asc")
            )
    return sort_obj

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
    def execute_search(state: GraphState, channel_ids: list[int], index_name=weaviate_index_name) -> GraphState:
        if state.get("debug"):
            print("\n=== NODE: execute_search ===\n")

        @tool
        def retriever_from_weaviate(
            query: Optional[list[str]] = None,
            filters: Optional[dict] = None,
            sort: Optional[list[dict]] = None,
            limit: Optional[int] = 10
        ) -> str:
            """
            Retrieves relevant Telegram chat messages from a Weaviate collection using semantic query and structured filters.

            This tool supports both vector-based similarity search (`near_text`) and traditional metadata-based filtering
            (`fetch_objects`) depending on whether a semantic query is provided.

            Parameters:
            - query (Optional[str]): A semantic search string. If provided, vector similarity (`near_text`) is used.
            - filters (Optional[dict]): A nested filter structure in JSON format specifying logical conditions for message retrieval.
                Must use only allowed fields: "text", "views", "timestamp".
                Logical operators supported: "and", "or". Not supported: "not".
                Comparison operators: "eq", "neq", "gt", "gte", "lt", "lte", "like", "contains_any", "contains_all", "isnull".
            - sort (Optional[List[dict]]): A list of sorting preferences. Each element must include:
                - "field": one of ["text", "views", "timestamp"]
                - "direction": "asc" (ascending) or "desc" (descending)
            - limit (int): Maximum number of results to return. If unspecified, defaults to 10.

            Behavior:
            - If `query` is provided, performs vector search using `near_text`.
            - If `query` is not provided, performs metadata-only filtering using `fetch_objects`.
            - Regardless of mode, results are always filtered by the allowed `channel_ids` via an internal AND condition.
            - Results are returned as XML-like formatted string for downstream processing.

            Returns:
            - A string of chat documents, each formatted as:
              <document>
                <context>{chat_text}</context>
                <metadata>
                    <timestamp>...</timestamp>
                    <url>...</url>
                    <views>...</views>
                </metadata>
              </document>
            """
            limit = min(20, limit) if limit else 8
            channel_id_filter = {
                "or": [
                    {"field": "channelId", "op": "eq", "value": channel_id}
                    for channel_id in channel_ids
                ]
            }

            filters = {
                "and": [
                    filters,
                    channel_id_filter
                ]
            } if filters else channel_id_filter

            with WeaviateClientContext() as client:
                filter_obj = parse_filter_node(filters) if filters else None
                sort_obj = parse_sort_list(sort) if sort else None
                collection = client.collections.get(index_name)

                # near_text or fetch_objects
                if query:
                    response = collection.query.near_text(
                        query=query,
                        filters=filter_obj,
                        # sort: 벡터 검색 수행 시에는 sort 인자는 사용 불가!
                        limit=limit
                    )
                else:
                    response = collection.query.fetch_objects(
                        filters=filter_obj,
                        sort=sort_obj,
                        limit=limit
                    )

                # 결과를 LangChain Document로 변환
                documents = []
                for obj in response.objects:
                    page_content = obj.properties.get("text") or ""
                    metadata = {
                        "channel id": obj.properties.get("channelId"),
                        "timestamp": obj.properties.get("timestamp"),
                        "url": obj.properties.get("url"),
                        "views": obj.properties.get("views"),
                    }
                    documents.append(Document(page_content=page_content, metadata=metadata))

            message = "\n\n".join(
                f"<document><context>{doc.page_content}</context><metadata>{dict_to_xml(doc.metadata)}</metadata></document>"
                for doc in documents
            )

            return message

        @tool
        def get_drug_pricing_information() -> str:
            """
            Retrieves structured summaries of drug pricing information from monitored Telegram channels.

            For each channel where catalog data is available, this function returns a formatted document containing:
            - <channel_id>: The unique Telegram channel ID
            - <catalog>: A human-readable summary of drug product types and their prices, grouped by item
            - <source>: A comma-separated list of t.me URLs pointing to the original Telegram messages containing the pricing information

            Only channels that have both catalog description and message references (chatIds) will be included.

            Returns:
                A concatenated XML-style string with one <document> block per channel, each containing:
                <channel_id>...</channel_id>
                <catalog>...</catalog>
                <source>...</source>

            This output is designed to be read by an AI model or investigator for reviewing summarized pricing intelligence per channel.
            """
            doc = ""
            for info in Database.Collection.Channel.INFO.find({"_id": {"$in": channel_ids}}):
                if info.get("catalog") and info.get("catalog").get("chatIds"):
                    doc += "<document>"
                    doc += f"<channel_id>{info.get("_id")}</channel_id>"
                    doc += f"<catalog>{info["catalog"].get("description")}</catalog>"
                    username = info.get("username")
                    sources = [f"<url>https://t.me/{username}/{chatId}</url>" for chatId in info["catalog"].get("chatIds")]
                    doc += f"<sources>\n{"\n".join(sources)}\n</sources>"
                    doc += f"</document>"
            return doc

        llm_with_tools = ChatOpenAI(temperature=0.5,
                                    model=MODEL_NAME,
                                    streaming=True).bind_tools([retriever_from_weaviate, get_drug_pricing_information])

        indication = Indications.Interpret.WEAVIATE
        prompt = ChatPromptTemplate.from_messages([
            ("system", indication),
            ("human", "{question}"),
        ])
        chain = prompt | llm_with_tools

        ai_msg = chain.invoke({"now": datetime.now(tz=timezone.utc).isoformat(), "question": state["question"]})

        messages = [ai_msg]
        # 결과를 ToolMessage로 변환
        for tool_call in ai_msg.tool_calls:
            selected_tool = {
                "retriever_from_weaviate": retriever_from_weaviate,
                "get_drug_pricing_information": get_drug_pricing_information
            }[tool_call["name"].lower()]
            tool_msg = selected_tool.invoke(tool_call)
            messages.append(tool_msg)

        return update_state(state,
                            node_name="execute_search",
                            messages=messages,
                            type="data",
                            )

    @staticmethod
    def handle_error(state: GraphState) -> GraphState:
        if state.get("debug"):
            print("\n=== NODE: handle error ===\n")
        return update_state(state, node_name="handle_error")

    # 모든 것이 검증된 후 context를 기반으로 답변을 생성하는 Graph Branch
    @staticmethod
    def generate(state: GraphState, channel_info: dict) -> GraphState:
        if state.get("debug"):
            print("\n=== NODE: generate ===\n")

        if state.get("type") != "others":
            indication = Indications.Generate.BY_CHATS  # type이 "chats"일 때

            # 기존 state["messages"]에 새로운 지시와 질문을 더해서 같이 제공한다.
            # memory를 설정하면 state["messages"]에 계속해서 대화 기록이 저장되기 때문에,
            # 이를 AI가 받아서 이전 채팅 기록에 근거한 답변을 생성할 수 있게 된다.
            prompt = ChatPromptTemplate.from_messages([
                # 최대 25개 대화 메세지를 기억으로 저장. toolmessage 등도 다 반영되기 때문에 실제로는 10번 정도의 질의응답 상호작용을 기억할 것.
                *(state["messages"][-min(len(state["messages"]), 50):]),
                ("system", indication),
                ("human", "{question}"),
            ])

            # RAG 체인 구성.
            # StrOutParser()를 사용하면 결과가 문자열이 되어서 state["messages"]에 추가될 때 자동으로 HumanMessage로 타입이 변환되기 때문에,
            # Memory에 저장 후 AI에게 제공해도 AI가 이를 AI의 응답으로 인식하지 못한다.
            # 따라서 StrOutputParser는 사용하지 말자.
            rag_chain = prompt | ChatOpenAI(model_name=MODEL_NAME, temperature=0, streaming=True)

            # 답변 생성
            response = rag_chain.invoke({"question": state.get("question", ""),
                                         "channel_information": channel_info
                                         })
        else:
            llm = ChatOpenAI(model_name=MODEL_NAME, temperature=0, streaming=True)
            # 답변 생성
            response = llm.invoke(state["messages"])

        return update_state(state,
                            node_name="generate",
                            messages=[response], )