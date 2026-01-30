# auto_news_scraper
自動的にG7加盟国からニュースをスクレイプし、ローカルLLM（ollama:mistral　量子化で軽量化されてるver）にとばしてすべて英訳し3点の箇条書きにしてディスコ―ドに飛ばすようにできています。SQLにニュースデータを溜めており、最終的には溜めたデータを研究に役立てる予定　ニュースに関するLLMのファインチューニングの材料にもなりうる。コードのpayload = {             "model": "mistral",             "prompt": f"{system_instruction}{text}",             "stream": False         }の部分をもっと高性能なLLMに変えればかなり実用的。
