import google.generativeai as genai
import json
from github import Github
from datetime import datetime
import feedparser
from bs4 import BeautifulSoup
import os
import pytz

# Secrets from environment variables
GITHUB_TOKEN = os.environ.get("GH_TOKEN")
REPO_NAME = os.environ.get("REPO_NAME")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not all([GITHUB_TOKEN, REPO_NAME, GEMINI_API_KEY]):
    print("Missing environment variables. Exiting.")
    exit(1)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-flash-latest')

g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

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
        repo.update_file(file_path, message, content, curr_file.sha)
    except:
        repo.create_file(file_path, message, content)

def fetch_and_analyze():
    feeds = load_json_from_github("feeds.json", [])
    news_archive = load_json_from_github("news_data.json", {})
    
    # Use KST
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    today = now.strftime("%Y-%m-%d")
    current_hour = now.strftime("%H:00")
    
    settings = load_json_from_github("settings.json", {
        "fetch_time": "08:00",
        "days": ["월", "화", "수", "목", "금", "토", "일"]
    })
    target_time = settings.get("fetch_time", "08:00")
    target_days = settings.get("days", ["월", "화", "수", "목", "금", "토", "일"])
    
    # Check hour
    target_hour = target_time.split(":")[0] + ":00"
    is_manual = os.environ.get("MANUAL_TRIGGER", "false").lower() == "true"
    
    # Check day of week
    days_map = {0: "월", 1: "화", 2: "수", 3: "목", 4: "금", 5: "토", 6: "일"}
    current_day = days_map[now.weekday()]
    
    if current_day not in target_days and not is_manual:
        print(f"Current KST day ({current_day}) is not in scheduled days ({target_days}). Skipping.")
        return
        
    if target_hour != current_hour and not is_manual:
        print(f"Current KST hour ({current_hour}) != scheduled hour ({target_hour}). Skipping.")
        return
        
    print(f"Triggering fetch for {today}...")
    all_headlines = []
    
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]: 
                summary_text = BeautifulSoup(entry.description, 'html.parser').text[:300]
                all_headlines.append(f"제목: {entry.title}\n요약: {summary_text}")
        except Exception as e:
            print(f"Error parsing feed {url}: {e}")

    if not all_headlines:
        print("No headlines found.")
        return

    prompt = f"""
    당신은 IT 전문 뉴스 큐레이터입니다. 다음은 오늘 수집된 국내 IT 및 AI 뉴스들입니다.
    날짜: {today}
    
    내용:
    {all_headlines}
    
    위 내용을 바탕으로 오늘 반드시 알아야 할 '핵심 브리핑'을 5가지 섹션으로 정리해줘. 
    각 섹션은 이모지와 함께 요약하고 시사점을 포함해줘. 한국어로 작성해줘.
    """
    
    try:
        response = model.generate_content(prompt)
        news_archive[today] = response.text
        save_json_to_github("news_data.json", news_archive, f"Automated update for {today}")
        print("Successfully updated news data.")
    except Exception as e:
        print(f"Gemini API Error: {e}")

if __name__ == "__main__":
    fetch_and_analyze()
