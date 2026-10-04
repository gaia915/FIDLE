import re
import hashlib
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any

@dataclass
class Event:
    id: str
    title: str
    artist: str
    date: str              # YYYY-MM-DD
    start_time: str        # HH:MM or ""
    venue: str             # 会場名
    area: str              # 渋谷, 新宿, 池袋, etc.
    url: str               # 詳細URL
    source: str            # 情報源
    free_type: str         # 観覧フリー / フリー入場あり / 優先券＋フリー etc.
    description: str       # 要約・注意点
    updated_at: str        # YYYY-MM-DDTHH:MM:SS

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def generate_id(url: str, date: str, title: str) -> str:
        raw = f"{url}_{date}_{title}"
        return hashlib.md5(raw.encode('utf-8')).hexdigest()[:12]

# 共通ユーザーエージェント
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
COMMON_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

# 無料・アイドル・リリイベ関連キーワード
FREE_KEYWORDS = [
    "観覧フリー", "フリー入場", "観覧無料", "フリーライブ", "入場無料",
    "ミニライブ", "特典会", "リリースイベント", "リリイベ", "インストア"
]

def is_free_event(text: str) -> bool:
    """テキストに観覧無料・フリーイベント関連のキーワードが含まれているか判定"""
    return any(keyword in text for keyword in FREE_KEYWORDS)

def clean_text(text: str) -> str:
    """不要な空白や改行を整理"""
    if not text:
        return ""
    text = re.sub(r'[\r\n\t]+', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()
