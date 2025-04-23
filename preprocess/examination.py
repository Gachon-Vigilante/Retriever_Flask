import sys
import os
import requests
import re
import pandas as pd
from extractor import extract_promotion_content
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QFileDialog, QLabel, QVBoxLayout, QWidget, QMessageBox
)
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from preprocess.ai_extractor import extract_promotion_by_openai
from server.logger import logger
# 경로 설정
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}

def get_html_from_url(url: str) -> str:
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            html_text = response.text
            return html_text
        except requests.RequestException as e:
            logger.warning(f"URL [{url}] 에 대한 요청 실패: {e}")
            return ""
        
def process_ai_extraction(idx,html):
    try:
        ai_res = extract_promotion_by_openai(html)
        ai_content = ai_res.get("promotion_content", "")
        ai_flag = "P" if ai_res.get("classification_result", False) else "NP"
    except Exception as e:
        ai_content, ai_flag = "ERROR", "ERROR"
        print(f"[AI 추출 오류]: {e}")
    return idx, ai_content, ai_flag

def clean_text(text):
    # Excel에서 문제 되는 null byte, 제어문자 제거
    if pd.isna(text):
        return ""
    return re.sub(r"[\x00-\x1f]", "", str(text))
        
class PromotionLabelerApp(QMainWindow):
    def __init__(self):
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
        file_path, _ = QFileDialog.getOpenFileName(self, "엑셀 파일 선택", "", "Excel Files (*.xlsx)")
        if file_path:
            self.label.setText(f"선택된 파일: {file_path}")
            self.label_file(file_path)

    

    def label_file(self, file_path):
        try:
            df = pd.read_excel(file_path)
            df = df.reset_index(drop=True)

            ai_tasks = []
            with ThreadPoolExecutor(max_workers=5) as executor:
                for idx in range(1, len(df)):
                    url = str(df.iloc[idx, 0]).strip()
                    if not url:
                        continue
                    
                    html = get_html_from_url(url)

                    # 알고리즘 기반 추출
                    if pd.isna(df.iloc[idx, 1]) or str(df.iloc[idx, 1]).strip() == "":
                        try:
                            alg_res = extract_promotion_content(html)
                            alg_content_raw = alg_res.get("promotion_content", "")
                            alg_content = alg_content_raw if alg_content_raw else "NONE"
                            alg_flag = "P" if alg_content_raw else "NP"
                        except Exception as e:
                            print(f"[알고리즘 오류] {url}: {e}")
                            alg_content, alg_flag = "ERROR", "ERROR"

                        df.iloc[idx, 1] = clean_text(alg_content)
                        df.iloc[idx, 3] = alg_flag
                        df.to_excel(file_path, index=False)
                    else:
                        print(f"[알고리즘 추출 건너뜀] 인덱스 {idx}")
                        
                    # AI 기반 추출
                    if pd.isna(df.iloc[idx, 2]) or str(df.iloc[idx, 2]).strip() == "":
                        ai_tasks.append(executor.submit(process_ai_extraction, idx, html))
                    else:
                        print(f"[AI 추출 건너뜀] 인덱스 {idx}")

                for future in as_completed(ai_tasks):
                    idx, ai_content, ai_flag = future.result()
                    df.iloc[idx, 2] = clean_text(ai_content)
                    df.iloc[idx, 4] = ai_flag
                    df.to_excel(file_path, index=False)

            QMessageBox.information(self, "완료", "검사 완료!\n원본 파일에 저장되었습니다.")

        except Exception as e:
            QMessageBox.critical(self, "에러 발생", f"파일 처리 중 문제가 발생했습니다:\n{e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PromotionLabelerApp()
    window.show()
    sys.exit(app.exec_())