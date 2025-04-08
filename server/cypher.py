import os
from dotenv import load_dotenv
from neo4j import GraphDatabase, Result
from typing import Dict, Any, List

load_dotenv()

uri = os.environ.get("NEO4J_URI")  # 원격 Neo4j 인스턴스 URI
username = os.environ.get("NEO4J_USERNAME")
password = os.environ.get("NEO4J_PASSWORD")
neo4j_driver = GraphDatabase.driver(uri, auth=(username, password))  # neo4j+s의 s가 이미 암호화이기 때문에 encrypted=True를 넣으면 오류


def run_cypher(query, parameters: Dict[str, Any] = None) -> Result:
    """
    주어진 Cypher 쿼리와 파라미터를 실행하고 결과를 리스트로 반환한다.
    :param query: 실행할 Cypher 쿼리 문자열
    :param parameters: 쿼리에 사용할 파라미터 (옵션)
    :return: 결과를 딕셔너리 리스트로 반환
    """
    parameters = parameters or {}

    # 세션 열기
    with neo4j_driver.session() as session:
        return session.run(query, parameters)


class Neo4j:
    class QueryTemplate:
        class Node:
            class Channel:
                CREATE = """
                    CREATE (c:Channel {
                      id: $id,
                      title: $title,
                      username: $username,
                      status: $status
                    })
                    RETURN c;
                """

            class Argot:
                CREATE = """
                    CREATE (a:Argot {
                      name: $name
                    })
                    RETURN a;
                """
                MERGE = """
                    MERGE (a:Argot {name: $name})
                    ON CREATE SET a.name = $name
                    RETURN a;
                """

            class Drug:
                MERGE = """
                    MERGE (d:Drug {id: $id})
                    ON CREATE SET d.name = $name, d.type = $type, d.englishName = $englishName
                    RETURN d;
                """

        class Edge:
            SELLS = """
                MATCH (c:Channel {id: $channelId})
                MATCH (a:Argot {name: $argotName})
                MERGE (c)-[r:SELLS]->(a)
                SET r.chatIds = CASE
                    WHEN r.chatIds IS NULL THEN [$chatId]
                    WHEN NOT $chatId IN r.chatIds THEN r.chatIds + $chatId
                    ELSE r.chatIds
                END;
            """
            REFERS_TO = """
                MATCH (a:Argot {name: $argotName})
                MATCH (d:Drug {id: $drugId})
                MERGE (a)-[r:REFERS_TO]->(d);
            """


