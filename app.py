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
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# Google API関連
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# --- 1. 設定とデータ定義 ---

# カテゴリ定義
CATEGORY_NAMES = ["技術・実務", "仕事の進め方", "対人・組織"]

# カテゴリごとの色設定（レーダーチャート用）
CATEGORY_COLORS_RT = {
    "技術・実務": "#4a69bd",   # アズール
    "仕事の進め方": "#009432", # オリーブ
    "対人・組織": "#b33939"    # ワインレッド
}

# PDF用背景色
CATEGORY_BG_COLORS = {
    "技術・実務": HexColor('#edf2fb'),
    "仕事の進め方": HexColor('#eafaf1'),
    "対人・組織": HexColor('#fdedec')
}

# 項目のカテゴリマッピング（どの項目がどのカテゴリに属するか）
# ここで定義することで、チャートやPDFの色分けを行う
TRAIT_CATEGORY_MAP = {
    # --- 技術・実務 (Hard Skills / Tech Stance) ---
    "可用性追求": "技術・実務", "セキュリティ意識": "技術・実務", "キャパシティ予測": "技術・実務", "イレギュラー耐性": "技術・実務",
    "自動化思考": "技術・実務", "根本原因探求": "技術・実務", "技術的負債への感度": "技術・実務", "コスト意識": "技術・実務",
    "万全な備え": "技術・実務", "変更管理": "技術・実務", "ユーザビリティ": "技術・実務", "具現化の速さ": "技術・実務",
    "可読性追求": "技術・実務", "未知への探究心": "技術・実務", "再利用性": "技術・実務", "創造的解決力": "技術・実務",
    "未来への構想力": "技術・実務", "組織の構築力": "技術・実務", "予算・リソース管理": "技術・実務", "成果への執着": "技術・実務",
    "安全第一": "技術・実務", "指差呼称": "技術・実務", "整頓・配線美": "技術・実務", "工具の扱い": "技術・実務",
    "空間認識力": "技術・実務", "物理セキュリティ": "技術・実務", "ハードウェア知見": "技術・実務", "作業迅速性": "技術・実務",
    "現場判断力": "技術・実務", "静寂・環境維持": "技術・実務",

    # --- 仕事の進め方 (Process / Work Style) ---
    "ドキュメント重視": "仕事の進め方", "標準化志向": "仕事の進め方", "危機察知能力": "仕事の進め方", "ロジカルシンキング": "仕事の進め方",
    "完了主義": "仕事の進め方", "継続学習力": "仕事の進め方", "自律性": "仕事の進め方", "優先順位付け": "仕事の進め方",
    "品質へのこだわり": "仕事の進め方", "柔軟な適応力": "仕事の進め方", "ビジネス感覚": "仕事の進め方", "即断即決力": "仕事の進め方",
    "権限委譲": "仕事の進め方", "準備・段取り": "仕事の進め方", "経験からの学習力": "仕事の進め方", "やり抜く力": "仕事の進め方",
    "時間管理": "仕事の進め方", "縁の下の力持ち": "仕事の進め方", "奉仕の精神": "仕事の進め方", "デモ力": "仕事の進め方",

    # --- 対人・組織 (Communication / Human Skills) ---
    "チームワーク": "対人・組織", "情報の透明性": "対人・組織", "他者へのリスペクト": "対人・組織", "専門用語の翻訳": "対人・組織",
    "支援要請": "対人・組織", "心理的安全性構築": "対人・組織", "合意形成": "対人・組織", "率直なフィードバック": "対人・組織",
    "粘り強さ": "対人・組織", "仕様の言語化": "対人・組織", "外的な交渉力": "対人・組織", "献身的な牽引力": "対人・組織",
    "モチベーション管理": "対人・組織", "フィードバックスキル": "対人・組織", "素直な吸収力": "対人・組織", "質問力": "対人・組織",
    "報連相の徹底": "対人・組織", "活気": "対人・組織", "議事録・記録": "対人・組織", "感謝の体現": "対人・組織",
    "ホスピタリティ": "対人・組織"
}

# --- フォント設定 ---
FONT_FILE = "ipaexg.ttf"
REGISTERED_FONT_NAME = "IPAexGothic"

if not os.path.exists(FONT_FILE):
    st.error(f"⚠️ エラー: フォントファイル `{FONT_FILE}` が見つかりません。")
    st.info("【解決策】 `ipaexg.ttf` をダウンロードし、`app.py` と同じ場所にアップロードしてください。")
    st.stop()

try:
    fm.fontManager.addfont(FONT_FILE)
    font_prop = fm.FontProperties(fname=FONT_FILE)
    plt.rcParams['font.family'] = font_prop.get_name()
    if REGISTERED_FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(REGISTERED_FONT_NAME, FONT_FILE))
except Exception as e:
    st.error(f"フォント登録中にエラーが発生しました: {e}")
    st.stop()

# --- 関数定義 ---

def create_radar_chart(scores_by_category):
    labels = CATEGORY_NAMES
    # カテゴリごとの合計値をそのままプロット
    values = [scores_by_category.get(d, 0) for d in labels]
    
    num_vars = len(labels)
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    values += values[:1]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(4, 4), subplot_kw=dict(polar=True))
    
    # 軸の設定
    max_val = 50
    ax.set_ylim(0, max_val + (max_val * 0.1))
    ax.set_yticks(np.linspace(0, max_val, 4))
    ax.set_yticklabels([])
    ax.set_rlabel_position(0)

    # ラベル設定
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontdict={'fontsize': 14, 'fontweight': 'bold'})

    # プロット
    ax.plot(angles, values, color='#34495e', linewidth=2, linestyle='solid')
    ax.fill(angles, values, color='#34495e', alpha=0.25)
    
    # マーカー
    for i, (angle, val) in enumerate(zip(angles[:-1], values[:-1])):
        color = CATEGORY_COLORS_RT.get(labels[i], "#333")
        ax.plot(angle, val, marker='o', color=color, markersize=8)

    plt.tight_layout(pad=1)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, transparent=False, facecolor='white')
    plt.close(fig)
    buf.seek(0)
    return buf

def create_pdf(name, role_name, all_ranked_data, category_scores, ai_text):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4,
        rightMargin=20*mm, leftMargin=20*mm,
        topMargin=25*mm, bottomMargin=25*mm
    )
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
    
    elements = []
    styles = getSampleStyleSheet()
    
    # スタイル定義
    title_style = ParagraphStyle(name='JpTitle', fontName=REGISTERED_FONT_NAME, fontSize=24, leading=30, alignment=TA_CENTER, spaceAfter=10*mm)
    h1_style = ParagraphStyle(name='JpH1', fontName=REGISTERED_FONT_NAME, fontSize=18, leading=22, spaceBefore=15*mm, spaceAfter=10*mm, textColor=colors.navy, borderPadding=5, borderWidth=0, backColor=colors.whitesmoke)
    h2_style = ParagraphStyle(name='JpH2', fontName=REGISTERED_FONT_NAME, fontSize=14, leading=18, spaceBefore=12*mm, spaceAfter=6*mm, textColor=colors.darkblue)
    body_style = ParagraphStyle(name='JpBody', fontName=REGISTERED_FONT_NAME, fontSize=10.5, leading=18, spaceAfter=3*mm, alignment=TA_LEFT)
    caption_style = ParagraphStyle(name='JpCaption', fontName=REGISTERED_FONT_NAME, fontSize=9, leading=12, textColor=colors.grey, alignment=TA_CENTER)

    # 1ページ目：サマリー
    elements.append(Paragraph(f"行動特性・強み分析レポート", title_style))
    elements.append(Paragraph(f"回答者: {name} 様 （職種：{role_name}）", ParagraphStyle(name='sub', parent=title_style, fontSize=14, spaceAfter=20*mm)))

    elements.append(Paragraph("■ 特性の全体バランスとTop10", h1_style))

    # チャート
    radar_buf = create_radar_chart(category_scores)
    radar_img = Image(radar_buf, width=80*mm, height=80*mm)
    
    # Top10テーブル
    top10_data = [["順位", "項目名", "カテゴリ", "スコア"]]
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
        cat = TRAIT_CATEGORY_MAP.get(theme, "-")
        bg_color = CATEGORY_BG_COLORS.get(cat, colors.white)
        top10_data.append([str(i+1), theme, cat, str(score)])
        t10_cmds.append(('BACKGROUND', (0, i+1), (-1, i+1), bg_color))

    top10_table = Table(top10_data, colWidths=[12*mm, 45*mm, 25*mm, 15*mm])
    top10_table.setStyle(TableStyle(t10_cmds))

    # 配置
    layout_data = [[radar_img, top10_table]]
    layout_table = Table(layout_data, colWidths=[90*mm, 90*mm])
    layout_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (0,0), 'CENTER'),
        ('ALIGN', (1,0), (1,0), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    elements.append(layout_table)
    elements.append(Spacer(1, 5*mm))
    elements.append(Paragraph("※チャートは「技術・実務」「仕事の進め方」「対人・組織」の3カテゴリ分類です。", caption_style))
    
    elements.append(PageBreak())

    # 2ページ目：全項目リスト
    elements.append(Paragraph("■ 全30項目の診断結果一覧", h1_style))
    
    half_idx = (len(all_ranked_data) + 1) // 2
    left_data = all_ranked_data[:half_idx]
    right_data = all_ranked_data[half_idx:]

    full_table_data = [["順位", "項目名", "カテゴリ", "スコア", "", "順位", "項目名", "カテゴリ", "スコア"]]
    ft_cmds = [
        ('FONT', (0,0), (-1,-1), REGISTERED_FONT_NAME, 9),
        ('GRID', (0,0), (3,-1), 0.25, colors.lightgrey),
        ('BACKGROUND', (0,0), (3,0), colors.midnightblue),
        ('GRID', (5,0), (8,-1), 0.25, colors.lightgrey),
        ('BACKGROUND', (5,0), (8,0), colors.midnightblue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 4),
    ]

    max_rows = len(left_data)
    for i in range(max_rows):
        row_data = []
        # 左
        l_item = left_data[i]
        l_cat = TRAIT_CATEGORY_MAP.get(l_item[0], "-")
        l_bg = CATEGORY_BG_COLORS.get(l_cat, colors.white)
        row_data.extend([str(i+1), l_item[0], l_cat, str(l_item[1])])
        ft_cmds.append(('BACKGROUND', (0, i+1), (3, i+1), l_bg))
        
        row_data.append("") # 空白列

        # 右
        if i < len(right_data):
            r_item = right_data[i]
            r_cat = TRAIT_CATEGORY_MAP.get(r_item[0], "-")
            r_bg = CATEGORY_BG_COLORS.get(r_cat, colors.white)
            row_data.extend([str(i+1+half_idx), r_item[0], r_cat, str(r_item[1])])
            ft_cmds.append(('BACKGROUND', (5, i+1), (8, i+1), r_bg))
        else:
            row_data.extend(["", "", "", ""])
        
        full_table_data.append(row_data)

    col_widths = [10*mm, 35*mm, 20*mm, 12*mm] * 2
    col_widths.insert(4, 10*mm)
    full_table = Table(full_table_data, colWidths=col_widths, repeatRows=1)
    
    # ai_textがNoneの場合のガード処理を追加
    if not ai_text: ai_text = "AI分析レポートはありません。"
    
    full_table.setStyle(TableStyle(ft_cmds))
    elements.append(full_table)
    
    elements.append(PageBreak())

    # 3ページ目：AIレポート
    elements.append(Paragraph("■ AIによるプロファイリング分析", h1_style))
    
    # Markdown簡易パース
    h_pattern = re.compile(r'^(#+)\s*(.*)')
    for line in ai_text.split('\n'):
        line = line.strip()
        if not line:
            elements.append(Spacer(1, 4*mm))
            continue
        
        line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)

        match = h_pattern.match(line)
        if match:
            clean_text = match.group(2)
            elements.append(Paragraph(clean_text, h2_style))
        elif line.startswith('- ') or line.startswith('* '):
            clean_text = line[2:].strip()
            list_style = ParagraphStyle(name='JpList', parent=body_style, leftIndent=5*mm, firstLineIndent=-5*mm)
            elements.append(Paragraph(f"• {clean_text}", list_style))
        elif line == "---":
            elements.append(Spacer(1, 5*mm))
        else:
            elements.append(Paragraph(line, body_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer

def save_to_drive(file_obj, filename, folder_id, creds_info):
    try:
        creds = service_account.Credentials.from_service_account_info(creds_info)
        service = build('drive', 'v3', credentials=creds)
        file_metadata = {'name': filename, 'parents': [folder_id]}
        file_obj.seek(0)
        media = MediaIoBaseUpload(file_obj, mimetype='application/pdf', resumable=True)
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file.get('id')
    except Exception as e:
        return f"Error: {str(e)}"

# --- データ構築：全質問データベースと職種設定 ---
# 全項目の質問プール（各5問）
MASTER_QUESTIONS_DB = {
    # --- インフラ・DC系 ---
    "可用性追求": ["99.9%では満足できず、100%の稼働を目指している。", "ダウンタイムが発生することに強いストレスを感じる。", "SPOF（単一障害点）を見つけると解消せずにはいられない。", "メンテナンス時でもサービスを止めない方法を常に考えている。", "「落ちないシステム」こそが正義だと思っている。"],
    "セキュリティ意識": ["利便性が多少犠牲になっても、安全性を優先すべきだ。", "脆弱性情報は常日頃チェックしている。", "パスワード管理や権限設定には人一倍厳しい。", "「これくらい大丈夫だろう」という甘い判断は絶対に許さない。", "セキュリティ事故は企業の死に直結すると常に意識している。"],
    "キャパシティ予測": ["リソース不足でアラートが鳴る前に増強計画を立てる。", "今の伸び率から、半年後の負荷状況を具体的にイメージできる。", "「余裕を持った設計」をしないと不安になる。", "突発的なスパイクアクセスにも耐えられる構成を常に考える。", "リソースの限界ギリギリで運用するのは恐怖だ。"],
    "イレギュラー耐性": ["障害でアラートが鳴り響く中でも冷静にログを見れる。", "想定外のトラブルが起きてもパニックにならず、逆に集中力が増す。", "混乱した状況下で優先順位を即座に判断できる。", "二転三転する状況を楽しめるタフさがある。", "プレッシャーがかかる場面ほど燃えるタイプだ。"],
    "万全な備え": ["バックアップが成功しているか毎日確認しないと落ち着かない。", "「データが消えたら終わり」という危機感を常に持っている。", "リストア（復元）手順を定期的に訓練している。(または用意している)", "冗長化されていないデータを見ると寒気がする。", "最悪のシナリオを想定して準備するのが好きだ。"],
    "変更管理": ["リリース手順書や承認フローを無視した作業は絶対に認めない。", "作業前のダブルチェックや承認プロセスは不可欠だと思う。", "「なんとなく」の設定変更が最大の事故原因だと知っている。", "変更履歴（ログ）を残さない作業はプロの仕事ではない。", "手順通りに進めることに快感を覚える。"],
    "縁の下の力持ち": ["目立つ機能開発より、土台を支える仕事に誇りを感じる。", "誰にも気づかれずにシステムが安定稼働しているのが一番嬉しい。", "派手な称賛よりも、静かな信頼を大切にしたい。", "サポート役としてチームに貢献することにやりがいを感じる。", "自分が支えているからサービスが動いているという自負がある。"],
    "奉仕の精神": ["社内の開発者が快適に作業できる環境を提供したい。", "「開発環境が遅い」と言われたらすぐに改善したくなる。", "インフラは開発者へのサービス業だと捉えている。", "依頼に対して「できません」と即答せず、代替案を考える。", "相手の困りごとを技術で解決してあげたい。"],
    "指差呼称": ["作業対象を指差し、声に出して確認する癖がついている。", "思い込みによる操作ミスを防ぐための確認動作を怠らない。", "「ヨシ！」という掛け声がないと作業に入れない。", "確認不足によるミスは恥ずべきことだと思う。", "安全確認の手順を省略することは絶対にない。"],
    "整頓・配線美": ["ケーブルが乱雑に配線されていると直したくてうずうずする。", "美しい配線や整えられた作業環境は必須だと思う。", "ラベルの貼り方や結束バンドの処理にも美学を持っている。", "整理整頓されたラックを見ると心が落ち着く。", "汚い現場からは良い仕事は生まれないと信じている。"],
    "工具の扱い": ["ドライバーやテスターなどの道具の手入れを欠かさない。", "用途に合った正しい工具を選んで使用している。", "工具の紛失や置き忘れには人一倍気を使う。", "新しい便利な工具を見つけると試したくなる。", "道具を大切に扱うことはプロの基本だと思う。"],
    "空間認識力": ["ラックの空きスペースを見て、機器の配置パズルを瞬時に解ける。", "物理的なサイズ感や収まりをイメージするのが得意だ。", "限られたスペースを最大限有効活用する配置を考えるのが好きだ。", "図面を見ただけで、実際の現場の様子が想像できる。", "物理的な干渉や熱溜まりを直感的に予見できる。"],
    "物理セキュリティ": ["入館証や鍵の管理には神経質なほど気を使う。", "共連れ入館を見かけたら注意せずにはいられない。", "物理的な不正侵入のリスクを常に警戒している。", "施錠確認を徹底しないと帰れない。", "セキュリティゲートを通過するときに緊張感を持っている。"],
    "ハードウェア知見": ["サーバーの蓋を開けて中身を見るのが好きだ。", "スペック表を見ただけでマシンの性能特性がわかる。", "部品交換の手順が頭に入っている。", "物理層のトラブルシューティングに自信がある。", "HWの進化や新製品情報には常にアンテナを張っている。"],
    "作業迅速性": ["障害時は1秒でも早く復旧させることに全力を注ぐ。", "パーツ交換作業の手際良さには自信がある。", "時間を意識してテキパキと動くのが得意だ。", "無駄な動きを極力減らして最短で作業を完了させたい。", "SLA（約束された復旧時間）を守る意識が強い。"],
    "現場判断力": ["現場のLEDの状態や異音を、電話先の相手に正確に伝えられる。", "現地の状況を言葉で描写する能力に長けている。", "リモート指示者の目となり耳となる意識を持っている。", "些細な違和感も見逃さずに報告する。", "現場で起きている「事実」を伝えることに徹している。"],
    "ホスピタリティ": ["リモートの依頼主が安心できるよう、こまめに状況報告をする。", "「何か他についでにやることはありますか？」と聞くことがある。", "顔が見えない相手だからこそ、丁寧な対応を心がけている。", "スマートハンズ作業では、期待以上の対応を目指している。", "「助かりました」と言われるのが一番の報酬だ。"],
    "静寂・環境維持": ["サーバールームの温度や湿度が規定値から外れると気になる。", "埃やゴミが落ちているとすぐに掃除したくなる。", "マシンのファン音の変化など細かい異変に気づくことがある。", "機器にとって最適な環境を守る番人だという意識がある。", "整然とした静寂（ファンの音だけがする状態）を守りたい。"],
    "専門用語の翻訳": ["インフラの専門用語を使わずに、非エンジニアに状況を説明できる。","「なぜサーバーが落ちたか」を、経営層や顧客にわかる言葉で例えられる。","相手の技術レベルに合わせて、話す内容や深さを調整している。","カタカナ語を乱用せず、平易な日本語に置き換えて話す努力をしている。","「つまりこういうことですね」と相手が理解できたか確認しながら話す。"],
    "安全第一": ["作業スピードよりも、自分と仲間の安全を最優先にしている。","高所作業や重量物運搬の際、保護具や手順を絶対に省略しない。","少しでも危険を感じたら、作業を中断する勇気を持っている。","「事故を起こさないこと」がプロフェッショナルの第一条件だと思っている。","ヒヤリハット（事故の一歩手前）を見逃さず、対策を講じている。"],

    # --- アプリ・開発系 ---
    "ユーザビリティ": ["技術的にすごくても、使いにくい機能はゴミだと思う。", "常に「ユーザーならどう感じるか？」を考えて実装している。", "UX（ユーザー体験）を損なう仕様にはNOと言える。", "自分の作ったものをユーザーとして使い倒すことが多い。", "画面の向こうにいる人の顔を想像して仕事をしている。"],
    "具現化の速さ": ["完成度100%を目指すより、まずは動くものを作ってリリースしたい。", "「とりあえずやってみる」精神でコードを書き始める。", "市場に出すスピード（Time to Market）を最優先する。", "悩み続けるより手を動かして検証するタイプだ。", "プロトタイプを爆速で作るのが得意だ。"],
    "可読性追求": ["自分以外の誰が見てもわかる「きれいなコード」書きたい。", "変数名の命名にはかなりこだわる。", "スパゲッティコードを見るとリファクタリングしたくなる。", "コードは書く時間より読まれる時間の方が長いと知っている。", "美しいコードは芸術だと思う。"],
    "未知への探究心": ["新しいフレームワークや言語が出るとすぐに触ってみる。", "枯れた技術より、最新のモダンな技術を使いたい。", "前例のない技術スタックでも恐れずに導入を提案する。", "技術トレンドを追うのが趣味だ。", "常に新しいことに挑戦していないと飽きてしまう。"],
    "再利用性": ["同じコードを2回書いたら、共通化（コンポーネント化）したくなる。", "汎用的に使えるライブラリやモジュールを作るのが好きだ。", "「これ、他のプロジェクトでも使えるな」と常に考えている。", "コピペコードが増殖するのが許せない。", "効率的な開発基盤を整えることに喜びを感じる。"],
    "柔軟な適応力": ["仕様変更があっても「より良くなるならOK」と受け入れられる。", "計画通りに進むことより、変化に対応することを重視する。", "朝令暮改の環境でもストレスを感じにくい。", "フィードバックを受けて即座に方向修正できる。", "完璧な計画よりも、柔軟な対応力を大切にしている。"],
    "創造的解決力": ["既存のやり方に囚われず、アイデアで壁を突破するのが好きだ。", "「無理」と言われると逆に燃えて解決策を探す。", "誰も思いつかなかったような実装方法を思いつくことがある。", "ハック的なアプローチで難題をクリアすることに快感を覚える。", "創意工夫でリソース不足を補うのが得意だ。"],
    "ビジネス感覚": ["コードを書くことは手段であり、目的は事業価値を生むことだと理解している。", "エンジニアも売上やKPIを意識すべきだと思う。", "ビジネスにつながらない技術的こだわりは捨てる勇気がある。", "「なぜこの機能が必要なのか」をビジネス視点で説明できる。", "事業の成長にコミットしている。"],
    "仕様の言語化": ["クライアントのふわっとした要望を、実装可能な仕様に落とし込める。", "エンジニア用語を使わずに仕様を説明できる。", "ビジネス要件と技術的制約のバランスを取るのが得意だ。", "「つまりこういうことですね」と要約して確認する癖がある。", "要件定義の漏れを見つけるのが得意だ。"],
    "デモ力": ["開発中の機能を魅力的に見せるプレゼンが得意だ。", "デモを見せてフィードバックを引き出すのが好きだ。", "動くものを見せるのが一番の説得材料だと思う。", "プレゼン資料よりデモ機を触ってもらうことを優先する。", "自分の作った機能を自慢したい気持ちがある。"],

    # --- マネジメント系 ---
    "未来への構想力": ["チームや組織の「あるべき姿」をよく語る。", "3年後、5年後の技術ロードマップを描くのが好きだ。", "未来のビジョンでメンバーをワクワクさせたい。", "目の前の課題だけでなく、長期的な方向性を示している。", "夢や理想を語ることはリーダーの責務だと思う。"],
    "組織の構築力": ["カルチャーにマッチする人材を見抜く目がある。", "チームの弱点を補うための配置を考えるのが好きだ。", "「誰と働くか」が成果に直結すると信じている。", "採用活動には時間と労力を惜しまない。", "強いチームを作るための組織設計に興味がある。"],
    "予算・リソース管理": ["限られた予算や人員で最大の成果を出すパズルが得意だ。", "コスト対効果（ROI）を常に意識して判断している。", "リソースの配分が偏らないように調整している。", "赤字プロジェクトにならないよう数字を管理している。", "経営資源を無駄にすることに痛みを感じる。"],
    "成果への執着": ["プロセスが良くても、結果（数字）が出なければ意味がないと思う。", "目標未達の言い訳をするのが嫌いだ。", "チーム全員で勝利（目標達成）することに燃える。", "シビアな現実から目を逸らさずに成果を追求する。", "ビジネスインパクトを出すことが最大の貢献だと考える。"],
    "外的な交渉力": ["他部署やクライアントとの調整役を買って出ることが多い。", "無理難題からチームを守るための交渉ができる。", "政治的な動きや根回しも必要なら厭わない。", "利害関係の調整をしてプロジェクトを円滑に進めるのが得意だ。", "「貸し借り」のバランスを取るのが上手い。"],
    "即断即決力": ["情報が不十分でも、止まるよりは決断して進める。", "決断のスピードが組織のスピードを決めると信じている。", "リスクを取って意思決定することに躊躇しない。", "「私が責任を持つからやってくれ」と言える。", "優柔不断な態度を見せることは避けている。"],
    "権限委譲": ["部下を信頼して仕事を任せることができている。", "マイクロマネジメント（細かい干渉）はしないようにしている。", "自分がいなくても回るチームを作りたい。", "失敗させる権利も部下に与えている。", "「任せる」ことの難しさと重要性を理解している。"],
    "献身的な牽引力": ["リーダーの役割はメンバーの障害物を取り除くことだと思う。", "部下が働きやすい環境を作るために汗をかいている。", "「俺についてこい」より「支えるから行ってこい」タイプだ。", "チームの成功が自分の成功だと本気で思える。", "メンバーのために雑用をすることも苦ではない。"],
    "モチベーション管理": ["メンバー一人ひとりの「やりがい」や「目標」を把握している。", "落ち込んでいるメンバーがいるとすぐに気づく。", "適切なタイミングで褒めたり励ましたりしている。", "個人のWill（やりたいこと）と業務のMustを繋げている。", "チームの士気を高めるための工夫をしている。"],
    "フィードバックスキル": ["言いにくいことでも、相手の成長のために率直に伝える。", "人格ではなく行動に対してフィードバックしている。", "叱るだけでなく、改善の道筋を一緒に考える。", "フィードバック面談の時間を大切にしている。", "相手が納得して行動を変えられるような伝え方を工夫している。"],

    # --- 新人・若手・成長系 ---
    "素直な吸収力": ["アドバイスや指摘を受けたら、言い訳せずにまずはやってみる。", "自分のやり方に固執せず、良い方法はすぐに取り入れる。", "教えてもらったことはメモを取り、同じ質問をしないようにする。", "スポンジのように新しい知識を吸収したい。", "フィードバックを成長の糧として歓迎する。"],
    "質問力": ["わからなくなったら、時間を浪費する前に質問する。", "「何がわかっていて、何がわからないか」を整理して聞ける。", "質問することは恥ではなく、業務遂行の責任だと捉えている。", "的確な質問をして先輩の時間を奪わないようにしている。", "不明点を放置して進めることの怖さを知っている。"],
    "報連相の徹底": ["悪いニュース（失敗や遅延）ほど早く報告する。", "状況が変わったらすぐに共有を入れる。", "「言ったつもり」をなくし、伝わったか確認する。", "上司や先輩を不安にさせない報告頻度を心がけている。", "報告・連絡・相談は仕事の基本動作だと思う。"],
    "時間管理": ["納期や約束の時間は絶対に守る。", "作業にかかる時間を見積もり、遅れそうなら事前に相談する。", "ダラダラ残業せず、時間内での成果を意識している。", "会議の開始時刻には必ず席についている。", "他人の時間を奪う遅刻は信用を失うと知っている。"],
    "準備・段取り": ["作業に取り掛かる前に、必要な情報や手順を確認している。", "行き当たりばったりではなく、段取りを考えてから動く。", "事前の準備で仕事の8割が決まると思う。", "会議の前にアジェンダや資料に目を通している。", "抜け漏れがないかリストアップして確認する。"],
    "経験からの学習力": ["ミスをした時、落ち込むだけでなく「なぜ起きたか」を振り返る。", "同じ失敗を二度と繰り返さないための対策を立てる。", "失敗を隠さず、ノートやWikiにまとめて次に活かす。", "失敗経験が自分を強くすると信じている。", "転んでもただでは起きない精神がある。"],
    "活気": ["自分から明るく挨拶をして、話しやすい雰囲気を作っている。", "チームが沈んでいる時こそ、元気に振る舞う。", "返事はハッキリと相手に聞こえるようにする。", "コミュニケーションの入り口としての挨拶を大切にしている。", "若手の特権として、場の空気を明るくしたい。"],
    "やり抜く力": ["難しい課題にぶつかっても、簡単には投げ出さない。", "地味な作業でも粘り強くやり遂げる。", "一度決めたことは最後までやり抜く根性がある。", "壁にぶつかった時こそ成長のチャンスだと思う。", "諦めの悪さは長所だと思う。"],
    "議事録・記録": ["会議の議事録や作業ログを積極的に残す。", "決定事項やTo Doを聞き漏らさない。", "記録に残すことでチームをサポートしたい。", "メモを取るスピードと正確さには自信がある。", "言った言わないのトラブルを防ぐ防波堤になりたい。"],
    "感謝の体現": ["教えてもらった時や助けてもらった時、すぐに「ありがとうございます」と言う。", "些細なことでも感謝の言葉を忘れない。", "感謝の体現ことで信頼関係が深まると思う。", "メールやチャットでも感謝の意を一言添える。", "礼儀正しさはスキルの一つだと考えている。"],

    # --- 全職種共通（Common） ---
    "自動化思考": ["同じ作業を2回やるなら、スクリプトを書いて自動化したい。", "手作業（Toil）を憎み、効率化することに執念を燃やす。", "「もっと楽にできないか」と常に考えている。", "RPAやIaCなどの自動化技術を積極的に使う。", "自分がサボるために全力を出すタイプだ。"],
    "根本原因探求": ["動いたからOKではなく「なぜ動いたのか」を理解したい。", "対症療法的な解決では満足できず、真因を突き止めたい。", "エラーログを深掘りすることに喜びを感じる。", "「なぜ？」を5回繰り返す思考が身についている。", "表面的な解決は再発を招くと知っている。"],
    "ドキュメント重視": ["属人化を防ぐため、知識は必ずWikiやドキュメントに残す。", "「自分が休んでも回る」状態を作るのが責任だと思う。", "ドキュメントがないシステムは負債だと感じる。", "わかりやすいマニュアルを作るのが好きだ。", "口頭伝承を嫌う。"],
    "技術的負債への感度": ["「とりあえず」のコードが将来の負債になることを予見できる。", "汚いコードや構成を放置することに罪悪感を感じる。", "リファクタリングの時間を確保するようにしている。", "長期的な保守性を考えて設計する。", "将来的に運用コストが膨らむのを恐れている。"],
    "標準化志向": ["独自のやり方をせず、チームのルールや規約を守る。", "例外処理を作らず、パターンを統一したい。", "誰がやっても同じ結果になる仕組みを作りたい。", "業界標準やライブラリに頼らず、独自のロジックや手法で機能を開発・構築することを嫌う。", "標準化こそがスケーラビリティの鍵だと思う。"],
    "コスト意識": ["クラウドの利用料やライセンス費用を常に意識している。", "無駄なリソースが起動していると停止したくなる。", "自分の作業工数もコスト換算して考えている。", "投資対効果（ROI）に合わない技術選定はしない。", "会社の金も自分の金のように大切に使う。"],
    "危機察知能力": ["変更作業を行う際、影響範囲を瞬時にイメージできる。", "「なんか嫌な予感がする」という勘がよく当たる。", "楽観的な計画に対して、あえてリスクを指摘する。", "最悪のケースを想定して準備する癖がある。", "石橋を叩いて渡る慎重さがある。"],
    "ロジカルシンキング": ["感情論ではなく、事実とデータに基づいて判断する。", "「なんとなく」ではなくロジカルに説明できる。", "物事を構造化して考えるのが得意だ。", "矛盾点を見つけるのが早い。", "冷静沈着に物事を分析する。"],
    "完了主義": ["中途半端な状態でタスクを放置するのが気持ち悪い。", "99%と100%（完了）の間には大きな壁があると思う。", "最後のテストや監視設定までやり切ってこそ「完了」だ。", "To Doリストを全て消し込むことに快感を覚える。", "やり遂げる力には自信がある。"],
    "継続学習力": ["業務時間外でも技術書を読んだり勉強会に参加したりする。", "新しいことを学ぶのが苦ではなく楽しみだ。", "現状のスキルで満足したら終わりだと思う。", "常に最新情報をキャッチアップしていないと不安になる。", "学習はエンジニアの呼吸と同じだ。"],
    "自律性": ["指示待ちにならず、自分から課題を見つけて提案する。", "放置されても自分で仕事を見つけて進められる。", "自分のキャリアや成長にオーナーシップを持っている。", "マイクロマネジメントされるのを嫌う。", "自分で決めて行動することにやりがいを感じる。"],
    "優先順位付け": ["タスクが溢れても、重要度と緊急度で瞬時に順位をつけられる。", "「やらないこと」を決めるのが得意だ。", "ビジネスインパクトの大きい仕事から着手する。", "マルチタスクでも混乱せずにさばける。", "リソースの限界を理解し、取捨選択ができる。"],
    "品質へのこだわり": ["プロとして、低品質な成果物を出すことはプライドが許さない。", "細部（誤字や数ピクセルのズレ）まで徹底的にこだわる。", "テストをおろそかにすることに恐怖を感じる。", "「まあいいか」で妥協することはまずない。", "品質は工程の中で作り込むものだと信じている。"],
    "チームワーク": ["個人の手柄より、チーム全体の成果を優先する。", "困っているメンバーがいたら自分の作業を止めてでも助ける。", "チームワークが良い時こそ最高のパフォーマンスが出る。", "情報の抱え込みをせず、チームに共有する。", "スタンドプレーより連携を重視する。"],
    "情報の透明性": ["ミスや悪い報告ほど、隠さずに即座に共有する。", "情報をオープンにすることが信頼に繋がると信じている。", "嘘やごまかしは絶対にしない。", "進捗状況を正直に可視化している。", "誠実さがプロフェッショナルの条件だと思う。"],
    "他者へのリスペクト": ["自分と異なる職種（営業やデザイナー等）への敬意を忘れない。", "相手の背景や立場を理解しようと努める。", "頭ごなしに否定せず、まずは意見を受け止める。", "技術力だけでなく人間性も大切にする。", "感謝の気持ちを行動で示している。"],
    "支援要請": ["自分で解決できない時は、時間を浪費する前に助けを求める。", "「わかりません」「助けてください」と言える強さがある。", "抱え込んでプロジェクトを遅延させるのが最悪だと知っている。", "適切なタイミングでアラートを上げられる。", "知ったかぶりをしない。"],
    "心理的安全性構築": ["ミスを責めるより、仕組みを改善しようと提案する。", "「何を言っても大丈夫」な空気を作り、失敗の報告やアイデアを出やすくする。", "メンバーの発言を否定せず、肯定から入る。", "失敗を共有しやすい雰囲気作りを心がけている。", "笑顔やユーモアで場を和ませる。"],
    "合意形成": ["対立する意見が出ても、粘り強く調整して着地点を見つける。", "「納得感」を大切にして物事を進める。", "ファシリテーターとして会議をまとめるのが得意だ。", "強引に進めるより、根回しをして合意を得る。", "みんなが同じ方向を向くように働きかける。"],
    "率直なフィードバック": ["相手のためを思い、耳の痛いことでもハッキリ伝える。", "仕様の矛盾や無駄な機能にはNOと言う勇気がある。", "忖度せずに、プロダクトのために意見する。", "建設的な批判は歓迎する。", "なあなあの関係より、切磋琢磨する関係を望む。"],
    "粘り強さ": ["原因不明のバグやトラブルでも、解決するまで諦めない。", "厳しい状況でも逃げ出さずに立ち向かう。", "泥臭い作業でもコツコツと続けられる。", "長期プロジェクトでもモチベーションを保てる。", "「もうダメだ」と思ってからが勝負だと思っている。"],
}

# 職種別リスト構成（30項目定義）
ROLE_CONFIG = {
    "インフラエンジニア": [
        "可用性追求", "セキュリティ意識", "キャパシティ予測", "イレギュラー耐性", "自動化思考",
        "根本原因探求", "ドキュメント重視", "技術的負債への感度", "標準化志向", "コスト意識",
        "危機察知能力", "ロジカルシンキング", "完了主義", "万全な備え", "継続学習力",
        "変更管理", "自律性", "優先順位付け", "縁の下の力持ち", "品質へのこだわり",
        "チームワーク", "情報の透明性", "他者へのリスペクト", "専門用語の翻訳", "支援要請",
        "心理的安全性構築", "合意形成", "奉仕の精神", "率直なフィードバック", "粘り強さ"
    ],
    "アプリエンジニア": [
        "ユーザビリティ", "具現化の速さ", "可読性追求", "未知への探究心", "自動化思考",
        "根本原因探求", "ドキュメント重視", "技術的負債への感度", "標準化志向", "再利用性",
        "危機察知能力", "ロジカルシンキング", "完了主義", "柔軟な適応力", "継続学習力",
        "創造的解決力", "自律性", "優先順位付け", "ビジネス感覚", "品質へのこだわり",
        "チームワーク", "情報の透明性", "他者へのリスペクト", "仕様の言語化", "支援要請",
        "心理的安全性構築", "合意形成", "デモ力", "率直なフィードバック", "粘り強さ"
    ],
    "マネジメント層": [
        "未来への構想力", "組織の構築力", "予算・リソース管理", "成果への執着", "自動化思考",
        "根本原因探求", "ドキュメント重視", "技術的負債への感度", "標準化志向", "外的な交渉力",
        "危機察知能力", "ロジカルシンキング", "完了主義", "即断即決力", "継続学習力",
        "権限委譲", "自律性", "優先順位付け", "献身的な牽引力", "品質へのこだわり",
        "チームワーク", "情報の透明性", "他者へのリスペクト", "モチベーション管理", "支援要請",
        "心理的安全性構築", "合意形成", "フィードバックスキル", "率直なフィードバック", "粘り強さ"
    ],
    "新入社員・若手": [
        "素直な吸収力", "質問力", "報連相の徹底", "時間管理", "自動化思考",
        "根本原因探求", "ドキュメント重視", "技術的負債への感度", "標準化志向", "準備・段取り",
        "危機察知能力", "ロジカルシンキング", "完了主義", "経験からの学習力", "継続学習力",
        "活気", "自律性", "優先順位付け", "やり抜く力", "品質へのこだわり",
        "チームワーク", "情報の透明性", "他者へのリスペクト", "議事録・記録", "支援要請",
        "心理的安全性構築", "合意形成", "感謝の体現", "率直なフィードバック", "粘り強さ"
    ],
    "DC保守・運用": [
        "安全第一", "指差呼称", "整頓・配線美", "工具の扱い", "標準化志向",
        "危機察知能力", "完了主義", "品質へのこだわり", "空間認識力", "物理セキュリティ",
        "根本原因探求", "ハードウェア知見", "作業迅速性", "現場判断力", "ロジカルシンキング",
        "ドキュメント重視", "継続学習力", "技術的負債への感度", "イレギュラー耐性", "自動化思考",
        "チームワーク", "情報の透明性", "他者へのリスペクト", "ホスピタリティ", "支援要請",
        "心理的安全性構築", "合意形成", "静寂・環境維持", "率直なフィードバック", "粘り強さ"
    ]
}

# --- 4. アプリケーション本体 ---
st.set_page_config(page_title="IT職種別コンピテンシー診断", layout="wide")

# Secrets取得
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

# Gemini初期化
if not gemini_api_key:
    st.warning("⚠️ Gemini APIキーが設定されていません。")
    client = None
else:
    client = genai.Client(api_key=gemini_api_key)

# サイドバー：職種選択
st.sidebar.title("🛠 設定")
selected_role = st.sidebar.selectbox(
    "あなたの職種を選択してください",
    options=list(ROLE_CONFIG.keys())
)

st.title(f"💻 IT職種別コンピテンシー診断：{selected_role}編")
st.markdown("""
この診断は、あなたの業務における行動特性や強みを分析するためのツールです。
今の自分に最も近い感覚で、直感的に回答してください。
**1:全く当てはまらない ... 5:非常によく当てはまる**
""")
st.info(f"💡 {selected_role}向けの30項目×5問＝計150問あります。")

st.markdown("### 回答者情報")
user_name = st.text_input("名前を入力してください", placeholder="例：山田 太郎")

# 質問データの準備
session_key = f"shuffled_questions_{selected_role}"

if session_key not in st.session_state:
    target_traits = ROLE_CONFIG[selected_role]
    questions_for_role = []
    
    for trait in target_traits:
        q_list = MASTER_QUESTIONS_DB.get(trait, [])
        if not q_list:
            st.error(f"Error: 項目 '{trait}' の質問定義が見つかりません。")
            continue
        for q in q_list:
            questions_for_role.append({"theme": trait, "q": q})
    
    random.shuffle(questions_for_role)
    st.session_state[session_key] = questions_for_role

questions_to_display = st.session_state[session_key]

# フォーム
with st.form("assessment_form"):
    # スコア初期化
    target_traits = ROLE_CONFIG[selected_role]
    scores = {theme: 0 for theme in target_traits}
    
    col1, col2 = st.columns(2)
    half = len(questions_to_display) // 2
    
    with col1:
        for i, item in enumerate(questions_to_display[:half]):
            q_text = item['q']
            theme = item['theme']
            st.write(f"**Q.{i+1}** {q_text}")
            ans = st.radio(f"{q_text}", options=[1, 2, 3, 4, 5], index=2, horizontal=True, key=f"{selected_role}_q_{i}", label_visibility="collapsed")
            st.write("---")
            scores[theme] += ans

    with col2:
        for i, item in enumerate(questions_to_display[half:]):
            idx = i + half
            q_text = item['q']
            theme = item['theme']
            st.write(f"**Q.{idx+1}** {q_text}")
            ans = st.radio(f"{q_text}", options=[1, 2, 3, 4, 5], index=2, horizontal=True, key=f"{selected_role}_q_{idx}", label_visibility="collapsed")
            st.write("---")
            scores[theme] += ans

    submitted = st.form_submit_button("📊 診断結果を表示する", use_container_width=True)

# 処理
if submitted:
    if not user_name:
        st.error("⚠️ 名前を入力してください。")
        st.stop()
    else:
        with st.spinner("AIが分析レポートを作成中..."):
            # スコア集計
            sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            all_ranks_str = "\n".join([f"{i+1}. {item[0]} ({item[1]}点)" for i, item in enumerate(sorted_scores)])
            
            # カテゴリ別スコア
            category_scores = {c: 0 for c in CATEGORY_NAMES}
            for theme, score in scores.items():
                cat = TRAIT_CATEGORY_MAP.get(theme)
                if cat:
                    category_scores[cat] += score

            # AI分析
            ai_text = "（AI分析エラー）"
            if client:
                try:
                    prompt = f"""
                    あなたはIT業界の熟練キャリアコーチです。
                    **「{selected_role}」** として働く {user_name} さんの行動特性診断（30項目）の結果を分析します。
                    
                    【全30項目のスコア順位】
                    {all_ranks_str}

                    【分析依頼】
                    スコア傾向に基づきこの人物の「全体像」を深くプロファイリングし、以下の構成でマークダウン形式のレポートを作成してください。
                    
                    ### 1. {selected_role}としてのプロファイル要約
                    この人物のタイプを一言で表すキャッチコピー（例：「鉄壁の守護神」「爆速のプロトタイパー」など）をつけ、
                    その理由を、上位資質と特徴的な中位・下位資質の組み合わせから解説してください。
                    
                    ### 2. 強みの相乗効果（Top Zone Analysis）
                    上位（1〜10位）にある資質が掛け合わさることで、どのような強みを発揮しているか。
                    単体の資質ではなく、組み合わせによるシナジーを解説してください。
                    
                    ### 3. 注意すべき盲点とリスク（Gap Analysis）
                    - 下位（20〜30位）にある資質から予測される、業務上の弱点やリスク。
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

            # PDF生成
            pdf_buffer = create_pdf(user_name, selected_role, sorted_scores, category_scores, ai_text)
            pdf_bytes = pdf_buffer.getvalue()
            save_msg = "※バックアップ機能は現在無効です"

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
                'role': selected_role,
                'scores': sorted_scores,
                'category_scores': category_scores,
                'ai_text': ai_text,
                'pdf_bytes': pdf_bytes,
                'save_msg': save_msg
            }

if 'result_data' in st.session_state:
    res = st.session_state['result_data']

    st.divider()
    st.header(f"🏆 {res['name']}さんの診断結果（{res['role']}）")
    st.warning(res['save_msg'])

    st.subheader("特性バランス（カテゴリ別）")
    radar_buf_web = create_radar_chart(res['category_scores'])
    st.image(radar_buf_web, caption="レーダーチャート", width=400)
    
    r_col1, r_col2 = st.columns([1, 2])
    
    with r_col1:
        st.subheader("全30項目の順位")
        df_all = pd.DataFrame(res['scores'], columns=["項目名", "スコア"])
        df_all.index = df_all.index + 1
        st.dataframe(df_all, height=600, use_container_width=True)

    with r_col2:
        st.subheader("AI分析レポート")
        st.markdown(res['ai_text'])

    st.divider()
    st.subheader("📥 レポート保存")
    st.download_button(
        label="📄 PDFレポートをダウンロード",
        data=res['pdf_bytes'],
        file_name=f"{res['name']}_{res['role']}_report.pdf",
        mime="application/pdf"
    )








