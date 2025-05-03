import typing
from typing import Optional

from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from server.logger import logger
from .datamodel import GraphState
from .memory import checkpointer
from .nodes import LangGraphNodes

if typing.TYPE_CHECKING:
    from rag.watson import Watson

load_dotenv()

class LangGraphMethods:
    def build_graph(self: 'Watson') -> Optional[CompiledStateGraph]:
        if not self.chats:
            return None

        workflow = StateGraph(GraphState)

        workflow.add_node("ask_question", LangGraphNodes.ask_question)
        workflow.add_node("classify", LangGraphNodes.classify)
        workflow.add_node("search", lambda state: LangGraphNodes.execute_search(state, self.channels))
        workflow.add_node("generate", LangGraphNodes.generate)

        # 시작점 설정
        workflow.set_entry_point("ask_question")
        # 첫 분기(메타데이터 기반인지/데이터 기반인지 분류)
        workflow.add_conditional_edges(
            "ask_question",
            LangGraphNodes.classify,
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
            return "채널에 채팅이 없어, 챗봇이 생성되지 않았습니다."
