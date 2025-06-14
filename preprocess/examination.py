import sys
import os
import requests
import re
import time
import datetime
import pandas as pd
from extractor import extract_promotion_content
from extractor import extract_text_blocks_from_html
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QFileDialog, QLabel, QVBoxLayout, QWidget, QMessageBox
)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from preprocess.ai_extractor import extract_promotion_by_openai
from server.logger import logger

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}

def get_html_from_url(url: str) -> str:
    """URL에서 HTML 내용을 가져옵니다.

    Args:
        url: HTML을 가져올 URL

    Returns:
        str: HTML 내용. 요청 실패 시 빈 문자열 반환
    """
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        html_text = response.text
        return html_text
    except requests.RequestException as e:
        logger.warning(f"URL [{url}] 에 대한 요청 실패: {e}")
        return ""
        
def process_ai_extraction(idx, html, max_retries=3):
    """AI를 사용하여 HTML에서 홍보 내용을 추출합니다.

    Args:
        idx: 처리 중인 인덱스
        html: HTML 문서 문자열
        max_retries: 최대 재시도 횟수 (기본값: 3)

    Returns:
        tuple: (인덱스, 추출된 내용, 분류 결과)
            - 추출된 내용: "NONE" 또는 추출된 텍스트 또는 "ERROR"
            - 분류 결과: "P" (홍보) 또는 "NP" (비홍보) 또는 "ERROR"
    """
    for attempt in range(max_retries):
        try:
            print(f"[DEBUG] AI 추출 시도 {attempt + 1}회: 인덱스 {idx}")
            ai_res = extract_promotion_by_openai(html)
            ai_content_raw = ai_res.get("promotion_content", "")
            ai_content = ai_content_raw if ai_content_raw.strip() else "NONE"
            ai_flag = "P" if ai_res.get("classification_result", False) else "NP"
            return idx, ai_content, ai_flag
        except Exception as e:
            if "rate limit" in str(e).lower() or "429" in str(e):
                print(f"[AI 추출 재시도 대기 - {attempt + 1}회]: {e}")
                time.sleep(15)
            else:
                print(f"[AI 추출 오류]: {e}")
                return idx, "ERROR", "ERROR"
    # 재시도 초과
    print(f"[AI 추출 실패 - 재시도 초과] 인덱스 {idx}")
    return idx, "ERROR", "ERROR"


def clean_text(text):
    """텍스트에서 제어 문자를 제거합니다.

    Args:
        text: 정제할 텍스트

    Returns:
        str: 정제된 텍스트
    """
    if pd.isna(text):
        return ""
    return re.sub(r"[\x00-\x1f]", "", str(text))

class PromotionLabelerApp(QMainWindow):
    """마약 홍보글 검사 도구의 GUI 애플리케이션 클래스입니다."""

    def __init__(self):
        """GUI 애플리케이션을 초기화합니다."""
        super().__init__()
        self.setWindowTitle("마약 홍보글 검사 도구")
        self.setGeometry(100, 100, 400, 200)

        self.label = QLabel("검사할 엑셀 파일을 선택해주세요.")
        self.button = QPushButton("엑셀 파일 선택 및 검사 시작")
        self.button.clicked.connect(self.select_and_label_file)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def select_and_label_file(self):
        """파일 선택 대화상자를 열고 선택된 파일을 검사합니다."""
        file_path, _ = QFileDialog.getOpenFileName(self, "엑셀 파일 선택", "", "Excel Files (*.xlsx)")
        if file_path:
            self.label.setText(f"선택된 파일: {file_path}")
            self.label_file(file_path)

    def label_file(self, file_path):
        """선택된 엑셀 파일의 URL들을 검사하고 결과를 저장합니다.

        Args:
            file_path: 검사할 엑셀 파일 경로
        """
        try:
            df = pd.read_excel(file_path)
            df = df.reset_index(drop=True)

            for idx in range(1, len(df)):
                url = str(df.iloc[idx, 0]).strip()
                if not url:
                    continue

                html = get_html_from_url(url)

                try:
                    text_blocks = extract_text_blocks_from_html(html)
                    text_block_text = " ".join(text_blocks)[:1000]
                except Exception as e:
                    print(f"[텍스트 블럭 추출 오류] {url}: {e}")
                    text_block_text = "ERROR"
                df.iloc[idx, 1] = clean_text(text_block_text)

                # 알고리즘 기반 추출
                if pd.isna(df.iloc[idx, 4]) or str(df.iloc[idx, 4]).strip() == "ERROR":
                    try:
                        alg_res = extract_promotion_content(html)
                        alg_content_raw = alg_res.get("promotion_content", "")
                        alg_content = alg_content_raw if alg_content_raw else "NONE"
                        alg_flag = "P" if alg_content_raw else "NP"
                    except Exception as e:
                        print(f"[알고리즘 오류] {url}: {e}")
                        alg_content, alg_flag = "ERROR", "ERROR"

                    df.iloc[idx, 2] = str(clean_text(alg_content))
                    df.iloc[idx, 4] = str(alg_flag)
                    df.to_excel(file_path, index=False)
                else:
                    print(f"[알고리즘 추출 건너뜀] 인덱스 {idx}")

                # AI 기반 추출
                if pd.isna(df.iloc[idx, 5]) or str(df.iloc[idx, 5]).strip() == "ERROR":
                    try:
                        print(f"[AI 추출 시작] 인덱스 {idx}")
                        ai_idx, ai_content, ai_flag = process_ai_extraction(idx, html)
                        df.iloc[ai_idx, 3] = str(clean_text(ai_content))
                        df.iloc[ai_idx, 5] = str(ai_flag)
                        df.to_excel(file_path, index=False)
                        print(f"[저장 완료] 인덱스 {ai_idx}")
                    except Exception as e:
                        print(f"[AI 추출 오류] 인덱스 {idx}: {e}")
                else:
                    print(f"[AI 추출 건너뜀] 인덱스 {idx}")

            print(f"[전체 완료] {len(df) - 1}개 중 검사된 {len(df) - 1}개 완료됨")  
            QMessageBox.information(self, "완료", "검사 완료!\n원본 파일에 저장되었습니다.")

        except Exception as e:
            QMessageBox.critical(self, "에러 발생", f"파일 처리 중 문제가 발생했습니다:\n{e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PromotionLabelerApp()
    window.show()
    sys.exit(app.exec_())
