import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Optional
from .base import Event, COMMON_HEADERS, clean_text, is_free_event

# 関東エリア判定用キーワード
KANTO_KEYWORDS = [
    "東京", "新宿", "池袋", "秋葉原", "錦糸町", "町田", "八王子", "立川", "吉祥寺", "品川", "お台場",
    "神奈川", "横浜", "川崎", "海老名", "ビナウォーク", "藤沢", "武蔵小杉",
    "埼玉", "浦和", "大宮", "川口", "越谷", "レイクタウン",
    "千葉", "津田沼", "TOKYO-BAY", "船橋", "柏"
]

def is_kanto(text: str) -> bool:
    return any(k in text for k in KANTO_KEYWORDS)

def detect_area(text: str) -> str:
    for area in ["新宿", "池袋", "秋葉原", "錦糸町", "渋谷", "横浜", "川崎", "海老名", "浦和", "大宮", "船橋", "町田", "八王子"]:
        if area in text:
            return area
    return "関東"

class TowerStoresScraper:
    BASE_URL = "https://tower.jp"
    EVENTS_URL = "https://tower.jp/store/event/"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(COMMON_HEADERS)

    def scrape(self, max_items: int = 40) -> List[Event]:
        events = []
        links = self._get_kanto_event_links(max_items)
        print(f"[TowerStores] 対象の関東イベント候補数: {len(links)}")

        for link in links:
            try:
                ev = self._parse_store_event(link)
                if ev:
                    events.append(ev)
            except Exception as e:
                print(f"[TowerStores] 解析エラー ({link}): {e}")

        return events

    def _get_kanto_event_links(self, max_items: int = 40) -> List[str]:
        target_links = []
        try:
            resp = self.session.get(self.EVENTS_URL, timeout=12)
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.content, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if re.match(r"^/store/event/\d{4}/\d{2}/", href):
                    full_url = self.BASE_URL + href
                    title_text = clean_text(a.get_text())
                    # 渋谷店は別スクレイパーで詳細取得するため除外
                    if "渋谷店" in title_text:
                        continue
                    # 関東の店舗かつフリー・リリイベ関連キーワード
                    if is_kanto(title_text) or is_free_event(title_text):
                        if full_url not in target_links:
                            target_links.append(full_url)
                            if len(target_links) >= max_items:
                                break
        except Exception as e:
            print(f"[TowerStores] 一覧取得エラー: {e}")
        return target_links

    def _parse_store_event(self, url: str) -> Optional[Event]:
        resp = self.session.get(url, timeout=12)
        if resp.status_code != 200:
            return None

        content = resp.content.decode("utf-8", errors="replace")
        soup = BeautifulSoup(content, "html.parser")

        container = soup.find("div", id="contentsArea09base") or soup.find("div", class_="event-detail")
        if not container:
            container = soup.find("body")
        if not container:
            return None

        text = container.get_text("\n", strip=True)

        # 無料判定
        if not is_free_event(text):
            return None

        # 関東判定
        if not is_kanto(text):
            return None

        # タイトル取得（og:title や <title> からイベント名を取得）
        title = ""
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = clean_text(og_title["content"])
            title = re.sub(r"\s*-\s*TOWER RECORDS ONLINE.*$", "", title).strip()
        
        if not title or title == "店舗イベント":
            if soup.title and soup.title.get_text():
                title = clean_text(soup.title.get_text())
                title = re.sub(r"\s*-\s*TOWER RECORDS ONLINE.*$", "", title).strip()
                title = re.sub(r"^店舗イベント\s*\|\s*", "", title).strip()

        if not title or title == "店舗イベント":
            # contentsArea09base 内の太字テキストや見出しを探索
            for p in container.find_all(["p", "h3", "h4", "strong"]):
                p_text = clean_text(p.get_text())
                if p_text and p_text != "店舗イベント" and len(p_text) > 5 and ("【" in p_text or "イベント" in p_text or "ライブ" in p_text):
                    title = p_text
                    break

        # 出演者
        artist = ""
        artist_match = re.search(r"【(.*?)】", title)
        if artist_match:
            artist = artist_match.group(1).strip()
        else:
            m = re.search(r"(?:出演|アーティスト)[：:\s]+([^\n\r]+)", text)
            if m:
                artist = clean_text(m.group(1))

        # 会場
        venue = ""
        venue_match = re.search(r"(?:場所|会場)[：:\s\n]+([^\n\r]+)", text)
        if venue_match:
            venue = clean_text(venue_match.group(1))
        if not venue or len(venue) > 50:
            # タイトル内の店名を探索
            shop_match = re.search(r"(タワーレコード[^\s＠@]+店|TOWER RECORDS[^\s＠@]+店)", text)
            if shop_match:
                venue = shop_match.group(1)
            else:
                venue = "タワーレコード関東各店"

        # 開催日時
        date_str = ""
        dt_match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
        if dt_match:
            y, m, d = dt_match.groups()
            date_str = f"{y}-{int(m):02d}-{int(d):02d}"

        # 開演時間
        start_time = ""
        time_match = re.search(r"(?:開演|スタート|START|開始|開催日時)[^\d\n]*(\d{1,2}:\d{2})", text, re.IGNORECASE)
        if time_match:
            start_time = time_match.group(1)

        # 無料種別
        free_type = "観覧フリー"
        if "優先観覧エリア" in text and ("フリー入場" in text or "観覧フリー" in text):
            free_type = "優先観覧＋フリー入場あり"
        elif "フリー入場" in text:
            free_type = "フリー入場あり"
        elif "観覧無料" in text:
            free_type = "観覧無料"

        # 説明
        desc_lines = []
        if "ミニライブ" in text:
            desc_lines.append("ミニライブ")
        if "特典会" in text:
            desc_lines.append("特典会")
        if "整理番号" in text or "優先入場券" in text:
            desc_lines.append("優先観覧エリア券あり")
        if "フリー入場" in text:
            desc_lines.append("フリー入場あり")
        description = " / ".join(desc_lines) if desc_lines else "観覧フリーイベント"

        if not date_str or not title:
            return None

        area = detect_area(venue + " " + title)
        event_id = Event.generate_id(url, date_str, title)

        return Event(
            id=event_id,
            title=title,
            artist=artist or title,
            date=date_str,
            start_time=start_time,
            venue=venue,
            area=area,
            url=url,
            source="タワーレコード店舗",
            free_type=free_type,
            description=description,
            updated_at=datetime.now().isoformat()
        )
