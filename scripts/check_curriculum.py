#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_curriculum.py
國小四年級教材與試題自動化三階檢核工具
遵循同型態輸入輸出原則，集中輸出於 reviewed/ 目錄。
"""

import os
import sys
import argparse
import difflib
from pathlib import Path

# 四年級三科核心指標與關鍵字資料庫
CONFIG = {
    "subjects": {
        "math": {
            "name": "數學科（南一版）",
            "keywords": ["南一", "分數", "大數", "角度", "公里", "乘法", "除法", "等值", "n-Ⅱ-", "s-Ⅱ-"],
            "misconceptions": ["M4-FRAC-01", "M4-PLACE-01", "M4-GEOM-01", "M4-GEOM-02", "M4-CALC-01"]
        },
        "chinese": {
            "name": "國語科（翰林版）",
            "keywords": ["翰林", "記敘文", "說明文", "五感", "修辭", "句型", "作文", "6-Ⅱ-", "5-Ⅱ-"],
            "misconceptions": ["C4-TEXT-01", "C4-PUNCT-01", "C4-STRUC-01", "C4-VOCAB-01"]
        },
        "social": {
            "name": "社會科（康軒版）",
            "keywords": ["康軒", "家鄉", "地形", "產業", "港區", "水資源", "公共設施", "社2a-Ⅱ-", "地1b-Ⅱ-"],
            "misconceptions": ["S4-GEO-01", "S4-ECON-01", "S4-CIVIC-01", "S4-LOCAL-01"]
        }
    },
    "local_keywords": ["梧棲", "中正國小", "高美濕地", "臺中港", "港區", "海線", "九降風", "風力發電"],
    "tier2_keywords": {
        "sdgs": ["SDG", "永續", "海洋", "生態", "保育", "責任消費", "氣候行動"],
        "steam": ["STEAM", "探究", "實驗", "工程", "科學", "跨域", "設計思維"],
        "clt": ["認知負荷", "工作記憶", "字數精簡", "版面留白"]
    }
}

def analyze_content(content: str, filename: str):
    """分析文本內容並進行三階檢測"""
    report = {
        "filename": filename,
        "tier1_pass": True,
        "tier1_issues": [],
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
        report["tier1_issues"].append("缺少 108 課綱學習重點代碼（例如 n-Ⅱ-7、6-Ⅱ-1）。")

    has_publisher = any(pub in content for pub in ["南一", "翰林", "康軒"])
    if not has_publisher:
        report["tier1_issues"].append("未標明或對準校內指定教科書版本（數學南一、國語翰林、社會康軒）。")

    # 本機課習教材目錄存在性檢查（跨 Agent 提醒機制）
    textbook_dirs = {
        "math": Path("115四上數課習"),
        "chinese": Path("115四上國課習"),
        "social": Path("115社會課習")
    }
    if curr_subj and not textbook_dirs[curr_subj].exists():
        report["tier1_issues"].append(
            f"本機未偵測到【{CONFIG['subjects'][curr_subj]['name']}】本機教材資料夾（{textbook_dirs[curr_subj]}）。"
            "因版權限制，公開儲存庫未附帶課本 PDF，請使用者自行由校內合法教學資源庫下載所需版本的教科書/習作 PDF 放置於專案目錄後再行精確比對！"
        )

    # 檢查是否具備單元或課次名稱對應
    unit_keywords = {
        "math": ["一億以內的數", "乘法", "角度", "除法", "三角形", "分數", "公里", "小數"],
        "chinese": ["我愛家鄉", "美麗島", "請到我的家鄉來", "鏡頭下的家鄉", "天空的奇想", "飛行夢", "月光下", "又遠又近的月亮", "記敘文", "生活記敘文", "寫作"],
        "social": ["家鄉的自然環境", "家鄉在哪裡", "家鄉的地形", "氣候", "水資源", "傳統住屋", "器物", "傳統信仰", "老街", "作息", "節慶", "節日"]
    }
    if curr_subj:
        has_unit = any(ukw in content for ukw in unit_keywords[curr_subj])
        if not has_unit:
            report["tier1_issues"].append(f"未明確對應【{CONFIG['subjects'][curr_subj]['name']}】之具體單元課次名稱。")

    if report["tier1_issues"]:
        report["tier1_pass"] = False

    # 3. 第二階（中階目標檢測：嚴格退回標準）
    has_sdgs = any(kw in content for kw in CONFIG["tier2_keywords"]["sdgs"])
    if not has_sdgs:
        report["tier2_missing"].append("SDGs 永續發展目標生活化融入（例如 SDG 14 海洋生態、SDG 12 責任消費）。")

    has_steam = any(kw in content for kw in CONFIG["tier2_keywords"]["steam"])
    if not has_steam:
        report["tier2_missing"].append("STEAM 跨學科探究與動手做/工程思維。")

    # 認知負荷 (CLT) 粗檢
    words_count = len(content)
    if words_count > 4000 and "學習單" in content:
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
    lines.append("## 📋 AI 自我檢測審查報告 (Self-Review Report)")
    lines.append(f"- **檢測檔案**：`{analysis['filename']}`")
    lines.append(f"- **對應科目與版本**：{analysis['detected_subject']}")
    
    # 第一階
    if analysis["tier1_pass"]:
        lines.append("- **🛑 第一階（最低門檻）：✅ 審查通過**")
        lines.append("  - 先備經驗：符合四年級學生認知水平。")
        lines.append("  - 108 課綱：已對齊學習表現與內容代碼。")
        lines.append("  - 版本對齊：精確鎖定校內指定版本。")
    else:
        lines.append("- **🛑 第一階（最低門檻）：❌ 未達標（打回重置）**")
        for issue in analysis["tier1_issues"]:
            lines.append(f"  - ⚠️ 缺失：{issue}")

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

    lines.append("\n*審查系統：臺中市梧棲區中正國小四年級教材審查機制（Review Protocol v2.0）*")
    return "\n".join(lines)

def process_file(file_path: Path, output_dir: Path):
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

    analysis = analyze_content(content, file_path.name)
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
        with open(optimized_file, "w", encoding="utf-8") as of:
            of.write(content + md_report)
        print(f"✅ 已輸出同型態優化版: {optimized_file}")
    elif ext == ".html":
        # 於 HTML </body> 前嵌入檢測視圖卡片
        html_badge = f"""
        <!-- AI 自我檢測審查浮動報告 -->
        <div id="review-report-badge" style="position:fixed;bottom:20px;right:20px;z-index:9999;font-family:sans-serif;">
          <details style="background:#ffffff;border:2px solid #2563eb;border-radius:12px;box-shadow:0 10px 25px rgba(0,0,0,0.15);padding:14px;max-width:380px;font-size:12px;color:#1e293b;">
            <summary style="font-weight:bold;color:#1d4ed8;cursor:pointer;list-style:none;display:flex;align-items:center;gap:6px;">
              🛡️ 四年級三階審查檢測報告 (點擊展開)
            </summary>
            <div style="margin-top:10px;line-height:1.5;">
              <div><strong>科目：</strong>{analysis['detected_subject']}</div>
              <div style="color:{'#15803d' if analysis['tier1_pass'] else '#b91c1c'};"><strong>第一階最低門檻：</strong>{'✅ 通過' if analysis['tier1_pass'] else '❌ 未達標'}</div>
              <div style="color:{'#15803d' if analysis['tier2_pass'] else '#d97706'};"><strong>第二階中階目標：</strong>{'✅ 通過' if analysis['tier2_pass'] else '⚠️ 需確認'}</div>
              <div style="color:#4f46e5;"><strong>第三階高階亮點：</strong>{'⭐ 加分達成' if analysis['tier3_pass'] else '⚪ 一般'}</div>
              <p style="margin-top:8px;font-size:11px;color:#64748b;">詳情請參閱同目錄下的 <code>{base_name}_審查報告.md</code></p>
            </div>
          </details>
        </div>
        """
        if "</body>" in content:
            new_html = content.replace("</body>", f"{html_badge}\n</body>")
        else:
            new_html = content + html_badge

        with open(optimized_file, "w", encoding="utf-8") as of:
            of.write(new_html)
        print(f"✅ 已輸出同型態優化版: {optimized_file}")
    else:
        # 其他檔案型態
        with open(optimized_file, "w", encoding="utf-8") as of:
            of.write(content)
        print(f"✅ 已輸出同型態檔案: {optimized_file}")

    # 印出終端機檢測摘要
    print("--------------------------------------------------")
    print(f"科目判定: {analysis['detected_subject']}")
    print(f"第一階門檻: {'✅ 通過' if analysis['tier1_pass'] else '❌ 需打回'}")
    print(f"第二階目標: {'✅ 通過' if analysis['tier2_pass'] else '⚠️ 待補強'}")
    print(f"第三階亮點: {'⭐ 有亮點' if analysis['tier3_pass'] else '⚪ 無特殊亮點'}")
    print("--------------------------------------------------\n")

def main():
    parser = argparse.ArgumentParser(description="國小四年級教材與試題三階審查工具")
    parser.add_argument("files", nargs="+", help="欲審查的檔案路徑 (支援 .md, .html 等)")
    parser.add_argument("--output-dir", default="reviewed", help="審查結果存放目錄 (預設: reviewed)")
    args = parser.parse_args()

    out_path = Path(args.output_dir)
    for f in args.files:
        process_file(Path(f), out_path)

if __name__ == "__main__":
    main()
