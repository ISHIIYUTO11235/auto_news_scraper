G7各国のニュースを自動収集し、ローカルLLMで英訳・要約して Discord に配信するパイプライン。収集したデータは将来的な研究・LLMファインチューニング用に蓄積する設計です。

## 概要

- G7加盟国のニュースを定期的に**自動スクレイピング**
- ローカルLLM（Ollama / Mistral・量子化軽量版）で**英訳 → 3点要約**
- 要約結果を **Discord** に自動投稿
- ニュース本文は **SQLデータベース** に蓄積し、後段の分析・学習データ化に活用
- `analyze.py` で蓄積データを**ベクトル化 → 2次元プロット（HTML出力）** し、記事の分布を可視化

## 工夫した点

- **ローカルLLM + 量子化**でAPI課金なし・オフライン動作を実現。`payload` のモデル指定を差し替えるだけで、より高性能なLLMへ容易に切り替え可能な構成にした。
- 単なる配信で終わらせず、**SQLへのデータ蓄積 → ベクトル化 → 可視化**まで一気通貫のデータ基盤として設計。
- もともと C# で実装していたものを、Pythonの機械学習エコシステム（ベクトル化等）を活用するため Python へ移植。

## 今後の展望

蓄積した記事ベクトルを**クラスタリング**し、類似ニュースの重複を排除。誰が見ても分かりやすいニュースを単一チャンネルから受信できる配信ボットへ発展させる予定。あわせて、蓄積データをニュース特化LLMの**ファインチューニング素材**として利用することを構想しています。

## 使用技術

- **言語**: Python
- **LLM**: Ollama（Mistral / 量子化モデル）
- **データ**: SQL（ニュースDB）
- **分析・可視化**: ベクトル埋め込み + 2次元プロット（HTML生成）
- **連携**: Discord Webhook / Bot

## 構成（主なスクリプト）

- 収集〜英訳〜要約〜Discord配信を行うメインスクリプト
- `analyze.py` … 蓄積ニュースをベクトル化し可視化HTMLを生成

> ※ 翻訳・要約に使うモデルはコード中の `payload`（`"model": "mistral"` の箇所）を変更することで切り替えられます。

It automatically scrapes news from G7 member countries, sends it to a local LLM (ollama:mistral, a lightweight version made lightweight by quantization), translates it all into English, creates a three-point list, and sends it to Discord. The news data is stored in SQL, and the plan is to ultimately use this data for research purposes; it could also be used as material for fine-tuning news-related LLMs. If you change the payload = { "model": "mistral", "prompt": f"{system_instruction}{text}", "stream": False } part of the code to a more powerful LLM, it will be quite practical.When analyze.py is started, the news stored in the database is converted into vectors and an html file with a 2D plot is generated so that it can be viewed. Ultimately, I would like to create a news distribution bot that can eliminate duplication by clustering news articles with similar vectors and allowing anyone to receive easy-to-understand news from a single channel.
