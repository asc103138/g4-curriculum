#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_curriculum_progress.py
進度感知與教材動態擴展模組（Progress-Adaptive Curriculum Sync）
1. 依據學期行事曆或手動設定，自動判定期中/期末進度階段。
2. 自動偵測本地端缺漏之期末/期中教材，並深度搜尋 Google Drive 與本地目錄。
3. 自動解壓縮並整合課習 PDF 至專案目錄，無縫擴展語料庫。
"""

import os
import sys
import re
import json
import shutil
import zipfile
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 專案路徑設定
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
LOCAL_TEXTBOOK_DIRS = {
    "math": WORKSPACE_ROOT / "115四上數課習",
    "chinese": WORKSPACE_ROOT / "115四上國課習",
    "social": WORKSPACE_ROOT / "115社會課習"
}

# 雲端硬碟與本機優先精確路徑
KNOWN_STAGE_DIRS = {
    "chinese": {
        "final": [
            Path("/Users/tunyuan/Library/CloudStorage/GoogleDrive-asc103138@st.tc.edu.tw/我的雲端硬碟/115四上教材/115四上期末國語課習"),
            Path("/Users/tunyuan/Library/CloudStorage/GoogleDrive-asc103138@st.tc.edu.tw/我的雲端硬碟/115四上教材/115四上國課習"),
        ],
        "midterm": [
            Path("/Users/tunyuan/Library/CloudStorage/GoogleDrive-asc103138@st.tc.edu.tw/我的雲端硬碟/115四上教材/115四上國課習"),
            Path("/Users/tunyuan/Library/CloudStorage/GoogleDrive-asc103138@st.tc.edu.tw/我的雲端硬碟/115四上期中國語/01_教材原始資源")
        ]
    },
    "math": {
        "final": [
            Path("/Users/tunyuan/Library/CloudStorage/GoogleDrive-asc103138@st.tc.edu.tw/我的雲端硬碟/115四上教材/115四上期末數學課習"),
            Path("/Users/tunyuan/Library/CloudStorage/GoogleDrive-asc103138@st.tc.edu.tw/我的雲端硬碟/115四上教材/115四上數課習"),
        ],
        "midterm": [
            Path("/Users/tunyuan/Library/CloudStorage/GoogleDrive-asc103138@st.tc.edu.tw/我的雲端硬碟/115四上教材/115四上數課習"),
        ]
    },
    "social": {
        "final": [
            Path("/Users/tunyuan/Library/CloudStorage/GoogleDrive-asc103138@st.tc.edu.tw/我的雲端硬碟/115四上教材/115四上期末社會課習"),
            Path("/Users/tunyuan/Library/CloudStorage/GoogleDrive-asc103138@st.tc.edu.tw/我的雲端硬碟/115四上教材/115四上社會課習"),
        ],
        "midterm": [
            Path("/Users/tunyuan/Library/CloudStorage/GoogleDrive-asc103138@st.tc.edu.tw/我的雲端硬碟/115四上教材/115四上社會課習"),
        ]
    }
}

# 備用廣泛搜尋根目錄（限制淺層，排除 .Trash / .tmp）
GDRIVE_CANDIDATE_ROOTS = [
    Path("/Users/tunyuan/Library/CloudStorage/GoogleDrive-asc103138@st.tc.edu.tw/我的雲端硬碟/115四上教材"),
    Path.home() / "anti",
    Path.home() / "Downloads"
]

# 四上課程範圍進度對照表
CURRICULUM_STAGE_MAP = {
    "chinese": {
        "midterm": {
            "name": "期中範圍（L1 ~ L6）",
            "units": ["第一單元我愛家鄉", "第二單元天空的奇想"],
            "lessons": ["L01", "L02", "L03", "統整一", "L04", "L05", "L06", "統整二"],
            "lesson_names": ["美麗島", "請到我的家鄉來", "鏡頭下的家鄉", "飛行夢", "月光下", "又遠又近的月亮"]
        },
        "final": {
            "name": "期末範圍（L7 ~ L12）",
            "units": ["第三單元品德小故事", "第四單元海洋世界"],
            "lessons": ["L07", "L08", "L09", "統整三", "L10", "L11", "L12", "統整四"],
            "lesson_names": ["松鼠先生的麵包", "平凡的大俠", "王子折箭", "海中的熱帶雨林", "美食島", "寧靜的音樂會"]
        }
    },
    "math": {
        "midterm": {
            "name": "期中範圍（Ch1 ~ Ch5）",
            "chapters": ["ch01", "ch02", "ch03", "ch04", "ch05"],
            "chapter_names": ["一億以內的數", "乘法", "角度", "除法", "三角形", "加油小站1"]
        },
        "final": {
            "name": "期末範圍（Ch6 ~ Ch10）",
            "chapters": ["ch06", "ch07", "ch08", "ch09", "ch10"],
            "chapter_names": ["分數", "等值分數", "垂直與平行", "四邊形", "小數", "公里與公尺", "加油小站2"]
        }
    },
    "social": {
        "midterm": {
            "name": "期中範圍（第1 ~ 2單元）",
            "units": ["1-1", "1-2", "1-3", "2-1", "2-2"],
            "unit_names": ["家鄉在哪裡", "家鄉的地形", "氣候水資源與生活", "家鄉的傳統住屋", "生活器物與生活演變"]
        },
        "final": {
            "name": "期末範圍（第3 ~ 4/5單元）",
            "units": ["3-1", "3-2", "4-1", "4-2", "4-3"],
            "unit_names": ["家鄉的傳統信仰", "老街與生活", "早期居民的作息", "傳統節慶活動", "現代節日與生活"]
        }
    }
}

def detect_semester_stage(target_date: Optional[datetime.date] = None) -> Tuple[str, str]:
    """
    依據日期自動判定國小學期教學進度階段：
    上學期（秋季）：
      9月1日 ~ 11月10日前後 -> 期中階段 (midterm)
      11月11日 ~ 1月31日 -> 期末階段 (final)
    下學期（春季）：
      2月1日 ~ 4月20日前後 -> 期中階段 (midterm)
      4月21日 ~ 6月30日 -> 期末階段 (final)
    """
    if target_date is None:
        target_date = datetime.date.today()

    month = target_date.month
    day = target_date.day

    # 針對秋季學期（四上）
    if 9 <= month <= 11 and not (month == 11 and day > 10):
        return "midterm", f"期中評量階段（目前日期：{target_date}，教學進度聚焦於前半學期範圍）"
    else:
        return "final", f"期末評量階段（目前日期：{target_date}，期中考已結束，進入後半學期期末教學範圍）"

def check_local_final_coverage() -> Dict[str, Dict[str, bool]]:
    """檢查本機工作目錄是否具備期末教材課本與習作 PDF"""
    status = {
        "chinese": {"has_midterm": False, "has_final": False},
        "math": {"has_midterm": False, "has_final": False},
        "social": {"has_midterm": False, "has_final": False}
    }

    # 1. 國語
    ch_dir = LOCAL_TEXTBOOK_DIRS["chinese"]
    if ch_dir.exists():
        files = [p.name for p in ch_dir.rglob("*.pdf")]
        status["chinese"]["has_midterm"] = any("L01" in f or "L02" in f for f in files)
        status["chinese"]["has_final"] = any("L07" in f or "L10" in f or "L12" in f for f in files)

    # 2. 數學（需同時涵蓋 ch06~ch10 課本）
    ma_dir = LOCAL_TEXTBOOK_DIRS["math"]
    if ma_dir.exists():
        tb_files = [p.name for p in ma_dir.glob("課本PDF/*.pdf")] + [p.name for p in ma_dir.glob("*.pdf")]
        status["math"]["has_midterm"] = any("ch01" in f or "ch02" in f for f in tb_files)
        status["math"]["has_final"] = any("ch06" in f or "ch07" in f or "ch10" in f for f in tb_files)

    # 3. 社會
    so_dir = LOCAL_TEXTBOOK_DIRS["social"]
    if so_dir.exists():
        files = [p.name for p in so_dir.rglob("*.pdf")]
        status["social"]["has_midterm"] = any("1-1" in f or "2-1" in f for f in files)
        status["social"]["has_final"] = any("3-1" in f or "4-1" in f or "4-3" in f for f in files)

    return status

def search_gdrive_and_sync(stage: str = "final", verbose: bool = True, allow_ego_fallback: bool = False) -> Dict[str, List[str]]:
    """
    三層教材自動補齊漏斗：
    1. 檢查本地教材目錄覆蓋率
    2. 搜尋 Google Drive 與本機路徑自動解壓縮同步
    3. 若 allow_ego_fallback=True 且雲端亦缺漏，自動調用 Ego Lite 電子書平台免重複登入即時抓取
    """
    synced_items = {"chinese": [], "math": [], "social": []}
    coverage = check_local_final_coverage()

    if stage == "final":
        need_chinese = not coverage["chinese"]["has_final"]
        need_math = not coverage["math"]["has_final"]
        need_social = not coverage["social"]["has_final"]
    else:
        need_chinese = not coverage["chinese"]["has_midterm"]
        need_math = not coverage["math"]["has_midterm"]
        need_social = not coverage["social"]["has_midterm"]

    if not (need_chinese or need_math or need_social):
        if verbose:
            print(f"✅ 本地已具備完整【{stage}】教材，無需同步。")
        return synced_items

    if verbose:
        print(f"🔍 正在為【{stage}】階段快速比對 Google Drive 與本機教材路徑...")

    # 1. 優先精確路徑比對 (秒級直達)
    for subj in ["chinese", "math", "social"]:
        needed = (subj == "chinese" and need_chinese) or (subj == "math" and need_math) or (subj == "social" and need_social)
        if not needed:
            continue

        target_dest = LOCAL_TEXTBOOK_DIRS[subj]
        target_dest.mkdir(parents=True, exist_ok=True)
        known_dirs = KNOWN_STAGE_DIRS.get(subj, {}).get(stage, [])
        for kd in known_dirs:
            if not kd.exists():
                continue
            
            # 若為目錄，檢查裡面的 zip 與 pdf
            zips = list(kd.glob("*.zip"))
            for zp in zips:
                try:
                    with zipfile.ZipFile(zp, 'r') as zf:
                        for member in zf.namelist():
                            if member.endswith(".pdf") and not member.startswith("__MACOSX"):
                                zf.extract(member, target_dest)
                                synced_items[subj].append(Path(member).name)
                except Exception:
                    pass
            
            pdfs = list(kd.glob("*.pdf"))
            for pdf in pdfs:
                dest_file = target_dest / pdf.name
                if not dest_file.exists():
                    shutil.copy2(pdf, dest_file)
                    synced_items[subj].append(pdf.name)

            if synced_items[subj]:
                if subj == "chinese": need_chinese = False
                elif subj == "math": need_math = False
                elif subj == "social": need_social = False
                break

    if verbose:
        for subj, items in synced_items.items():
            if items:
                print(f"📦 【{subj}】成功由雲端同步 {len(items)} 個檔案！")
            else:
                still_missing = (subj == "chinese" and need_chinese) or (subj == "math" and need_math) or (subj == "social" and need_social)
                if still_missing:
                    if allow_ego_fallback:
                        print(f"🌐 【{subj}】本地與雲端皆缺【{stage}】教材，啟動第 3 層備援：Ego Lite 電子書自動登入抓取...")
                        try:
                            from ego_ebook_fetcher import load_ebook_config, check_or_fetch_subject
                            ego_cfg = load_ebook_config()
                            res = check_or_fetch_subject(subj, ego_cfg, stage=stage, check_only=False)
                            if res.get("status") == "DOWNLOADED":
                                synced_items[subj].extend([Path(d["file"]).name for d in res.get("downloaded", [])])
                        except Exception as e:
                            print(f"⚠️ 【{subj}】Ego Lite 電子書抓取失敗：{e}")
                    else:
                        print(f"⚠️ 【{subj}】未於雲端硬碟找到【{stage}】教材，可加上 `--fetch-ebook` 透過 Ego Lite 自動登入電子書抓取。")

    # 若有新同步檔案，清除語料快取以促使重新建構
    total_synced = sum(len(v) for v in synced_items.values())
    if total_synced > 0:
        cache_file = WORKSPACE_ROOT / ".cache/textbook_corpus.json"
        if cache_file.exists():
            cache_file.unlink()
            if verbose:
                print("🔄 已自動重置語料快取 (.cache/textbook_corpus.json)，下一次審查將納入新同步文本！")

    return synced_items

def detect_content_progress_alignment(content: str, subject_key: str, active_stage: str) -> Dict:
    """
    檢測當前被審查的教材內容，其單元主題是否符合目前學期進度階段 (期中 vs 期末)
    """
    stage_info = CURRICULUM_STAGE_MAP.get(subject_key, {})
    if not stage_info:
        return {"aligned": True, "detected_unit": None, "stage_detected": "unknown", "message": "無特定進度限制"}

    found_midterm_kws = []
    found_final_kws = []

    # 國語
    if subject_key == "chinese":
        mid_names = stage_info["midterm"]["lesson_names"]
        fin_names = stage_info["final"]["lesson_names"]
        for name in mid_names:
            if name in content:
                found_midterm_kws.append(name)
        for name in fin_names:
            if name in content:
                found_final_kws.append(name)

    # 數學
    elif subject_key == "math":
        mid_names = stage_info["midterm"]["chapter_names"]
        fin_names = stage_info["final"]["chapter_names"]
        for name in mid_names:
            if name in content:
                found_midterm_kws.append(name)
        for name in fin_names:
            if name in content:
                found_final_kws.append(name)

    # 社會
    elif subject_key == "social":
        mid_names = stage_info["midterm"]["unit_names"]
        fin_names = stage_info["final"]["unit_names"]
        for name in mid_names:
            if name in content:
                found_midterm_kws.append(name)
        for name in fin_names:
            if name in content:
                found_final_kws.append(name)

    content_stage = None
    if found_midterm_kws and not found_final_kws:
        content_stage = "midterm"
    elif found_final_kws and not found_midterm_kws:
        content_stage = "final"
    elif found_midterm_kws and found_final_kws:
        content_stage = "mixed"

    aligned = True
    notice = ""
    if content_stage and content_stage != "mixed":
        if content_stage != active_stage:
            aligned = False
            notice = f"⚠️ 進度警示：目前學期處於【{active_stage}（期末進度）】，但偵測到此教材為【{content_stage}（期中進度）】單元主題（命中關鍵詞：{found_midterm_kws or found_final_kws}）。若是期中補救教學或複習卷則合規；若為當前教學單元請注意進度銜接！"
        else:
            notice = f"✅ 進度對齊：此教材單元主題完全符合當前【{active_stage}】教學進度（命中：{found_midterm_kws or found_final_kws}）。"

    return {
        "aligned": aligned,
        "content_stage": content_stage,
        "active_stage": active_stage,
        "found_keywords": found_midterm_kws + found_final_kws,
        "notice": notice
    }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="進度感知與教材動態擴展模組（支援 Google Drive + Ego Lite 電子書自動補齊）")
    parser.add_argument("--stage", choices=["midterm", "final", "auto"], default="auto", help="指定進度階段 (預設 auto)")
    parser.add_argument("--sync", action="store_true", help="強制執行雲端與本地同步")
    parser.add_argument("--fetch-ebook", action="store_true", help="若本地與雲端皆缺少當前進度教材，自動透過 Ego Lite 登入各科電子書即時抓取")
    args = parser.parse_args()

    stage, desc = detect_semester_stage()
    if args.stage != "auto":
        stage = args.stage
        desc = f"手動指定階段：{stage}"

    print(f"📅 學期進度判定結果：{desc}")
    coverage = check_local_final_coverage()
    print("📊 本地教材覆蓋情況：")
    for subj, cov in coverage.items():
        print(f"  - {subj}: 期中={cov['has_midterm']}, 期末={cov['has_final']}")

    if args.sync or args.fetch_ebook or stage == "final":
        synced = search_gdrive_and_sync(stage=stage, verbose=True, allow_ego_fallback=args.fetch_ebook)
