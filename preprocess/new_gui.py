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
        self.web_view = None
        self.initUI()
        self.current_index = 0
        self.df = None
        self.file_path = ""
        

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

        self.p_button = QPushButton("P (홍보글)")
        self.np_button = QPushButton("NP (홍보글X)")
        button_layout.addWidget(self.p_button)
        button_layout.addWidget(self.np_button)
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
        self.p_button.clicked.connect(lambda: self.save_result("P"))
        self.np_button.clicked.connect(lambda: self.save_result("NP"))
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
            self.df = pd.read_excel(file_path, dtype=str)
            self.df.fillna("", inplace=True)
            self.result_col_index = 2
            self.find_start_index()

            

    def find_start_index(self):
        # 판단 안 된 URL부터 시작
        for i in range(len(self.df)):
            if pd.isna(self.df.iloc[i, self.result_col_index]) or self.df.iloc[i, self.result_col_index] == "":
                self.current_index = i
                return
                

    def load_current_url(self):
        print("DEBUG: self.web_view =", self.web_view) 
        if not self.web_view:
            QMessageBox.critical(self, "오류", "웹뷰가 아직 초기화되지 않았습니다!")
            return
        
        url = self.df.iloc[self.current_index, 0]
        if not url.startswith("http"):
            url = "http://" + url
        self.web_view.load(QUrl(url))
        self.file_index_label.setText(f"{self.current_index + 1} / {len(self.df)}")
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
