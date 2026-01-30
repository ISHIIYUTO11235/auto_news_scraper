import os
import asyncio
import sqlite3
import datetime
import feedparser
import discord
from discord.ext import tasks
from dotenv import load_dotenv
import aiohttp

# --- 設定 ---

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GLOBAL_CHANNEL_ID = 1400070228666486837 

# ニュース取得間隔（分）
WAIT_TIME_MINUTES = 30 

# User-Agent（ブラウザのふりをするための名札）
RSS_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"

# 厳選した安定RSSリスト
NEWS_SOURCES = {
    "JP": { # NHK World (English) - 日本の公式英語ニュース
        "channel_id": 1385660657700966510,
        "rss_url": "https://www3.nhk.or.jp/nhkworld/en/news/list.xml"
    },
    "US": { # CBS News World - 米国大手、RSSが安定
        "channel_id": 1385660708506697959,
        "rss_url": "https://www.cbsnews.com/latest/rss/world"
    },
    "GB": { # BBC News World - 世界で最も安定しているRSS
        "channel_id": 1385660728131846354,
        "rss_url": "https://feeds.bbci.co.uk/news/world/rss.xml"
    },
    "FR": { # France 24 - 確認済み
        "channel_id": 1385660688277700729,
        "rss_url": "https://www.france24.com/en/rss"
    },
    "DE": { # Deutsche Welle (DW) - ドイツ公共放送（英語）
        "channel_id": 1385660749266944040, # チャンネルIDがない場合はコメントアウトしてください
        "rss_url": "https://rss.dw.com/xml/rss-en-world"
    },
    "IT": { # ANSA - イタリア主要通信社（英語）
        "channel_id": 1385660782313996428, # ID要確認
        "rss_url": "https://www.ansa.it/sito/ansait_rss/english_news.xml"
    },
    "CA": { # CBC World - カナダ公共放送
        "channel_id": 1385660814731776332,
        "rss_url": "https://www.cbc.ca/cmlink/rss-world"
    },
    "IN": { # Times of India - インド最大手
        "channel_id": 1385660837095804959, # ID要確認
        "rss_url": "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms"
    },
    "CN": { # South China Morning Post (Asia) - 香港紙（本土のRSSは遮断されやすいためこちらが安定）
        "channel_id": 1385660867231875173, # ID要確認
        "rss_url": "https://www.scmp.com/rss/318206/feed"
    }
}

# --- データベース管理 ---
class DatabaseManager:
    def __init__(self, db_name="posted_news.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_table()

    def create_table(self):
        # summaryカラムを追加したテーブル定義
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS posted_articles (
                url TEXT PRIMARY KEY,
                summary TEXT,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # 既存のテーブルにsummaryがない場合のマイグレーション（念のため）
        try:
            self.cursor.execute("ALTER TABLE posted_articles ADD COLUMN summary TEXT")
        except sqlite3.OperationalError:
            pass # すでにカラムがある場合は何もしない
        self.conn.commit()

    def is_posted(self, url):
        self.cursor.execute('SELECT 1 FROM posted_articles WHERE url = ?', (url,))
        return self.cursor.fetchone() is not None

    def add_article(self, url, summary):
        try:
            self.cursor.execute('INSERT INTO posted_articles (url, summary) VALUES (?, ?)', (url, summary))
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass 
    
    def close(self):
        self.conn.close()

# --- Discord Bot ---
class NewsBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db = DatabaseManager()
        self.llm_api_url = "http://localhost:11434/api/generate"

    async def setup_hook(self):
        self.news_loop.start()

    async def on_ready(self):
        print(f'✅ Logged in as {self.user}')
        print(f'📋 監視対象: {list(NEWS_SOURCES.keys())}')

    async def query_llm(self, text, mode="summary"):
        """
        RSSの短いテキストに対応したプロンプト
        """
        if mode == "summary":
            # 要点を箇条書きで抽出するプロンプト
            system_instruction = (
                "Read the following news snippet. "
                "1. Identify the language and translate it into English if needed. "
                "2. Extract the key facts and output them as 'Key Points' in 3 bullet points or less. "
                "Do not add any introductory text like 'Here is the summary'. Just the bullet points.:\n\n"
            )
        elif mode == "title":
            system_instruction = "Translate to English and create a short, catchy headline (under 10 words) for this news:\n\n"

        payload = {
            "model": "mistral",
            "prompt": f"{system_instruction}{text}",
            "stream": False
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.llm_api_url, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("response", "").strip()
                    return f"Error: {response.status}"
        except Exception as e:
            return f"LLM Error: {e}"

    def get_feed(self, url):
        """User-Agentを指定してRSSを取得するラッパー"""
        return feedparser.parse(url, agent=RSS_AGENT)

    @tasks.loop(minutes=WAIT_TIME_MINUTES)
    async def news_loop(self):
        print(f"🔄 RSS確認開始: {datetime.datetime.now()}")
        
        for country, config in NEWS_SOURCES.items():
            await self.process_rss(country, config)

    async def process_rss(self, country, config):
        # チャンネルIDが設定されていない、または無効な場合はスキップ
        try:
            channel_id = config.get("channel_id")
            if not channel_id:
                return
            
            channel = self.get_channel(channel_id)
            if not channel:
                # print(f"⚠️ チャンネルが見つかりません: {country} (ID: {channel_id})")
                return

            # RSS取得
            feed = await asyncio.to_thread(self.get_feed, config["rss_url"])
            
            # 記事が取れなかった場合
            if not feed.entries:
                print(f"⚠️ 記事なしまたはアクセス拒否 ({country})")
                return

            print(f"📡 {country}: {len(feed.entries)}件の記事を取得")

            # 最新3件まで処理
            for entry in feed.entries[:3]:
                url = entry.link
                if self.db.is_posted(url):
                    continue

                # テキスト抽出 (Description or Summary)
                raw_text =  entry.get('description') or entry.get('summary') or entry.title
                
                # HTMLタグの簡易除去（Descriptionに画像タグなどが含まれる場合があるため）
                if raw_text and "<" in raw_text:
                    import re
                    raw_text = re.sub(r'<[^>]+>', '', raw_text)

                print(f"🆕 記事発見 ({country}): {entry.title}")

                # LLM処理
                key_points = await self.query_llm(raw_text, mode="summary")
                title_en = await self.query_llm(entry.title, mode="title")

                # フォーマット: タイトル + Key Points + URL
                message = f"**{title_en}**\n\n{key_points}\n\n{url}"
                
                # 国別チャンネルへ送信
                await channel.send(message)
                
                # グローバルチャンネルへ送信
                global_ch = self.get_channel(GLOBAL_CHANNEL_ID)
                if global_ch:
                    await global_ch.send(f"[{country}] {message}")

                # データベースに保存
                self.db.add_article(url, key_points)
                
                # レート制限考慮（少し待機）
                await asyncio.sleep(3)

        except Exception as e:
            print(f"❌ エラー ({country}): {e}")

    @news_loop.before_loop
    async def before_news_loop(self):
        await self.wait_until_ready()

if __name__ == "__main__":
    intents = discord.Intents.default()
    client = NewsBot(intents=intents)
    client.run(DISCORD_TOKEN)