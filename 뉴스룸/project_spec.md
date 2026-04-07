1. 시스템 구조 및 워크플로우
데이터 저장: GitHub 리포지토리에 feeds.json(RSS 목록), news_data.json(분석 결과), stats.json(통계)을 저장합니다.
GitHub 연동: PyGithub 라이브러리를 사용하여 Streamlit에서 GitHub로 직접 JSON 파일을 커밋(Push/Pull)합니다.
AI 분석: Gemini 1.5 Flash 모델을 사용하여 비용을 절감하면서도 빠른 브리핑을 생성합니다.
배포: Streamlit Cloud에 배포하며, API 키와 GitHub 토큰은 Secrets 기능을 통해 관리합니다.
2. 사전 준비
GitHub 토큰 발급: GitHub Settings에서 repo 권한이 있는 **Personal Access Token (Fine-grained 추천)**을 발급받으세요.
Gemini API 키: Google AI Studio에서 발급받으세요.
파일 구조:
app.py: 메인 코드
requirements.txt: 라이브러리 목록 (streamlit, google-generativeai, feedparser, PyGithub, beautifulsoup4)
3. 핵심 코드 구현 (app.py)
code
Python
import streamlit as st
import feedparser
import google.generativeai as genai
import json
import pandas as pd
from github import Github
from datetime import datetime
from bs4 import BeautifulSoup

# --- 1. 설정 및 보안 ---
# Streamlit Cloud의 Secrets에서 불러옵니다.
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO_NAME = st.secrets["REPO_NAME"] # 예: "username/my-newsroom"
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# GitHub 연결 설정
g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

# --- 2. GitHub JSON 데이터 관리 함수 ---
def load_json_from_github(file_path, default_data):
    try:
        content = repo.get_contents(file_path)
        return json.loads(content.decoded_content.decode('utf-8'))
    except:
        return default_data

def save_json_to_github(file_path, data, message):
    content = json.dumps(data, ensure_ascii=False, indent=4)
    try:
        curr_file = repo.get_contents(file_path)
        repo.update_contents(file_path, message, content, curr_file.sha)
    except:
        repo.create_contents(file_path, message, content)

# --- 3. 뉴스 수집 및 분석 로직 ---
def fetch_and_analyze():
    feeds = load_json_from_github("feeds.json", [])
    news_archive = load_json_from_github("news_data.json", {})
    
    today = datetime.now().strftime("%Y-%m-%d")
    all_headlines = []

    for url in feeds:
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]: # 각 피드당 최신 5개
            all_headlines.append(f"제목: {entry.title}\n요약: {BeautifulSoup(entry.description, 'html.parser').text}")

    # Gemini 분석
    prompt = f"""
    당신은 IT 전문 뉴스 큐레이터입니다. 다음은 오늘 수집된 국내 IT 및 AI 뉴스들입니다.
    날짜: {today}
    
    내용:
    {all_headlines}
    
    위 내용을 바탕으로 오늘 반드시 알아야 할 '핵심 브리핑'을 5가지 섹션으로 정리해줘. 
    각 섹션은 이모지와 함께 요약하고 시사점을 포함해줘. 한국어로 작성해줘.
    """
    
    response = model.generate_content(prompt)
    news_archive[today] = response.text
    
    save_json_to_github("news_data.json", news_archive, f"Update news for {today}")
    return response.text

# --- 4. 통계 관리 ---
def update_stats():
    stats = load_json_from_github("stats.json", {"views": 0, "history": {}})
    today = datetime.now().strftime("%Y-%m-%d")
    stats["views"] += 1
    stats["history"][today] = stats["history"].get(today, 0) + 1
    save_json_to_github("stats.json", stats, "Update visitor stats")
    return stats

# --- 5. UI 구성 ---
st.set_page_config(page_title="AI IT Newsroom", layout="wide")

# 사이드바 메뉴
menu = st.sidebar.selectbox("메뉴", ["뉴스룸 브리핑", "관리자 대시보드"])

if menu == "뉴스룸 브리핑":
    stats = update_stats()
    st.title("🚀 나만의 AI IT 뉴스룸")
    st.caption(f"총 방문수: {stats['views']} | 오늘 날짜: {datetime.now().strftime('%Y-%m-%d')}")
    
    news_archive = load_json_from_github("news_data.json", {})
    sorted_dates = sorted(news_archive.keys(), reverse=True)
    
    if not sorted_dates:
        st.info("아직 분석된 뉴스가 없습니다. 관리자 대시보드에서 수집을 시작하세요.")
    else:
        for date in sorted_dates:
            with st.expander(f"📅 {date} 주요 IT 뉴스 브리핑", expanded=(date == sorted_dates[0])):
                st.markdown(news_archive[date])

elif menu == "관리자 대시보드":
    st.title("🛠 관리자 대시보드")
    
    # 비밀번호 간이 보안 (실제 서비스시 더 강화 필요)
    pw = st.text_input("관리자 암호를 입력하세요", type="password")
    if pw == st.secrets.get("ADMIN_PASSWORD", "1234"):
        
        tab1, tab2, tab3 = st.tabs(["RSS 관리", "데이터 수집/분석", "접속 통계"])
        
        with tab1:
            st.subheader("RSS 피드 목록")
            feeds = load_json_from_github("feeds.json", [])
            new_feed = st.text_input("새 RSS URL 추가 (예: 블로터, ZDNet 등)")
            if st.button("추가"):
                feeds.append(new_feed)
                save_json_to_github("feeds.json", feeds, "Add new RSS feed")
                st.success("추가되었습니다.")
            
            st.write("현재 목록:")
            for i, url in enumerate(feeds):
                col1, col2 = st.columns([0.8, 0.2])
                col1.write(url)
                if col2.button("삭제", key=f"del_{i}"):
                    feeds.pop(i)
                    save_json_to_github("feeds.json", feeds, "Delete RSS feed")
                    st.rerun()

        with tab2:
            st.subheader("AI 분석 실행")
            if st.button("지금 뉴스 수집 및 Gemini 분석 시작"):
                with st.spinner("AI가 뉴스를 읽고 브리핑을 작성 중입니다..."):
                    result = fetch_and_analyze()
                    st.success("분석 완료!")
                    st.markdown(result)

        with tab3:
            st.subheader("방문자 통계")
            stats = load_json_from_github("stats.json", {"views": 0, "history": {}})
            st.metric("누적 방문자수", stats["views"])
            if stats["history"]:
                df = pd.DataFrame(list(stats["history"].items()), columns=["날짜", "방문수"])
                st.line_chart(df.set_index("날짜"))

    else:
        st.error("암호가 틀렸습니다.")
4. 추천 RSS 주소 (국내 IT/AI)
관리자 페이지에서 다음 주소들을 테스트용으로 넣어보세요:
블로터(AI/로봇): https://www.bloter.net/rss/newsSection/21
ZDNet Korea: https://zdnet.co.kr/rss/all.xml
AI타임스: https://www.aitimes.com/rss/allSection.xml
테크M: https://www.techm.kr/rss/allSection.xml
5. 배포 방법 (Streamlit Cloud)
GitHub 리포지토리 생성: 위의 app.py, requirements.txt, 그리고 빈 feeds.json([] 입력) 등을 업로드합니다.
Streamlit Cloud 연결: Streamlit Cloud에서 해당 리포지토리를 선택합니다.
Secrets 설정: 앱 설정(Settings -> Secrets)에 아래 내용을 입력합니다:
code
Toml
GITHUB_TOKEN = "ghp_여러분의토큰내용"
REPO_NAME = "유저네임/리포지토리명"
GEMINI_API_KEY = "AI_스튜디오_API_키"
ADMIN_PASSWORD = "관리자_페이지_비밀번호"
이 방식의 장점
완전 무료: GitHub(스토리지), Streamlit(호스팅), Gemini(무료 티어)를 사용하므로 비용이 들지 않습니다.
DB 미사용: JSON 파일을 GitHub에 커밋하는 방식이라 별도의 데이터베이스 설정이 필요 없습니다.
히스토리 관리: 날짜별로 JSON에 저장되므로 과거 브리핑을 언제든 다시 볼 수 있습니다.
이제 이 코드를 바탕으로 본인만의 멋진 뉴스룸을 완성해 보세요! 추가로 디자인 수정이 필요하면 언제든 말씀해 주세요.
Model AM 12:10
ThinkingThoughts
Expand to view model thoughts

chevron_right
프로젝트 'Antigravity' (나만의 AI IT 뉴스룸) 제작을 위한 전체 명세서입니다. 이 문서를 가이드 삼아 개발을 진행하거나, 나중에 코드의 구조를 변경할 때 참조하십시오.
📝 Project Antigravity: AI IT Newsroom 명세서
1. 프로젝트 개요
프로젝트명: Antigravity (AI 기반 IT/AI 동향 분석 뉴스룸)
목적: 국내외 주요 IT 및 AI RSS 피드를 수집하여 Gemini AI로 요약 분석하고, 날짜별 브리핑 형태로 제공하는 개인화된 뉴스 서비스.
핵심 가치:
정보 과잉 시대의 효율적인 정보 습득 (Daily Briefing)
별도의 DB 없이 GitHub를 스토리지로 활용하는 Serverless 아키텍처
관리자 중심의 커스텀 피드 관리
2. 기술 스택 (Tech Stack)
Language: Python 3.9+
Web Framework: Streamlit
AI Engine: Google Gemini 1.5 Flash (API)
Data Parsing: Feedparser (RSS), Newspaper3k or BeautifulSoup (Content extraction)
Storage (Database-less): GitHub Repository (JSON files)
Version Control & Hosting: GitHub, Streamlit Cloud
3. 시스템 아키텍처
Collector: feedparser가 등록된 RSS URL에서 최신 기사 목록 수집.
Extractor: 기사 원문 링크를 방문하여 텍스트 데이터 추출.
Analyzer: Google Gemini API가 텍스트를 분석하여 섹션별 요약 및 시사점 도출.
Persistence: 분석된 결과와 통계를 JSON 형태로 변환하여 PyGithub를 통해 GitHub 리포지토리에 저장(Commit/Push).
Frontend: Streamlit이 JSON 데이터를 읽어와 날짜별로 시각화 및 관리자 UI 제공.
4. 주요 기능 상세 (Functional Requirements)
4.1. 메인 화면 (Newsroom Briefing)
날짜별 브리핑: 최신순으로 정렬된 날짜별 뉴스 분석 리포트 출력 (Expander 형식).
주요 지표 표시: 오늘 날짜 및 누적 방문자 수 표시.
반응형 레이아웃: 모바일/데스크톱 최적화.
4.2. 관리자 대시보드 (Admin Dashboard)
로그인: 간단한 비밀번호 인증 (Streamlit Secrets 활용).
RSS 피드 관리:
RSS URL 추가/삭제 기능.
현재 구독 중인 피드 리스트 확인.
수집 및 분석 실행:
버튼 클릭 시 수동으로 RSS 스크래핑 및 AI 분석 프로세스 시작.
진행 상황을 Spinner로 표시.
접속 통계:
일별 방문자 수 추이 그래프 (Line Chart).
총 페이지뷰(PV) 확인.
5. 데이터 명세 (Data Schema)
데이터베이스 대신 사용하는 JSON 파일 구조입니다.
5.1. feeds.json (RSS 목록)
code
JSON
[
  "https://www.bloter.net/rss/newsSection/21",
  "https://zdnet.co.kr/rss/all.xml"
]
5.2. news_data.json (분석 결과 저장)
code
JSON
{
  "2023-10-27": "### 🚀 오늘의 AI 동향\n1. 핵심 내용...\n2. 시사점...",
  "2023-10-26": "### 🚀 오늘의 AI 동향\n..."
}
5.3. stats.json (통계 데이터)
code
JSON
{
  "views": 150,
  "history": {
    "2023-10-26": 12,
    "2023-10-27": 25
  }
}
6. 보안 및 환경 설정 (Security)
Streamlit Cloud의 Secrets 관리 기능을 통해 다음 변수를 안전하게 관리합니다.
GEMINI_API_KEY: Google AI Studio 발급 키
GITHUB_TOKEN: GitHub Personal Access Token (Repo 권한 필요)
REPO_NAME: "계정명/리포지토리명"
ADMIN_PASSWORD: 관리자 페이지 접속용 암호
7. UI/UX 설계 (Wireframe)
Sidebar:
Logo: "Antigravity News"
Navigation: [뉴스룸 브리핑] | [관리자 대시보드]
Main Content:
Header: "📅 2023년 10월 27일 IT 리포트"
Body: Markdown 형식의 AI 생성 리포트
Admin Content:
Tabs: [피드 편집] | [분석 실행] | [데이터 통계]
8. 개발 로드맵 (Roadmap)
Phase 1: 기본 Streamlit UI 구조 잡기 및 RSS 파싱 테스트.
Phase 2: Gemini API 연동 및 프롬프트 엔지니어링 (IT/AI 특화 요약).
Phase 3: PyGithub를 이용한 JSON 파일 읽기/쓰기 모듈 구현.
Phase 4: 관리자 대시보드 및 통계 기능 구현.
Phase 5: Streamlit Cloud 배포 및 최종 테스트.