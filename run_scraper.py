import os
import sys
import argparse

# WindowsコンソールでのUnicodeEncodeErrorを防止
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        pass

from scraper.manager import EventManager

def main():
    parser = argparse.ArgumentParser(description="無料アイドルイベント情報スクレイパー")
    parser.add_argument("--max-items", type=int, default=30, help="各ソースから取得する最大件数 (デフォルト: 30)")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"プロジェクトベースディレクトリ: {base_dir}")

    manager = EventManager(base_dir)
    events = manager.run_all(max_items_per_source=args.max_items)
    print(f"\n[OK] 正常に全処理が完了しました！ (有効イベント: {len(events)} 件)")

if __name__ == "__main__":
    main()
