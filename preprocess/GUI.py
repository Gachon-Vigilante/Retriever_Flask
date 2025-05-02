import sys
import pandas as pd
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QFileDialog, QLabel, QMessageBox
)
from PyQt5.QtCore import QUrl


class DrugPromotionDetector(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.current_index = 0
        self.df = None
        self.file_path = ""
        self.web_view = None

    def initUI(self):
        self.setWindowTitle('Drug Promotion Detector')
        self.setGeometry(100, 100, 1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QHBoxLayout()

        # 웹뷰 영역
        left_layout = QVBoxLayout()
        self.web_view = QWebEngineView()
        left_layout.addWidget(self.web_view)

        # 오른쪽 패널
        right_layout = QVBoxLayout()

        self.extracted_text = QTextEdit()
        self.extracted_text.setReadOnly(True)
        right_layout.addWidget(QLabel("추출된 본문:"))
        right_layout.addWidget(self.extracted_text)

        # 버튼 영역
        button_layout = QHBoxLayout()
        self.file_index_label = QLabel("0 / 0")
        button_layout.addWidget(self.file_index_label)

        self.fp_button = QPushButton("FP (오탐)")
        self.fn_button = QPushButton("FN (미탐)")
        self.tp_button = QPushButton("TP (정탐)")
        self.tn_button = QPushButton("TN (비탐)")
        button_layout.addWidget(self.fp_button)
        button_layout.addWidget(self.fn_button)
        button_layout.addWidget(self.tp_button)
        button_layout.addWidget(self.tn_button)
        right_layout.addLayout(button_layout)

        self.comment = QTextEdit()
        self.comment.setPlaceholderText("비고")
        right_layout.addWidget(QLabel("비고:"))
        right_layout.addWidget(self.comment)

        navigation_layout = QHBoxLayout()
        self.prev_button = QPushButton("이전")
        self.skip_button = QPushButton("건너뛰기")
        navigation_layout.addWidget(self.prev_button)
        navigation_layout.addWidget(self.skip_button)
        right_layout.addLayout(navigation_layout)

        layout.addLayout(left_layout, 2)
        layout.addLayout(right_layout, 1)
        central_widget.setLayout(layout)

        # 이벤트 연결
        self.fp_button.clicked.connect(lambda: self.save_result("FP"))
        self.fn_button.clicked.connect(lambda: self.save_result("FN"))
        self.tp_button.clicked.connect(lambda: self.save_result("TP"))
        self.tn_button.clicked.connect(lambda: self.save_result("TN"))
        self.prev_button.clicked.connect(self.prev_url)
        self.skip_button.clicked.connect(self.next_url)

        # 메뉴 바
        menubar = self.menuBar()
        file_menu = menubar.addMenu('File')
        open_action = file_menu.addAction('Open Excel File')
        open_action.triggered.connect(self.open_file)

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Excel File", "", "Excel Files (*.xlsx)")
        if file_path:
            self.file_path = file_path
            self.df = pd.read_excel(file_path)
            self.df.fillna("", inplace=True)  # NaN 방지
            self.url_list = self.df.iloc[1:, 0].tolist()  # 2번째 행부터 URL
            self.result_col_index = 2  # 3번째 열이 결과 컬럼
            self.find_start_index()
            self.load_current_url()

    def find_start_index(self):
        # 판단 안 된 URL(3번째 열이 비어있는 곳)부터 시작
        for i in range(1, len(self.df)):
            if self.df.iloc[i, self.result_col_index] == "":
                self.current_index = i
                return
        self.current_index = len(self.df)  # 모두 끝난 경우

    def load_current_url(self):
        if self.current_index >= len(self.df):
            self.show_message("모든 URL이 처리되었습니다.")
            return

        url = self.df.iloc[self.current_index, 0]
        if not url.startswith("http"):
            url = "http://" + url
        self.web_view.load(QUrl(url))
        self.file_index_label.setText(f"{self.current_index + 1} / {len(self.df)}")

        # 추출 텍스트 초기화
        self.extracted_text.clear()
        self.comment.clear()

    def save_result(self, label):
        self.df.iloc[self.current_index, self.result_col_index] = label
        try:
            self.df.to_excel(self.file_path, index=False)
        except Exception as e:
            self.show_message(f"파일 저장 중 오류 발생: {str(e)}")
        self.current_index += 1
        self.load_current_url()

    def prev_url(self):
        if self.current_index > 1:
            self.current_index -= 1
            self.load_current_url()

    def next_url(self):
        self.current_index += 1
        self.load_current_url()

    def show_message(self, message):
        QMessageBox.information(self, "알림", message)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = DrugPromotionDetector()
    ex.show()
    sys.exit(app.exec_())
