from tkinter import Tk
from tkinter.filedialog import askopenfilename
import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from collections import Counter

def shorten_html_for_ai(html: str, max_tokens=4000):
    text = BeautifulSoup(html, "html.parser").get_text(separator="\n")
    return text[:max_tokens]  # 예: 최대 4000자까지만 사용

# 🗂️ 파일 선택창 띄우기
Tk().withdraw()  # tkinter 메인창 숨기기
file_path = askopenfilename(title="엑셀 파일을 선택하세요", filetypes=[("Excel files", "*.xlsx")])
'''
# 📄 엑셀 파일에서 URL 불러오기 (A열 2행부터 시작)
df = pd.read_excel(file_path, header=0)
urls = df.iloc[:, 0].dropna().tolist()

# 🌐 크롬 드라이버 설정
options = webdriver.ChromeOptions()
options.add_experimental_option("detach", True)  # 브라우저 꺼지지 않게
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# 🚀 URL 열기 + 5초 대기
for url in urls:
    try:
        print(f"Opening: {url}")
        driver.get(url)
        time.sleep(5)
    except Exception as e:
        print(f"Error opening {url}: {e}")
        continue

driver.quit()
'''
'''
def compare_and_save_labels(file_path: str) -> None:
    df = pd.read_excel(file_path)

    # 결과 저장용 리스트
    col_9_results = []
    col_10_results = []

    # 2행부터 시작 (index 1부터)
    for i in range(len(df)):
        val_4 = str(df.iloc[i, 4]).strip().upper()  # 4열 (index 3)
        val_5 = str(df.iloc[i, 5]).strip().upper()  # 5열 (index 4)
        val_6 = str(df.iloc[i, 6]).strip().upper()  # 6열 (index 5)

        # 8열: 4열 vs 6열 비교
        if val_4 in ['P', 'NP'] and val_6 in ['P', 'NP']:
            if val_4 == 'P' and val_6 == 'P':
                col_9_results.append("TP")
            elif val_4 == 'NP' and val_6 == 'NP':
                col_9_results.append("TN")
            elif val_4 == 'P' and val_6 == 'NP':
                col_9_results.append("FP")
            elif val_4 == 'NP' and val_6 == 'P':
                col_9_results.append("FN")
        else:
            col_9_results.append("")

        # 9열: 5열 vs 6열 비교
        if val_5 in ['P', 'NP'] and val_6 in ['P', 'NP']:
            if val_5 == 'P' and val_6 == 'P':
                col_10_results.append("TP")
            elif val_5 == 'NP' and val_6 == 'NP':
                col_10_results.append("TN")
            elif val_5 == 'P' and val_6 == 'NP':
                col_10_results.append("FP")
            elif val_5 == 'NP' and val_6 == 'P':
                col_10_results.append("FN")
        else:
            col_10_results.append("")

    # 8열(새 컬럼 7번 인덱스), 9열(8번 인덱스)에 저장
    df["최종 탐지 결과 (알고리즘)"] = pd.Series(col_9_results, dtype="object")  # 8번째 열
    df["최종 탐지 결과 (AI)"] = pd.Series(col_10_results, dtype="object")  # 9번째 열

    # 저장 (덮어쓰기)
    df.to_excel(file_path, index=False)
    print("✅ 비교 결과가 엑셀에 저장되었습니다.")

file_path = askopenfilename(filetypes=[("Excel files", "*.xlsx")])
compare_and_save_labels(file_path)

'''

# ⬇️ 저장된 비교 결과를 다시 불러와서 통계 계산
df = pd.read_excel(file_path)

algo_result = df["최종 탐지 결과 (알고리즘)"].dropna().astype(str).str.upper().tolist()
ai_result = df["최종 탐지 결과 (AI)"].dropna().astype(str).str.upper().tolist()

algo_count = Counter(algo_result)
ai_count = Counter(ai_result)

print("\n📊 [알고리즘 기반 결과 요약]")
total_algo = sum(algo_count[label] for label in ['TP', 'TN', 'FP', 'FN'])
for label in ['TP', 'TN', 'FP', 'FN']:
    count = algo_count.get(label, 0)
    percent = (count / total_algo * 100) if total_algo > 0 else 0
    print(f"{label}: {count}개 ({percent:.2f}%)")

print("\n📊 [AI 기반 결과 요약]")
total_ai = sum(ai_count[label] for label in ['TP', 'TN', 'FP', 'FN'])
for label in ['TP', 'TN', 'FP', 'FN']:
    count = ai_count.get(label, 0)
    percent = (count / total_ai * 100) if total_ai > 0 else 0
    print(f"{label}: {count}개 ({percent:.2f}%)")
