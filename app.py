import streamlit as st
from google import genai
import pandas as pd
import random
import io
import re
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import os

# ReportLab関連
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# Google API関連
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# --- 1. 設定と関数定義 ---
# 4つの領域定義
DOMAIN_NAMES = ["実行力", "影響力", "人間関係構築力", "戦略的思考力"]
DOMAIN_COLORS_RT = { # レーダーチャート用
    "実行力": "#9b59b6", # 紫
    "影響力": "#f1c40f", # 黄
    "人間関係構築力": "#3498db", # 青
    "戦略的思考力": "#2ecc71"  # 緑
}
# 資質と領域のマッピング
THEME_TO_DOMAIN = {
    "達成欲": "実行力", "アレンジ": "実行力", "信念": "実行力", "公平性": "実行力", "慎重さ": "実行力", "規律性": "実行力", "目標志向": "実行力", "責任感": "実行力", "回復志向": "実行力",
    "活発性": "影響力", "指令性": "影響力", "コミュニケーション": "影響力", "競争性": "影響力", "最上志向": "影響力", "自己確信": "影響力", "自我": "影響力", "社交性": "影響力",
    "適応性": "人間関係構築力", "運命思考": "人間関係構築力", "成長促進": "人間関係構築力", "共感性": "人間関係構築力", "調和性": "人間関係構築力", "包含": "人間関係構築力", "個別化": "人間関係構築力", "ポジティブ": "人間関係構築力", "親密性": "人間関係構築力",
    "分析思考": "戦略的思考力", "原点思考": "戦略的思考力", "未来志向": "戦略的思考力", "着想": "戦略的思考力", "収集心": "戦略的思考力", "内省": "戦略的思考力", "学習欲": "戦略的思考力", "戦略性": "戦略的思考力"
}
# PDFテーブル用の色設定
DOMAIN_BG_COLORS = {
    "実行力": colors.lavender,
    "影響力": colors.lightyellow,
    "人間関係構築力": colors.aliceblue,
    "戦略的思考力": colors.honeydew,
}



# --- フォント設定 ---
# フォルダにあるフォントファイル名を指定
FONT_FILE = "ipaexg.ttf"
REGISTERED_FONT_NAME = "IPAexGothic"

if not os.path.exists(FONT_FILE):
    st.error(f"⚠️ エラー: フォントファイル `{FONT_FILE}` が見つかりません。")
    st.info("【解決策】 `ipaexg.ttf` をダウンロードし、`app.py` と同じ場所にアップロードしてください。")
    st.stop()

# フォント登録処理
try:
    # 1. Matplotlibへの登録 (グラフ用)
    fm.fontManager.addfont(FONT_FILE)
    font_prop = fm.FontProperties(fname=FONT_FILE)
    plt.rcParams['font.family'] = font_prop.get_name()

    # 2. ReportLabへの登録 (PDF用)
    # 既に登録されているかチェックしてから登録（リロード時のエラー防止）
    if REGISTERED_FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(REGISTERED_FONT_NAME, FONT_FILE))

except Exception as e:
    st.error(f"フォント登録中にエラーが発生しました: {e}")
    st.stop()

# レーダーチャート作成関数
def create_radar_chart(scores_by_domain):
    # データ準備
    labels = DOMAIN_NAMES
    # 領域ごとの資質数で割って平均点にする場合
    # counts = {"実行力": 9, "影響力": 8, "人間関係構築力": 9, "戦略的思考力": 8}
    # values = [scores_by_domain[d] / counts[d] for d in labels]
    # 合計点のまま表示する場合（今回はこちらを採用）
    values = [scores_by_domain[d] for d in labels]
    
    num_vars = len(labels)
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    values += values[:1] # 閉じた多角形にするため最初のデータを最後に追加
    angles += angles[:1]

    # プロット設定
    fig, ax = plt.subplots(figsize=(4, 4), subplot_kw=dict(polar=True))
    
    # Y軸の目盛り（グリッド）設定
    max_val = max(values) if values else 25 # 最大値に応じて調整（ここでは適当に25）
    yticks = np.linspace(0, max_val, 5) # 5分割
    ax.set_yticks(yticks)
    ax.set_yticklabels([]) # 数値は表示しない
    ax.set_rlabel_position(0)

    # X軸（ラベル）設定
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontdict={'fontsize': 14, 'fontweight': 'bold'})

    # データプロット
    ax.plot(angles, values, color='#34495e', linewidth=2, linestyle='solid')
    ax.fill(angles, values, color='#34495e', alpha=0.25)
    
    # 領域ごとに色分けした点を打つ
    for i, (angle, val) in enumerate(zip(angles[:-1], values[:-1])):
        color = DOMAIN_COLORS_RT[labels[i]]
        ax.plot(angle, val, marker='o', color=color, markersize=8)

    # 余白調整
    plt.tight_layout(pad=1)
    
    # 画像バッファに保存
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf

# PDF作成関数
def create_pdf(name, all_ranked_data, domain_scores, ai_text):
    buffer = io.BytesIO()
    # 余白を意識した設定（上下左右の余白を広めに取る）
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4,
        rightMargin=20*mm, leftMargin=20*mm,
        topMargin=25*mm, bottomMargin=25*mm
    )
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
    
    elements = []
    
    # --- スタイル定義  ---
    styles = getSampleStyleSheet()
    # タイトル
    title_style = ParagraphStyle(
        name='JpTitle', fontName=REGISTERED_FONT_NAME, fontSize=24, leading=30, alignment=TA_CENTER, spaceAfter=20*mm
    )
    # 大見出し（H1相当）
    h1_style = ParagraphStyle(
        name='JpH1', fontName=REGISTERED_FONT_NAME, fontSize=18, leading=22, 
        spaceBefore=15*mm, spaceAfter=10*mm, textColor=colors.navy,
        borderPadding=5, borderWidth=0, borderColor=colors.navy, backColor=colors.whitesmoke # 簡易的な背景帯
    )
    # 中見出し（H2相当：AIテキスト内で使用）
    h2_style = ParagraphStyle(
        name='JpH2', fontName=REGISTERED_FONT_NAME, fontSize=14, leading=18,
        spaceBefore=12*mm, spaceAfter=6*mm, textColor=colors.darkblue
    )
    # 本文
    body_style = ParagraphStyle(
        name='JpBody', fontName=REGISTERED_FONT_NAME, fontSize=10.5, leading=18, # 行間を広めに
        spaceAfter=3*mm, alignment=TA_LEFT
    )
    # キャプション
    caption_style = ParagraphStyle(
        name='JpCaption', fontName=REGISTERED_FONT_NAME, fontSize=9, leading=12, textColor=colors.grey, alignment=TA_CENTER
    )

    # =========================================
    # ページ1: タイトルと全体サマリー（チャート＆Top10）
    # =========================================
    elements.append(Paragraph(f"ストレングス分析レポート", title_style))
    elements.append(Paragraph(f"回答者: {name} さん", ParagraphStyle(name='sub', parent=title_style, fontSize=14, spaceAfter=30*mm)))

    elements.append(Paragraph("■ 強みの全体構成（4領域バランスとTop10）", h1_style))

    # --- ② レーダーチャート画像生成 ---
    radar_buf = create_radar_chart(domain_scores)
    radar_img = Image(radar_buf, width=80*mm, height=80*mm)
    
    # --- Top10 テーブル作成 ---
    top10_data = [["順位", "資質名", "領域", "スコア"]]
    t10_cmds = [
        ('FONT', (0,0), (-1,-1), REGISTERED_FONT_NAME, 10),
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('BACKGROUND', (0,0), (-1,0), colors.midnightblue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 5),
    ]
    for i, (theme, score) in enumerate(all_ranked_data[:10]):
        domain = THEME_TO_DOMAIN.get(theme, "-")
        bg_color = DOMAIN_BG_COLORS.get(domain, colors.white)
        top10_data.append([str(i+1), theme, domain, str(score)])
        t10_cmds.append(('BACKGROUND', (0, i+1), (-1, i+1), bg_color))

    top10_table = Table(top10_data, colWidths=[12*mm, 35*mm, 25*mm, 15*mm])
    top10_table.setStyle(TableStyle(t10_cmds))

    # --- チャートとテーブルを横並び配置 ---
    # 1行2列の透明なテーブルに入れてレイアウトする
    layout_data = [[radar_img, top10_table]]
    layout_table = Table(layout_data, colWidths=[90*mm, 90*mm])
    layout_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (0,0), 'CENTER'), # 左セル（チャート）は中央寄せ
        ('ALIGN', (1,0), (1,0), 'LEFT'),   # 右セル（表）は左寄せ
        ('VALIGN', (0,0), (-1,-1), 'TOP'), # 上揃え
    ]))
    elements.append(layout_table)
    # キャプション追加
    elements.append(Spacer(1, 5*mm))
    elements.append(Paragraph("※レーダーチャートは各領域のスコア合計値を示しています。", caption_style))
    
    # ④ ここで1回だけ改ページ
    elements.append(PageBreak())

    # =========================================
    # ページ2: 全34資質の詳細リスト（2段組み表示）
    # =========================================
    elements.append(Paragraph("■ 全34資質の順位一覧", h1_style))

    # データを左右に分割（17個ずつ）
    half_idx = (len(all_ranked_data) + 1) // 2
    left_data = all_ranked_data[:half_idx]
    right_data = all_ranked_data[half_idx:]

    # 2段組み用のデータ構造を作成（左データ, 空白, 右データ）
    # ヘッダー行
    full_table_data = [["順位", "資質名", "領域", "スコア", "", "順位", "資質名", "領域", "スコア"]]
    
    ft_cmds = [
        ('FONT', (0,0), (-1,-1), REGISTERED_FONT_NAME, 9),
        # 左側のスタイル
        ('GRID', (0,0), (3,-1), 0.25, colors.lightgrey),
        ('BACKGROUND', (0,0), (3,0), colors.midnightblue),
        # 右側のスタイル
        ('GRID', (5,0), (8,-1), 0.25, colors.lightgrey),
        ('BACKGROUND', (5,0), (8,0), colors.midnightblue),
        # 共通ヘッダー文字色
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 4),
    ]

    # データ行の作成
    max_rows = len(left_data)
    for i in range(max_rows):
        row_data = []
        # 左側データ追加
        l_item = left_data[i]
        l_rank = i + 1
        l_domain = THEME_TO_DOMAIN.get(l_item[0], "-")
        l_bg = DOMAIN_BG_COLORS.get(l_domain, colors.white)
        row_data.extend([str(l_rank), l_item[0], l_domain, str(l_item[1])])
        ft_cmds.append(('BACKGROUND', (0, i+1), (3, i+1), l_bg))
        
        # 中央の空白列
        row_data.append("")

        # 右側データ追加（存在する場合）
        if i < len(right_data):
            r_item = right_data[i]
            r_rank = i + 1 + half_idx
            r_domain = THEME_TO_DOMAIN.get(r_item[0], "-")
            r_bg = DOMAIN_BG_COLORS.get(r_domain, colors.white)
            row_data.extend([str(r_rank), r_item[0], r_domain, str(r_item[1])])
            ft_cmds.append(('BACKGROUND', (5, i+1), (8, i+1), r_bg))
        else:
            # 右側にデータがない場合は空白埋め
            row_data.extend(["", "", "", ""])
        
        full_table_data.append(row_data)

    # カラム幅の設定（左4列 + 空白1列 + 右4列）
    col_widths = [10*mm, 30*mm, 25*mm, 12*mm] * 2
    col_widths.insert(4, 10*mm) # 真ん中に10mmの空白列

    full_table = Table(full_table_data, colWidths=col_widths, repeatRows=1)
    full_table.setStyle(TableStyle(ft_cmds))
    elements.append(full_table)

    # ④ 2回目の改ページ
    elements.append(PageBreak())

    # =========================================
    # ページ3: AI分析レポート
    # =========================================
    elements.append(Paragraph("■ AIによるプロファイリング分析", h1_style))

    # Markdown整形処理
    
    # 見出し判定用の正規表現コンパイル
    h_pattern = re.compile(r'^(#+)\s*(.*)')

    for line in ai_text.split('\n'):
        line = line.strip()
        if not line:
            elements.append(Spacer(1, 4*mm)) # 空行は少し狭めに
            continue

        # エスケープ処理
        line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        # 太字変換
        line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)

        # 見出しマッチング
        match = h_pattern.match(line)
        if match:
            # level = len(match.group(1)) # #の数（今回はすべて同じスタイルにする）
            clean_text = match.group(2) # 記号を除去したテキスト
            elements.append(Paragraph(clean_text, h2_style))
            
        elif line.startswith('- ') or line.startswith('* '):
            # リスト項目
            clean_text = line[2:].strip()
            # 箇条書き用のインデントスタイルを適用
            list_style = ParagraphStyle(
                name='JpList', parent=body_style,
                leftIndent=5*mm, firstLineIndent=-5*mm # ぶら下げインデント
            )
            elements.append(Paragraph(f"• {clean_text}", list_style))
        
        elif line == "---":
            # 区切り線
            elements.append(Spacer(1, 5*mm))
            # elements.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey)) # 線を引きたい場合
            elements.append(Spacer(1, 5*mm))
            
        else:
            # 通常の段落
            elements.append(Paragraph(line, body_style))

    # PDF生成
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ドライブ保存関数
def save_to_drive(file_obj, filename, folder_id, creds_info):
    try:
        creds = service_account.Credentials.from_service_account_info(creds_info)
        service = build('drive', 'v3', credentials=creds)

        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }
        # ポインタを先頭に戻してからアップロード
        file_obj.seek(0)
        media = MediaIoBaseUpload(file_obj, mimetype='application/pdf', resumable=True)

        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file.get('id')
    except Exception as e:
        return f"Error: {str(e)}"


st.set_page_config(page_title="簡易ストレングスファインダー", layout="wide")
# Streamlit CloudのSecretsから読み込む設計
try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
except:
    gemini_api_key = None

# Google Drive用の設定読み込み（一時的に無効化）
# try:
#     drive_folder_id = st.secrets["DRIVE_FOLDER_ID"]
#     # secretsの辞書を通常の辞書に変換（gcp_service_accountセクション）
#     gcp_sa_info = dict(st.secrets["gcp_service_account"])
# except:
#     drive_folder_id = None
#     gcp_sa_info = None

# 変数だけはNoneで定義しておく（エラー回避）
drive_folder_id = None
gcp_sa_info = None

if not gemini_api_key:
    st.warning("⚠️ Gemini APIキーが設定されていません。")
    client = None
else:
    client = genai.Client(api_key=gemini_api_key)

# --- 2. 質問データベース（34資質×5問：IT企業・ビジネス研修向け） ---
QUESTIONS_DB = {
    # --- 実行力 (Executing) ---
    "達成欲": [
        "メールやToDoリストを消化することに快感を覚える。",
        "プロジェクトが完了しても、すぐに次の技術習得やタスクに取り掛かる。",
        "長時間集中してコーディングや作業に没頭することができる。",
        "「忙しい状態」が自分にとって最も生産的だと感じる。",
        "成果物やコミット数など、目に見える実績がない日は満足できない。"
    ],
    "アレンジ": [
        "急な仕様変更やトラブルが起きても、柔軟にリソースを再配置できる。",
        "複雑なシステム構成図やスケジュールを整理・調整するのが得意だ。",
        "「もっと効率的な手順があるはずだ」と常にプロセスを疑っている。",
        "複数のプロジェクトを並行して進めるマルチタスクが得意だ。",
        "チームメンバーの個性を把握し、最適なタスクを割り振るのが好きだ。"
    ],
    "信念": [
        "技術的な流行よりも、プロダクトの「あるべき姿」や倫理観を重視する。",
        "オープンソース精神やチームの理念に反することには断固として反対する。",
        "自分の仕事が社会やユーザーにどう貢献しているか、意義を感じられないとやる気が出ない。",
        "一度「これは正しい」と決めたアーキテクチャや方針は、簡単には曲げない。",
        "給与や待遇以上に、企業のミッションへの共感を重視する。"
    ],
    "公平性": [
        "誰に対しても同じルールでコードレビューや評価を行うべきだと思う。",
        "一部の人だけが情報を握っている状況（属人化）が許せない。",
        "チーム内のタスク配分が偏っていると、すぐに是正したくなる。",
        "プロセスや手順が明確にドキュメント化されている環境を好む。",
        "「あの人だから特別」という判断は、組織のリスクになると感じる。"
    ],
    "慎重さ": [
        "リリース前のテストやセキュリティチェックは、念には念を入れるべきだ。",
        "新しいライブラリやツールを導入する際、まずはリスクを徹底的に洗い出す。",
        "会議では、楽観的な意見に対してあえて懸念点を指摘する役回りが多い。",
        "プライベートな情報は、たとえ同僚でも慎重に開示する。",
        "「とりあえずやってみよう」という言葉には危うさを感じる。"
    ],
    "規律性": [
        "コーディング規約やディレクトリ構成がきっちり整っていないと気持ち悪い。",
        "締め切りやマイルストーンは、何があっても守るべきだと思う。",
        "アジェンダのない会議や、時間の延長は非効率だと感じる。",
        "毎朝のルーチン（ログ確認やメールチェック等）が決まっている。",
        "計画通りにタスクが進むことに喜びを感じる。"
    ],
    "目標志向": [
        "プロジェクトのゴール（KGI/KPI）から逆算して今のタスクを決める。",
        "目的に直結しない無駄な会議や機能開発は排除したくなる。",
        "「何のためにこれをやるのか？」が明確でないと動きたくない。",
        "一度決めたマイルストーンに向かって、脇目も振らず進むことができる。",
        "優先順位をつけるのが得意で、「やらないこと」を明確にできる。"
    ],
    "責任感": [
        "自分の担当した業務にミスを発見したら、深夜でも修正しないと気が済まない。",
        "「やります」と言ったタスクは、何としてでもやり遂げる。",
        "他人のミスでも、チームの責任として自分事のように感じる。",
        "中途半端なクオリティで成果物を出すことはプライドが許さない。",
        "信頼を裏切ることに対して強い恐怖感や嫌悪感がある。"
    ],
    "回復志向": [
        "問題や課題が発生すると、逆に「解決してやる」と燃える。",
        "マイナス（不具合）をゼロ（正常）に戻す作業に達成感を感じる。",
        "炎上しているプロジェクトの火消し役に指名されることが多い。",
        "根本原因を突き止めるデバッグ作業が好きだ。",
        "うまくいっていないチームやコードを見ると、放っておけない。"
    ],

    # --- 影響力 (Influencing) ---
    "活発性": [
        "長時間の会議よりも、まずはプロトタイプを作って動かしたい。",
        "「やってみてダメなら直せばいい」という考えが好きだ。",
        "議論が停滞したとき、「よし、こうしよう」と決定を促すことが多い。",
        "新しい技術やツールが出ると、すぐに試してみたくなる。",
        "決断に時間をかけすぎることは、機会損失だと感じる。"
    ],
    "指令性": [
        "緊急事態（システムダウン等）の際、自然と周りに指示を出している。",
        "意見が対立したとき、なあなあにせず白黒はっきりさせたい。",
        "他人の顔色を伺うよりも、事実や必要なことをストレートに伝える。",
        "混乱しているプロジェクトに入ると、主導権を握って整理したくなる。",
        "困難な状況でも、動じずに決断を下すことができる。"
    ],
    "コミュニケーション": [
        "技術的な内容を、非エンジニアにもわかる言葉で説明するのが得意だ。",
        "プレゼンテーションやLT（ライトニングトーク）をするのが好きだ。",
        "ドキュメントを書く際、読み手を惹きつけるストーリー構成を考える。",
        "沈黙が続く会議で、話を振って場を盛り上げることがよくある。",
        "自分の書いたコードやアイデアについて語り始めると止まらない。"
    ],
    "競争性": [
        "競合他社のサービスや、他のチームの成果と比較して勝ちたいと思う。",
        "売上ランキングやパフォーマンス計測の数値を見るとやる気が出る。",
        "「平均的なエンジニア」でいることは我慢できない。",
        "ハッカソンや社内コンペなどで順位がつくと燃える。",
        "自分の成果がチーム内で一番だとわかるとモチベーションが上がる。"
    ],
    "最上志向": [
        "バグがないだけでなく、美しく効率的なコード（リファクタリング）を追求したい。",
        "平均的なチームを育てるより、優秀な精鋭チームで高い成果を出したい。",
        "自分の強みを極めて、スペシャリストになりたい。",
        "「弱みを克服する」より「強みを伸ばす」方が効率的だと思う。",
        "品質に妥協せず、ユーザーに「最高」と言われるUXを提供したい。"
    ],
    "自己確信": [
        "周りが反対しても、自分の技術選定や判断には自信がある。",
        "未経験の言語やフレームワークでも「なんとかなる」と思える。",
        "リスクのある決断をする際も、あまり迷いや不安を感じない。",
        "自分のキャリアや人生の進むべき方向がはっきりと見えている。",
        "正解のない問題に対して、指針を示すことができる。"
    ],
    "自我": [
        "自分の名前がクレジットされる仕事や、目立つプロジェクトに参加したい。",
        "「あなたにお願いしたい」と指名されることに大きな喜びを感じる。",
        "自分の仕事が、会社や業界にインパクトを与えるものであってほしい。",
        "フィードバックがないと不安になる。評価されていることを実感したい。",
        "プロフェッショナルとして、周囲から一目置かれる存在でありたい。"
    ],
    "社交性": [
        "カンファレンスや勉強会で、知らない人と名刺交換をするのが苦ではない。",
        "新しいプロジェクトチームに入っても、すぐにメンバーと打ち解けられる。",
        "クライアントや他部署の人と雑談をして関係を築くのが得意だ。",
        "人見知りをせず、誰とでもフラットに会話ができる。",
        "「広い人脈」はビジネスにおいて重要な資産だと思う。"
    ],

    # --- 人間関係構築力 (Relationship Building) ---
    "適応性": [
        "仕様変更や急なトラブル対応が入っても、ストレスなく予定を変更できる。",
        "長期的な計画を立てるより、その日その場の状況に合わせて動くのが好きだ。",
        "複数の割り込みタスクがあっても、冷静にさばくことができる。",
        "「なんとかなるさ」という精神で、不確実な状況を楽しめる。",
        "ガチガチに管理された開発フローよりも、アジャイルな環境が向いている。"
    ],
    "運命思考": [
        "チームメンバーとの出会いや、今の仕事には何らかの「縁」があると感じる。",
        "システム全体を俯瞰し、個々のモジュールがどう繋がり影響し合うかを考える。",
        "一時的な利益よりも、長期的な信頼関係やエコシステムを大切にしたい。",
        "「情けは人の為ならず」で、困っている人を助ければ自分に返ってくると思う。",
        "組織のサイロ化（縦割り）を嫌い、全体最適を常に意識する。"
    ],
    "成長促進": [
        "後輩や部下のメンターになり、彼らの成長を見るのが好きだ。",
        "後輩の小さな進歩でも、一緒に喜ぶことができる。",
        "完成された成果物より、そこに至るまでの試行錯誤のプロセスを評価する。",
        "人の潜在能力を見抜き、適材適所の役割を与えるのが得意だ。",
        "「教えること」は自分自身の学びにもなると感じる。"
    ],
    "共感性": [
        "ユーザーインタビューなどで、相手の言葉の裏にある感情を察することができる。",
        "チームの空気が悪いと、自分までパフォーマンスが落ちると感じる。",
        "同僚が悩んでいるとき、論理的な解決策より先にまず話を聞いてあげたい。",
        "テキストコミュニケーションでも、相手の感情への配慮を欠かさない。",
        "直感的に「あの人は今、無理をしているな」と気づくことができる。"
    ],
    "調和性": [
        "コードレビューや会議で対立が起きた際、妥協点を探して仲裁することが多い。",
        "無駄な議論で時間を浪費するより、合意形成をして前に進めたい。",
        "攻撃的な口調の人や、競争が激しすぎる環境は苦手だ。",
        "チーム全体の合意がないまま進めることには抵抗がある。",
        "目立つことよりも、チームの潤滑油として機能することを好む。"
    ],
    "包含": [
        "新しく入ったメンバーが輪に入れないでいると、声をかけたくなる。",
        "情報の共有漏れや、会議に呼ばれていない人がいると気になる。",
        "多様なバックグラウンドを持つ人が集まるチームが好きだ。",
        "「誰一人取り残さない」というスタンスで仕事をする。",
        "排他的なグループや派閥ができるのを嫌う。"
    ],
    "個別化": [
        "マニュアル通りの対応よりも、その人のスキルや状況に合わせた対応をする。",
        "メンバーそれぞれの「強み」や「こだわり」を把握している。",
        "全員に同じマネジメント手法を使うのは効果的ではないと思う。",
        "チーム編成の際、相性の良し悪しを直感的に判断できる。",
        "「普通はこうする」という言葉より「あなたはどうしたい？」を重視する。"
    ],
    "ポジティブ": [
        "過酷な労働の中でも、冗談を言って場を和ませる。",
        "失敗しても「良い経験になった」と前向きに捉えることができる。",
        "人を褒めるのが得意で、チームのモチベーションを上げるのが好きだ。",
        "ネガティブな発言ばかりする人とは距離を置きたくなる。",
        "仕事は楽しむものだという信念がある。"
    ],
    "親密性": [
        "広く浅い付き合いよりも、信頼できる少数のメンバーと深く付き合いたい。",
        "仕事だけの関係よりも、プライベートな話もできる関係を望む。",
        "気心の知れたメンバーとなら、阿吽の呼吸で高いパフォーマンスが出せる。",
        "一度信頼した相手のことは、何があっても裏切らない。",
        "表面的な社交辞令のやり取りは時間の無駄だと感じる。"
    ],

    # --- 戦略的思考力 (Strategic Thinking) ---
    "分析思考": [
        "「なぜ？」と根本原因を突き止めるまで気が済まない。",
        "感覚的な意見よりも、ログデータやメトリクス（数値）を信用する。",
        "コードのパフォーマンスや効率性を論理的に証明するのが好きだ。",
        "感情論で話が進むと、「事実ベースで話そう」と言いたくなる。",
        "複雑なデータの中にパターンや法則を見出すのが得意だ。"
    ],
    "原点思考": [
        "新しい機能を開発する前に、「過去の経緯」や「既存仕様」を深く理解したい。",
        "レガシーコードを読むとき、当時の開発者がなぜそう書いたのかを想像する。",
        "過去の成功事例や失敗事例（ポストモーテム）から学ぶことを重視する。",
        "歴史や経緯を知らずに、表面的な改革を行うことには反対だ。",
        "「昔はどうだったか」を知ることで、未来の予測ができると思う。"
    ],
    "未来志向": [
        "3年後、5年後の技術トレンドがどうなっているかを想像するのが好きだ。",
        "今の作業が、将来のどんな大きなビジョンに繋がっているかを常に意識する。",
        "「まだ世の中にないサービスやシステム」について語り合うとワクワクする。",
        "目の前のバグ修正よりも、次世代アーキテクチャの構想に時間を割きたい。",
        "ビジョンや夢を語ることで、チームを鼓舞することができる。"
    ],
    "着想": [
        "ブレインストーミングで、突飛とも思えるアイデアを出すのが得意だ。",
        "一見関係のない技術と技術を組み合わせて、新しい解決策を思いつく。",
        "既存のやり方に囚われず、全く新しいアプローチを試したくなる。",
        "単調なルーチンワークは退屈ですぐに飽きてしまう。",
        "「もし〜だったらどうなるだろう？」と考える時間が楽しい。"
    ],
    "収集心": [
        "使う予定がなくても、面白そうなライブラリや技術記事をブックマークしてしまう。",
        "社内Wikiやドキュメントを読み漁り、知識を蓄えるのが好きだ。",
        "知らない言葉が出てくると、すぐに検索せずにはいられない。",
        "「物知り」や「情報通」と言われることに喜びを感じる。",
        "情報はアウトプットするより、まずはインプットして整理しておきたい。"
    ],
    "内省": [
        "一人で静かにコードを書いたり、設計を考えたりする時間を大切にしたい。",
        "会議で即答するより、一度持ち帰ってじっくり考えたい。",
        "哲学的な問いや、概念的なアーキテクチャについて考えるのが好きだ。",
        "自分の思考プロセスを反芻し、なぜそう考えたのかを検証する。",
        "表面的な会話よりも、知的なディスカッションを好む。"
    ],
    "学習欲": [
        "新しい言語やフレームワークを学ぶこと自体が楽しい。",
        "結果を出すこと以上に、その過程で何を得たかを重視する。",
        "変化の激しいIT業界は、常に学び続けられるので天職だと感じる。",
        "わからないことがあれば、すぐにドキュメントや講座で勉強を始める。",
        "現状維持のまま、新しいスキルが身につかない環境には耐えられない。"
    ],
    "戦略性": [
        "ゴールにたどり着くための選択肢を瞬時に複数思いつく。",
        "「もしプランAがダメならプランB」と常に代替案を用意している。",
        "複雑なプロジェクトでも、ボトルネックを見抜き最短経路を見つけられる。",
        "全体像を俯瞰し、リソース配分の最適解を見つけるのが得意だ。",
        "行き当たりばったりではなく、大局的なシナリオを描いて行動する。"
    ]
}

# --- 3. UI構築 ---
st.set_page_config(page_title="簡易ストレングスファインダー", layout="wide")

st.title("🧩 簡易ストレングスファインダー")
st.markdown("""
この診断は、あなたのビジネスにおける強みを分析するためのツールです。  
日常業務やプロジェクトでの行動を思い浮かべながら、直感で回答してください。
1:全く当てはまらない ... 5:非常によく当てはまる
""")

st.info("💡 全34資質×5問＝計170問あります。所要時間は約10〜15分です。")

# --- シャッフル処理（セッションステートで固定） ---
if 'shuffled_questions' not in st.session_state:
    # 質問DBをフラットなリストに変換
    # [{"theme": "達成欲", "q": "質問文..."}, ...]
    all_questions = []
    for theme, q_list in QUESTIONS_DB.items():
        for q in q_list:
            all_questions.append({"theme": theme, "q": q})
    
    # シャッフル
    random.shuffle(all_questions)
    
    # 保存
    st.session_state['shuffled_questions'] = all_questions

st.markdown("### 回答者情報")
user_name = st.text_input("名前を入力してください", placeholder="例：山田 太郎")
if user_name:
    st.caption(f"こんにちは、{user_name}さん。準備ができたら診断を始めてください。")

# 保存されたシャッフル済みリストを取得
questions_to_display = st.session_state['shuffled_questions']

# フォームの開始
with st.form("assessment_form"):
    scores = {theme: 0 for theme in QUESTIONS_DB.keys()} # スコア初期化
    
    # 視認性を上げるため、2列レイアウトにする
    col1, col2 = st.columns(2)
    
    # 半分で分割
    half = len(questions_to_display) // 2
    
    # 左カラム
    with col1:
        for i, item in enumerate(questions_to_display[:half]):
            q_text = item['q']
            theme = item['theme']
            
            st.write(f"**Q.{i+1}**") # 質問番号
            ans = st.radio(
                f"{q_text}",
                options=[1, 2, 3, 4, 5],
                index=2, # デフォルト3
                horizontal=True,
                key=f"q_{i}", # ユニークなキー
                help="1:全く当てはまらない ... 5:非常によく当てはまる"
            )
            st.write("---") # 区切り線
            scores[theme] += ans # スコア加算

    # 右カラム
    with col2:
        for i, item in enumerate(questions_to_display[half:]):
            idx = i + half # 通し番号
            q_text = item['q']
            theme = item['theme']
            
            st.write(f"**Q.{idx+1}**")
            ans = st.radio(
                f"{q_text}",
                options=[1, 2, 3, 4, 5],
                index=2,
                horizontal=True,
                key=f"q_{idx}",
                label_visibility="collapsed"
            )
            st.write("---")
            scores[theme] += ans

    submitted = st.form_submit_button("📊 診断結果を表示する", use_container_width=True)

# --- 4. 集計とAI分析 ---
if submitted:
    if not user_name:
        st.error("⚠️ 名前が入力されていません。ページ上部の入力欄に名前を入力してください。")
        st.stop()
    else:
        with st.spinner("AIがあなたの強みを分析し、レポートを作成中...（約30〜60秒かかります）"):
            # スコア集計
            sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            all_ranks_str = "\n".join([f"{i+1}. {item[0]} ({item[1]}点)" for i, item in enumerate(sorted_scores)])
            
            # 領域別スコア集計
            domain_scores = {d: 0 for d in DOMAIN_NAMES}
            for theme, score in scores.items():
                domain = THEME_TO_DOMAIN.get(theme)
                if domain:
                    domain_scores[domain] += score

            ai_text = "（AI分析エラー）"
            if client:
                try:
                    prompt = f"""
                    あなたはIT業界に精通した熟練のキャリアコーチ兼HRコンサルタントです。
                    あるIT従事者{user_name}さんのストレングス診断（全34資質）の結果は以下の通りです。
                    このデータは「1位」から順に「34位」まで並んでいます。
                
                    【全34資質の順位データ】
                    {all_ranks_str}
                
                    【分析依頼】
                    34資質すべての並び順とスコアのバランスを考慮し、
                    この人物の「全体像」を深くプロファイリングしてください。
                    以下の構成でマークダウン形式で出力してください。
                
                    ### 1. プロファイル要約（キャッチコピー）
                    この人物をIT業界の役割で例えると何か？（例：「火消し役の鬼軍曹」「未来を創るアーキテクト」「チームの精神的支柱」など）
                    その理由を、上位資質と特徴的な中位・下位資質の組み合わせから解説してください。
                
                    ### 2. 強みの構造分析（Top Zone）
                    上位（1〜10位）にある資質がどのように連携して機能しているか。
                    単体の強みではなく「掛け合わせ」で生まれるパワー（例：着想×戦略性＝イノベーション力）を解説してください。
                
                    ### 3. 注意すべき盲点と葛藤（Bottom Zone & Gap）
                    - 下位（25〜34位）にある資質から予測される、業務上の苦手分野やリスク。
                    - 「上位にあるが過剰に働きすぎると危険な資質」や「上位資質と下位資質のギャップによる葛藤」（例：責任感は高いが、共感性が低い場合のバーンアウト・衝突リスクなど）について指摘してください。
                
                    ### 4. 明日から使えるIT業務アクションプラン
                    この強み構成を最大限に活かし、弱みをカバーするための具体的な行動指針。
                    （エンジニアリング、マネジメント、コミュニケーションの観点から）
                
                    ---
                    ※トーン＆マナー：
                    専門的かつ洞察に富んだ分析を行い、読者が「自分の説明書」を手に入れたと感じるような、納得感と前向きさを与える文章にしてください。
                    """
                    response = client.models.generate_content(
                        model="gemini-3-flash-preview",
                        contents=prompt,
                    )
                    ai_text = response.text
                except Exception as e:
                    ai_text = f"AI分析中にエラーが発生しました: {e}"

            #  PDF生成 (メモリ上)
            pdf_buffer = create_pdf(user_name, sorted_scores, domain_scores, ai_text)
            pdf_bytes = pdf_buffer.getvalue() # バイナリデータを取り出しておく
            save_msg = "※バックアップ保存機能は無効化されています"
            # 【自動実行】Googleドライブへ保存　一時的に無効化
            # save_msg = ""
            # if drive_folder_id and gcp_sa_info:
            #     # バッファをリセットして渡す
            #     pdf_buffer.seek(0)
            #     file_id = save_to_drive(pdf_buffer, f"{user_name}_strength_report.pdf", drive_folder_id, gcp_sa_info)
            #     if "Error" in str(file_id):
            #         save_msg = f"⚠️ 保存失敗: {file_id}"
            #     else:
            #         save_msg = f"✅ 診断結果をバックアップしました (File ID: {file_id})"
            # else:
            #     save_msg = "※ドライブ設定がないため保存されませんでした"
            # 結果をセッションステートに保存 (画面リロード対策)
            st.session_state['result_data'] = {
                'name': user_name,
                'scores': sorted_scores,
                'domain_scores': domain_scores,
                'ai_text': ai_text,
                'pdf_bytes': pdf_bytes,
                'save_msg': save_msg
            }

if 'result_data' in st.session_state:
    res = st.session_state['result_data']

    st.divider()
    st.header(f"🏆 {res['name']}さんの診断結果レポート")
    
    # 保存結果の通知 (無効化されているため常にwarningで表示)
    # if "✅" in res['save_msg']:
    #     st.success(res['save_msg'])
    # else:
    st.warning(res['save_msg'])

    st.subheader("領域別バランス")
    radar_buf_web = create_radar_chart(res['domain_scores'])
    st.image(radar_buf_web, caption="レーダーチャート", width=400)
    
    # 結果表示用カラム
    r_col1, r_col2 = st.columns([1, 2])
    
    with r_col1:
        st.subheader("全34資質の順位")
        # データフレーム化して表示
        df_all = pd.DataFrame(res['scores'], columns=["資質名", "スコア"])
        df_all.index = df_all.index + 1 # 1位から表示
        st.dataframe(df_all, height=600, use_container_width=True)

    with r_col2:
        st.subheader("AI分析レポート")
        st.markdown(res['ai_text'])

    st.divider()

    # F. 【ユーザー選択】ローカルへの保存ボタン
    st.subheader("📥 ローカルに保存する")
    st.write("必要であればここからPDFをダウンロードできます。")
    
    st.download_button(
        label="📄 PDFレポートをダウンロード",
        data=res['pdf_bytes'],
        file_name=f"{res['name']}_strength_report.pdf",
        mime="application/pdf"
    )
















