from typing import Literal

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


class Report(BaseModel):
    """"""
    report_type: Literal[
        "상품 소개",
        "가격",
        "이벤트 안내",
        "입고 소식",
        "직원 구인",
        "개인정보",
        "판매 지역",
        "구매 방법",
        "새로운 은어",
    ] = Field(description="""The type of the report. 
    Must be one of: 
    '상품 소개' (Product Introduction), 
    '가격' (Price)
    '이벤트 안내' (Event Notice), 
    '입고 소식' (Stock Update), 
    '직원 구인' (Recruitment), 
    '개인정보' (Personal Information),
    '판매 지역' (Sales Region), 
    '구매 방법' (Purchase Method),
    '새로운 은어' (New Argot/Slang). 
    """)
    report_content: str = Field(description="""
        The exact phrases or sentences from the message that contains the intelligence. Do not paraphrase or translate.
    """)
    report_description: str = Field(description="""
        A short explanation in Korean (1–2 sentences) justifying why the content is categorized as the selected report type. Answer in Korean.
    """)

class Intelligence(BaseModel):
    reports: list[Report] = Field(
        default_factory=list,
        description="A list of reports extracted from the input message. Can be empty if no valid intelligence is detected."
    )

def get_reports_by_openai(message: str) -> list[Report]:
    # LLM 모델 초기화 -> 구조화된 출력을 위한 LLM 설정
    llm_with_structured_output = ChatOpenAI(temperature=0,
                                            model=MODEL_NAME).with_structured_output(Intelligence)

    # 메세지를 분석해서 report 묶음을 intelligence 객체로 생성하기를 요구하는 프롬프트 템플릿 정의
    system_prompt = SystemMessagePromptTemplate.from_template(
        """You are an AI assistant specializing in monitoring and extracting intelligence from Telegram messages related to illegal drug sales.

You will be given a single message. Your task is to analyze the message and extract zero or more structured intelligence reports based on the content.

Each report must have:
- `report_type`: One of the following six categories:
  - "상품 소개" (Product Introduction): Information introducing or describing drugs for sale.
  - "가격" (Price): Clues about the transaction price or cost of drug products (e.g., per gram pricing).
  - "이벤트 안내" (Event Notice): Announcements of promotions, discounts, or time-limited offers.
  - "입고 소식" (Stock Update): Notifications about restocking or unavailability of certain drugs.
  - "직원 구인" (Recruitment): Attempts to recruit staff for roles in drug-related operations.
  - "개인정보" (Personal Information): Messages that may contain seller or buyer personal information (e.g., phone numbers, locations, usernames).
  - "새로운 은어" (New Slang): Suspicious new slang or codewords that may refer to illegal drugs but are not part of existing drug slang databases.
  - "판매 지역" (Sales Region): Information indicating the specific geographic location where the drugs are available or the transaction is intended to occur (e.g., cities, stations, districts, or delivery zones).
  - "구매 방법" (Purchase Method): Instructions or methods on how to buy the drugs, such as steps for ordering, use of encrypted messengers, payment procedures, or required contact methods (e.g., DM for purchase).

- `report_content`: The exact part(s) of the original message that contains the relevant intelligence (verbatim).
- `report_description`: A concise justification in Korean, explaining why this part of the message matches the category.

Return a list of such reports under `reports` property.

### **Rules:**
- If **multiple parts of the message** match the same `report_type`, you must **combine them into a single report** of that type. Do not create multiple reports for the same type. Concatenate the matching parts in `report_content`, and provide a unified `report_description`.
- If no relevant intelligence is found, return an empty list of reports.
- Do not make up or assume information not present in the message.
- report_description must be written in **Korean**.

### **Drug-related argot examples:**
- 떨, 위드, 허브, 해쉬, 브액, 대마초, 대마, 고기 (refers to marijuana)
- 아이스, 크리스탈, 술, 히로뽕, 필로폰, 작대기, 빙두 (refers to methamphetamine)
- 몰리, 엑시, 엑스터시, 도리도리, 캔디, XTC (refers to MDMA or ecstasy)
- 엘, 엘에스디, LSD (LSD)
- 케이 (Ketamine)

### **Examples:**

**message**: "할인 이벤트 시작합니다. 오늘 떨 신상 입고 완료됐습니다. 2g 7만 이벤트 한정가 진행 중. 필요한 분 전화번호 010-1234-5678"
**reports**: [
    {{
      "report_type": "입고 소식",
      "report_content": "오늘 떨 신상 입고 완료됐습니다.",
      "report_description": "마리화나 신상품의 입고 사실을 알리고 있습니다."
    }},
    {{
      "report_type": "이벤트 안내",
      "report_content": "'할인 이벤트 시작합니다', '2g 7만 이벤트 한정가 진행 중.'",
      "report_description": "가격 할인을 안내하고 있습니다."
    }},
    {{
      "report_type": "개인정보",
      "report_content": "전화번호 010-1234-5678",
      "report_description": "판매자와 연락 가능한 전화번호가 발견되었습니다."
    }}
  ]
""",
    )
    human_prompt = HumanMessagePromptTemplate.from_template("""Analyze the following message:\n\n{message}\n\n""")

    # prompt + llm 바인딩 체인 생성
    chain = ChatPromptTemplate.from_messages([system_prompt, human_prompt]) | llm_with_structured_output

    # 결과 수신
    intelligence = chain.invoke({"message": message})
    return intelligence.reports

