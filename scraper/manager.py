import os
import json
import re
from datetime import datetime, date, timedelta
from typing import List, Dict, Any
from .base import Event
from .tower_shibuya import TowerShibuyaScraper
from .tower_stores import TowerStoresScraper
from .sunshine_city import SunshineCityScraper

class EventManager:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.data_dir = os.path.join(base_dir, "data")
        self.docs_dir = os.path.join(base_dir, "docs")
        self.docs_data_dir = os.path.join(self.docs_dir, "data")
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.docs_data_dir, exist_ok=True)

    def run_all(self, max_items_per_source: int = 30) -> List[Event]:
        all_events: List[Event] = []

        scrapers = [
            ("Tower Records Shibuya", TowerShibuyaScraper()),
            ("Tower Records Kanto Stores", TowerStoresScraper()),
            ("Sunshine City Fountain Plaza", SunshineCityScraper()),
        ]

        for name, scraper in scrapers:
            try:
                print(f"\n==========================================")
                print(f"[*] スクレイピング開始: {name}")
                if hasattr(scraper, 'scrape'):
                    if isinstance(scraper, TowerShibuyaScraper):
                        res = scraper.scrape(max_pages=2)
                    elif isinstance(scraper, TowerStoresScraper):
                        res = scraper.scrape(max_items=max_items_per_source)
                    elif isinstance(scraper, SunshineCityScraper):
                        res = scraper.scrape(max_items=max_items_per_source)
                    else:
                        res = scraper.scrape()
                    print(f"[+] {name} から {len(res)} 件取得")
                    all_events.extend(res)
            except Exception as e:
                print(f"[-] {name} のスクレイピングに失敗: {e}")

        # 重複排除とマージ
        deduped = self._deduplicate_and_filter(all_events)
        print(f"\n合計 {len(deduped)} 件のイベントを処理しました。")

        # 保存
        self.save_events(deduped)
        self.save_icalendar(deduped)
        self.update_readme(deduped)

        return deduped

    def _deduplicate_and_filter(self, events: List[Event]) -> List[Event]:
        seen_keys = set()
        unique_events = []

        # 過去7日より前の古いイベントは除外（今日以降または直近を保持）
        today = date.today()
        cutoff_date = today - timedelta(days=7)

        for ev in events:
            # 重複判定キー: (日付, 会場のコア名, タイトルの正規化)
            norm_title = re.sub(r'[\s【】『』「」\-_]', '', ev.title).lower()[:20]
            norm_venue = re.sub(r'\s+', '', ev.venue).lower()[:10]
            key = (ev.date, norm_venue, norm_title)

            if key in seen_keys:
                continue
            seen_keys.add(key)

            try:
                ev_date = datetime.strptime(ev.date, "%Y-%m-%d").date()
                if ev_date < cutoff_date:
                    continue
            except ValueError:
                pass

            unique_events.append(ev)

        # 日付昇順、時間昇順でソート
        unique_events.sort(key=lambda x: (x.date, x.start_time or "99:99"))
        return unique_events

    def save_events(self, events: List[Event]):
        event_dicts = [e.to_dict() for e in events]
        meta = {
            "last_updated": datetime.now().isoformat(),
            "total_count": len(events),
            "events": event_dicts
        }

        # data/events.json
        data_json_path = os.path.join(self.data_dir, "events.json")
        with open(data_json_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        # docs/data/events.json
        docs_json_path = os.path.join(self.docs_data_dir, "events.json")
        with open(docs_json_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        print(f"[+] JSON保存完了: {data_json_path}, {docs_json_path}")

    def save_icalendar(self, events: List[Event]):
        """RFC 5545 準拠の iCalendar (.ics) ファイルを生成"""
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//FIDLE//Free Idol Event Finder//JA",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "X-WR-CALNAME:無料アイドルイベント情報",
            "X-WR-TIMEZONE:Asia/Tokyo",
        ]

        now_stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

        for ev in events:
            # 日時パース
            date_clean = ev.date.replace("-", "")
            time_clean = ev.start_time.replace(":", "") if ev.start_time else ""

            if time_clean and len(time_clean) == 4:
                # 開始時刻あり (JSTとして扱う)
                dtstart = f"{date_clean}T{time_clean}00"
                # デフォルト1時間後を終了とする
                try:
                    start_dt = datetime.strptime(f"{ev.date} {ev.start_time}", "%Y-%m-%d %H:%M")
                    end_dt = start_dt + timedelta(hours=1)
                    dtend = end_dt.strftime("%Y%m%dT%H%M%S")
                except ValueError:
                    dtend = dtstart
            else:
                # 終日イベント
                dtstart = f"{date_clean}"
                dtend = f"{date_clean}"

            summary = f"【{ev.free_type}】{ev.title}"
            desc = f"出演: {ev.artist}\\n種別: {ev.free_type}\\n詳細: {ev.description}\\nURL: {ev.url}"
            location = ev.venue

            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{ev.id}@fidle.local",
                f"DTSTAMP:{now_stamp}",
                f"DTSTART;TZID=Asia/Tokyo:{dtstart}" if ":" in ev.start_time else f"DTSTART;VALUE=DATE:{dtstart}",
                f"DTEND;TZID=Asia/Tokyo:{dtend}" if ":" in ev.start_time else f"DTEND;VALUE=DATE:{dtend}",
                f"SUMMARY:{summary}",
                f"LOCATION:{location}",
                f"DESCRIPTION:{desc}",
                f"URL:{ev.url}",
                "END:VEVENT"
            ])

        lines.append("END:VCALENDAR")
        ics_content = "\r\n".join(lines) + "\r\n"

        for p in [os.path.join(self.data_dir, "events.ics"), os.path.join(self.docs_data_dir, "events.ics")]:
            with open(p, "w", encoding="utf-8") as f:
                f.write(ics_content)
        print(f"[+] iCalendar保存完了")

    def update_readme(self, events: List[Event]):
        readme_path = os.path.join(self.base_dir, "README.md")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 直近15件の表を作成
        table_rows = []
        for ev in events[:20]:
            time_display = ev.start_time if ev.start_time else "時間未定"
            title_link = f"[{ev.title}]({ev.url})"
            table_rows.append(f"| {ev.date} | {time_display} | {ev.area} | {ev.venue} | {title_link} | `{ev.free_type}` |")

        table_md = "\n".join(table_rows) if table_rows else "| - | - | - | - | 現在登録された直近のイベントはありません | - |"

        content = f"""# 🎤 FIDLE - 無料アイドルイベント情報カレンダー

関東・都内近郊のCDショップや商業施設で開催される**観覧無料・フリーライブ・リリイベ情報**を自動収集・公開するプロジェクトです。  
GitHub Actions により毎日自動巡回し、最新情報に更新されます。

🌐 **Web版（GitHub Pages）:** [https://YOUR_GITHUB_USERNAME.github.io/FIDLE/](https://YOUR_GITHUB_USERNAME.github.io/FIDLE/)  
📅 **iCalendar連携 (Googleカレンダー/Appleカレンダー):** `data/events.ics` または Web版から直接登録可能

---

## 📅 直近の無料イベント一覧 (最新20件)
*最終更新日時: {now_str} (JST)*

| 開催日 | 開演 | エリア | 会場 | イベント名 / 出演 | 観覧条件 |
| :--- | :--- | :--- | :--- | :--- | :--- |
{table_md}

> 💡 全件の一覧や日付検索・カレンダー表示・エリア絞り込みは [Web版 (GitHub Pages)](https://YOUR_GITHUB_USERNAME.github.io/FIDLE/) をご覧ください。

---

## 🛠 システム構成

- **データ収集 (Scraper):** Python (BeautifulSoup, Requests)
  - タワーレコード渋谷店 (B1F CUTUP STUDIO, 9F, 5F イベントスペース 等)
  - タワーレコード関東各店舗 (新宿、池袋、錦糸町、川崎、横浜ビブレ、海老名 等)
  - サンシャインシティ噴水広場 (池袋)
- **定期更新:** GitHub Actions (cronで毎日自動実行＆Gitコミット)
- **公開形式:**
  - `docs/` : GitHub Pages向けレスポンシブWebアプリケーション
  - `data/events.json` : 構造化JSONデータ
  - `data/events.ics` : iCalendar購読データ
  - `README.md` : リポジトリトップでの一覧表示

---

## 🚀 ローカルでの実行方法

```bash
# 依存パッケージのインストール
pip install -r requirements.txt

# スクレイピングの実行
python run_scraper.py
```
"""
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[+] README.md 更新完了")
