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
    """Neo4j 데이터베이스에서 Cypher 쿼리를 실행합니다.

    Args:
        query: 실행할 Cypher 쿼리 문자열
        parameters: 쿼리에 사용할 파라미터 (기본값: None)

    Returns:
        Result: Neo4j 쿼리 실행 결과
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
                    RETURN c
                """
                MERGE = """
                    MERGE (c:Channel {id: $id})
                    ON CREATE SET
                        c.title = $title, 
                        c.username = $username,
                        c.status = $status
                    ON MATCH SET
                        c.title = $title,
                        c.username = $username,
                        c.status = $status
                    RETURN c
                """

            class Post:
                MERGE = """
                    MERGE (p:Post {link: $link})
                    ON CREATE SET 
                        p.siteName = $siteName,
                        p.content = $content, 
                        p.createdAt = $createdAt,
                        p.updatedAt = $updatedAt,
                        p.deleted = $deleted
                    ON MATCH SET
                        p.siteName = $siteName,
                        p.content = $content, 
                        p.updatedAt = $updatedAt,
                        p.deleted = $deleted
                    RETURN p
                """

            class Argot:
                CREATE = """
                    CREATE (a:Argot {
                      name: $name,
                      drugId: $drugId
                    })
                    RETURN a
                """
                MERGE = """
                    MERGE (a:Argot {name: $name})
                    ON CREATE SET
                        a.drugId = $drugId
                    RETURN a
                """

            class Drug:
                MERGE = """
                    MERGE (d:Drug {id: $id})
                    ON CREATE SET d.name = $name, d.type = $type, d.englishName = $englishName
                    RETURN d
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
                MERGE (a)-[r:REFERS_TO]->(d)
            """
            PROMOTES = """
                MATCH (p:Post {link: $link})
                MATCH (c:Channel {id: $channelId})
                MERGE (p)-[pr:PROMOTES]->(c)
            """


if __name__ == "__main__":
    from datetime import datetime

    for channelId, posts in {
        2229635697: [
            {
                "link": "https://quizlet.com/kr/677249748/%ED%85%94%EB%A0%88-popr777-%EC%95%84%EC%9D%B4%EC%8A%A4%EA%B5%AC%EB%A7%A4%EC%B2%98-%EC%95%84%EC%9D%B4%EC%8A%A4%ED%8C%9D%EB%8B%88%EB%8B%A4-%EC%95%84%EC%9D%B4%EC%8A%A4%EA%B5%AC%EC%9E%85%EC%B2%98-flash-cards/",
                "siteName": "quizlet.com",
                "content": """안녕하세요.풍선아이스입니다.
    텔레그램ID ☎️ : popr777 텔레그램ID ☎️ : popr777 텔레그램ID ☎️ : popr777 텔레그램ID ☎️ : popr777
    아이스(필로폰 , 히로뽕 ) / 엑스터시( 캔디 ) / 떨( 위드,대마,고기 ) / 떨액 / 케타민( 케이 )
    순도 높은 제품으로 안전하고 깔끔한 거래를 합니다.
    장기적으로 이용할수있는 분들 연락주세요.
    고순도 제품 / 그람수는 넉넉히
    필요할때 언제든지 믿고 이용할수 있게!!
    아이스 아이스구입 아이스구매 아이스판매 아이스파는곳 아이스구입방법 아이스구매방법 아이스작대기 아이스팝니다 아이스가격 아이스술 아이스구해요 아이스구합니다 아이스구입사이트 아이스판매사이트 얼음술 아이스구매사이트 아이스술팝니다 필로폰 아이스정품구입
    작대기 작대기구입 작대기구매 작대기판매 작대기파는곳 작대기구입방법 작대기구매방법 작대기팝니다 작대기가격 작대기구입사이트 정품작대기구입사이트 작대기판매사이트
    대마초 대마초구입 대마초구매 대마초판매 대마초파는곳 대마초구입방법 대마초구매방법 대마초팝니다 대마초가격 대마초구입사이트 대마초판매하는곳 대마초구매사이트 대마초판매사이트
    엑스터시 엑스터시구입 엑스터시구매 엑스터시판매 엑스터시파는곳 엑스터시구입방법 엑스터시구매방법 엑스터시팝니다 엑스터시가격 엑스터시구입사이트 정품엑스터시팝니다 엑스터시후기
    떨구입 떨구매 떨판매 떨파는곳 떨구입방법 떨구매방법 떨팝니다 떨가격 떨구입사이트 홍대떨구입방법 떨구매사이트 서울떨팝니다 떨판매사이트
    액상대마 액상대마구입 액상대마구매 액상대마판매 액상대마파는곳 액상대마구입방법 액상대마구매방법 액상대마팝니다 액상대마가격 액상대마구입사이트
    액상떨 액상떨구입 액상떨구매 액상떨판매 액상떨파는곳 액상떨구입방법 액상떨구매방법 액상떨팝니다 액상떨가격 액상떨구입사이트
    빙두 빙두구입 빙두구매 빙두판매 빙두파는곳 빙두구입방법 빙두구매방법 빙두팝니다 빙두가격
    #아이스 #아이스구입 #아이스구입방법 #아이스구입사이트 #아이스구매 #아이스구매방법 #아이스판매 #아이스팝니다 #아이스파는곳 #아이스가격 #아이스구합니다 #아이스구해요 #아이스술 #아이스작대기 #아이스판매사이트 #얼음술 #아이스구매사이트 #아이스술팝니다 #필로폰 #아이스정품구입
    #작대기 #작대기구입 #작대기구입방법 #작대기구매 #작대기구매방법 #작대기판매 #작대기파는곳 #작대기가격 #작대기구입사이트 #정품작대기구입사이트 #작대기판매사이트
    #대마초 #대마초구입 #대마초구매 #대마초판매 #대마초파는곳 #대마초구입방법 #대마초구매방법 #대마초팝니다 #대마초가격 #대마초구입사이트 #대마초판매하는곳 #대마초구매사이트 #대마초판매사이트
    #엑스터시 #엑스터시구입 #엑스터시구매 #엑스터시판매 #엑스터시파는곳 #엑스터시구입방법 #엑스터시구매방법 #엑스터시팝니다 #엑스터시가격 #엑스터시구입사이트 #정품엑스터시팝니다 #엑스터시후기
    #액상대마 #액상대마구입 #액상대마구매 #액상대마판매 #액상대마파는곳 #액상대마구입방법 #액상대마구매방법 #액상대마팝니다 #액상대마가격 #액상대마구입사이트
    #액상떨 #액상떨구입 #액상떨구매 #액상떨판매 #액상떨파는곳 #액상떨구입방법 #액상떨구매방법 #액상떨팝니다 #액상떨가격 #액상떨구입사이트
    #떨구입 #떨구매 #떨판매 #떨파는곳 #떨구입방법 #떨구매방법 #떨팝니다 #떨가격 #떨구입사이트 #홍대떨구입방법 #떨구매사이트 #서울떨팝니다 #떨판매사이트
    #빙두 #빙두구입 #빙두구매 #빙두판매 #빙두파는곳 #빙두구입방법 #빙두구매방법 #빙두팝니다 #빙두가격
    """,
                "createdAt": datetime.now(),
                "updatedAt": datetime.now(),
                "deleted": False,
            }, {
                "link": "https://arte365.kr/?s=%ED%85%94%EB%A0%88%EA%B7%B8%EB%9E%A8%EC%95%84%EC%9D%B4%EC%8A%A4%EC%95%88%EC%A0%84%EB%93%9C%EB%9E%8D%E2%88%AE%E2%88%88@%E1%B4%8F%C9%B4%E1%B4%87%CA%9C%E1%B4%8F1004%E2%88%8B%E3%83%94/=%EC%95%84%EC%9D%B4%EC%8A%A4%EC%9B%90%ED%98%B8?loc=ko",
                "siteName": "arte365.kr",
                "content": "",
                "createdAt": datetime.now(),
                "updatedAt": datetime.now(),
                "deleted": True,
            }, {
                "link": "https://yozm.wishket.com/magazine/questions/share/DsiVon1Vm9cPAPav/",
                "siteName": "yozm.wishket.com",
                "content": r"""남순아이스 텔레그램 @NAMSOON892 아이스작대기 판매 " 작대기아이스팝니다 namsoon524 남순아이스 텔레그램 아이디가 뭔가요? 남순아이스 텔레그램 @NAMSOON892 아이스작대기 판매 " 작대기아이스팝니다 namsoon524 남순아이스 텔레그램 아이디가 뭔가요? 남순아이스 텔레그램 @NAMSOON892 아이스작대기 판매 " 작대기아이스팝니다 namsoon524 남순아이스 텔레그램 아이디가 뭔가요?""",
                "createdAt": datetime.now(),
                "updatedAt": datetime.now(),
                "deleted": False,
            },
        ],
        2452254167: [
            {
                "link": "https://kum3.cafe24.com/m/board/product/read.html?no=2288411&board_no=6&cate_no=1&page=5",
                "siteName": "kum3.cafe24.com",
                "content": r"""텔레그램 yourtrip01 떨팝니다.


    Yourtrip &

    stealthstore떨팝니다.



    기간이 안전성을 보증합니다.



    텔레그램 정책 변경으로



    세션과 시그널에서 거래하고있습니닷





    떨액,버드,헤쉬쉬,Lsd

    캔디,케이,허브,몰리,브액



    하이코리아 미미월드 위니플



    yourtrip

    stealthstore



    아실만한분들은 대화해보시면 아실거라 생각합니닷



    구력이 된 유저분들 은 대화 몇마디에 바로 아실겁니다.



    24시간 문의가능

    세션(session)메신저 아이디코드 :

    05df280daae92f58ecb30796d71659eb1126364f9131879d26d98a39eed9cab257



    시그널 메신저

    Yourtrip.01



    텔레그램 @yourtrip01



    텔레그램 채널

    T.me/sessionyourtrip



    함께 일하실분 구합니다.



    이바닥 제대로 배워 큰돈벌어보실분 연락주세요.



    #떨팝니다#떨액팝니다#강남떨#부산떨#떨선드랍#케이팝니다#고수익알바#해외알바""",
                "createdAt": datetime.now(),
                "updatedAt": datetime.now(),
                "deleted": False,
            }, {
                "link": "http://kctuscn.org/?pageid=3&page_id=418&mod=document&uid=2730",
                "siteName": "kctuscn.org",
                "content": r"""텔레그램 yourtrip01 떨팝니다.

    Yourtrip &
    stealthstore떨팝니다.

    기간이 안전성을 보증합니다.

    텔레그램 정책 변경으로

    세션과 시그널에서 거래하고있습니닷


    떨액,버드,헤쉬쉬,Lsd
    캔디,케이,허브,몰리,브액

    하이코리아 미미월드 위니플

    yourtrip
    stealthstore

    아실만한분들은 대화해보시면 아실거라 생각합니닷

    구력이 된 유저분들 은 대화 몇마디에 바로 아실겁니다.

    24시간 문의가능
    세션(session)메신저 아이디코드 :
    05df280daae92f58ecb30796d71659eb1126364f9131879d26d98a39eed9cab257

    시그널 메신저
    Yourtrip.01

    텔레그램 @yourtrip01

    텔레그램 채널
    T.me/sessionyourtrip

    함께 일하실분 구합니다.

    이바닥 제대로 배워 큰돈벌어보실분 연락주세요.

    #떨팝니다#떨액팝니다#강남떨#부산떨#떨선드랍#케이팝니다#고수익알바#해외알바""",
                "createdAt": datetime.now(),
                "updatedAt": datetime.now(),
                "deleted": False,
            }, {
                "link": "http://www.dowonpension.co.kr/board/bbs/board.php?bo_table=after&wr_id=10330&page=13",
                "siteName": "www.dowonpension.co.kr",
                "content": r"""텔레그램 yourtrip01 떨팝니다.

    Yourtrip &
    stealthstore떨팝니다.

    기간이 안전성을 보증합니다.

    텔레그램 정책 변경으로

    세션과 시그널에서 거래하고있습니닷


    떨액,버드,헤쉬쉬,Lsd
    캔디,케이,허브,몰리,브액

    하이코리아 미미월드 위니플

    yourtrip
    stealthstore

    아실만한분들은 대화해보시면 아실거라 생각합니닷

    구력이 된 유저분들 은 대화 몇마디에 바로 아실겁니다.

    24시간 문의가능
    세션(session)메신저 아이디코드 :
    05df280daae92f58ecb30796d71659eb1126364f9131879d26d98a39eed9cab257

    시그널 메신저
    Yourtrip.01

    텔레그램 @yourtrip01

    텔레그램 채널
    T.me/sessionyourtrip

    함께 일하실분 구합니다.

    이바닥 제대로 배워 큰돈벌어보실분 연락주세요.

    #떨팝니다#떨액팝니다#강남떨#부산떨#떨선드랍#케이팝니다#고수익알바#해외알바""",
                "createdAt": datetime.now(),
                "updatedAt": datetime.now(),
                "deleted": False,
            }, {
                "link": "https://www.evanix.com/bbs/board.php?bo_table=notice&wr_id=50376&sst=wr_hit&sod=desc&sop=and&page=3428",
                "siteName": "www.dowonpension.co.kr",
                "content": r"""텔레그램 yourtrip01 떨팝니다.

    Yourtrip &
    stealthstore떨팝니다.

    기간이 안전성을 보증합니다.

    텔레그램 정책 변경으로

    세션과 시그널에서 거래하고있습니닷


    떨액,버드,헤쉬쉬,Lsd
    캔디,케이,허브,몰리,브액

    하이코리아 미미월드 위니플

    yourtrip
    stealthstore

    아실만한분들은 대화해보시면 아실거라 생각합니닷

    구력이 된 유저분들 은 대화 몇마디에 바로 아실겁니다.

    24시간 문의가능
    세션(session)메신저 아이디코드 :
    05df280daae92f58ecb30796d71659eb1126364f9131879d26d98a39eed9cab257

    시그널 메신저
    Yourtrip.01

    텔레그램 @yourtrip01

    텔레그램 채널
    T.me/sessionyourtrip

    함께 일하실분 구합니다.

    이바닥 제대로 배워 큰돈벌어보실분 연락주세요.

    #떨팝니다#떨액팝니다#강남떨#부산떨#떨선드랍#케이팝니다#고수익알바#해외알바""",
                "createdAt": datetime.now(),
                "updatedAt": datetime.now(),
                "deleted": False,
            },
        ],
    }.items():
        for post in posts:
            run_cypher(Neo4j.QueryTemplate.Node.Post.MERGE, post)
            run_cypher(Neo4j.QueryTemplate.Edge.PROMOTES, {
                'channelId': channelId,
                'link': post['link'],
            })
            print(channelId, post['link'])
