import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Optional
from .base import Event, COMMON_HEADERS, clean_text, is_free_event

class SunshineCityScraper:
    BASE_URL = "https://sunshinecity.jp"
    SEARCH_URL = "https://sunshinecity.jp/event/"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(COMMON_HEADERS)

    def scrape(self, max_items: int = 30) -> List[Event]:
        events = []
        links = self._get_fountain_event_links(max_items)
        print(f"[SunshineCity] 噴水広場イベント候補数: {len(links)}")

        for link in links:
            try:
                ev = self._parse_event_page(link)
                if ev:
                    events.append(ev)
            except Exception as e:
                print(f"[SunshineCity] 解析エラー ({link}): {e}")

        return events

    def _get_fountain_event_links(self, max_items: int = 30) -> List[str]:
        links = []
        try:
            params = {"kw": "噴水広場"}
            resp = self.session.get(self.SEARCH_URL, params=params, timeout=12)
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.content, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/event/entry-" in href:
                    full_url = href if href.startswith("http") else self.BASE_URL + href
                    if full_url not in links:
                        links.append(full_url)
                        if len(links) >= max_items:
                            break
        except Exception as e:
            print(f"[SunshineCity] 一覧取得エラー: {e}")
        return links

    def _parse_event_page(self, url: str) -> Optional[Event]:
        resp = self.session.get(url, timeout=12)
        if resp.status_code != 200:
            return None

        content = resp.content.decode("utf-8", errors="replace")
        soup = BeautifulSoup(content, "html.parser")
        full_text = soup.get_text("\n", strip=True)

        # 噴水広場でない、または無料/フリー要素がないイベントはスキップ
        if "噴水広場" not in full_text:
            return None
        if not is_free_event(full_text) and "観覧無料" not in full_text and "無料" not in full_text:
            return None

        # 就活・展示会・物産等、音楽/アイドル以外の一般催事を除外
        EXCLUDE_KEYWORDS = ["就活", "インターン", "合同説明会", "物産フェア", "物産展", "催事", "相談会", "セミナー"]
        if any(kw in full_text for kw in EXCLUDE_KEYWORDS):
            return None

        # テーブルからメタデータ抽出
        kv = {}
        for tr in soup.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if len(cells) >= 2:
                k = clean_text(cells[0].get_text())
                v = clean_text(cells[1].get_text(" "))
                kv[k] = v

        # タイトル
        title = ""
        h1 = soup.find("h1")
        if h1:
            title = clean_text(h1.get_text())
            # タイトル先頭の日付を除去
            title = re.sub(r"^\d{4}/\d{1,2}/\d{1,2}\([^\)]+\)\s*", "", title)
        if not title:
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                title = clean_text(og_title["content"])
                title = re.sub(r"\s*\|\s*イベント.*$", "", title).strip()

        # 日付 (開催期間 / 開催日 から抽出)
        date_str = ""
        period_str = kv.get("開催期間", "") or kv.get("開催日", "")
        m = re.search(r"(\d{4})[年/](\d{1,2})[月/](\d{1,2})", period_str)
        if m:
            y, mo, d = m.groups()
            date_str = f"{y}-{int(mo):02d}-{int(d):02d}"

        # 時間
        start_time = ""
        time_raw = kv.get("開催時間", "")
        # ミニライブや開演時間を優先探索
        tm = re.search(r"(?:ミニライブ|開演|スタート|START)[^\d]*(\d{1,2}:\d{2})", time_raw, re.IGNORECASE)
        if tm:
            start_time = tm.group(1)
        else:
            tm2 = re.search(r"(\d{1,2}:\d{2})", time_raw)
            if tm2:
                start_time = tm2.group(1)

        # 料金・観覧条件
        fee = kv.get("料金", "")
        free_type = "観覧無料"
        if "優先観覧" in full_text:
            free_type = "優先観覧＋フリー入場あり"
        elif fee:
            free_type = fee if "無料" in fee else "観覧無料"

        # アーティスト
        artist = ""
        m_artist = re.search(r"【(.*?)】", title)
        if m_artist:
            artist = m_artist.group(1).strip()
        else:
            first_word = title.split(" ")[0] if title else ""
            artist = first_word if len(first_word) > 1 else title

        venue = "サンシャインシティ 噴水広場（池袋）"
        description = kv.get("開催時間", "") or "池袋サンシャインシティ噴水広場 フリーイベント"

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
            area="池袋",
            url=url,
            source="サンシャインシティ噴水広場",
            free_type=free_type,
            description=description,
            updated_at=datetime.now().isoformat()
        )
