from langchain_core.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate, \
    ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_teddynote.models import get_model_name, LLMs
from pydantic import BaseModel, Field

from preprocess.extractor import extract_text_blocks_from_html
from server.logger import logger

MODEL_NAME = get_model_name(LLMs.GPT4o)

# 글의 내용 분석 결과를 저장하는 데이터 모델 정의
class Analysis(BaseModel):
    """A binary score for relevance checks"""
    binary_classification: bool = Field(
        description="Return True if the given HTML content clearly promotes drug sales. If it does not, return False."
                    "If it is just news articles, police reports, or discussions that merely **report** on drug-related incidents without advertising or facilitating drug sales or the content appears to be a news report (e.g., contains terms like “arrested”, “report”, “crackdown”, “police investigation”, “journalist”, etc.) or describes third-party actions without promoting sales, classify it as `False`."
    )
    promotion_content: str = Field(
        description="If the given HTML promotes drug sales, return the promotional content as promotion_content. If not, return an empty string. Do not translate the promotional content; extract and return it exactly as it appears in the original input. (e.g. if the original input was Korean, return it in Korean.)"
    )
    telegram_keys: list[str] = Field(
        description="If the given HTML promotes drug sales, return a list of strings that appear to be Telegram addresses, @usernames, or invitation links, which is mentioned in the promotion content."
    )

def extract_promotion_by_openai(html: str) -> dict[str, str]:
    """OpenAI 의 API를 사용해 마약 홍보 정보를 추출하는 API.
    gpt-4o 모델을 사용해서, 마약 홍보글인지 여부와 만약 그렇다면 발견되는 텔레그램 주소를 반환한다."""
    logger.debug(f"HTML 텍스트에서 마약 홍보 관련 내용 추출 시작. 텍스트 길이: {len(html)}")
    # 전체 HTMl 텍스트를 블록으로 분할
    text_blocks = extract_text_blocks_from_html(html)


    # LLM 모델 초기화 -> 구조화된 출력을 위한 LLM 설정
    llm_with_structured_output = ChatOpenAI(temperature=0,
                                            model=MODEL_NAME,
                                            streaming=True).with_structured_output(Analysis)

    # HTML을 분석해서 마약 홍보글 여부와 텔레그램 링크를 요구하는 프롬프트 템플릿 정의
    system_prompt = SystemMessagePromptTemplate.from_template(
        """You are an assistant to an investigator tracking illegal drug sales **advertised** on the internet.

You are given blocks of text extracted from web pages. These may include user-generated content, messages, or news articles. Your job is to determine whether **any portion** of the text **explicitly promotes or advertises** the sale of illegal drugs.

### REMEMBER:
Classify as `False` for news articles, police reports, or discussions that merely **report** on drug-related incidents without advertising or facilitating drug sales. 
If the content appears to be a news report (e.g., contains terms like “arrested”, “report”, “crackdown”, “police investigation”, “journalist”, etc.) or describes third-party actions without promoting sales, classify it as `False`.

The following argot terms are commonly used to refer to illegal drugs and may indicate promotional content when found in a commercial context (e.g., with words like "팝니다", "삽니다", "판매", "구매", "샘플", etc.):

### **Drug-related argot examples:**
- 떨, 위드, 허브, 해쉬, 브액, 대마초, 대마, 고기 (refers to marijuana)
- 아이스, 크리스탈, 술, 히로뽕, 필로폰, 작대기, 빙두 (refers to methamphetamine)
- 몰리, 엑시, 엑스터시, 도리도리, 캔디, XTC (refers to MDMA or ecstasy)
- 엘, 엘에스디, LSD (LSD)
- 케이 (Ketamine)


## Guidelines:
* Return True under `binary_classification` only if the text explicitly promotes or facilitates the sale of drugs, such as by listing prices, product names, or Telegram handles for orders.
* Return False under `binary_classification` if the content merely reports on drug-related activities (e.g., police investigations, news coverage, public announcements) without promoting sales.
* If meaning is ambiguous or there's no clear evidence of promotion, return False under `binary_classification`.
* If `binary_classification` is `False`, leave other fields empty.
* If `binary_classification` is `True`, return the exact portion of the input text that promotes drug sales under `promotion_content` (without translation or alteration). Also, from the promotion content, return any strings that appear to be Telegram addresses, @usernames, or invitation links as a list under `telegram_key`. This means:
    - Strip prefixes like t.me/, @, or phrases like <텔레그램 주소>.
    - Normalize any visually obfuscated text using Unicode characters that resemble Latin letters (e.g., 𝐎𝐆𝐆𝐎𝐎𝐌𝐀𝐍 → OGGOOMAN) before extracting.
    - For example, from t.me/𝐲𝐨𝐮𝐫𝐭𝐫𝐢𝐩𝟎𝟏, extract "yourtrip01".


### **Rules:**
- Only rely on what is explicitly written in the text.
- Do not hallucinate or imagine any content not present.
- If the promotional content is embedded within normal text, you must still detect and extract it.
- If the meaning is unclear or ambiguous, return `False` and leave other fields empty.
""",
    )
    human_prompt = HumanMessagePromptTemplate.from_template("""Analyze the following text:\n\n{text}\n\n""")

    # prompt + llm 바인딩 체인 생성
    chain = ChatPromptTemplate.from_messages([system_prompt, human_prompt]) | llm_with_structured_output

    # 결과 수신
    analysis = chain.invoke({"text": text_blocks})

    logger.debug(f"HTML 텍스트에서 추출한 결과: * 유의미한 글 내용: "
                 f"{'있음, * 발견된 텔레그램 주소: ' + str(len(analysis.telegram_keys)) + '개' if analysis.binary_classification else '없음'}")
    return {
        "classification_result": analysis.binary_classification,
        "promotion_content": analysis.promotion_content,
        "telegrams": analysis.telegram_keys,
    }