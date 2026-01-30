import sqlite3
import ollama
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.cluster import KMeans

# Windowsで日本語フォントを表示するための設定
plt.rcParams['font.family'] = 'Meiryo' 

def get_data():
    """データベースからニュースの要約を取得"""
    conn = sqlite3.connect("posted_news.db")
    df = pd.read_sql("SELECT summary FROM posted_articles WHERE summary IS NOT NULL", conn)
    conn.close()
    return df

def get_embeddings(texts):
    """Ollamaを使ってテキストをベクトル化"""
    vectors = []
    print(f"🔄 {len(texts)} 件のデータをベクトル化中...")
    
    for i, text in enumerate(texts):
        # 改行などを除去
        clean_text = text.replace('\n', ' ')
        
        # Mistralを使ってEmbeddingを取得
        response = ollama.embeddings(model='mistral', prompt=clean_text)
        vectors.append(response['embedding'])
        
        if (i + 1) % 5 == 0:
            print(f"   ... {i + 1} 件完了")
            
    return np.array(vectors)

def main():
    # 1. データのロード
    df = get_data()
    
    if len(df) < 5:
        print("⚠️ データが少なすぎます。Botを動かしてニュースが5件以上溜まってから実行してください。")
        return

    # 2. ベクトル化 (Embedding)
    # テキストの意味を数値の配列に変換します
    vectors = get_embeddings(df['summary'].tolist())

    # 3. 次元圧縮 (多次元 -> 2次元)
    # PCAで大まかに圧縮してから、t-SNEで分布を調整するのが一般的です
    print("📉 2次元に圧縮中...")
    
    # データ数が少ない場合はperplexityを下げる必要があります
    perp = min(30, len(df) - 1)
    
    # t-SNEを使って2次元座標に変換
    tsne = TSNE(n_components=2, random_state=42, perplexity=perp, init='pca', learning_rate='auto')
    coords = tsne.fit_transform(vectors)

    # 4. クラスタリング (K-Means)
    # 近い位置にある点を色分けします（ここでは3グループに分類）
    num_clusters = 3 
    kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init='auto')
    clusters = kmeans.fit_predict(vectors)

    # 5. プロット
    print("🎨 描画中...")
    plt.figure(figsize=(12, 8))
    
    # 散布図を描く
    scatter = plt.scatter(coords[:, 0], coords[:, 1], c=clusters, cmap='viridis', alpha=0.7)
    
    # 各点に要約の冒頭を表示（マウスオーバー等はできないので文字で出力）
    for i, txt in enumerate(df['summary']):
        # 文字が長すぎると見づらいので先頭15文字だけ
        label = txt[:15].replace('\n', '') + "..."
        plt.annotate(label, (coords[i, 0], coords[i, 1]), fontsize=8, alpha=0.8)

    plt.title("ニュース記事のトピック分布 (Semantic Map)")
    plt.xlabel("Dimension 1")
    plt.ylabel("Dimension 2")
    plt.colorbar(scatter, label="Cluster Group")
    plt.grid(True, alpha=0.3)
    
    # 保存して表示
    plt.savefig("news_map.png")
    print("✅ 'news_map.png' に保存しました")
    plt.show()

if __name__ == "__main__":
    main()