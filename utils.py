from flask import jsonify

from itertools import zip_longest

def merge_lists_remove_duplicates(lists):
    seen = set()  # 중복 체크용
    result = []

    # zip_longest를 사용하여 여러 리스트를 병렬로 순회
    for items in zip_longest(*lists, fillvalue=None):
        for item in items:
            if item is not None and item not in seen:  # 중복 제거
                seen.add(item)
                result.append(item)

    return result

from collections import deque

def merge_parallel_unique_by_link(all_urls: dict[str, list[dict[str, str]]]) -> list[dict[str, str]]:
    """
        여러 개의 리스트(dict[str, str] 형식)를 병렬적으로 interleaving 순회하면서,
        각 dict의 "link" 값을 기준으로 중복을 제거한 결과 리스트를 반환합니다.

        각 리스트의 앞쪽부터 번갈아 가며 요소를 하나씩 추출하고,
        "link" 값이 중복되지 않는 경우에만 결과에 추가합니다.

        :param all_urls: 여러 개의 dict[str, str] 리스트를 값으로 가지는 딕셔너리
                         예: {"a": [{"link": "url1", ...}, ...], "b": [...], ...}
        :type all_urls: dict[str, list[dict[str, str]]]
        :return: 중복되지 않은 "link"를 기준으로 병렬적으로 수집된 결과 리스트
        :rtype: list[dict[str, str]]
    """
    queues = [deque(lst) for lst in all_urls.values()] # deque된 Queue 객체를 여러 개 생성
    seen_links = set()
    result = []

    while any(queues): # 값이 있는 Queue가 하나라도 있다면 계속해서 순회
        for queue in queues: # 모든 Queue에 대해서 각 Queue에서 데이터를 하나씩 순회하면서 뽑아서 저장(interleaving)
            if queue: # Queue가 [], 즉 소진되지 않았을 경우에만 데이터 pop
                item:dict[str, str] = queue.popleft()
                link = item.get("link")
                if link and link not in seen_links:
                    seen_links.add(link)
                    result.append(item)
    return result

def merge_parallel_unique(all_urls: dict[str, list[str]]) -> list[str]:
    """
        여러 개의 문자열 리스트를 병렬적으로 interleaving 순회하면서,
        중복되지 않은 문자열만을 결과 리스트로 반환합니다.

        각 리스트의 앞쪽부터 번갈아 가며 하나씩 값을 뽑고,
        이미 등장한 문자열은 무시하고 새로운 문자열만 추가합니다.

        :param all_urls: 문자열 리스트들을 값으로 가지는 딕셔너리
                         예: {"a": ["url1", "url2"], "b": ["url3", ...], ...}
        :type all_urls: dict[str, list[str]]
        :return: 중복되지 않은 문자열로 구성된 리스트
        :rtype: list[str]
    """
    queues = [deque(lst) for lst in all_urls.values()] # deque된 Queue 객체를 여러 개 생성
    seen_urls = set()
    result = []

    while any(queues): # 값이 있는 Queue가 하나라도 있다면 계속해서 순회
        for queue in queues: # 모든 Queue에 대해서 각 Queue에서 데이터를 하나씩 순회하면서 뽑아서 저장(interleaving)
            if queue: # Queue가 [], 즉 소진되지 않았을 경우에만 데이터 pop
                url:str = queue.popleft()
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    result.append(url)
    return result


from typing import get_origin, get_args, Any, Union, Literal

def is_valid_type(value, expected_type):
    origin = get_origin(expected_type)
    args = get_args(expected_type)

    if origin is Union:
        # Union 타입 처리: 여러 타입 중 하나라도 만족하면 True
        return any(is_valid_type(value, arg) for arg in args)

    elif origin is Literal:
        # Literal 타입: 고정된 값 중 하나여야 함
        return value in args

    elif origin is list:
        if not isinstance(value, list):
            return False
        if args:  # e.g. list[str]
            return all(is_valid_type(item, args[0]) for item in value)
        return True

    elif origin is dict:
        if not isinstance(value, dict):
            return False
        if args:  # e.g. dict[str, int]
            key_type, value_type = args
            return all(is_valid_type(k, key_type) and is_valid_type(v, value_type)
                       for k, v in value.items())
        return True

    elif origin is tuple:
        if not isinstance(value, tuple):
            return False
        if args:
            return all(is_valid_type(v, t) for v, t in zip(value, args))
        return True

    elif isinstance(expected_type, type):
        return isinstance(value, expected_type)

    return False

def confirm_request(data: dict, required: dict[str, Any]):
    if not data:
        return jsonify({"error": "Please provide JSON request body."}), 400

    for key, expected_type in required.items():
        if key not in data:
            return jsonify({"error": f"Please provide '{key}' field in the JSON request body."}), 400
        if not is_valid_type(data[key], expected_type):
            return jsonify({
                "error": f"Field '{key}' has invalid datatype or value. "
                         f"Expected {expected_type}, got {data[key]!r} ({type(data[key]).__name__})"
            }), 400

    return None

import uuid
import typing
def generate_integer_id64(existing_ids:typing.Iterable[int]=None):
    """64비트 무작위 정수 ID를 생성해서 반환하는 함수."""
    # uuid4()를 사용하여 무작위 UUID 생성 후, 정수형으로 변환
    if not existing_ids:
        return uuid.uuid4().int % (1 << 63)
    while (new_id:=uuid.uuid4().int % (1 << 63)) in existing_ids:
        pass
    return new_id


def compare_dicts_sorted(
        dict1: dict[str, list[int]],
        dict2: dict[str, list[int]]
) -> bool:
    """두 개의 딕셔너리를 비교해서 원소가 완벽히 동일하면 참을, 그렇지 않으면 거짓을 반환하는 함수."""
    # 두 딕셔너리의 키 집합이 동일한지 확인
    if set(dict1.keys()) != set(dict2.keys()):
        return False

    # 각 키별로 정렬된 리스트를 비교 (중복을 고려)
    for key in dict1:
        if sorted(dict1[key]) != sorted(dict2[key]):
            return False

    return True


import requests

def request_api(**request_kwargs):
    """간단한 API 요청 함수."""
    if request_kwargs.get('method') == "GET":
        return requests.get(request_kwargs.get('url'), params=request_kwargs['params'])
    elif request_kwargs.get('method') == "POST":
        return requests.post(request_kwargs.get('url'), json=request_kwargs['data'])
    else:
        return requests.models.Response()

class ApiResponse:
    def __init__(self, response):
        self.status_code = response.status_code
        try:
            self.data = response.json()
        except Exception as e:
            self.data = response.reason

    def __repr__(self):
        string = f"status: {self.status_code}\ndata:"
        if isinstance(self.data, dict):
            for key, value in self.data.items():
                string += f"\n\t{key}: {value}"
        else:
            string += f"\t{self.data}"
        return string

def api_test(**request_kwargs):
    return ApiResponse(request_api(**request_kwargs))