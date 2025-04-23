from langchain_core.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate, \
    ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_teddynote.models import get_model_name, LLMs
from pydantic import BaseModel, Field

MODEL_NAME = get_model_name(LLMs.GPT4o)

class BinaryClassification(BaseModel):
    """A binary score for whether telegram channel sells drugs or not."""
    binary_classification: bool = Field(
        description="""
            If the given chat history from a Telegram channel indicates that drugs are being sold or promoted, return True. 
            If drugs are not being sold or promoted, or if there is no chat history, return False."
        """
    )

def check_telegram_by_openai(message: str) -> bool:
    # LLM 모델 초기화 -> 구조화된 출력을 위한 LLM 설정
    llm_with_structured_output = ChatOpenAI(temperature=0,
                                            model=MODEL_NAME,
                                            streaming=True).with_structured_output(BinaryClassification)

    # HTML을 분석해서 마약 홍보글 여부와 텔레그램 링크를 요구하는 프롬프트 템플릿 정의
    system_prompt = SystemMessagePromptTemplate.from_template(
        """You are an assistant to an investigator tracking illegal drug sales on telegrams.

You are given text extracted from telegram channel. Your job is to detect if the channel explicitly promotes the sale of illegal drugs.

The following argot terms are commonly used to refer to illegal drugs:

### **Drug-related argot examples:**
- 떨, 위드, 허브, 해쉬, 브액, 대마초, 대마, 고기 (refers to marijuana)
- 아이스, 크리스탈, 술, 히로뽕, 필로폰, 작대기, 빙두 (refers to methamphetamine)
- 몰리, 엑시, 엑스터시, 도리도리, 캔디, XTC (refers to MDMA or ecstasy)
- 엘, 엘에스디, LSD (LSD)
- 케이 (Ketamine)

If the given chat history from a Telegram channel indicates that drugs are being sold or promoted, return True. 
If drugs are not being sold or promoted, or if there is no chat history, return False.

### **Rules:**
- Only rely on what is explicitly written in the text.
- Do not hallucinate or imagine any content not present.
- If the meaning is unclear or ambiguous, return `False` and leave other fields empty.
""",
    )
    human_prompt = HumanMessagePromptTemplate.from_template("""Analyze the following text:\n\n{text}\n\n""")

    # prompt + llm 바인딩 체인 생성
    chain = ChatPromptTemplate.from_messages([system_prompt, human_prompt]) | llm_with_structured_output

    # 결과 수신
    analysis = chain.invoke({"text": message})
    return analysis.binary_classification