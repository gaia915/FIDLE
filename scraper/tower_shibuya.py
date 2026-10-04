import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List
from .base import Event, COMMON_HEADERS, clean_text, is_free_event

class TowerShibuyaScraper:
    BASE_URL = "https://towershibuya.jp"
    EVENTS_URL = "https://towershibuya.jp/events"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(COMMON_HEADERS)

    def scrape(self, max_pages: int = 2) -> List[Event]:
        events = []
        event_links = self._get_event_links(max_pages)
        print(f"[TowerShibuya] 見つかったイベントリンク数: {len(event_links)}")

        for link in event_links:
            try:
                ev = self._parse_event_page(link)
                if ev:
                    events.append(ev)
            except Exception as e:
                print(f"[TowerShibuya] 解析エラー ({link}): {e}")

        return events

    def _get_event_links(self, max_pages: int = 2) -> List[str]:
        links = []
        for page in range(1, max_pages + 1):
            url = f"{self.EVENTS_URL}/page/{page}" if page > 1 else self.EVENTS_URL
            try:
                resp = self.session.get(url, timeout=12)
                if resp.status_code != 200:
                    break
                soup = BeautifulSoup(resp.content, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    # towershibuya.jp/YYYY/MM/DD/ID 形式のリンクを抽出
                    if re.match(r"^https://towershibuya\.jp/\d{4}/\d{2}/\d{2}/\d+", href):
                        if href not in links:
                            links.append(href)
            except Exception as e:
                print(f"[TowerShibuya] ページ取得エラー ({url}): {e}")
                break
        return links

    def _parse_event_page(self, url: str) -> Event | None:
        resp = self.session.get(url, timeout=12)
        if resp.status_code != 200:
            return None

        # 文字コードをUTF-8で明示的にデコード
        content = resp.content.decode("utf-8", errors="replace")
        soup = BeautifulSoup(content, "html.parser")
        full_text = soup.get_text("\n", strip=True)

        # 無料・観覧フリー要素があるかチェック
        if not is_free_event(full_text):
            return None

        # タイトルの取得
        title = ""
        title_meta = soup.find("meta", property="og:title")
        if title_meta and title_meta.get("content"):
            title = title_meta["content"]
            # 不要なサイト名 suffix を削除
            title = re.sub(r"\s*-\s*TOWER RECORDS SHIBUYA.*$", "", title).strip()
        if not title:
            # ページ内ヘッダー等から探索
            for heading in soup.find_all(["h1", "h2", "h3"]):
                text = heading.get_text(strip=True)
                if text and "TOWER RECORDS" not in text and len(text) > 5:
                    title = text
                    break

        # アーティスト名の抽出（【アーティスト名】形式が多い）
        artist = ""
        artist_match = re.search(r"【(.*?)】", title)
        if artist_match:
            artist = artist_match.group(1).strip()
        else:
            # 本文中の「出演」行を探す
            出演_match = re.search(r"(?:出演|アーティスト)[：:\s]+([^\n\r]+)", full_text)
            if 出演_match:
                artist = clean_text(出演_match.group(1))

        # 日付と時刻の抽出
        # URL内の日付 YYYY/MM/DD をベースにする
        date_str = ""
        url_date_match = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
        if url_date_match:
            y, m, d = url_date_match.groups()
            date_str = f"{y}-{m}-{d}"

        # 開演時間・開始時間の探索
        start_time = ""
        time_match = re.search(r"(?:開演|スタート|START|開始)(?:時間)?[：:\s]*([0-2]?\d:[0-5]\d)", full_text, re.IGNORECASE)
        if time_match:
            start_time = time_match.group(1)
        else:
            # 例: "17:00～"
            time_match2 = re.search(r"([0-2]?\d:[0-5]\d)\s*～", full_text)
            if time_match2:
                start_time = time_match2.group(1)

        # 会場の取得
        venue = "タワーレコード渋谷店"
        venue_match = re.search(r"(?:場所|会場)[：:\s]+([^\n\r]+)", full_text)
        if venue_match:
            v_text = clean_text(venue_match.group(1))
            if "タワーレコード" not in v_text:
                venue = f"タワーレコード渋谷店 {v_text}"
            else:
                venue = v_text
        else:
            # フロア情報を探す（B1F CUTUP STUDIO, 9Fイベントスペース, 5Fなど）
            floor_match = re.search(r"([B\d]+F\s*(?:CUTUP STUDIO|イベントスペース|屋上|TOWER VINYL)?)", full_text)
            if floor_match:
                venue = f"タワーレコード渋谷店 {floor_match.group(1)}"

        # 無料種別
        free_type = "観覧フリー"
        if "優先観覧エリア" in full_text and ("フリー入場" in full_text or "観覧フリー" in full_text):
            free_type = "優先観覧＋フリー入場あり"
        elif "フリー入場" in full_text:
            free_type = "フリー入場あり"
        elif "観覧無料" in full_text:
            free_type = "観覧無料"

        # 説明・要約
        desc_lines = []
        if "特典会" in full_text:
            desc_lines.append("ミニライブ＆特典会")
        if "整理番号" in full_text or "優先入場券" in full_text:
            desc_lines.append("優先観覧エリア整理券配布あり")
        if "フリー入場" in full_text:
            desc_lines.append("フリー入場あり（規定人数に達し次第終了の場合あり）")
        description = " / ".join(desc_lines) if desc_lines else "ミニライブ観覧フリー"

        if not date_str:
            # 本文の日付（YYYY年MM月DD日）を探す
            dt_match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", full_text)
            if dt_match:
                y, m, d = dt_match.groups()
                date_str = f"{y}-{int(m):02d}-{int(d):02d}"

        if not date_str or not title:
            return None

        event_id = Event.generate_id(url, date_str, title)
        return Event(
            id=event_id,
            title=title,
            artist=artist or title,
            date=date_str,
            start_time=start_time,
            venue=venue,
            area="渋谷",
            url=url,
            source="タワーレコード渋谷店",
            free_type=free_type,
            description=description,
            updated_at=datetime.now().isoformat()
        )
