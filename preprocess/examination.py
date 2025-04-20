import sys
import os
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QFileDialog, QLabel, QVBoxLayout, QWidget, QMessageBox
)

# 경로 설정
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from crawl.crawler import get_html_from_url
from preprocess.extractor import extract_promotion_content

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

            for idx in range(1, len(df)):
                url = str(df.iloc[idx, 0]).strip()
                if url:
                    try:
                        html = get_html_from_url(url)
                        result = extract_promotion_content(html)
                        content = result.get("promotion_content", "")
                        
                        # 2열: 본문 저장
                        df.iloc[idx, 1] = content if content else "NONE"
                        # 4열: 라벨 저장
                        df.iloc[idx, 3] = "P" if content else "NP"
                    except Exception as e:
                        df.iloc[idx, 1] = "ERROR"
                        df.iloc[idx, 3] = "ERROR"
                        print(f"[오류] {url}: {e}")
                    df.to_excel(file_path, index=False)
                    QMessageBox.information(self, "완료", f"검사 완료!\n원본 파일에 저장되었습니다.")

            

        except Exception as e:
            QMessageBox.critical(self, "에러 발생", f"파일 처리 중 문제가 발생했습니다:\n{str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PromotionLabelerApp()
    window.show()
    sys.exit(app.exec_())