import requests
import xml.etree.ElementTree as ET
import time

class NewsClient:
    def __init__(self):
        self.last_fetch_time = 0
        self.cached_news = []
        
    def get_latest_xrp_news(self) -> list:
        """구글 뉴스 RSS를 통해 최근 24시간 내 XRP 관련 한국어 뉴스 헤드라인 3개 수집"""
        # 10분에 한 번만 새로고침 (API 차단 방지 및 성능 최적화)
        current_time = time.time()
        if current_time - self.last_fetch_time < 600 and self.cached_news:
            return self.cached_news
            
        url = "https://news.google.com/rss/search?q=XRP+when:1d&hl=ko&gl=KR&ceid=KR:ko"
        try:
            response = requests.get(url, timeout=5)
            root = ET.fromstring(response.content)
            
            headlines = []
            for item in root.findall('.//item')[:3]:
                title = item.find('title').text
                # 구글 뉴스의 불필요한 뒤쪽 출처 텍스트(- 출처) 제거 처리
                if " - " in title:
                    title = title.rsplit(" - ", 1)[0]
                headlines.append(title)
                
            self.cached_news = headlines
            self.last_fetch_time = current_time
            return headlines
        except Exception as e:
            print(f"뉴스 수집 실패: {e}")
            return self.cached_news

news_client = NewsClient()
