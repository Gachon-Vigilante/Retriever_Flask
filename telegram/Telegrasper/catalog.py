from typing import Union

from langchain_core.prompts import ChatPromptTemplate

from server.db import Database
from server.logger import logger
from utils import dict_to_xml
from langchain_openai import ChatOpenAI
from ai.indications import Indications
from ai.datamodel import Catalog


def get_catalog(channel_id: int) -> dict[str, Union[list[int], str]]:
    logger.info(f"텔레그램 채널에서 가격 정보 검색 시작. Channel ID: {channel_id}")
    channel_data = Database.Collection.Channel.DATA

    # g, ml, 정, 팟, 지, 통, 만원, 만과 같은 단위가 포함되어 있고 숫자도 있거나,
    # 숫자가 2개 이상 있는 채팅을 불러오는 aggregation pipeline.
    pipeline = [
        {
            "$match": {
                "$and": [  # 기존 필터와 channelId 조건을 모두 만족해야 하므로 AND로 묶음
                    {
                        "channelId": channel_id
                    },
                    {
                        "$or": [
                            {
                                "$and": [
                                    {
                                        "text": {
                                            "$regex": "(g|ml|정|팟|지|통|만원|만)",
                                            "$options": "i"
                                        }
                                    },
                                    {
                                        "text": {
                                            "$regex": "\\d"
                                        }
                                    }
                                ]
                            },
                            {
                                "$expr": {
                                    "$gte": [
                                        {
                                            "$size": {
                                                "$regexFindAll": {
                                                    "input": "$text",
                                                    "regex": "\\d"
                                                }
                                            }
                                        },
                                        2
                                    ]
                                }
                            }
                        ]
                    }
                ]
            }
        }
    ]

    context = ["<chat>"+dict_to_xml({
        "id": doc["id"],
        "text": doc["text"],
    })+"</chat>" for doc in channel_data.aggregate(pipeline)]

    if context:
        llm = ChatOpenAI(model_name="gpt-4o", temperature=0).with_structured_output(Catalog)

        prompt = ChatPromptTemplate.from_messages([
            ("system", Indications.Extract.CATALOG),
            ("human", "Analyze this chats:\n{context}"),
        ])

        rag_chain = prompt | llm

        response:Catalog = rag_chain.invoke({"context": context})

        chat_ids = response.chatIds
        catalog = response.catalog

    else:
        chat_ids = []
        catalog = "가격 정보를 찾을 수 없습니다."

    logger.info(f"가격 정보 검색 결과(Channel Id: {channel_id}: {catalog}")

    return {
        "chatIds": chat_ids,
        "description": catalog,
    }

def update_catalog(channel_id: int) -> None:
    Database.Collection.Channel.INFO.update_one(
        {"_id": channel_id},
        {"$set": {"catalog": get_catalog(channel_id)}}
    )
