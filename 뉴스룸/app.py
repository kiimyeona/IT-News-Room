import streamlit as st
import feedparser
import google.generativeai as genai
import json
import pandas as pd
from github import Github
from datetime import datetime
from bs4 import BeautifulSoup

# --- 1. 설정 및 보안 ---
REQUIRED_SECRETS = ["GITHUB_TOKEN", "REPO_NAME", "GEMINI_API_KEY"]
missing_secrets = [key for key in REQUIRED_SECRETS if key not in st.secrets]

if missing_secrets:
    st.error(f"누락된 Streamlit Secrets: {', '.join(missing_secrets)}")
    st.stop()

GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO_NAME = st.secrets["REPO_NAME"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "1234")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

try:
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
except Exception as e:
    st.error(f"GitHub 연결 오류: {e}")
    st.stop()
 
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
        repo.update_file(curr_file.path, message, content, curr_file.sha)
    except Exception:
        try:
            repo.create_file(file_path, message, content)
        except Exception as e:
            st.error(f"{file_path} 저장 오류: {e}")

# --- 3. 뉴스 수집 및 분석 로직 ---
def fetch_and_analyze():
    feeds = load_json_from_github("feeds.json", [])
    news_archive = load_json_from_github("news_data.json", {})

    today = datetime.now().strftime("%Y-%m-%d")
    all_headlines = []

    if not feeds:
        return "등록된 RSS 피드가 없습니다. 관리자 대시보드에서 RSS를 먼저 추가하세요."

    for url in feeds:
        try:
            feed = feedparser.parse(url)

            if not getattr(feed, "entries", None):
                continue

            for entry in feed.entries[:3]:
                title = str(getattr(entry, "title", "")).strip()
                desc = str(
                    getattr(entry, "description", "") or getattr(entry, "summary", "")
                ).strip()

                if not title and not desc:
                    continue

                summary_text = BeautifulSoup(desc, "html.parser").text.strip()[:300]

                if not title:
                    title = "제목 없음"
                if not summary_text:
                    summary_text = "요약 없음"

                all_headlines.append(f"제목: {title}\n요약: {summary_text}")

        except Exception:
            continue

    if not all_headlines:
        return "수집된 뉴스가 없습니다. RSS 주소 또는 피드 내용을 확인하세요."

    news_text = "\n\n".join(all_headlines[:10]).strip()

    if not news_text:
        return "뉴스 본문이 비어 있습니다."

    prompt = f"""
당신은 AI 트렌드를 쉽게 설명하는 뉴스 큐레이터입니다.
다음은 오늘 수집된 뉴스입니다.
날짜: {{today}}

내용:
{{news_text}}

위 내용 중 AI와 관련된 뉴스를 중심으로 오늘의 핵심 5가지를 정리해주세요.
작성 규칙:
- AI를 잘 모르는 직장인도 이해할 수 있도록 쉬운 말로 써주세요
- AI 용어는 괄호 안에 한 줄로 설명을 추가해주세요
- 각 뉴스가 우리 일상이나 업무에 어떤 변화를 가져오는지 한 줄로 써주세요
- 딱딱하지 않고 대화하듯 자연스러운 문체로 써주세요
- AI 관련 뉴스가 부족하면 기술 트렌드 뉴스로 채워주세요
- 한국어로 작성해주세요
""".strip()

    try:
        response = model.generate_content(prompt)
        result_text = getattr(response, "text", "").strip()

        if not result_text:
            return "Gemini 응답이 비어 있습니다."

    except Exception as e:
        return f"Gemini 호출 오류: {e}"

    news_archive[today] = result_text
    save_json_to_github("news_data.json", news_archive, f"Update news for {today}")
    return result_text

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

menu = st.sidebar.selectbox("메뉴", ["뉴스룸 브리핑", "관리자 대시보드"])

if menu == "뉴스룸 브리핑":
    stats = update_stats()
    news_archive = load_json_from_github("news_data.json", {})
    sorted_dates = sorted(news_archive.keys(), reverse=True)

    col1, col2 = st.columns([0.7, 0.3])
    with col1:
        st.title("🚀  AI 뉴스룸")
        st.caption(f"총 방문수: {stats['views']} | 오늘 날짜: {datetime.now().strftime('%Y-%m-%d')}")
    
    with col2:
        if sorted_dates:
            selected_date = st.selectbox("📅 날짜 선택 (과거 브리핑 보기)", ["전체 보기"] + sorted_dates)
        else:
            selected_date = "전체 보기"
            st.selectbox("📅 날짜 선택", ["데이터 없음"], disabled=True)

    st.markdown("---")
    
    if not sorted_dates:
        st.info("아직 분석된 뉴스가 없습니다. 관리자 대시보드에서 수집을 시작하세요.")
    else:
        if selected_date == "전체 보기":
            for date in sorted_dates:
                with st.expander(f"📅 {date} 주요 IT 뉴스 브리핑", expanded=(date == sorted_dates[0])):
                    st.markdown(news_archive[date])
        else:
            st.subheader(f"📅 {selected_date} 주요 IT 뉴스 브리핑")
            st.markdown(news_archive[selected_date])

elif menu == "관리자 대시보드":
    st.title("🛠 관리자 대시보드")
    
    pw = st.text_input("관리자 암호를 입력하세요", type="password")
    if pw == st.secrets.get("ADMIN_PASSWORD", "1234"):
        
        tab1, tab2, tab3, tab4 = st.tabs(["RSS 관리", "데이터 수집/분석", "접속 통계", "자동 수집 설정"])
        
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

        with tab4:
            st.subheader("자동 수집 스케줄 설정")
            st.write("GitHub Actions를 통해 정해진 요일과 시간에 자동으로 뉴스를 수집합니다.")
            settings = load_json_from_github("settings.json", {
                "fetch_time": "08:00",
                "days": ["월", "화", "수", "목", "금", "토", "일"]
            })
            
            try:
                default_time = datetime.strptime(settings.get("fetch_time", "08:00"), "%H:%M").time()
            except:
                default_time = datetime.strptime("08:00", "%H:%M").time()
            
            days_of_week = ["월", "화", "수", "목", "금", "토", "일"]
            selected_days = st.multiselect(
                "수집할 요일 선택",
                options=days_of_week,
                default=settings.get("days", days_of_week)
            )
            
            selected_time = st.time_input("수집할 시간 지정 (예: 08:00)", value=default_time)
            
            if st.button("스케줄 저장"):
                settings["fetch_time"] = selected_time.strftime("%H:%M")
                settings["days"] = selected_days
                save_json_to_github("settings.json", settings, "Update fetch schedule setting")
                st.success(f"매주 {', '.join(selected_days)}요일 {selected_time.strftime('%H:%M')}에 뉴스를 자동 수집하도록 설정되었습니다! \n(GitHub Repository Secrets 설정이 완료되어 있어야 작동합니다.)")

    else:
        st.error("암호가 틀렸습니다.")
