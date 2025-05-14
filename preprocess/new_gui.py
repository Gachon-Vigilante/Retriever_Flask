import sys
import os
import pandas as pd
import requests
from bs4 import BeautifulSoup
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineSettings
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QFileDialog, QLabel, QMessageBox
)
from PyQt5.QtCore import QUrl


# JS 감시용 페이지
class MonitoringPage(QWebEnginePage):
    """웹 페이지의 JavaScript 로그를 모니터링하는 클래스입니다."""

    def __init__(self, parent=None):
        """모니터링 페이지를 초기화합니다.

        Args:
            parent: 부모 위젯
        """
        super().__init__(parent)
        self.js_logs = []
        self.interrupt_threshold = 10  # JS 로그 30개 넘으면 fallback 트리거

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        """JavaScript 콘솔 메시지를 처리합니다.

        Args:
            level: 로그 레벨
            message: 로그 메시지
            lineNumber: 라인 번호
            sourceID: 소스 ID
        """
        print(f"[JS] {message}")
        self.js_logs.append(message)

        ad_keywords = ['adsbygoogle', 'doubleclick', 'taboola', 'kakao_ad_area', 'adpnut', 'pelican', 'document.write']
        if any(keyword in message.lower() for keyword in ad_keywords):
            if len(self.js_logs) >= self.interrupt_threshold:
                print("⚠️ JS 로그 과다 - fallback 실행")
                self.view().stop()
                if self.parent():
                    self.parent().fallback_to_html()


class DrugPromotionDetector(QMainWindow):
    """마약 홍보글 검사 도구의 GUI 애플리케이션 클래스입니다."""

    def __init__(self):
        """GUI 애플리케이션을 초기화합니다."""
        super().__init__()
        self.current_index = 0
        self.df = None
        self.file_path = ""
        self.result_col_index = 5
        self.initUI()

    def initUI(self):
        """GUI 컴포넌트들을 초기화하고 배치합니다."""
        self.setWindowTitle('Drug Promotion Detector')
        self.setGeometry(100, 100, 1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QHBoxLayout()

        # 왼쪽 웹뷰
        left_layout = QVBoxLayout()
        self.web_view = QWebEngineView()
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        self.page = MonitoringPage(self)
        self.page.profile().clearHttpCache()
        self.web_view.setPage(self.page)
        left_layout.addWidget(self.web_view)

        # 오른쪽 본문 및 버튼
        right_layout = QVBoxLayout()
        self.extracted_text = QTextEdit()
        self.extracted_text.setReadOnly(True)
        right_layout.addWidget(QLabel("추출된 본문:"))
        right_layout.addWidget(self.extracted_text)

        button_layout = QHBoxLayout()
        self.file_index_label = QLabel("0 / 0")
        self.p_button = QPushButton("P (홍보글)")
        self.np_button = QPushButton("NP (홍보글X)")
        button_layout.addWidget(self.file_index_label)
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
        """엑셀 파일을 선택하고 데이터를 로드합니다."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Excel File", "", "Excel Files (*.xlsx)")
        if file_path:
            self.file_path = file_path
            self.df = pd.read_excel(file_path, dtype=str).fillna("")
            self.find_start_index()
            self.load_current_url()

    def find_start_index(self):
        """처리되지 않은 URL의 인덱스를 찾습니다."""
        for i in range(len(self.df)):
            if self.df.iloc[i, self.result_col_index] == "":
                self.current_index = i
                return

    def load_current_url(self):
        """현재 인덱스의 URL을 웹뷰에 로드합니다."""
        if not self.web_view:
            QMessageBox.critical(self, "오류", "웹뷰가 아직 초기화되지 않았습니다!")
            return

        url = self.df.iloc[self.current_index, 0]
        if not url.startswith("http"):
            url = "http://" + url
        print(f"[LOADING] {url}")
        self.page.js_logs.clear()
        self.web_view.load(QUrl(url))
        self.file_index_label.setText(f"{self.current_index + 1} / {len(self.df)}")
        self.extracted_text.clear()
        self.comment.clear()

    def fallback_to_html(self):
        """웹뷰 로드 실패 시 HTML 직접 파싱으로 대체합니다."""
        url = self.df.iloc[self.current_index, 0]
        if not url.startswith("http"):
            url = "http://" + url
        try:
            res = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(res.text, "html.parser")
            # article 태그가 있으면 우선 추출
            main_content = ""
            article = soup.find("article")
            if article:
                main_content = article.get_text(separator="\n", strip=True)
            else:
                # 자주 쓰는 본문 클래스명들
                for cls in ["article-body", "content", "read", "news_body"]:
                    section = soup.find("div", class_=cls)
                    if section:
                        main_content = section.get_text(separator="\n", strip=True)
                        break
                else:
                    main_content = soup.get_text(separator="\n", strip=True)

            # 본문 출력
            self.extracted_text.setPlainText("[텍스트 fallback 모드]\n" + main_content[:3000])  # 너무 길면 잘라줌
        except Exception as e:
            self.extracted_text.setPlainText(f"[ERROR] 본문 추출 실패: {e}")

    def save_result(self, label):
        """현재 URL의 검사 결과를 저장하고 다음 URL로 이동합니다.

        Args:
            label: 검사 결과 라벨 ("P" 또는 "NP")
        """
        self.df.iloc[self.current_index, self.result_col_index] = label
        self.df.iloc[self.current_index, self.result_col_index + 1] = self.comment.toPlainText()
        try:
            temp_path = self.file_path + ".tmp"
            self.df.to_excel(temp_path, index=False)
            os.replace(temp_path, self.file_path)  # 원본 파일 덮어쓰기
        except Exception as e:
            self.show_message(f"파일 저장 중 오류 발생: {str(e)}")
        self.current_index += 1
        self.load_current_url()

    def prev_url(self):
        """이전 URL로 이동합니다."""
        if self.current_index > 0:
            self.current_index -= 1
            self.load_current_url()

    def next_url(self):
        """다음 URL로 이동합니다."""
        self.current_index += 1
        self.load_current_url()

    def show_message(self, message):
        """메시지 박스를 표시합니다.

        Args:
            message: 표시할 메시지
        """
        QMessageBox.information(self, "알림", message)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = DrugPromotionDetector()
    ex.show()
    sys.exit(app.exec_())