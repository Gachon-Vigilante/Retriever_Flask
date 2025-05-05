from typing import Any, Literal, Annotated, Sequence, TypedDict, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field, Json


# 데이터 모델 정의
class Classification(BaseModel):
    """Classification result for user question."""
    question_classification: Literal["data", "others"] = Field(
        description="""Response 'data' if the question is based on data of telegram channel and chats(e.g. channel id, send time, views, sale contact, recruitment, drug product type, sale place, price, discount event, how to buy etc.),
                       'others' if the question is just only general question(e.g. greetings, questions based on ONLY previous chat history NOT telegram channel or chats...)"""
    )

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

class GraphState(TypedDict):
    """
    에이전트 상태를 정의하는 타입 딕셔너리.
    메시지 시퀀스를 관리하고 추가 동작 정의
    """
    # add_messages reducer 함수를 사용하여 메시지 시퀀스를 관리
    messages: Annotated[Sequence[BaseMessage], add_messages]
    question: Annotated[str, "Question"]  # 질문
    debug: Annotated[bool, "Debug"]
    type: Annotated[Literal["data", "others"], "Type"]


class SearchCondition(BaseModel):
    """LLM이 생성할 Weaviate 벡터 검색 조건"""
    query: Optional[str] = Field(None, description="The search text to use for vector-based similarity.")
    channelId: Optional[int] = Field(None, description="Target Telegram channel ID for filtering.")
    after: Optional[str] = Field(None, description="ISO date string for filtering messages after a time.")
    before: Optional[str] = Field(None, description="ISO date string for filtering messages before a time.")
    keyword: Optional[str] = Field(None, description="A keyword that should appear in the document.")


class Catalog(BaseModel):
    chatIds: list[int] = Field(
        description="""
        list of chatIds which are Telegram chat messages that appear to contain information about **drug pricing**.
        """
    )
    catalog: str = Field(
        description="""
        A well-formatted summary of drug pricing information extracted from the referenced chat messages.
        This should organize the data by product type, price, and any relevant units (e.g., grams, milliliters, packs).
        The result should be human-readable, concise, and categorized by drug type or sale format if possible.
        """
    )