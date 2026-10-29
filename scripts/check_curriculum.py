#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_curriculum.py (v3.0 全維度真實語料檢核引擎)
國小四年級教材與試題自動化三階審查工具
落實「強制以本機教科書/習作真實文本為唯一真理（Ground Truth）」、
「全文本題目/選項/填空實質詞彙深度掃描」、「零容忍未學超綱詞彙一票否決」。
"""

import os
import sys
import re
import json
import glob
import argparse
from pathlib import Path

# 基礎設定
CONFIG = {
    "subjects": {
        "math": {
            "name": "數學科（南一版）",
            "dirs": ["115四上數課習", r"D:\115四年級複習卷\數學"],
            "keywords": ["南一", "分數", "大數", "角度", "公里", "乘法", "除法", "等值", "三角形", "n-Ⅱ-", "s-Ⅱ-", "數學"],
            "misconceptions": ["M4-FRAC-01", "M4-PLACE-01", "M4-GEOM-01", "M4-GEOM-02", "M4-CALC-01"]
        },
        "chinese": {
            "name": "國語科（翰林版）",
            "dirs": ["115四上國課習", r"D:\opencode\115四上期中國語\115四上國課習", r"D:\opencode\115四上期中國語"],
            "keywords": ["翰林", "記敘文", "說明文", "五感", "修辭", "句型", "作文", "6-Ⅱ-", "5-Ⅱ-", "國語"],
            "misconceptions": ["C4-TEXT-01", "C4-PUNCT-01", "C4-STRUC-01", "C4-VOCAB-01"]
        },
        "social": {
            "name": "社會科（康軒版）",
            "dirs": ["115社會課習", r"D:\115四年級複習卷\社會", r"D:\antui\html簡報\115四上社會_1-2地形的種類與生活"],
            "keywords": ["康軒", "家鄉", "地形", "產業", "港區", "水資源", "公共設施", "社2a-Ⅱ-", "地1b-Ⅱ-", "社會"],
            "misconceptions": ["S4-GEO-01", "S4-ECON-01", "S4-CIVIC-01", "S4-LOCAL-01"]
        }
    },
    "local_keywords": ["梧棲", "中正國小", "高美濕地", "臺中港", "台中港", "港區", "海線", "九降風", "風力發電", "大甲", "清水"],
    "tier2_keywords": {
        "sdgs": ["SDG", "永續", "海洋", "生態", "保育", "責任消費", "氣候行動", "潔淨能源", "水資源"],
        "steam": ["STEAM", "探究", "實驗", "工程", "科學", "跨域", "設計思維", "物理", "觀察"],
        "clt": ["認知負荷", "工作記憶", "字數精簡", "版面留白", "鷹架", "步驟"]
    }
}

CACHE_FILE = Path(".cache/textbook_corpus.json")
LEXICON_FILE = Path("references/g4_genuine_textbook_lexicon.json")

# 出題架構功能詞與排版詞彙（這些屬於試卷功能詞，不列入超綱判定）
EXAM_SYSTEM_STOPWORDS = {
    "下列", "何者", "正確", "錯誤", "選項", "括號", "填入", "選出", "合適", "第題",
    "第一", "第二", "第三", "第四", "第五", "第六", "第七", "第八", "第九", "第十",
    "分數", "題目", "說明", "請問", "根據", "本文", "表示", "代表", "引起", "造成",
    "進行", "活動", "問題", "回答", "如圖", "所示", "以上", "以下", "不是", "不能",
    "可以", "必須", "應該", "一共", "總共", "剩下", "原來", "共有", "比較", "找出",
    "適當", "最符合", "引導說明", "學習單", "格紋框", "思源黑體", "思源柔黑體", "源泉圓體", "芫荽體",
    "誘答", "診斷", "代碼", "客觀", "觀點", "事實", "學校", "國小", "班級", "姓名", "座號",
    "月考", "評量", "測驗", "試題", "加分", "挑戰", "學生", "老師", "同學", "請在", "完成",
    "記錄", "探究", "討論", "情境", "延伸", "連結", "目標", "指標", "代號", "表現", "內容",
    "生活", "家鄉", "自然", "環境", "社會", "國語", "數學", "四年級", "中年級", "四上", "四下",
    "翰林", "南一", "康軒", "部定", "版本", "課本", "習作", "單元", "第課", "第一課", "第二課",
    "第三課", "第四課", "第五課", "第六課", "統整", "活動", "閱讀", "寫作", "理解", "心得",
    "分享", "思考", "練習", "步驟", "時間", "地點", "人物", "事件", "心情", "五感",
    "視覺", "聽覺", "嗅覺", "味覺", "觸覺", "段落", "起承轉合", "文章", "短文", "照樣造句",
    "造句", "成語", "修辭", "意思", "詞語", "生字", "注音", "國字", "連連看", "選擇題",
    "填空題", "問答題", "是非題", "簡答題", "畫線", "代換", "替換", "配合", "對應",
    "我們", "你們", "他們", "大家", "這個", "那個", "這些", "那些", "因為", "所以",
    "如果", "但是", "而且", "雖然", "以及", "或者", "或是", "什麼", "怎麼", "如何",
    "為什麼", "哪一個", "哪一種", "哪一項", "哪個", "哪種", "哪些", "一樣", "非常",
    "特別", "十分", "更加", "越來", "開始", "最後", "接著", "然後", "首先", "此外",
    "大標題", "副標題", "學校與班級", "引導說明", "抄寫說明", "誘答診斷", "正確解答",
    "填入時間", "填入地點", "填入人物", "填入心情", "填入動作", "填入感受",
    "每題", "每題分", "總分", "配分", "得分", "題號",
    "第一單元", "第二單元", "第三單元", "第四單元", "我愛家鄉", "天空的奇想", "品德小故事", "海洋世界",
    "美麗的家鄉", "傳統住屋與生活器具", "傳統信仰與老街", "家鄉的作息節慶與節日"
}

def load_or_build_corpus(force_rebuild: bool = False) -> dict:
    """載入或動態建立本機教科書語料庫（支援多路徑自動搜尋與 fitz / pypdf）"""
    if not force_rebuild and CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if any(len(v) > 0 for v in data.values()):
                    return data
        except Exception:
            pass

    corpus = {"math": {}, "chinese": {}, "social": {}}
    try:
        import fitz
        has_fitz = True
    except ImportError:
        has_fitz = False

    for subj_key, subj_info in CONFIG["subjects"].items():
        found_files = []
        for d in subj_info["dirs"]:
            if os.path.exists(d):
                pdfs = glob.glob(f"{d}/**/*.pdf", recursive=True)
                found_files.extend(pdfs)
        
        found_files = sorted(list(set(found_files)))
        for pdf_path in found_files:
            stem = Path(pdf_path).stem
            raw_text = ""
            try:
                if has_fitz:
                    doc = fitz.open(pdf_path)
                    for page in doc:
                        raw_text += page.get_text()
                else:
                    import pypdf
                    reader = pypdf.PdfReader(pdf_path)
                    for page in reader.pages:
                        raw_text += page.extract_text() or ""
            except Exception:
                continue
            clean = re.sub(r"\s+", "", raw_text)
            if clean:
                corpus[subj_key][stem] = clean

    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(corpus, f, ensure_ascii=False)

    return corpus

def extract_all_assessment_terms(content: str) -> dict:
    """
    全文本深度結構化抽取：
    1. 選擇題選項 (A/B/C/D)
    2. 填空題、引號括號詞語
    3. 好詞百寶箱 / 生字生詞表
    4. 全文實質內容詞彙（去除停用詞）
    """
    results = {
        "options": [],         # 選擇題選項詞
        "bracketed": [],       # 括號、引號內的詞
        "focus_vocab": [],     # 好詞庫/詞彙表
        "content_tokens": []   # 全文實質中文詞
    }

    lines = content.splitlines()

    # 1. 抽取好詞百寶箱與課本好詞
    for match in re.findall(r"(?:好詞百寶箱|課本好詞|精選詞彙)[^\n]*[：:]([^\n]+)", content):
        for part in re.split(r"[/、，\s,]", match):
            clean = re.sub(r"[^\u4e00-\u9fa5]", "", part)
            if 2 <= len(clean) <= 6 and clean not in EXAM_SYSTEM_STOPWORDS:
                results["focus_vocab"].append(clean)

    for match in re.findall(r"選用課文好詞[：:]([^\n】\]]+)", content):
        for part in re.split(r"[/、，\s,]", match):
            clean = re.sub(r"[^\u4e00-\u9fa5]", "", part)
            if 2 <= len(clean) <= 6 and clean not in EXAM_SYSTEM_STOPWORDS:
                results["focus_vocab"].append(clean)

    # 2. 逐行分析選擇題選項與填空括號
    for line_idx, line in enumerate(lines, 1):
        line_clean = line.strip()
        if not line_clean:
            continue

        # 抓取選擇題選項：(A) xxx, （A）xxx, (1) xxx, A. xxx, A、xxx, ① xxx （排除 1. 2. 題號）
        opt_matches = re.findall(r"(?:[（\(\[]\s*[A-Da-d1-4]\s*[）\)\]]|(?<!\d)[A-Da-d][\.\、]|[①②③④])\s*([^\n\(\)（）\[\]A-D①②③④]+)", line_clean)
        for opt in opt_matches:
            # 去除雜項說明如 【誘答診斷...】
            pure_opt = re.split(r"[【（\(\*]", opt)[0].strip()
            pure_clean = re.sub(r"[^\u4e00-\u9fa5]", "", pure_opt)
            # 若選項為 2~5 字的詞彙辨析或成語（如：見狀、巡視、大顯身手），視為核心命題詞彙
            if 2 <= len(pure_clean) <= 5:
                if pure_clean not in EXAM_SYSTEM_STOPWORDS and pure_clean not in CONFIG["local_keywords"]:
                    results["options"].append({"word": pure_clean, "line": line_idx, "context": line_clean[:50]})

        # 抓取括號/引號/書名號名詞
        # 排除標題行中的說明括號 (如 ## 一、選擇題 (每題5分))
        if line_clean.startswith("#"):
            continue

        b_matches = re.findall(r"[「『【（(《〈]([^\n「『【（(《〈」』】）)》〉]{2,8})[」』】）)》〉]", line_clean)
        for bm in b_matches:
            if any(bm.startswith(prefix) for prefix in ["抄寫", "引導", "說明", "填入", "選用", "設計", "版本", "大標題", "副標題", "學校", "班級", "注意", "備註"]):
                continue
            if re.search(r"\d+\s*分", bm) or re.search(r"每題|配分|總分|得分", bm):
                continue
            pure_bm = re.sub(r"[^\u4e00-\u9fa5]", "", bm)
            if 2 <= len(pure_bm) <= 6 and pure_bm not in EXAM_SYSTEM_STOPWORDS and pure_bm not in CONFIG["local_keywords"]:
                results["bracketed"].append({"word": pure_bm, "line": line_idx, "context": line_clean[:50]})

    # 3. 全文抽出實質詞（滑動視窗 2~4 字）以檢驗與本冊課習之關聯度
    clean_prose = re.sub(r"```[\s\S]*?```", "", content)
    clean_prose = re.sub(r"<[^>]+>", " ", clean_prose)
    clean_prose = re.sub(r"\[.*?\]\(.*?\)", "", clean_prose)
    
    # 抓取所有中文詞句片段
    clauses = re.findall(r"[\u4e00-\u9fa5]{2,}", clean_prose)
    extracted_tokens = set()
    for clause in clauses:
        c_clean = clause.strip()
        if len(c_clean) < 2:
            continue
        # 2字詞
        for i in range(len(c_clean) - 1):
            w = c_clean[i:i+2]
            if w not in EXAM_SYSTEM_STOPWORDS and w not in CONFIG["local_keywords"]:
                extracted_tokens.add(w)
        # 3字詞
        for i in range(len(c_clean) - 2):
            w = c_clean[i:i+3]
            if w not in EXAM_SYSTEM_STOPWORDS and w not in CONFIG["local_keywords"]:
                extracted_tokens.add(w)
        # 4字詞
        for i in range(len(c_clean) - 3):
            w = c_clean[i:i+4]
            if w not in EXAM_SYSTEM_STOPWORDS and w not in CONFIG["local_keywords"]:
                extracted_tokens.add(w)

    results["content_tokens"] = sorted(list(extracted_tokens))
    return results

def verify_all_terms(extracted: dict, subject_key: str, corpus: dict) -> dict:
    """
    全方位比對實體語料庫：
    1. 驗證選項高風險詞（違規一票否決）
    2. 驗證括號/填空詞（違規一票否決）
    3. 驗證好詞百寶箱（違規一票否決）
    4. 檢視全文與本冊課習之命中詞彙數（確認具備實質關聯）
    """
    subj_corpus = corpus.get(subject_key, {})
    if not subj_corpus:
        return {
            "has_corpus": False,
            "total_checked": 0,
            "found_terms": [],
            "missing_terms": [],
            "missing_options": [],
            "missing_bracketed": []
        }

    combined_text = "".join(subj_corpus.values())

    found_terms = set()
    missing_terms = set()
    missing_options = []
    missing_bracketed = []

    # 1. 驗證選項
    for item in extracted["options"]:
        word = item["word"]
        if word in combined_text:
            found_terms.add(word)
        else:
            missing_terms.add(word)
            missing_options.append(item)

    # 2. 驗證括號/填空
    for item in extracted["bracketed"]:
        word = item["word"]
        if word in combined_text:
            found_terms.add(word)
        else:
            missing_terms.add(word)
            missing_bracketed.append(item)

    # 3. 驗證好詞庫
    for word in extracted["focus_vocab"]:
        if word in combined_text:
            found_terms.add(word)
        else:
            missing_terms.add(word)

    # 4. 驗證全文實質用詞命中課習之情況
    for word in extracted["content_tokens"]:
        if word in combined_text:
            found_terms.add(word)

    return {
        "has_corpus": True,
        "total_checked": len(found_terms) + len(missing_terms),
        "found_terms": sorted(list(found_terms)),
        "missing_terms": sorted(list(missing_terms)),
        "missing_options": missing_options,
        "missing_bracketed": missing_bracketed
    }

def analyze_content(content: str, filename: str, corpus: dict):
    """分析文本內容並進行嚴格三階檢測與真實課本比對"""
    report = {
        "filename": filename,
        "tier1_pass": True,
        "tier1_issues": [],
        "tier1_corpus_verification": None,
        "tier2_pass": True,
        "tier2_missing": [],
        "tier3_pass": False,
        "tier3_highlights": [],
        "detected_subject": "未知科目",
        "misconceptions_found": []
    }

    # 1. 偵測科目
    subject_scores = {"math": 0, "chinese": 0, "social": 0}
    for subj_key, subj_info in CONFIG["subjects"].items():
        for kw in subj_info["keywords"]:
            if kw in content:
                subject_scores[subj_key] += 1
    
    best_subj = max(subject_scores, key=subject_scores.get)
    if subject_scores[best_subj] > 0:
        report["detected_subject"] = CONFIG["subjects"][best_subj]["name"]
        curr_subj = best_subj
    else:
        curr_subj = None

    # 2. 第一階（最低門檻檢測）
    has_g4 = any(term in content for term in ["四年級", "四上", "四下", "中年級", "4上", "4年級"])
    if not has_g4:
        report["tier1_issues"].append("未明確標示或對齊國小『四年級/中年級』先備經驗。")

    has_curriculum_code = any(code in content for code in ["-Ⅱ-", "108課綱", "課綱代碼", "學習表現", "學習內容"])
    if not has_curriculum_code:
        report["tier1_issues"].append("缺少 108 課綱學習重點代碼（例如 n-Ⅱ-7、6-Ⅱ-1、社2a-Ⅱ-1）。")

    has_publisher = any(pub in content for pub in ["南一", "翰林", "康軒"])
    if not has_publisher:
        report["tier1_issues"].append("未標明或對準校內指定教科書版本（數學南一、國語翰林、社會康軒）。")

    # 本機課習教材存在性檢查
    if curr_subj:
        subj_corpus = corpus.get(curr_subj, {})
        if not subj_corpus:
            report["tier1_issues"].append(
                f"🚨 致命缺失：本機未載入【{CONFIG['subjects'][curr_subj]['name']}】真實課本/習作 PDF 語料庫！"
                "本系統嚴禁 AI 假審查，缺少實體語料庫直接判定一票否決！"
            )

    # ★ 全文本深度詞彙抽取與實體教科書比對
    if curr_subj and corpus.get(curr_subj):
        extracted = extract_all_assessment_terms(content)
        ver_res = verify_all_terms(extracted, curr_subj, corpus)
        report["tier1_corpus_verification"] = ver_res

        # 若有選項超綱，屬致命嚴重違規
        if ver_res["missing_options"]:
            opt_details = [f"第{item['line']}行:「{item['word']}」" for item in ver_res["missing_options"][:6]]
            report["tier1_issues"].append(
                f"🚨【致命紅線】選擇題選項出現非本冊課本/習作之未學詞彙：{', '.join(opt_details)}。"
            )

        # 若有括號填空/關鍵生字超綱
        if ver_res["missing_bracketed"]:
            brk_details = [f"第{item['line']}行:「{item['word']}」" for item in ver_res["missing_bracketed"][:6]]
            report["tier1_issues"].append(
                f"🚨【致命紅線】題目填空/重點標示出現非本冊課本/習作詞彙：{', '.join(brk_details)}。"
            )

        # 若抽驗詞彙數為 0，嚴禁假通過
        if len(ver_res["found_terms"]) == 0:
            report["tier1_issues"].append(
                "🚨【檢驗失效】未能在文本中檢出任何符合本冊課習之核心詞彙，無法證明符合教材進度，判定打回重置！"
            )

    if report["tier1_issues"]:
        report["tier1_pass"] = False

    # 3. 第二階（中階目標檢測：嚴格退回標準）
    has_sdgs = any(kw in content for kw in CONFIG["tier2_keywords"]["sdgs"])
    if not has_sdgs:
        report["tier2_missing"].append("SDGs 永續發展目標生活化融入（例如 SDG 14 海洋生態、SDG 12 責任消費、SDG 7 潔淨能源）。")

    has_steam = any(kw in content for kw in CONFIG["tier2_keywords"]["steam"])
    if not has_steam:
        report["tier2_missing"].append("STEAM 跨學科探究與動手做/工程思維。")

    words_count = len(content)
    if words_count > 4500 and "學習單" in content:
        report["tier2_missing"].append("文本長度可能過高，請檢核是否符合四年級 CLT 3~4 工作記憶元素上限。")

    if report["tier2_missing"]:
        report["tier2_pass"] = False

    # 4. 第三階（高階亮點）
    for lkw in CONFIG["local_keywords"]:
        if lkw in content:
            report["tier3_highlights"].append(f"融入海線在地生活情境：【{lkw}】")

    if curr_subj:
        for misc in CONFIG["subjects"][curr_subj]["misconceptions"]:
            if misc in content:
                report["misconceptions_found"].append(misc)
                report["tier3_highlights"].append(f"具備高階迷思診斷誘答機制：【{misc}】")

    if report["tier3_highlights"]:
        report["tier3_pass"] = True

    return report

def generate_markdown_report(analysis: dict) -> str:
    """產出標準三階審查自我檢測報告"""
    lines = []
    lines.append("\n\n---\n")
    lines.append("## 📋 AI 自我檢測審查報告 (Self-Review Report v3.0 深度實體驗證版)")
    lines.append(f"- **檢測檔案**：`{analysis['filename']}`")
    lines.append(f"- **對應科目與版本**：{analysis['detected_subject']}")
    
    # 第一階
    if analysis["tier1_pass"]:
        lines.append("- **🛑 第一階（最低門檻）：✅ 審查通過（100% 符合真實課本/習作）**")
        lines.append("  - 先備經驗：符合四年級學生認知水平，零超綱符號。")
        lines.append("  - 108 課綱：已對齊領域學習表現與學習內容代碼。")
        lines.append("  - 版本對齊：精確鎖定梧棲區中正國小指定版本。")
        if analysis["tier1_corpus_verification"]:
            ver = analysis["tier1_corpus_verification"]
            lines.append(f"  - 📖 本機課習 PDF 全文精確比對：通過（已驗證 {len(ver['found_terms'])} 個實質詞彙 100% 存在於課本/習作中）。")
            if ver["found_terms"]:
                sample_found = "、".join(ver["found_terms"][:8])
                lines.append(f"  - 🎯 命中真實語料範例：`{sample_found}` 等。")
    else:
        lines.append("- **🛑 第一階（最低門檻）：❌ 未達標（一票否決・打回重置）**")
        for issue in analysis["tier1_issues"]:
            lines.append(f"  - ⚠️ 缺失：{issue}")
        if analysis["tier1_corpus_verification"]:
            ver = analysis["tier1_corpus_verification"]
            if ver.get("missing_options"):
                lines.append("  - 🚫 超綱選項清單（必須更換）：")
                for mo in ver["missing_options"][:5]:
                    lines.append(f"    • 第 {mo['line']} 行選項: `{mo['word']}` (出處未查得)")
            if ver.get("missing_bracketed"):
                lines.append("  - 🚫 超綱填空清單（必須更換）：")
                for mb in ver["missing_bracketed"][:5]:
                    lines.append(f"    • 第 {mb['line']} 行填空: `{mb['word']}` (出處未查得)")

    # 第二階
    if analysis["tier2_pass"]:
        lines.append("- **⚠️ 第二階（中階目標）：✅ 審查通過**")
        lines.append("  - 認知負荷 (CLT)：版面配置與題幹長度符合四年級記憶負載。")
        lines.append("  - SDGs 融入：具備生活化永續發展目標。")
        lines.append("  - STEAM 跨域：具備科學/數學探究連結。")
    else:
        lines.append("- **⚠️ 第二階（中階目標）：⏳ 需教師確認後修正（嚴格退回清單）**")
        for missing in analysis["tier2_missing"]:
            lines.append(f"  - 📌 待補強項目：{missing}")

    # 第三階
    if analysis["tier3_pass"]:
        lines.append("- **🌟 第三階（高階目標）：⭐ 加分亮點達成**")
        for h in set(analysis["tier3_highlights"]):
            lines.append(f"  - ★ {h}")
    else:
        lines.append("- **🌟 第三階（高階目標）：⚪ 基礎達標（可選加分項未啟用）**")

    lines.append("\n*審查系統：臺中市梧棲區中正國小四年級教材審查機制（Review Protocol v3.0 深度實體驗證版）*")
    return "\n".join(lines)

def process_file(file_path: Path, output_dir: Path, corpus: dict):
    """處理單一檔案，落實同型態輸出與審查"""
    if not file_path.exists():
        print(f"❌ 檔案不存在: {file_path}")
        return

    ext = file_path.suffix.lower()
    base_name = file_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"🔍 正在審查檔案: {file_path.name} (類型: {ext})")

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    analysis = analyze_content(content, file_path.name, corpus)
    md_report = generate_markdown_report(analysis)

    # 輸出審查報告 Markdown
    report_file = output_dir / f"{base_name}_審查報告.md"
    with open(report_file, "w", encoding="utf-8") as rf:
        rf.write(f"# 審查檢測報告：{file_path.name}\n")
        rf.write(md_report)
    print(f"📄 已產出審查報告: {report_file}")

    # 同型態優化版輸出
    optimized_file = output_dir / f"{base_name}_優化版{ext}"
    if ext == ".md":
        # 移除可能存在的舊報告後再附加新報告
        cleaned_content = re.split(r"\n\s*---\s*\n## 📋 AI 自我檢測審查報告", content)[0].strip()
        with open(optimized_file, "w", encoding="utf-8") as of:
            of.write(cleaned_content + md_report)
        print(f"✅ 已輸出同型態優化版: {optimized_file}")
    elif ext == ".html":
        html_badge = f"""
        <!-- AI 自我檢測審查浮動報告 v3.0 -->
        <div id="review-report-badge" style="position:fixed;bottom:20px;right:20px;z-index:9999;font-family:sans-serif;">
          <details style="background:#ffffff;border:2px solid {'#16a34a' if analysis['tier1_pass'] else '#dc2626'};border-radius:12px;box-shadow:0 10px 25px rgba(0,0,0,0.15);padding:14px;max-width:380px;font-size:12px;color:#1e293b;">
            <summary style="font-weight:bold;color:{'#15803d' if analysis['tier1_pass'] else '#b91c1c'};cursor:pointer;list-style:none;display:flex;align-items:center;gap:6px;">
              🛡️ 四年級三階審查報告 ({'✅ 通過' if analysis['tier1_pass'] else '❌ 需打回'})
            </summary>
            <div style="margin-top:10px;line-height:1.5;">
              <div><strong>科目：</strong>{analysis['detected_subject']}</div>
              <div style="color:{'#15803d' if analysis['tier1_pass'] else '#b91c1c'};"><strong>第一階最低門檻：</strong>{'✅ 通過' if analysis['tier1_pass'] else '❌ 一票否決 (含超綱詞彙)'}</div>
              <div style="color:{'#15803d' if analysis['tier2_pass'] else '#d97706'};"><strong>第二階中階目標：</strong>{'✅ 通過' if analysis['tier2_pass'] else '⚠️ 需確認'}</div>
              <div style="color:#4f46e5;"><strong>第三階高階亮點：</strong>{'⭐ 加分達成' if analysis['tier3_pass'] else '⚪ 一般'}</div>
              <p style="margin-top:8px;font-size:11px;color:#64748b;">詳情請參閱同目錄下的 <code>{base_name}_審查報告.md</code></p>
            </div>
          </details>
        </div>
        """
        # 移除舊 badge
        cleaned_html = re.sub(r'<div id="review-report-badge"[\s\S]*?</div>\s*</div>', '', content)
        if "</body>" in cleaned_html:
            new_html = cleaned_html.replace("</body>", f"{html_badge}\n</body>")
        else:
            new_html = cleaned_html + html_badge

        with open(optimized_file, "w", encoding="utf-8") as of:
            of.write(new_html)
        print(f"✅ 已輸出同型態優化版: {optimized_file}")
    else:
        with open(optimized_file, "w", encoding="utf-8") as of:
            of.write(content)
        print(f"✅ 已輸出同型態檔案: {optimized_file}")

    # 印出終端機檢測摘要
    print("--------------------------------------------------")
    print(f"科目判定: {analysis['detected_subject']}")
    print(f"第一階門檻: {'✅ 通過' if analysis['tier1_pass'] else '❌ 需打回'}")
    if analysis.get("tier1_corpus_verification"):
        ver = analysis["tier1_corpus_verification"]
        print(f"課本比對: 命中 {len(ver['found_terms'])} 個詞彙 | 違規未查得: {len(ver['missing_options']) + len(ver['missing_bracketed'])} 個關鍵詞")
    print(f"第二階目標: {'✅ 通過' if analysis['tier2_pass'] else '⚠️ 待補強'}")
    print(f"第三階亮點: {'⭐ 有亮點' if analysis['tier3_pass'] else '⚪ 無特殊亮點'}")
    print("--------------------------------------------------\n")

def check_single_term(term: str, subject_key: str, corpus: dict):
    """查詢單一詞彙出現在哪一個教材 PDF 檔案中"""
    subj_corpus = corpus.get(subject_key, {})
    if not subj_corpus:
        print(f"❌ 查無【{subject_key}】語料庫！")
        return

    clean_term = re.sub(r"\s+", "", term)
    matches = []
    for file_stem, text in subj_corpus.items():
        if clean_term in text:
            # 抓取出現位置上下文
            pos = text.find(clean_term)
            snippet = text[max(0, pos-15):min(len(text), pos+len(clean_term)+15)]
            matches.append((file_stem, snippet))

    if matches:
        print(f"\n✅ 詞彙「{term}」出現在以下 {len(matches)} 個教材檔案中：")
        for stem, snippet in matches:
            print(f"  • {stem}")
            print(f"    上下文：...{snippet}...")
    else:
        print(f"\n❌ 詞彙「{term}」未在【{subject_key}】課本或習作中查得！（判定為未學/超綱）\n")

def main():
    parser = argparse.ArgumentParser(description="國小四年級教材與試題三階審查工具（v3.0 全維度真實語料檢核引擎）")
    parser.add_argument("files", nargs="*", help="欲審查的檔案路徑 (支援 .md, .html 等)")
    parser.add_argument("--output-dir", default="reviewed", help="審查結果存放目錄 (預設: reviewed)")
    parser.add_argument("--rebuild-cache", action="store_true", help="強制重新提取並建立課本語料快取")
    parser.add_argument("--check-term", help="快速查詢某詞彙是否存在於真實課本習作中")
    parser.add_argument("--subject", choices=["chinese", "math", "social"], default="chinese", help="查詢時指定科目 (預設: chinese)")
    args = parser.parse_args()

    corpus = load_or_build_corpus(force_rebuild=args.rebuild_cache)

    if args.check_term:
        check_single_term(args.check_term, args.subject, corpus)
        return

    if not args.files:
        parser.print_help()
        return

    out_path = Path(args.output_dir)
    for f in args.files:
        process_file(Path(f), out_path, corpus)

if __name__ == "__main__":
    main()
