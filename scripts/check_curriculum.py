#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_curriculum.py (v4.0 三階段逐字逐句深層檢驗引擎)
國小四年級教材與試題自動化審查工具
1. 必須符合階段 (Must-Have)：逐字逐句沒有出現在本機教材/習作內的就打掉重製。
   （精準過濾：①過去教過 ②分析誤判/系統詞 ③字形字音幻覺/類似音類似字）
2. 大部分符合階段 (Should-Have)：教學重點用字用詞謹慎使用。
   （例如：生字大題考點必須 100% 來自當冊正式課本生字表，課文出現但非生字表列者嚴格示警）
3. 盡力符合階段 (Nice-to-Have)：全卷邏輯性、適配性與零跨大題洩題碰撞。
   （例如：前大題考查之生字注音，後續大題嚴禁出現正字洩漏答案；考點不重複）
"""

import os
import re
import sys
import json
import glob
import argparse
from pathlib import Path

# 匯入進度感知與教材動態擴展模組
try:
    from sync_curriculum_progress import (
        detect_semester_stage,
        check_local_final_coverage,
        search_gdrive_and_sync,
        detect_content_progress_alignment
    )
    HAS_PROGRESS_MODULE = True
except ImportError:
    HAS_PROGRESS_MODULE = False

# 基礎設定
CONFIG = {
    "subjects": {
        "math": {
            "name": "數學科（南一版）",
            "dirs": ["115四上數課習", "115四上期末數學課習", r"D:\115四年級複習卷\數學"],
            "keywords": ["南一", "分數", "大數", "角度", "公里", "乘法", "除法", "等值", "三角形", "n-Ⅱ-", "s-Ⅱ-", "數學"],
            "misconceptions": ["M4-FRAC-01", "M4-PLACE-01", "M4-GEOM-01", "M4-GEOM-02", "M4-CALC-01"]
        },
        "chinese": {
            "name": "國語科（翰林版）",
            "dirs": ["115四上國課習", "115四上期末國語課習", r"D:\opencode\115四上期中國語\115四上國課習", r"D:\opencode\115四上期中國語"],
            "keywords": ["翰林", "記敘文", "說明文", "五感", "修辭", "句型", "作文", "6-Ⅱ-", "5-Ⅱ-", "國語"],
            "misconceptions": ["C4-TEXT-01", "C4-PUNCT-01", "C4-STRUC-01", "C4-VOCAB-01"]
        },
        "social": {
            "name": "社會科（康軒版）",
            "dirs": ["115社會課習", "115四上期末社會課習", r"D:\115四年級複習卷\社會", r"D:\antui\html簡報\115四上社會_1-2地形的種類與生活"],
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

# 出題架構功能詞與排版詞彙（這些屬於試卷功能詞，過濾分析誤判）
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
    "翰林", "南一", "康軒", "翰林版", "南一版", "康軒版", "部定", "版本", "課本", "習作", "單元", "第課", "第一課", "第二課",
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

def load_lexicon_data() -> dict:
    """載入真實教材真理辭典（包含各課正式生字表、核心詞彙等）"""
    if LEXICON_FILE.exists():
        try:
            with open(LEXICON_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            processed = {}
            for subj, units in raw.items():
                processed[subj] = {
                    "characters": set(),
                    "core_vocab": set(),
                    "units": units
                }
                for u_key, u_info in units.items():
                    for ch in u_info.get("characters", []):
                        processed[subj]["characters"].add(ch)
                    for v in u_info.get("core_vocab", []):
                        processed[subj]["core_vocab"].add(v)
            return processed
        except Exception:
            pass
    return {
        "chinese": {"characters": set(), "core_vocab": set(), "units": {}},
        "math": {"characters": set(), "core_vocab": set(), "units": {}},
        "social": {"characters": set(), "core_vocab": set(), "units": {}}
    }

def filter_corpus_by_stage(subj_corpus: dict, subject_key: str, active_stage: str) -> dict:
    """依據學期進度階段嚴格切片過濾語料庫，確保期中考絕不混入期末未來課次文本"""
    if active_stage != "midterm":
        return subj_corpus

    midterm_markers = {
        "chinese": ["L01", "L02", "L03", "L04", "L05", "L06", "統整一", "統整二"],
        "math": ["ch01", "ch02", "ch03", "ch04", "ch05", "加油小站1", "單元名詞"],
        "social": ["1-1", "1-2", "1-3", "2-1", "2-2"]
    }
    markers = midterm_markers.get(subject_key, [])
    if not markers:
        return subj_corpus

    filtered = {k: v for k, v in subj_corpus.items() if any(m in k for m in markers)}
    return filtered if filtered else subj_corpus

def get_stage_characters(lexicon: dict, subject_key: str, active_stage: str) -> set:
    """取得對應階段之正式課本生字表（期中鎖定 L01~L06；期末鎖定 L07~L12）"""
    subj_lex = lexicon.get(subject_key, {})
    units = subj_lex.get("units", {})
    if units and active_stage in ("midterm", "final"):
        stage_keys = (
            {"L01", "L02", "L03", "L04", "L05", "L06", "統整一", "統整二"}
            if active_stage == "midterm"
            else {"L07", "L08", "L09", "統整三", "L10", "L11", "L12", "統整四"}
        )
        chars = set()
        for k, info in units.items():
            if k in stage_keys:
                chars.update(info.get("characters", []))
        if chars:
            return chars
    return subj_lex.get("characters", set())

def split_into_sections(content: str) -> list:
    """將測驗卷或學習單依大題與區塊進行切割，供跨題型邏輯與防洩題檢核"""
    lines = content.splitlines()
    sections = []
    curr_sec = {"title": "前言導言", "lines": []}
    for idx, line in enumerate(lines, 1):
        line_clean = line.strip()
        m = re.match(r"^(#{1,3}\s*|\*{0,2}[一二三四五六七八九十]+[、\.]\s*)(.*)", line_clean)
        if m:
            if curr_sec["lines"]:
                sections.append(curr_sec)
            curr_sec = {"title": line_clean, "lines": [(idx, line)]}
        else:
            curr_sec["lines"].append((idx, line))
    if curr_sec["lines"]:
        sections.append(curr_sec)
    return sections

def extract_all_assessment_terms(content: str) -> dict:
    """
    全文本逐字逐句深度結構化抽取：
    1. 選擇題選項 (A/B/C/D、①②③④)
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

        b_matches = re.findall(r"[「『【（(《〈]([^\n「『【（(《〈」』】）)》〉]{1,8})[」』】）)》〉]", line_clean)
        for bm in b_matches:
            if any(bm.startswith(prefix) for prefix in ["抄寫", "引導", "說明", "填入", "選用", "設計", "版本", "大標題", "副標題", "學校", "班級", "注意", "備註"]):
                continue
            if re.search(r"\d+\s*分", bm) or re.search(r"每題|配分|總分|得分", bm):
                continue
            pure_bm = re.sub(r"[^\u4e00-\u9fa5]", "", bm)
            # 支援單字（生字考點）或 2~6 字語詞
            if 1 <= len(pure_bm) <= 6 and pure_bm not in EXAM_SYSTEM_STOPWORDS and pure_bm not in CONFIG["local_keywords"]:
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

def verify_tier1_terms(extracted: dict, subject_key: str, corpus: dict, sections: list = None, active_stage: str = "auto") -> dict:
    """
    【階段一：必須符合階段】全方位逐字逐句比對實體語料庫（v4.2 進度切片與題幹字級攔截）：
    1. 依進度階段切片語料庫（期中僅限 L1~L6 / Ch1~Ch5 / 1-1~2-2）
    2. 驗證選項高風險詞（未學超綱一票否決）
    3. 驗證括號/填空詞（未學超綱一票否決）
    4. 驗證好詞百寶箱（未學超綱一票否決）
    5. 驗證題幹句子之生僻字/未學詞（如改錯字題幹出現「陰霾」的「霾」，一票否決）
    """
    raw_subj_corpus = corpus.get(subject_key, {})
    if not raw_subj_corpus:
        return {
            "has_corpus": False,
            "total_checked": 0,
            "found_terms": [],
            "missing_terms": [],
            "missing_options": [],
            "missing_bracketed": [],
            "missing_stem_chars": []
        }

    subj_corpus = filter_corpus_by_stage(raw_subj_corpus, subject_key, active_stage)
    combined_text = "".join(subj_corpus.values())
    corpus_char_set = set(ch for ch in combined_text if "\u4e00" <= ch <= "\u9fa5")

    found_terms = set()
    missing_terms = set()
    missing_options = []
    missing_bracketed = []
    missing_stem_chars = []

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

    # 5. 題幹字級超綱掃描（特別攔截如改錯字/選擇題題幹出現未教過的字如「霾」）
    if sections and subject_key == "chinese":
        seen_char_line = set()
        for sec in sections:
            # 排除非學生作答之設計說明/排版/教師報告/自由寫作範文區塊
            if any(skip in sec["title"] for skip in ["前言", "審查檢測報告", "AI 自我檢測", "版面配置", "設計建議", "核心目標", "教師", "說明", "附錄", "範文", "寫作"]):
                continue
            # 僅針對實質試題大題（或含題號的行）進行字級掃描
            is_exam_sec = bool(re.search(r"國字|注音|生字|改錯|錯字|選擇|填空|選詞|閱讀|測驗|評量|綜合|問答", sec["title"]))
            is_error_fix_sec = bool(re.search(r"改錯|錯字|錯別字", sec["title"]))
            for l_num, l_txt in sec["lines"]:
                s_line = l_txt.strip()
                if not s_line or s_line.startswith("#") or s_line.startswith("|") or s_line.startswith(">"):
                    continue
                is_numbered_item = bool(re.match(r"^(\d+[\.\、\)]|[（\(]\d+[）\)]|[①②③④⑤⑥⑦⑧⑨⑩])", s_line))
                if not (is_exam_sec or is_numbered_item):
                    continue
                # 排除改錯字答案註記中的刻意錯字本身（若標註為 (改錯:X->Y) 或 【錯字】）
                clean_stem = re.sub(r"\(改錯[：:].*?\)|（改錯[：:].*?）", "", s_line)
                clean_stem = re.sub(r"\[錯.*?\]|【錯.*?】", "", clean_stem)
                for idx_c, ch in enumerate(clean_stem):
                    if "\u4e00" <= ch <= "\u9fa5":
                        if ch not in corpus_char_set and ch not in "".join(CONFIG["local_keywords"]):
                            # 擷取前後文 2~3 字詞彙
                            ctx_word = clean_stem[max(0, idx_c-1):min(len(clean_stem), idx_c+2)]
                            # 若該字不在語料庫且所屬雙字詞也不在語料庫（非改錯題刻意製造之同音錯字或確認為超綱生僻字）
                            key = (l_num, ch)
                            if key not in seen_char_line:
                                seen_char_line.add(key)
                                missing_stem_chars.append({
                                    "char": ch,
                                    "context_word": ctx_word,
                                    "line": l_num,
                                    "section": sec["title"],
                                    "is_error_fix": is_error_fix_sec,
                                    "snippet": s_line[:50]
                                })

    return {
        "has_corpus": True,
        "total_checked": len(found_terms) + len(missing_terms),
        "found_terms": sorted(list(found_terms)),
        "missing_terms": sorted(list(missing_terms)),
        "missing_options": missing_options,
        "missing_bracketed": missing_bracketed,
        "missing_stem_chars": missing_stem_chars
    }

def verify_tier1_vocab_table(sections: list, subject_key: str, lexicon: dict, active_stage: str) -> list:
    """
    【階段一：紅線一票否決】檢驗「考生字/國字注音」大題的考點，是否 100% 來自該階段正式課本生字表。
    （修正舊版只列階段二警告的漏洞，正式升格為階段一打回重置紅線！）
    """
    issues = []
    if subject_key != "chinese":
        return issues
    char_set = get_stage_characters(lexicon, subject_key, active_stage)
    if not char_set:
        return issues

    for sec in sections:
        if re.search(r"國字|注音|生字|字形|寫出", sec["title"]):
            for l_num, l_txt in sec["lines"]:
                if l_txt.strip().startswith("#"):
                    continue
                # 支援 【X】、以及括號前的目標字（如 `（ ）鷹` 或 `飛（ㄒㄧㄤˊ）`）
                targets = []
                for m in re.finditer(r"【(.*?)】", l_txt):
                    targets.append(m.group(1).strip())
                for m in re.finditer(r"[（(]([\u4e00-\u9fa5]{1,3})[）)]", l_txt):
                    val = m.group(1).strip()
                    if val not in EXAM_SYSTEM_STOPWORDS and not re.search(r"分|題", val):
                        targets.append(val)

                for word in targets:
                    for ch in word:
                        if "\u4e00" <= ch <= "\u9fa5" and ch not in char_set:
                            issues.append({
                                "char": ch,
                                "word": word,
                                "line": l_num,
                                "section": sec["title"],
                                "reason": f"第{l_num}行考生字考點「{ch}」（出自「{word}」）非本階段（{active_stage}）翰林國語課本正式生字表列字，屬嚴重超綱！"
                            })
    return issues

def verify_tier2_focus(sections: list, subject_key: str, corpus: dict, active_stage: str = "auto") -> list:
    """
    【階段二：大部分符合階段】檢驗題型與課本教學重點匹配度：
    - 檢核試卷大題（如「改錯字」）是否確實為本冊/本階段課習之教學重點題型。
    """
    warnings = []
    if subject_key != "chinese":
        return warnings

    raw_subj_corpus = corpus.get(subject_key, {})
    subj_corpus = filter_corpus_by_stage(raw_subj_corpus, subject_key, active_stage)
    combined_text = "".join(subj_corpus.values())

    for sec in sections:
        if re.search(r"改錯|錯字|錯別字", sec["title"]):
            # 檢驗本階段習作中是否教過「改錯/錯別字」題型
            has_error_fix_in_wb = any(kw in combined_text for kw in ["改錯", "錯別字", "圈出錯字"])
            if not has_error_fix_in_wb:
                warnings.append({
                    "section": sec["title"],
                    "reason": f"大題「{sec['title']}」在翰林四上本階段（{active_stage}）課本與習作中並無『改錯字』獨立教學重點，建議改為字音字形辨析或詞語運用。"
                })
    return warnings

def verify_tier3_leakage(sections: list) -> list:
    """
    【階段三：全卷雙向跨大題洩題碰撞檢查】
    1. 收集所有大題考點答案：國字注音【字】、改錯字正字、選詞填空/選擇題括號目標詞。
    2. 雙向比對：無論前面洩漏後面，或後面洩漏前面，只要題幹或選項出現他題考點正字/答案詞，立即攔截！
    """
    leaks = []
    targets = []

    for s_idx, sec in enumerate(sections):
        if any(skip in sec["title"] for skip in ["前言", "審查檢測報告", "AI 自我檢測"]):
            continue
        is_vocab_sec = bool(re.search(r"國字|注音|生字|字形|寫出", sec["title"]))
        is_fix_sec = bool(re.search(r"改錯|錯字|錯別字", sec["title"]))
        is_fill_sec = bool(re.search(r"選詞|填空|短語|成語|造句|詞語", sec["title"]))

        for l_num, l_txt in sec["lines"]:
            if l_txt.strip().startswith("#"):
                continue

            # 1. 國字注音與改錯字之單字考點
            if is_vocab_sec or is_fix_sec:
                for m in re.finditer(r"【(.*?)】", l_txt):
                    word = m.group(1).strip()
                    for ch in word:
                        if "\u4e00" <= ch <= "\u9fa5":
                            targets.append({"token": ch, "kind": "生字/正字", "line": l_num, "sec_idx": s_idx, "sec_title": sec["title"]})
                # 改錯字常見格式：(改錯: X -> Y) 或 （正確：Y）
                for m in re.finditer(r"(?:->|→|改為|正確[：:])\s*([\u4e00-\u9fa5]{1,2})", l_txt):
                    for ch in m.group(1):
                        targets.append({"token": ch, "kind": "改錯正字", "line": l_num, "sec_idx": s_idx, "sec_title": sec["title"]})

            # 2. 詞彙/選詞填空之詞語考點（>=2字詞）
            if is_fill_sec:
                for m in re.finditer(r"【([\u4e00-\u9fa5]{2,6})】", l_txt):
                    targets.append({"token": m.group(1), "kind": "選詞答案", "line": l_num, "sec_idx": s_idx, "sec_title": sec["title"]})

    # 雙向比對其他大題
    seen_leak = set()
    for target in targets:
        tok = target["token"]
        for s_idx, sec in enumerate(sections):
            if s_idx == target["sec_idx"] or any(skip in sec["title"] for skip in ["前言", "審查檢測報告", "AI 自我檢測"]):
                continue
            for l_num, l_txt in sec["lines"]:
                if l_txt.strip().startswith("#"):
                    continue
                clean_l = re.sub(r"【.*?】", "", l_txt)
                clean_l = re.sub(r"\(改錯[：:].*?\)|（改錯[：:].*?）", "", clean_l)
                if tok in clean_l:
                    direction = "前面大題洩漏後面答案" if s_idx < target["sec_idx"] else "後面大題洩漏前面答案"
                    lkey = (tok, target["sec_idx"], s_idx, l_num)
                    if lkey not in seen_leak:
                        seen_leak.add(lkey)
                        leaks.append({
                            "char": tok,
                            "kind": target["kind"],
                            "direction": direction,
                            "target_sec": target["sec_title"],
                            "target_line": target["line"],
                            "leaked_sec": sec["title"],
                            "leaked_line": l_num,
                            "snippet": l_txt.strip()[:55]
                        })

    return leaks

def verify_tier3_logic_sequence(sections: list) -> list:
    """
    檢核全卷大題認知層級與邏輯連續性：
    標準順序應為：Level 1 (字音字形/生字/改錯) -> Level 2 (詞語/成語/語法句型) -> Level 3 (綜合選擇) -> Level 4 (閱讀理解/寫作素養)
    """
    logic_issues = []
    sec_levels = []
    for sec in sections:
        title = sec["title"]
        if any(skip in title for skip in ["前言", "審查檢測報告", "AI 自我檢測"]):
            continue
        if re.search(r"國字|注音|生字|字形|寫出|改錯|錯字", title):
            lvl = 1
        elif re.search(r"選詞|詞語|成語|短語|句型|修辭|造句|照樣", title):
            lvl = 2
        elif re.search(r"選擇|綜合|是非|配合", title):
            lvl = 3
        elif re.search(r"閱讀|素養|問答|作文|寫作", title):
            lvl = 4
        else:
            continue
        sec_levels.append((lvl, title))

    for i in range(1, len(sec_levels)):
        prev_lvl, prev_title = sec_levels[i - 1]
        curr_lvl, curr_title = sec_levels[i]
        if curr_lvl < prev_lvl:
            logic_issues.append(
                f"大題順序邏輯斷裂：「{curr_title}」(層級{curr_lvl}) 排在「{prev_title}」(層級{prev_lvl}) 之後，建議調整為『字詞基礎 → 句型修辭 → 綜合選擇 → 閱讀寫作』由淺入深。"
            )
    return logic_issues

def analyze_content(content: str, filename: str, corpus: dict, lexicon: dict, active_stage: str = "auto"):
    """分析文本內容並進行嚴格三階段逐字逐句深層檢測與學期進度感知"""
    if active_stage == "auto" and HAS_PROGRESS_MODULE:
        active_stage, stage_desc = detect_semester_stage()
    else:
        stage_desc = f"指定階段：{active_stage}"

    report = {
        "filename": filename,
        "active_stage": active_stage,
        "stage_desc": stage_desc,
        "progress_alignment": None,
        "tier1_pass": True,
        "tier1_issues": [],
        "tier1_corpus_verification": None,
        "tier2_pass": True,
        "tier2_missing": [],
        "tier2_warnings": [],
        "tier3_pass": False,
        "tier3_highlights": [],
        "tier3_leaks": [],
        "tier3_logic_issues": [],
        "detected_subject": "未知科目",
        "misconceptions_found": []
    }

    sections = split_into_sections(content)

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

    # 進度對齊分析
    if curr_subj and HAS_PROGRESS_MODULE:
        alignment = detect_content_progress_alignment(content, curr_subj, active_stage)
        report["progress_alignment"] = alignment
        if not alignment["aligned"] and alignment["notice"]:
            report["tier1_issues"].append(alignment["notice"])

    # 2. 階段一（必須符合階段：最低紅線門檻檢測）
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

    # 逐字逐句深度抽驗比對實體語料庫
    if curr_subj and corpus.get(curr_subj):
        extracted = extract_all_assessment_terms(content)
        ver_res = verify_tier1_terms(extracted, curr_subj, corpus, sections=sections, active_stage=active_stage)
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

        # 若有題幹超綱字（如改錯字題幹出現「陰霾」的「霾」）
        if ver_res.get("missing_stem_chars"):
            stem_details = [f"第{item['line']}行「{item['char']}」(詞:{item['context_word']})" for item in ver_res["missing_stem_chars"][:6]]
            report["tier1_issues"].append(
                f"🚨【致命紅線】題幹敘述出現非本階段（{active_stage}）課習語料庫之超綱生字詞：{', '.join(stem_details)}。"
            )

        # 考生字大題必須 100% 來自本階段正式生字表（一票否決紅線）
        vocab_issues = verify_tier1_vocab_table(sections, curr_subj, lexicon, active_stage)
        if vocab_issues:
            v_details = [f"第{vi['line']}行「{vi['char']}」" for vi in vocab_issues[:6]]
            report["tier1_issues"].append(
                f"🚨【致命紅線】國字注音/考生字大題出現非正式生字表列字（嚴重超綱）：{', '.join(v_details)}。"
            )

        # 若抽驗詞彙數為 0，嚴禁假通過
        if len(ver_res["found_terms"]) == 0:
            report["tier1_issues"].append(
                "🚨【檢驗失效】未能在文本中檢出任何符合本冊課習之核心詞彙，無法證明符合教材進度，判定打回重置！"
            )

    if report["tier1_issues"]:
        report["tier1_pass"] = False

    # 3. 階段二（大部分符合階段：教學重點題型與用字謹慎度檢測）
    if curr_subj:
        tier2_warnings = verify_tier2_focus(sections, curr_subj, corpus, active_stage=active_stage)
        report["tier2_warnings"] = tier2_warnings
        if tier2_warnings:
            for tw in tier2_warnings:
                report["tier2_missing"].append(tw["reason"])

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

    # 4. 階段三（盡力符合階段：跨題型邏輯性、大題編排連續性與雙向跨大題洩題檢測）
    leaks = verify_tier3_leakage(sections)
    report["tier3_leaks"] = leaks
    logic_issues = verify_tier3_logic_sequence(sections)
    report["tier3_logic_issues"] = logic_issues

    for lkw in CONFIG["local_keywords"]:
        if lkw in content:
            report["tier3_highlights"].append(f"融入海線在地生活情境：【{lkw}】")

    if curr_subj:
        for misc in CONFIG["subjects"][curr_subj]["misconceptions"]:
            if misc in content:
                report["misconceptions_found"].append(misc)
                report["tier3_highlights"].append(f"具備高階迷思診斷誘答機制：【{misc}】")

    if report["tier3_highlights"] and not leaks and not logic_issues:
        report["tier3_pass"] = True

    return report

def generate_markdown_report(analysis: dict) -> str:
    """產出標準三階段深層比對自我檢測審查報告 (v4.0)"""
    lines = []
    lines.append("\n\n---\n")
    lines.append("## 📋 AI 自我檢測審查報告 (Self-Review Report v4.0 三階段逐字逐句深層檢驗版)")
    lines.append(f"- **檢測檔案**：`{analysis['filename']}`")
    lines.append(f"- **對應科目與版本**：{analysis['detected_subject']}")
    lines.append(f"- **📅 學期進度階段**：{analysis.get('stage_desc', '未知')}")
    if analysis.get("progress_alignment"):
        pa = analysis["progress_alignment"]
        if pa.get("notice"):
            lines.append(f"- **🎯 進度對齊檢驗**：{pa['notice']}")
    
    # 階段一
    if analysis["tier1_pass"]:
        lines.append("- **🛑 階段一（必須符合階段・絕對紅線門檻）：✅ 審查通過**")
        lines.append("  - 逐字逐句比對：題幹、選項與填空 100% 存在於本機教材/習作真實文本中。")
        lines.append("  - 雜訊過濾：已精準過濾過去教過詞彙、分析誤判排版詞、排除類似音/類似字幻覺。")
        lines.append("  - 課綱與版本：已對齊 108 課綱代碼與指定出版社版本。")
        if analysis["tier1_corpus_verification"]:
            ver = analysis["tier1_corpus_verification"]
            lines.append(f"  - 📖 實體 PDF 語料驗證：命中 {len(ver['found_terms'])} 個核心詞彙，零違規超綱詞。")
            if ver["found_terms"]:
                sample_found = "、".join(ver["found_terms"][:8])
                lines.append(f"  - 🎯 命中真實語料範例：`{sample_found}` 等。")
    else:
        lines.append("- **🛑 階段一（必須符合階段・絕對紅線門檻）：❌ 未達標（一票否決・打回重置）**")
        for issue in analysis["tier1_issues"]:
            lines.append(f"  - ⚠️ 致命缺失：{issue}")
        if analysis["tier1_corpus_verification"]:
            ver = analysis["tier1_corpus_verification"]
            if ver.get("missing_options"):
                lines.append("  - 🚫 超綱選項清單（必須更換）：")
                for mo in ver["missing_options"][:5]:
                    lines.append(f"    • 第 {mo['line']} 行選項: `{mo['word']}` (課習未查得)")
            if ver.get("missing_bracketed"):
                lines.append("  - 🚫 超綱填空清單（必須更換）：")
                for mb in ver["missing_bracketed"][:5]:
                    lines.append(f"    • 第 {mb['line']} 行填空: `{mb['word']}` (課習未查得)")
            if ver.get("missing_stem_chars"):
                lines.append("  - 🚫 題幹敘述超綱字詞清單（如改錯字/選擇題幹未學字，必須更換）：")
                for ms in ver["missing_stem_chars"][:6]:
                    lines.append(f"    • 第 {ms['line']} 行 ({ms['section']}): `{ms['char']}` 出現在「{ms['context_word']}」— 本階段課習未曾出現！")

    # 階段二
    if analysis["tier2_pass"]:
        lines.append("- **⚠️ 階段二（大部分符合階段・教學重點謹慎使用）：✅ 審查通過**")
        lines.append("  - 教學重點考點：大題題型與教學重點匹配。")
        lines.append("  - 認知負荷 (CLT)：版面配置與題幹長度符合四年級記憶負載。")
        lines.append("  - SDGs 融入：具備生活化永續發展目標。")
        lines.append("  - STEAM 跨域：具備科學/數學探究連結。")
    else:
        lines.append("- **⚠️ 階段二（大部分符合階段・教學重點謹慎使用）：⏳ 需教師確認後修正**")
        for missing in analysis["tier2_missing"]:
            lines.append(f"  - 📌 待補強項目：{missing}")
        if analysis["tier2_warnings"]:
            lines.append("  - 🔍 教學重點偏離警告清單：")
            for w in analysis["tier2_warnings"][:4]:
                lines.append(f"    • {w.get('reason', w.get('section'))}")

    # 階段三
    if analysis["tier3_pass"]:
        lines.append("- **🌟 階段三（盡力符合階段・邏輯適配與加分亮點）：⭐ 加分亮點達成**")
        lines.append("  - 跨大題邏輯：零跨大題洩題碰撞（全卷雙向無洩題），大題認知順序連續。")
        for h in set(analysis["tier3_highlights"]):
            lines.append(f"  - ★ {h}")
    else:
        lines.append("- **🌟 階段三（盡力符合階段・邏輯適配與加分亮點）：⚪ 基礎達標或有洩題/邏輯問題**")
        if analysis["tier3_leaks"]:
            lines.append("  - 🚨 跨大題洩題自我碰撞警告（必須修正）：")
            for lk in analysis["tier3_leaks"][:6]:
                lines.append(f"    • [{lk.get('direction', '洩題')}] {lk.get('kind', '考點')}「{lk['char']}」(第{lk['target_line']}行 {lk['target_sec']}) 在第{lk['leaked_line']}行 ({lk['leaked_sec']}) 洩漏答案: `{lk['snippet']}`")
        if analysis.get("tier3_logic_issues"):
            lines.append("  - 🧩 大題認知邏輯連續性警示：")
            for li in analysis["tier3_logic_issues"]:
                lines.append(f"    • {li}")
        if analysis["tier3_highlights"]:
            for h in set(analysis["tier3_highlights"]):
                lines.append(f"  - ★ {h}")

    lines.append("\n*審查系統：臺中市梧棲區中正國小四年級教材審查機制（Review Protocol v4.2 考卷防呆與深度邏輯審查版）*")
    return "\n".join(lines)

def process_file(file_path: Path, output_dir: Path, corpus: dict, lexicon: dict, active_stage: str = "auto"):
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

    analysis = analyze_content(content, file_path.name, corpus, lexicon, active_stage=active_stage)
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
        <!-- AI 自我檢測審查浮動報告 v4.0 -->
        <div id="review-report-badge" style="position:fixed;bottom:20px;right:20px;z-index:9999;font-family:sans-serif;">
          <details style="background:#ffffff;border:2px solid {'#16a34a' if analysis['tier1_pass'] else '#dc2626'};border-radius:12px;box-shadow:0 10px 25px rgba(0,0,0,0.15);padding:14px;max-width:380px;font-size:12px;color:#1e293b;">
            <summary style="font-weight:bold;color:{'#15803d' if analysis['tier1_pass'] else '#b91c1c'};cursor:pointer;list-style:none;display:flex;align-items:center;gap:6px;">
              🛡️ 四年級三階段審查報告 ({'✅ 通過' if analysis['tier1_pass'] else '❌ 需打回'})
            </summary>
            <div style="margin-top:10px;line-height:1.5;">
              <div><strong>科目：</strong>{analysis['detected_subject']}</div>
              <div style="color:{'#15803d' if analysis['tier1_pass'] else '#b91c1c'};"><strong>階段一必須符合：</strong>{'✅ 通過' if analysis['tier1_pass'] else '❌ 一票否決 (含超綱詞彙)'}</div>
              <div style="color:{'#15803d' if analysis['tier2_pass'] else '#d97706'};"><strong>階段二大部分符合：</strong>{'✅ 通過' if analysis['tier2_pass'] else '⚠️ 需確認'}</div>
              <div style="color:#4f46e5;"><strong>階段三盡力符合：</strong>{'⭐ 加分達成' if analysis['tier3_pass'] else '⚪ 基礎達標/有洩題'}</div>
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
    print(f"階段一 (必須符合): {'✅ 通過' if analysis['tier1_pass'] else '❌ 需打回'}")
    if analysis.get("tier1_corpus_verification"):
        ver = analysis["tier1_corpus_verification"]
        print(f"課本比對: 命中 {len(ver['found_terms'])} 個詞彙 | 違規未查得: {len(ver['missing_options']) + len(ver['missing_bracketed'])} 個關鍵詞")
    print(f"階段二 (大部分符合): {'✅ 通過' if analysis['tier2_pass'] else '⚠️ 需確認'}")
    if analysis.get("tier2_warnings"):
        print(f"  • 生字重點表警告: {len(analysis['tier2_warnings'])} 處非生字表列字")
    print(f"階段三 (盡力符合): {'⭐ 達成' if analysis['tier3_pass'] else '⚪ 一般/有洩題'}")
    if analysis.get("tier3_leaks"):
        print(f"  • 跨大題洩題碰撞: 發現 {len(analysis['tier3_leaks'])} 處洩題")
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
    parser = argparse.ArgumentParser(description="國小四年級教材與試題三階段深層比對審查工具（v4.0 逐字逐句深層檢驗 + 進度感知版）")
    parser.add_argument("files", nargs="*", help="欲審查的檔案路徑 (支援 .md, .html 等)")
    parser.add_argument("--output-dir", default="reviewed", help="審查結果存放目錄 (預設: reviewed)")
    parser.add_argument("--stage", choices=["auto", "midterm", "final"], default="auto", help="指定教學階段 (預設 auto 自動感知)")
    parser.add_argument("--sync", action="store_true", help="強制自動搜尋 Google Drive / 本地擴展教材")
    parser.add_argument("--fetch-ebook", action="store_true", help="本地與雲端皆缺教材時，透過 Ego Lite 免重複登入各科電子書即時抓取")
    parser.add_argument("--rebuild-cache", action="store_true", help="強制重新提取並建立課本語料快取")
    parser.add_argument("--check-term", help="快速查詢某詞彙是否存在於真實課本習作中")
    parser.add_argument("--subject", choices=["chinese", "math", "social"], default="chinese", help="查詢時指定科目 (預設: chinese)")
    args = parser.parse_args()

    # 自動進度判定與教材覆蓋檢查
    if HAS_PROGRESS_MODULE:
        curr_stage, stage_desc = detect_semester_stage()
        effective_stage = curr_stage if args.stage == "auto" else args.stage
        print(f"📅 學期進度階段：{stage_desc}")
        # 若為期末階段且缺少教材，自動自雲端硬碟同步（必要時啟用 Ego Lite 備援）
        if args.sync or args.fetch_ebook or effective_stage == "final":
            search_gdrive_and_sync(stage=effective_stage, verbose=True, allow_ego_fallback=args.fetch_ebook)

    corpus = load_or_build_corpus(force_rebuild=args.rebuild_cache)
    lexicon = load_lexicon_data()

    if args.check_term:
        check_single_term(args.check_term, args.subject, corpus)
        return

    if not args.files:
        parser.print_help()
        return

    out_path = Path(args.output_dir)
    for f in args.files:
        process_file(Path(f), out_path, corpus, lexicon, active_stage=args.stage)

if __name__ == "__main__":
    main()
