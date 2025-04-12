from typing import Literal

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from pydantic import Field, BaseModel

from rag.watson.graph import GraphState, update_state, LIGHT_MODEL_NAME, DB_INFORMATION, MODEL_NAME
from langchain_openai import ChatOpenAI


class LegacyMethods:

    @staticmethod
    def validate_db_query(state: GraphState) -> GraphState:
        if state.get("debug"):
            print("\n=== NODE: validate db query ===\n")
        return update_state(state, node_name="validate_db_query")

    @staticmethod
    def evaluate_db_query(state: GraphState) -> Literal["rewrite_query", "end"]:
        if state.get("debug"):
            print("\n=== BRANCH: evaluate db query ===\n")

        from pydantic import BaseModel
        class NextAction(BaseModel):
            """A binary score for relevance checks"""
            next_action: str = Field(
                description="Response 'end' if the collection and pipeline is correctly formatted or 'rewrite_query' if it is not."
            )
            reason: str = Field(
                description="The reason why you chose the next action."
            )

        # LLM 모델 초기화 -> 구조화된 출력을 위한 설정
        llm_with_structured_output = ChatOpenAI(temperature=0, model=LIGHT_MODEL_NAME,
                                                streaming=True).with_structured_output(NextAction)

        # SQL Query 프롬프트 템플릿 정의. 기본적으로 PromptTemplate에서 {}는 사용자 입력으로 인식되기 때문에, {{}}로 escape해야 한다.
        system_message = """You are an evaluator responsible for assessing whether the generated MongoDB query is appropriate for the given user question.
            # Database Information: 
            {database_information}

            # Your Primary Mission:
            Based on the provided channel information, evaluate whether the JSON adheres to the following criteria:

            1. The top-level keys in the JSON must be exactly two: "collection", which specifies the collection to query, and "pipeline", which represents the aggregation pipeline.
            2. The value of the "collection" key must be either "channel_info" or "channel_data".
            3. The value of the "pipeline" key must be an array containing a valid aggregation pipeline that correctly retrieves the requested data.
            4. If the user question is asked without specifying a channel ID or any identifying information for a channel, assume that the data should be retrieved from all channels by default.
            5. The response must contain only string and JSON, without any Markdown formatting or other non-JSON text. 
            6. The aggregation pipeline should be directly convertible to JSON.

            If the JSON is correctly formatted, return "end".
            If there is an issue, such as selecting the wrong collection, constructing an incorrect query, or violating any of the above requirements, return "rewrite_query".

            # Example:
            For example, if a user asks:
            "Show me the most viewed chat message in the channels after January 1, 2025."
            and JSON is:

            collection: channel_data
            pipeline: ```json
            [
              {{
                "$match": {{
                  "timestamp": {{ "$gte": ISODate("2025-01-01T00:00:00Z") }}
                }}
              }},
              {{ "$sort": {{ "views": -1 }} }},
              {{ "$limit": 1 }}
            ]
            ```
            In this case, even if all other conditions are met, the presence of unnecessary Markdown formatting strings like json makes it impossible to directly convert the response to JSON. Therefore, the correct answer of this case is "rewrite_query".
            """

        prompts = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("user", """
            # User Question:
            {question}

            # collection:
            {collection}
            # pipeline:
            {pipeline}
            """),
        ])

        # prompt + llm 바인딩 체인 생성
        chain = prompts | llm_with_structured_output

        # 데이터베이스 쿼리 받기
        answer = chain.invoke({
            "database_information": DB_INFORMATION,
            "question": state["question"],
            "collection": state["db_query"].collection,
            "pipeline": state["db_query"].pipeline,
        })

        if answer.next_action == "end":
            return "end"
        return "rewrite_query"

    @staticmethod
    def rewrite_db_query(state: GraphState) -> GraphState:
        if state.get("debug"):
            print("\n=== NODE: rewrite db query ===\n")
        return update_state(state, node_name="rewrite_db_query")


    @staticmethod
    def validate_retrieved_context(state:GraphState) -> GraphState:
        if state.get("debug"):
            print("\n=== NODE: validate retrieved context ===\n")
        # 가장 마지막 메시지 추출 (가장 마지막 메세지가 retrieve ToolNode가 생성한 ToolMessage) -> 검색된 문서 추출
        retrieved_docs = state["messages"][-1].content
        return update_state(state, node_name="validate_retrieved_context", context=retrieved_docs)

    @staticmethod
    def evaluate_retrieved_context(state:GraphState) -> Literal["generate", "rewrite_question"]:
        if state.get("debug"):
            print("\n=== BRANCH: evaluate retrieved context ===\n")

        # 데이터 모델 정의
        class Grade(BaseModel):
            """A binary score for relevance checks"""

            binary_score: str = Field(
                description="Response 'yes' if the document is relevant to the question or 'no' if it is not."
            )
            reason: str = Field(
                description="The reason why you graded this document as your decision."
            )

        # LLM 모델 초기화 & 구조화된 출력을 위한 LLM 설정
        llm_with_structured_output = ChatOpenAI(temperature=0, model=LIGHT_MODEL_NAME, streaming=True).with_structured_output(Grade)

        # 프롬프트 템플릿 정의
        prompt = PromptTemplate(
            template="""You are a grader assessing relevance of a retrieved document to a user question. \n 
            Here is the retrieved document: \n\n {context} \n\n
            Here is the user question: {question} \n
            If the document contains keyword(s) or semantic meaning related to the user question, grade it as relevant. \n
            Give a binary score 'yes' or 'no' score to indicate whether the document is relevant to the question.""",
            input_variables=["context", "question"],
        )

        # llm + tool 바인딩 체인 생성
        chain = prompt | llm_with_structured_output

        # 원래 질문과 현재 retriever로 검색한 context 문서 간의 관련성 평가 실행
        scored_result = chain.invoke({"question": state["question"], "context": state["context"]})

        # 관련성 여부 추출
        score = scored_result.binary_score

        # 관련성 여부에 따른 결정
        if score == "yes":
            if state.get("debug"):
                print("==== [DECISION: DOCS RELEVANT] ====")
            return "generate"

        else:
            if state.get("debug"):
                print("==== [DECISION: DOCS NOT RELEVANT] ====")
            return "rewrite_question"

    @staticmethod
    def rewrite_question(state:GraphState) -> GraphState:
        if state.get("debug"):
            print("\n=== NODE: rewrite question ===\n")
        # 원래 질문 추출
        question = state["question"]

        # 질문 개선을 위한 프롬프트 구성
        msg = [
            HumanMessage(
                content=f""" \n 
            Look at the input and try to reason about the underlying semantic intent / meaning. \n 
            Here is the initial question:
            \n ------- \n
            {question} 
            \n ------- \n
            Formulate an improved question: """,
            )
        ]

        # LLM 모델로 질문 개선
        model = ChatOpenAI(temperature=0, model=MODEL_NAME, streaming=True)
        # Query-Transform 체인 실행
        response = model.invoke(msg)
        return update_state(state, node_name="rewrite_question", messages=[response])