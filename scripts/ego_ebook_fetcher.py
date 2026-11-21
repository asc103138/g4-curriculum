#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ego_ebook_fetcher.py
整合 Ego Lite (ego-browser) 的「當前進度教科書自動登入與 PDF 即時抓取機制」
核心功能：
1. 免重複登入（Persistent Profile）：運用 Ego Lite 原生持久化瀏覽器 Profile 保存各科電子書登入 Session。
   - 若已登入：全自動抓取課本/習作 PDF 或 Zip，無需重複輸入帳密。
   - 若尚未登入或 Session 過期：自動呼叫 task.handOff() 交由使用者於 Ego Lite 介面登入一次（如教育雲 OpenID），
     絕不硬編碼帳密，絕不繞過 CAPTCHA/驗證門檻。
2. 進度感知抓取：自動讀取 sync_curriculum_progress.py 的當前學期階段（期中 midterm / 期末 final），
   依 config/ebook_sources.json 所設定的各科版本電子書入口，即時抓入當前進度的課本與習作 PDF。
3. 通用需登入檔案下載器（--download-url）：任何需要登入才能下載的教材/題庫檔案，
   自動借用 Ego Lite 已登入的 Cookie/Session（page.fetch(..., { saveAs })）直接落地並自動解壓歸檔。
"""

import os
import re
import sys
import json
import time
import shutil
import zipfile
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = WORKSPACE_ROOT / "config/ebook_sources.json"
LOCAL_CONFIG_FILE = WORKSPACE_ROOT / "config/ebook_sources.local.json"
CACHE_FILE = WORKSPACE_ROOT / ".cache/textbook_corpus.json"
DOWNLOADS_DIR = Path.home() / "Downloads"

# 匯入進度感知模組
try:
    from sync_curriculum_progress import detect_semester_stage, check_local_final_coverage
    HAS_PROGRESS_MODULE = True
except ImportError:
    HAS_PROGRESS_MODULE = False


def load_ebook_config() -> dict:
    """載入電子書來源設定（支援 config/ebook_sources.local.json 覆蓋個人設定）"""
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"找不到電子書設定檔：{CONFIG_FILE}")

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    if LOCAL_CONFIG_FILE.exists():
        try:
            with open(LOCAL_CONFIG_FILE, "r", encoding="utf-8") as lf:
                local_cfg = json.load(lf)
            # 淺層合併頂層與各科設定
            for k, v in local_cfg.items():
                if k == "subjects" and isinstance(v, dict):
                    for sk, sv in v.items():
                        if sk in cfg["subjects"]:
                            cfg["subjects"][sk].update(sv)
                        else:
                            cfg["subjects"][sk] = sv
                else:
                    cfg[k] = v
        except Exception as e:
            print(f"⚠️ 讀取本機覆蓋設定 {LOCAL_CONFIG_FILE.name} 失敗，改用預設設定：{e}")

    return cfg


def resolve_ego_binary(cfg: dict) -> str:
    """解析 ego-browser 執行檔路徑"""
    bin_name = cfg.get("ego_browser_bin", "ego-browser")
    found = shutil.which(bin_name)
    if found:
        return found
    fallback = Path.home() / ".local/bin/ego-browser"
    if fallback.exists():
        return str(fallback)
    raise RuntimeError(
        "找不到 ego-browser 指令！請確認已安裝 Ego Lite（參考 ego-browser skill 的 references/install-macos.md）。"
    )


def run_ego_node_script(js_code: str, ego_bin: str, timeout: int = 90) -> Tuple[bool, dict, str]:
    """
    透過 `ego-browser nodejs` 執行 ESM 腳本，並從輸出中解析標記 JSON 結果。
    遵循 ego-browser skill 規範：不依賴環境變數與相對路徑，所有參數直接寫入腳本。
    """
    try:
        proc = subprocess.run(
            [ego_bin, "nodejs"],
            input=js_code,
            text=True,
            capture_output=True,
            timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return False, {"error": "ego-browser 執行逾時"}, "timeout"
    except Exception as e:
        return False, {"error": str(e)}, str(e)

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    combined = stdout + "\n" + stderr

    # 解析腳本輸出的結構化 JSON 標記（相容 stdout 與 stderr）
    match = re.search(r"__EGO_RESULT_START__\s*(\{.*?\})\s*__EGO_RESULT_END__", combined, flags=re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            return proc.returncode == 0, data, combined
        except json.JSONDecodeError:
            pass

    return proc.returncode == 0, {"raw_stdout": stdout.strip(), "raw_stderr": stderr.strip()}, combined


def extract_and_reset_cache(target_dir: Path, saved_files: List[Path], verbose: bool = True) -> List[str]:
    """若下載檔案包含 .zip，自動解壓縮裡面的 PDF 至目標目錄，並重置語料快取"""
    extracted_pdfs = []
    for fpath in saved_files:
        if not fpath.exists():
            continue
        if fpath.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(fpath, "r") as zf:
                    for member in zf.namelist():
                        if member.lower().endswith(".pdf") and not member.startswith("__MACOSX"):
                            zf.extract(member, target_dir)
                            extracted_pdfs.append(Path(member).name)
                if verbose:
                    print(f"📦 已自動解壓縮 {fpath.name} -> 提取 {len(extracted_pdfs)} 個 PDF 至 {target_dir.name}/")
            except Exception as e:
                print(f"⚠️ 解壓縮 {fpath.name} 失敗：{e}")
        elif fpath.suffix.lower() == ".pdf":
            extracted_pdfs.append(fpath.name)

    if extracted_pdfs and CACHE_FILE.exists():
        CACHE_FILE.unlink()
        if verbose:
            print("🔄 已自動重置課本語料快取 (.cache/textbook_corpus.json)，下一次審查將立即納入新教材！")

    return extracted_pdfs


def check_or_fetch_subject(
    subject_key: str,
    cfg: dict,
    stage: str = "auto",
    check_only: bool = False,
    space_id: Optional[int] = None
) -> dict:
    """
    透過 Ego Lite 開啟指定科目版本電子書：
    1. 檢查是否已在 Ego Lite Profile 登入（免重複登入）。
    2. 若未登入：自動呼叫 task.handOff()，保留分頁交由使用者登入一次。
    3. 若已登入：即時掃描符合當前進度（midterm / final）之課本/習作 PDF 與 Zip 連結，
       使用 page.fetch(url, { saveAs }) 帶著登入狀態直接抓取至專案本地目錄並解壓縮！
    """
    ego_bin = resolve_ego_binary(cfg)
    subj_cfg = cfg["subjects"].get(subject_key)
    if not subj_cfg:
        raise ValueError(f"未設定的科目代碼：{subject_key}（支援：{list(cfg['subjects'].keys())}）")

    if stage == "auto" and HAS_PROGRESS_MODULE:
        stage, stage_desc = detect_semester_stage()
    else:
        stage_desc = f"指定階段：{stage}"

    target_dir = (WORKSPACE_ROOT / subj_cfg["local_dir"]).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    stage_kws = subj_cfg.get("stage_keywords", {}).get(stage, [])
    dl_kws = subj_cfg.get("download_keywords", [])
    portal_url = subj_cfg["portal_url"]
    login_indicators = subj_cfg.get("login_indicators", ["登入", "login", "signin"])
    logged_in_indicators = subj_cfg.get("logged_in_indicators", ["登出", "我的書櫃", "logout"])

    print(f"\n📚 [{subj_cfg['name']}] 目標進度：{stage} ({stage_desc})")
    print(f"🌐 透過 Ego Lite 開啟電子書入口：{portal_url}")

    payload = {
        "spaceId": space_id,
        "goalName": f"G4電子書同步-{subj_cfg['publisher']}{subj_cfg['name']}",
        "portalUrl": portal_url,
        "loginIndicators": login_indicators,
        "loggedInIndicators": logged_in_indicators,
        "stageKeywords": stage_kws,
        "downloadKeywords": dl_kws,
        "targetDir": str(target_dir),
        "checkOnly": check_only
    }

    js_script = f"""
const CFG = {json.dumps(payload, ensure_ascii=False)};

const entry = CFG.spaceId === null
  ? undefined
  : (await listTaskSpaces()).find((s) => s.id === CFG.spaceId);

const task = !entry
  ? await taskSpace(CFG.goalName)
  : entry.ownership === "user"
    ? await claimTaskSpace(CFG.spaceId)
    : entry.ownership === "agentDelegatedToUser"
      ? await takeOverTaskSpace(CFG.spaceId)
      : await taskSpace(CFG.spaceId);

const page = (await task.pages())[0] ?? (await task.adopt((await task.tabs())[0].page));

await page.goto(CFG.portalUrl, {{ timeout: 30000 }});
try {{
  await page.waitForLoadState("load", {{ timeout: 12000 }});
}} catch {{}}
await page.waitForTimeout(2500);

const pageState = await page.evaluate((cfg) => {{
  const url = window.location.href;
  const title = document.title || "";
  const bodyText = (document.body?.innerText || "").slice(0, 6000);
  const lowerUrl = url.toLowerCase();

  const isVisible = (el) => {{
    if (!el) return false;
    const style = window.getComputedStyle(el);
    return style.display !== "none" && style.visibility !== "hidden" && style.opacity !== "0" && (el.offsetWidth > 0 || el.offsetHeight > 0);
  }};

  const hasPasswordInput = Array.from(document.querySelectorAll('input[type="password"]')).some(isVisible);

  // 只檢查「實際可見」的按鈕/連結文字，避免隱藏 DOM 干擾
  const actionTexts = Array.from(document.querySelectorAll("a, button, [role='button'], span"))
    .filter(isVisible)
    .map((el) => (el.innerText || "").trim())
    .filter((t) => t.length > 0 && t.length <= 20);

  const hasLoginBtn = actionTexts.some((t) => ["登入", "會員登入", "教師登入", "立即登入", "登入/註冊", "登入／註冊", "Sign in", "Login"].includes(t));
  const hasLogoutBtn = actionTexts.some((t) => t.includes("登出") || t.toLowerCase().includes("logout") || t.includes("個人資料") || t.includes("會員中心"));
  const hasLoggedInText = cfg.loggedInIndicators.some((kw) => kw.length >= 2 && bodyText.includes(kw));
  const hasLoginPromptText = cfg.loginIndicators.some((kw) => kw.length >= 3 && bodyText.includes(kw));

  // 若已出現書櫃/登出等強登入特徵（包含南一 /bookshelf 頁面常駐隱藏登入框的情況），即判定已免重複登入
  const isNaniBookshelfLoggedIn = lowerUrl.includes("/bookshelf") && bodyText.includes("登出");
  const loggedInHit = isNaniBookshelfLoggedIn || (!hasPasswordInput && (hasLogoutBtn || (hasLoggedInText && !hasLoginBtn && !hasLoginPromptText) || bodyText.includes("進入書本")));
  const loginHit = hasPasswordInput
    || hasLoginBtn
    || hasLoginPromptText
    || lowerUrl.includes("login")
    || lowerUrl.includes("signin")
    || lowerUrl.includes("sso");

  // 收集頁面上所有潛在 PDF / ZIP 或教材下載連結
  const links = Array.from(document.querySelectorAll("a[href]")).map((a) => ({{
    href: a.href,
    text: (a.innerText || a.getAttribute("title") || a.getAttribute("aria-label") || "").trim()
  }})).filter((item) => {{
    const h = item.href.toLowerCase();
    const t = item.text.toLowerCase();
    return h.endsWith(".pdf") || h.endsWith(".zip") || h.includes("download") || t.includes("pdf") || t.includes("課本") || t.includes("習作");
  }});

  return {{
    url,
    title,
    hasPasswordInput,
    hasLoginBtn,
    hasLogoutBtn,
    loggedInHit,
    needsLogin: !loggedInHit && loginHit,
    snippet: bodyText.replace(/\s+/g, " ").slice(0, 220),
    candidateLinks: links.slice(0, 60)
  }};
}}, CFG);

if (pageState.needsLogin) {{
  if (CFG.checkOnly) {{
    await task.finish({{ keep: [] }});
  }} else {{
    await task.handOff();
  }}
  console.log("__EGO_RESULT_START__");
  console.log(JSON.stringify({{
    status: "NEED_LOGIN",
    taskSpaceId: task.spaceId,
    url: pageState.url,
    title: pageState.title,
    hasLoginBtn: pageState.hasLoginBtn,
    hasLogoutBtn: pageState.hasLogoutBtn,
    snippet: pageState.snippet,
    message: "偵測到出版社網站尚未登入，請於 Ego Lite 視窗完成一次性登入以保存 Session 免重複登入。"
  }}));
  console.log("__EGO_RESULT_END__");
}} else if (CFG.checkOnly) {{
  await task.finish({{ keep: [] }});
  console.log("__EGO_RESULT_START__");
  console.log(JSON.stringify({{
    status: "LOGGED_IN",
    taskSpaceId: task.spaceId,
    url: pageState.url,
    title: pageState.title,
    hasLoginBtn: pageState.hasLoginBtn,
    hasLogoutBtn: pageState.hasLogoutBtn,
    snippet: pageState.snippet,
    candidateCount: pageState.candidateLinks.length
  }}));
  console.log("__EGO_RESULT_END__");
}} else {{
  // 篩選符合當前進度（stageKeywords）或下載關鍵字（downloadKeywords）的直接檔案連結
  const matched = pageState.candidateLinks.filter((item) => {{
    const hay = (item.text + " " + decodeURIComponent(item.href || "")).toLowerCase();
    const isFile = item.href.toLowerCase().includes(".pdf") || item.href.toLowerCase().includes(".zip");
    if (!isFile) return false;
    const hitStage = CFG.stageKeywords.length === 0 || CFG.stageKeywords.some((kw) => hay.includes(kw.toLowerCase()));
    const hitDl = CFG.downloadKeywords.some((kw) => hay.includes(kw.toLowerCase()));
    return hitStage || hitDl;
  }});

  const downloaded = [];
  const failed = [];
  for (let i = 0; i < matched.length; i++) {{
    const item = matched[i];
    try {{
      const u = new URL(item.href);
      let fname = decodeURIComponent(u.pathname.split("/").pop() || "");
      if (!fname || (!fname.toLowerCase().endsWith(".pdf") && !fname.toLowerCase().endsWith(".zip"))) {{
        const ext = item.href.toLowerCase().includes(".zip") ? ".zip" : ".pdf";
        fname = `ebook_${{i + 1}}${{ext}}`;
      }}
      const savePath = `${{CFG.targetDir}}/${{fname}}`;
      const res = await page.fetch(item.href, {{ saveAs: savePath, timeout: 60000 }});
      if (res.ok) {{
        downloaded.push({{ file: savePath, url: item.href, text: item.text }});
      }} else {{
        failed.push({{ url: item.href, status: res.status }});
      }}
    }} catch (err) {{
      failed.push({{ url: item.href, error: String(err) }});
    }}
  }}

  if (downloaded.length > 0) {{
    await task.finish({{ keep: [] }});
    console.log("__EGO_RESULT_START__");
    console.log(JSON.stringify({{
      status: "DOWNLOADED",
      taskSpaceId: task.spaceId,
      url: pageState.url,
      downloaded,
      failed
    }}));
    console.log("__EGO_RESULT_END__");
  }} else {{
    // 頁面已登入但下載連結需透過 SPA 互動點擊（如各出版商書櫃介面）：保留分頁交接，下載後自動歸檔
    await task.finish({{ keep: ["p1"] }});
    console.log("__EGO_RESULT_START__");
    console.log(JSON.stringify({{
      status: "LOGGED_IN_INTERACTIVE",
      taskSpaceId: task.spaceId,
      url: pageState.url,
      title: pageState.title,
      candidateLinks: pageState.candidateLinks.slice(0, 15),
      message: "已免重複登入進入出版社書櫃頁面。此平台採用動態前端書櫃，已保留分頁供點擊下載，下載後可執行 --ingest-downloads 自動歸檔並更新語料庫。"
    }}));
    console.log("__EGO_RESULT_END__");
  }}
}}
"""

    ok, data, raw_log = run_ego_node_script(js_script, ego_bin)
    status = data.get("status", "ERROR")

    if status == "NEED_LOGIN":
        print(f"🔐 [{subj_cfg['name']}] 尚未登入（URL: {data.get('url')} | 標題: {data.get('title')}）")
        if data.get("snippet"):
            print(f"   頁面摘要：{data['snippet'][:120]}...")
        if not check_only:
            print(f"👉 已在 Ego Lite 開啟登入視窗（TaskSpace #{data.get('taskSpaceId')}），請完成一次性登入，之後即免重複登入！")
    elif status == "LOGGED_IN":
        print(f"✅ [{subj_cfg['name']}] 已登入（免重複登入 Session 有效）！URL: {data.get('url')} | 標題: {data.get('title')}")
        if data.get("snippet"):
            print(f"   頁面摘要：{data['snippet'][:120]}...")
    elif status == "DOWNLOADED":
        saved_paths = [Path(item["file"]) for item in data.get("downloaded", [])]
        print(f"🎉 [{subj_cfg['name']}] 成功抓取 {len(saved_paths)} 個教材檔案！")
        extract_and_reset_cache(target_dir, saved_paths)
    elif status == "LOGGED_IN_INTERACTIVE":
        print(f"✅ [{subj_cfg['name']}] 已自動沿用登入狀態進入書櫃（{data.get('title')}），已保留分頁供選取下載。")
        print("👉 下載完成後執行 `python3 scripts/ego_ebook_fetcher.py --ingest-downloads` 即可自動歸檔並更新語料庫。")
    else:
        print(f"⚠️ [{subj_cfg['name']}] 執行過程發生異常：{data.get('error') or raw_log[:300]}")

    return data


def download_authenticated_file(
    url: str,
    cfg: dict,
    subject_key: Optional[str] = None,
    output_path: Optional[Path] = None,
    space_id: Optional[int] = None
) -> dict:
    """
    通用需登入檔案下載器：
    透過 Ego Lite 已登入的 Session (`page.fetch(url, { saveAs })`) 直接下載受保護的 PDF/Zip。
    若伺服器回應 401/403 或重導向登入頁，自動呼叫 task.handOff() 讓使用者於 Ego Lite 登入一次，
    達成「登入一次即免重複登入」的無縫下載體驗。
    """
    ego_bin = resolve_ego_binary(cfg)
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}/"

    if output_path is None:
        if subject_key and subject_key in cfg["subjects"]:
            dest_dir = (WORKSPACE_ROOT / cfg["subjects"][subject_key]["local_dir"]).resolve()
        else:
            dest_dir = (WORKSPACE_ROOT / "downloaded_materials").resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)
        fname = Path(parsed.path).name or f"material_{int(time.time())}.pdf"
        output_path = dest_dir / fname
    else:
        output_path = output_path.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "spaceId": space_id,
        "goalName": f"EgoLite免重複登入下載-{parsed.netloc}",
        "originUrl": origin,
        "targetUrl": url,
        "saveAs": str(output_path)
    }

    js_script = f"""
const CFG = {json.dumps(payload, ensure_ascii=False)};

const entry = CFG.spaceId === null
  ? undefined
  : (await listTaskSpaces()).find((s) => s.id === CFG.spaceId);

const task = !entry
  ? await taskSpace(CFG.goalName)
  : entry.ownership === "user"
    ? await claimTaskSpace(CFG.spaceId)
    : entry.ownership === "agentDelegatedToUser"
      ? await takeOverTaskSpace(CFG.spaceId)
      : await taskSpace(CFG.spaceId);

const page = (await task.pages())[0] ?? (await task.adopt((await task.tabs())[0].page));

// 先前往同網域確保 Cookie 與同源上下文就緒
await page.goto(CFG.originUrl, {{ timeout: 30000 }});
try {{ await page.waitForLoadState("load", {{ timeout: 10000 }}); }} catch {{}}

const res = await page.fetch(CFG.targetUrl, {{ saveAs: CFG.saveAs, timeout: 60000 }});
const ct = (res.headers?.["content-type"] || res.headers?.["Content-Type"] || "").toLowerCase();
const isAuthRedirect = res.status === 401 || res.status === 403 || (res.url || "").toLowerCase().includes("login") || ct.includes("text/html");

if (res.ok && !isAuthRedirect) {{
  await task.finish({{ keep: [] }});
  console.log("__EGO_RESULT_START__");
  console.log(JSON.stringify({{
    status: "DOWNLOADED",
    taskSpaceId: task.spaceId,
    saveAs: CFG.saveAs,
    httpStatus: res.status,
    contentType: ct
  }}));
  console.log("__EGO_RESULT_END__");
}} else {{
  // 檔案受登入保護且尚未登入 -> 開啟頁面並 handOff 讓使用者登入一次
  await page.goto(CFG.targetUrl, {{ timeout: 30000 }});
  await task.handOff();
  console.log("__EGO_RESULT_START__");
  console.log(JSON.stringify({{
    status: "NEED_LOGIN",
    taskSpaceId: task.spaceId,
    httpStatus: res.status,
    redirectUrl: res.url,
    message: "此下載連結需要登入，已在 Ego Lite 開啟登入視窗。請登入一次後重新執行，往後將免重複登入。"
  }}));
  console.log("__EGO_RESULT_END__");
}}
"""

    print(f"📥 正在透過 Ego Lite 下載受保護檔案：{url}")
    ok, data, raw_log = run_ego_node_script(js_script, ego_bin)
    status = data.get("status", "ERROR")

    if status == "DOWNLOADED":
        print(f"✅ 免重複登入下載成功！檔案已儲存至：{output_path}")
        extract_and_reset_cache(output_path.parent, [output_path])
    elif status == "NEED_LOGIN":
        print(f"🔐 檔案需要登入驗證！已在 Ego Lite 開啟視窗（TaskSpace #{data.get('taskSpaceId')}），請登入一次後重新執行。")
    else:
        print(f"⚠️ 下載失敗：{data.get('error') or raw_log[:300]}")

    return data


def ingest_from_downloads(cfg: dict, max_age_hours: int = 24) -> Dict[str, List[str]]:
    """
    掃描 ~/Downloads 中最近下載的課本/習作 PDF 與 Zip，
    自動依科目關鍵字歸檔搬移至專案對應教材目錄並解壓縮、重置語料快取！
    """
    ingested = {"chinese": [], "math": [], "social": []}
    if not DOWNLOADS_DIR.exists():
        print("⚠️ 找不到本機 Downloads 資料夾。")
        return ingested

    now = time.time()
    cutoff = now - max_age_hours * 3600

    subject_matchers = {
        "chinese": ["國語", "翰林", "L01", "L02", "L03", "L04", "L05", "L06", "L07", "L08", "L09", "L10", "L11", "L12"],
        "math": ["數學", "南一", "ch01", "ch02", "ch03", "ch04", "ch05", "ch06", "ch07", "ch08", "ch09", "ch10"],
        "social": ["社會", "康軒", "1-1", "1-2", "1-3", "2-1", "2-2", "3-1", "3-2", "4-1", "4-2", "4-3"]
    }

    for fpath in sorted(DOWNLOADS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not fpath.is_file() or fpath.suffix.lower() not in {".pdf", ".zip"}:
            continue
        if fpath.stat().st_mtime < cutoff:
            continue

        fname = fpath.name
        # 必須與課本/習作/教材相關，避免誤搬一般下載檔
        if not any(k in fname for k in ["課本", "習作", "國語", "數學", "社會", "4上", "四年級", "115"]):
            continue

        matched_subj = None
        for subj, kws in subject_matchers.items():
            if any(kw.lower() in fname.lower() for kw in kws):
                matched_subj = subj
                break

        if not matched_subj:
            continue

        target_dir = (WORKSPACE_ROOT / cfg["subjects"][matched_subj]["local_dir"]).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        dest_file = target_dir / fname
        if not dest_file.exists():
            shutil.copy2(fpath, dest_file)
            extracted = extract_and_reset_cache(target_dir, [dest_file], verbose=True)
            ingested[matched_subj].extend(extracted if extracted else [fname])
            print(f"📂 已自動歸檔 [{matched_subj}]：{fname} -> {target_dir.name}/")

    total = sum(len(v) for v in ingested.values())
    if total == 0:
        print(f"ℹ️ 最近 {max_age_hours} 小時內在 Downloads 未發現新的四上課習 PDF/Zip。")
    else:
        print(f"🎉 共自動歸檔並更新 {total} 份課習教材！")
    return ingested


def main():
    parser = argparse.ArgumentParser(
        description="Ego Lite 自動登入各科電子書與當前進度課習 PDF 即時抓取工具"
    )
    parser.add_argument("--subject", choices=["chinese", "math", "social", "all"], default="all", help="指定抓取科目 (預設 all)")
    parser.add_argument("--stage", choices=["auto", "midterm", "final"], default="auto", help="指定學期進度階段 (預設 auto 自動判定)")
    parser.add_argument("--check-auth", action="store_true", help="僅檢查各科電子書在 Ego Lite 的登入狀態（免重複登入驗證）")
    parser.add_argument("--download-url", help="使用 Ego Lite 免重複登入直接下載指定的受保護檔案 URL")
    parser.add_argument("--output", help="搭配 --download-url 指定儲存路徑")
    parser.add_argument("--ingest-downloads", action="store_true", help="自動掃描 ~/Downloads 並將剛下載的課習 PDF/Zip 歸檔解壓縮")
    parser.add_argument("--space-id", type=int, default=None, help="接續既有 Ego Lite TaskSpace ID（例如使用者登入完成後繼續）")
    args = parser.parse_args()

    cfg = load_ebook_config()

    if args.ingest_downloads:
        ingest_from_downloads(cfg)
        return

    if args.download_url:
        subj = None if args.subject == "all" else args.subject
        out_p = Path(args.output) if args.output else None
        download_authenticated_file(args.download_url, cfg, subject_key=subj, output_path=out_p, space_id=args.space_id)
        return

    subjects = ["chinese", "math", "social"] if args.subject == "all" else [args.subject]
    for s in subjects:
        check_or_fetch_subject(s, cfg, stage=args.stage, check_only=args.check_auth, space_id=args.space_id)


if __name__ == "__main__":
    main()
