import logging
import os
import sys
from bs4 import BeautifulSoup
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from server.logger import logger
from server.db import Database
from typing import Optional, Union

def extract_text_blocks_from_html(html) -> list:
    if not html:
        return []

    # HTML 문서에서 텍스트 블록 추출
    soup = BeautifulSoup(html, "html.parser")
    text_blocks = soup.get_text(separator=" ").split("\n")

    text_blocks = [block.strip() for block in text_blocks if block.strip()]  # 빈 줄 제거

    

    # 추가적으로 태그 내부 텍스트도 수집 (특히 <h1>, <h2>, <p>, <div> 등의 class 포함)
    '''additional_texts = []
    for tag in soup.find_all(['h1', 'h2', 'p', 'div', 'span']):
        text = tag.get_text(strip=True)
        if text:
            additional_texts.append(text)

    # 합쳐서 중복 제거 후 반환
    all_blocks = list(set([block.strip() for block in text_blocks + additional_texts if block.strip()]))
    '''
    # 🔹 해시태그 텍스트들을 하나의 문자열로 합치기
    '''hashtag_texts = [
        a_tag.get_text(strip=True)
        for a_tag in soup.find_all("a", href=True)
        if "/hashtag/" in a_tag["href"]
    ]
    if hashtag_texts:
        joined_hashtags = " ".join(hashtag_texts)
        all_blocks.append(joined_hashtags)
'''
    # 중복 제거 후 반환
    #return list(set(all_blocks))
    return text_blocks
   
       

import json

# 데이터베이스에서 마약 은어/약어 로드(추후 데이터베이스에서 로드하도록 변경)
argot_collection = Database.Collection.ARGOT
drugs_collection = Database.Collection.DRUGS
argot_dictionary = dict()
for argot in argot_collection.find():
    argot_dictionary[argot["name"]] = argot["drugId"]

# 텍스트 길이가 가장 길고 특정 텍스트를 포함하는 원소를 반환하는 함수
def extract_by_length(strings: Union[str, list[str]]) -> Optional[str]:
    # 은어/약어 사전에 맞는 문자열들을 필터링
    filtered_strings = [chunk for chunk in strings if sum(keyword in chunk for keyword in argot_dictionary) >= 3]

    # 조건에 맞는 문자열이 있다면 가장 긴 문자열을 글 내용으로 반환하고, 없다면 None 반환
    return str(max(filtered_strings, key=len)) if filtered_strings else None


# HTML 텍스트에서 마약 홍보에 관련된 유의미한 글 내용을 추출하고, 발견된 텔레그램 주소가 있다면 주소까지 반환하는 함수
def extract_promotion_content(html: str) -> dict[str, str]:
    # 전체 HTMl 텍스트를 블록으로 분할하여 유의미한 텍스트를 추출해보고, 없다면 None 저장
    logger.debug(f"HTML 텍스트에서 마약 홍보 관련 내용 추출 시작. 텍스트 길이: {len(html)}")
    extracted_content = extract_by_length(text_blocks := extract_text_blocks_from_html(html))
    # 추출된 결과가 있다면 텔레그램 주소도 찾아보고, 없다면 텔레그램 주소도 빈 배열로 반환
    telegrams = extract_telegram_links(text_blocks) if extracted_content else []

    logger.debug(f"HTML 텍스트에서 추출한 결과: * 유의미한 글 내용: "
                 f"{'있음, * 발견된 텔레그램 주소: '+str(len(telegrams))+'개' if extracted_content else '없음'}")
    return {
        "promotion_content": extracted_content,
        "telegrams": telegrams
    }


import re

# 텍스트에서 텔레그램 링크들을 식별해서 리스트로 묶어 반환하는 함수
def extract_telegram_links(data: Union[str, list[str]]) -> list[str]:
    telegram_pattern = r"(?i)(?:https?://)?t\.me/(?:s/|joinchat/)?([~+]?[a-zA-Z0-9_-]+)(?:/\d+)?"


    if not data:
        return []  # None이나 빈 값이면 그냥 빈 리스트로 반환

    if isinstance(data, str):
        return re.findall(telegram_pattern, data)

    elif isinstance(data, list):
        if all(isinstance(text, str) for text in data):
            return [
                telegram_link
                for regex_result in map(re.findall, [telegram_pattern] * len(data), data)
                for telegram_link in regex_result
            ]
        else:
            logging.critical("extract_telegram_links: 리스트 내부에 문자열이 아닌 요소가 있음.")
            return []

    else:
        logging.critical(f"extract_telegram_links: 예상치 못한 타입 입력됨: {type(data)}")
        return []



if __name__ == "__main__":
   # print(extract_telegram_links("http://t.me/+sample"))
    sample_html = '''
    <div class="description" ng-show="$state.includes('model.detail')">
		<div read-more="" content="<p>아이스팝니다 텔레icegame911 작대기팝니다 아이스샘플 작대기샘플 빙두샘플 차가운술샘플 시원한술샘플 히로뽕샘플 캔디팝니다 엑스터시팝니다 도리도리팝니다 엑시팝니다 엑시팔아요 엑스터시팔어요 엑시파는곳 도리도리팔아요 도리도리파는곳 캔디파는곳 히로뽕파는곳 빙두팔아요 빙두파는곳 히로뽕팔아요 작대기파는곳 작대기팔아요 아이스팔아요 아이스파는곳 떨팝니다 대마초팝니다 대마팝니다 대마팔아요 대마초팔아요 떨팔아요&nbsp;텔레&nbsp;icegame911 캔디구해요 작대기구해요 아이스구해요 빙두구해요 빙두사는곳 아이스사는곳 텔레 icegame911 엘팝니다 lsd팝니다 엘구해요 캔디사요 아이스사요 작대기사요 작대기판매 아이스판매 떨판매 대마초판매 대마판매 아이스구입 작대기구입 빙두판매 차가운술판매 크리스탈팝니다 시원한술판매 차가운술구입 캔디구입 도리도리구입 도리도리판매 시원한술사요 차가운술사요 시원한술구입 텔레 icegame911 아이스가격 아이스1g가격 작대기가격 빙두가격 차가운술가격 시원한술가격 크리스탈가격 떨가격 캔디가격 대마가격 엑스터시가격 대마초가격 엑시가격 도리도리가격 엘사는곳 lsd사는곳 텔레 icegame911 lsd구합니다 아이스구합니다 아이스구히는곳 작대기구하는곳 아이스 차가운술 시원한술 작대기 캔디 엑스터시 엑시 크리스탈 빙두 도리도리 떨 엘 대마 lsd 대마초</p>" text-class="text-overflow" link-class="link color-blue text-big" class="ng-isolate-scope"><div class="readMoreContentContainer text-overflow" ng-bind-html="content"><p>아이스팝니다 텔레icegame911 작대기팝니다 아이스샘플 작대기샘플 빙두샘플 차가운술샘플 시원한술샘플 히로뽕샘플 캔디팝니다 엑스터시팝니다 도리도리팝니다 엑시팝니다 엑시팔아요 엑스터시팔어요 엑시파는곳 도리도리팔아요 도리도리파는곳 캔디파는곳 히로뽕파는곳 빙두팔아요 빙두파는곳 히로뽕팔아요 작대기파는곳 작대기팔아요 아이스팔아요 아이스파는곳 떨팝니다 대마초팝니다 대마팝니다 대마팔아요 대마초팔아요 떨팔아요&nbsp;텔레&nbsp;icegame911 캔디구해요 작대기구해요 아이스구해요 빙두구해요 빙두사는곳 아이스사는곳 텔레 icegame911 엘팝니다 lsd팝니다 엘구해요 캔디사요 아이스사요 작대기사요 작대기판매 아이스판매 떨판매 대마초판매 대마판매 아이스구입 작대기구입 빙두판매 차가운술판매 크리스탈팝니다 시원한술판매 차가운술구입 캔디구입 도리도리구입 도리도리판매 시원한술사요 차가운술사요 시원한술구입 텔레 icegame911 아이스가격 아이스1g가격 작대기가격 빙두가격 차가운술가격 시원한술가격 크리스탈가격 떨가격 캔디가격 대마가격 엑스터시가격 대마초가격 엑시가격 도리도리가격 엘사는곳 lsd사는곳 텔레 icegame911 lsd구합니다 아이스구합니다 아이스구히는곳 작대기구하는곳 아이스 차가운술 시원한술 작대기 캔디 엑스터시 엑시 크리스탈 빙두 도리도리 떨 엘 대마 lsd 대마초</p></div><a href="" class="read-more link color-blue text-big shadow" ng-class="{shadow: !expanded}" ng-show="showLinks" ng-click="toggle()" style="">Show more...</a></div>
	</div>
    '''
    print(extract_promotion_content(sample_html))
    print(extract_text_blocks_from_html(sample_html))

    

