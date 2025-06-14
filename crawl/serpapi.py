import requests
import os

from serpapi import GoogleSearch

from preprocess import extractor
from server.logger import logger
from utils import merge_parallel_unique_by_link, merge_parallel_unique

SERPAPI_KEY = os.getenv('SERPAPI_KEY')  # SerpApi API Key

def serp(q: str,
         api_key: str = SERPAPI_KEY,
         engine: str = "google",
         max_result: int = 10,
         ) -> tuple[list[dict[str, str]], list[str]]:
    """
        SerpAPI를 이용해 Google 검색을 수행하고, 검색 결과 중 텔레그램 링크와 일반 웹페이지 링크를 추출합니다.

        검색 결과의 각 항목에서 링크를 분석하여 텔레그램 채널 링크는 별도로 분류하고,
        일반 웹 링크는 제목, 링크, 출처(source) 정보를 포함한 딕셔너리 형태로 리스트에 저장합니다.

        또한 SerpAPI의 페이지네이션을 이용해 최대 max_result 수만큼 결과를 반복적으로 수집합니다.

        :param q: 검색어 쿼리 문자열
        :type q: str
        :param api_key: SerpAPI 키 (기본값은 환경 변수 또는 상수로 정의된 SERPAPI_KEY)
        :type api_key: str
        :param engine: 사용할 검색 엔진 이름 (기본값: "google")
        :type engine: str
        :param max_result: 최대 검색 결과 수. 페이지네이션을 통해 반복적으로 결과를 수집하며 이 수를 넘지 않도록 제한.
        :type max_result: int
        :return: (1) 일반 웹 페이지 결과 리스트, (2) 추출된 텔레그램 채널 이름 리스트
        :rtype: tuple[list[dict[str, str]], list[str]]
    """

    params = {
        "api_key": api_key,  # SerpAPI 키
        "engine": engine,
        "q": q,
        "hl": "ko",  # 한국어로 검색
        "gl": "kr",  # 한국 지역에서 검색
        "nfpr": 1,  # 자동 교정된 검색 제외
        "lr": "lang_ko",  # 검색 결과에서 한국어만 반환
        "safe": "off",  # 성인 콘텐츠 검열 안함
    }

    serpapi_result = GoogleSearch(params).get_dict()

    urls: list[dict[str, str]] = []
    telegrams: list[str] = []

    while serpapi_result and serpapi_result.get("organic_results"):
        for item in serpapi_result["organic_results"]:
            if max_result < 1:
                break

            if item.get("link"):
                extracted_telegram_links = extractor.extract_telegram_links(item.get("link"))
                # 추출된 텔레그램 링크가 있을 경우 텔레그램 항목에 추가
                if extracted_telegram_links:
                    # Google 검색 결과이기 때문에 반환된 텔레그램 주소 목록은 1개뿐이고, 때문에 index=0만 바로 사용
                    channel_name = extracted_telegram_links[0].lower()
                    telegrams.append(channel_name)
                else:
                    urls.append({
                        "title": item.get("title"),
                        "link": item.get("link"),
                        "source": item.get("source")
                    })  # 검색 결과 링크의 웹페이지 제목, 도메인 이름(soruce)을 같이 저장
                max_result -= 1  # 검색 가능 수를 1 차감

        # 다음 페이지가 있고, 검색 가능 결과 수가 남았을 경우 다음 페이지로 다시 검색
        if (next_link := serpapi_result["serpapi_pagination"].get("next")) and max_result > 0:
            try:
                response = requests.get(next_link, params={"api_key": api_key}, timeout=30) # "serpapi의 "next"에는 API KEY는 빠져 있으므로, 다시 지정해 주어야 함.
            except Exception as e:
                logger.error(e)
                break
            if response.status_code == 200:
                serpapi_result = response.json()
            else:
                logger.warning(f"SerpApi returned with an error message: {response.text}")
                serpapi_result = None
        else:  # 다음 페이지가 없거나 최대 검색 수에 도달했을 경우 검색 중단
            serpapi_result = None

    return urls, telegrams


# SerpApi 검색 결과에서 URL을 가져오는 함수
def search_links_by_serpapi(queries: list[str],
                            max_results: int=10) -> dict:
    """
        주어진 복수의 검색어에 대해 SerpAPI를 사용하여 검색을 수행하고,
        각 검색어에 대해 일반 웹 링크와 텔레그램 링크를 병렬적으로 interleaving 방식으로 수집합니다.

        중복을 제거한 최종 결과는 'google' 키에 일반 링크, 'telegrams' 키에 텔레그램 링크로 구성된 딕셔너리로 반환됩니다.

        :param queries: 검색어 문자열 리스트
        :type queries: list[str]
        :param max_results: 각 검색어마다 가져올 최대 검색 결과 수 (None이면 기본값 10 사용)
        :type max_results: int
        :return: {
            "google": list[dict[str, str]],  # 제목, 링크, 출처를 포함한 일반 검색 결과
            "telegrams": list[str]           # 추출된 텔레그램 채널 이름들
        }
        :rtype: dict
    """
    if max_results is None:
        max_results=10
    logger.info(f'검색어 {len(queries)}개에 대한 검색 시작...')
    # 모든 검색어에 대한 검색 수행
    all_urls: dict[str, list[dict[str, str]]] = {}
    all_telegrams: dict = {}
    for query in queries:
        logger.debug(f'검색어 "{query}"에 대한 검색 시작...')
        # 검색 후 값 저장
        urls, telegrams = serp(q=query,
                               api_key=SERPAPI_KEY,
                               engine="google",
                               max_result=max_results,)
        all_urls[query], all_telegrams[query] = urls, telegrams
        logger.debug(f'검색어 "{query}"에 대한 검색 결과(최대 {max_results}개): URL {len(urls)}개, Telegram 채널 {len(telegrams)}개')

    all_urls: list[dict[str, str]] = merge_parallel_unique_by_link(all_urls)
    all_telegrams: list[str] = merge_parallel_unique(all_telegrams)

    if not all_urls:
        logger.info(f"검색어 {len(queries)}개에 대한 전체 검색 결과가 없습니다.")
    else:
        logger.info(f"검색어 {len(queries)}개에 대한 검색 결과: URL {len(all_urls)}개, Telegram 채널 {len(all_telegrams)}")

    # URL들과 텔레그램 채널 결과를 합쳐서 딕셔너리로 결과 반환
    return {
        'google': all_urls,
        'telegrams': all_telegrams
    }