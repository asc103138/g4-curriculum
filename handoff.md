# 交接與進度記錄 (handoff.md)

## 專案狀態
- **日期**：2026-11-15
- **目前進度**：
  - **完成考卷防呆與深度邏輯審查升級 (v4.2)**：
    - **生字表升級為階段一紅線一票否決**：在 [`scripts/check_curriculum.py`](./scripts/check_curriculum.py) 新增 `verify_tier1_vocab_table()` 與 `filter_corpus_by_stage()`，支援 `【】` / `（）` 格式並依期中/期末嚴格切片隔離語料庫與生字表（期中絕不混用未來課次）。
    - **題幹字級超綱攔截 & 教學重點檢核**：針對所有試題大題題幹逐字比對本階段課習語料庫，精準攔截未教過字詞（如「陰霾」的「霾」）；並自動核對「改錯字」等大題是否符合本階段習作教學重點。修正 [`scripts/sync_curriculum_progress.py`](./scripts/sync_curriculum_progress.py) 期末真實課名（L07~L12）。
    - **全卷雙向跨大題洩題碰撞 + 大題邏輯連續性檢核**：升級 `verify_tier3_leakage()` 涵蓋單字、改錯正字、選詞答案雙向碰撞；新增 `verify_tier3_logic_sequence()` 檢核大題編排是否符合「字詞 → 句型 → 選擇 → 閱讀寫作」遞進順序。
  - **完成進度適應調整與 Scrapling 爬蟲審查管線升級 (v4.1)**：
    - **1. 進度感知與自動教材擴展 (Progress-Adaptive Review)**：
      - 開發 [`scripts/sync_curriculum_progress.py`](./scripts/sync_curriculum_progress.py)，根據當前日期（11月中旬自動識別為期末階段）動態切換期中/期末進度範圍。
      - 本地缺少期末課習時，自動掃描 Google Drive（`我的雲端硬碟/115四上教材/`）及本地下載目錄，自動解壓縮同步期末教材（國語 L7~L12、數學 Ch6~Ch10、社會 3-1~4-3），並自動擴充更新真實課本文本語料庫。
      - 審查引擎升級進度對齊檢驗（Progress Alignment），比對教材單元與當前學期進度是否相符，給予精確進度提醒或警告。
    - **2. Scrapling 高效抗阻斷爬蟲與結構化解析整合**：
      - 閱讀並深入分析 `https://github.com/D4Vinci/Scrapling.git`，安裝全域技能 [`scrapling`](file:///Users/tunyuan/.gemini/config/skills/scrapling)。
      - 開發 [`scripts/scrape_educational_resources.py`](./scripts/scrape_educational_resources.py)，整合 `Fetcher` 與 `StealthyFetcher` 高效抓取全國中小學題庫網與教育資源網，自動清洗導覽列與版面雜訊轉為標準 Markdown，並一鍵無縫送入三階漏斗審查。
    - **3. 全域機制與規範文件同步升級**：
      - 更新專案 [`AGENTS.md`](./AGENTS.md)、[`docs/review-protocol.md`](./docs/review-protocol.md) 及全域技能 [`g4-curriculum-review`](file:///Users/tunyuan/.gemini/config/skills/g4-curriculum-review/SKILL.md)。
  - 完成全域技能 `g4-curriculum-review` 建置並納入 `antigravity-lazy-packs` 清單。
  - 完成 RDQ 3 輪訪談並產出 Confirmed 需求規格卡：[`rdq/RDQ-spec-curriculum-review-20261004.md`](./rdq/RDQ-spec-curriculum-review-20261004.md)。
  - 建立專案三階審查規範與迷思代碼庫：[`docs/review-protocol.md`](./docs/review-protocol.md)。
  - 開發自動化三階檢核與同型態輸出腳本：[`scripts/check_curriculum.py`](./scripts/check_curriculum.py)。
  - 建立集中輸出目錄 `reviewed/`，並實測產出國語學習單與社會科試題之審查報告與優化版。
  - 配置 `.gitignore` 隔離大型教材與壓縮檔（如 `115四上數課習/`、`115四上國課習/`、`115社會課習/`）。
  - **完成全域教材審查強制機制部署**：
    - 建立全域規則檔 [`~/.gemini/config/rules/curriculum-review-protocol.md`](file:///Users/tunyuan/.gemini/config/rules/curriculum-review-protocol.md)。
    - 升級全域技能 [`g4-curriculum-review`](file:///Users/tunyuan/.gemini/config/skills/g4-curriculum-review/SKILL.md) 與 [`antigravity-lazy-packs`](file:///Users/tunyuan/.gemini/config/skills/antigravity-lazy-packs/SKILL.md) 索引，規範未來所有專案生成考卷、學習單、簡報或教材時，皆須符合三階審查後再輸出。
    - 更新 [`antigravity-workflow`](file:///Users/tunyuan/.gemini/config/skills/antigravity-workflow/SKILL.md) 範本，未來新專案初始化自動自帶教材審查規範。
  - **完成真實 PDF 字串精確比對引擎升級 (v2.1 Anti-Hallucination)**：
    - 升級 [`scripts/check_curriculum.py`](./scripts/check_curriculum.py)，直接讀取本機真實課習 PDF 語料進行精確 Substring 比對，杜絕概略印象的幻覺審查。
    - 在各級規則（`AGENTS.md`、`docs/review-protocol.md`、全域規則）明訂「嚴禁幻覺審查守則」。
    - 重新優化《作文句型學習單：快樂的家庭活動》，使引導好詞 100% 來自翰林四上課習真實生詞（大顯身手、大飽口福、煙霧瀰漫、彷彿等），通過實體語料庫 20/20 全數命中驗證。
  - **實施期中評量試卷 v4.0 審查檢測**：
    - 運用三階段深層比對引擎完成對 115 四上期中試卷初稿之體檢，精準診斷出「選擇題課外成語（多采多姿/垂涎三尺）」、「第六課超綱太空詞彙（毅力號/測量氣溫）」、「非生字表列字充當考點（中/正/國/小）」以及「跨大題洩題碰撞（第1大題考鷹/翔，後續題幹直接洩漏解答）」等問題，已備齊修正方針與待改清單。
  - **升級教材審查機制至 v4.0（三階段逐字逐句深層檢驗版）**：
    - **階段一（必須符合・一票否決門檻）**：落實題幹、選項（A/B/C/D、①②③④）、填空括號【】、「」逐字逐句比對本機課習 PDF。精準過濾「過去教過詞彙」、「排版分析誤判」與「字形字音幻覺/類似音類似字」。未達標直接打回重置。
    - **階段二（大部分符合・教學重點謹慎使用）**：檢驗生字考點（如第一大題寫國字注音）必須 100% 來自當冊正式課本生字表（認讀/習寫生字欄）；課文中出現但非生字表列者發出嚴格教學重點違規警告。
    - **階段三（盡力符合・邏輯適配與零洩題）**：增加跨題型邏輯與零洩題自我碰撞檢測（例如第一大題考【鷹】、【翔】，後續選擇題、改錯題嚴禁出現正字洩漏答案；考點不重複）。
    - **全域規則與 chezmoi 同步**：同步更新 AGENTS.md、全域規則 curriculum-review-protocol.md、全域技能 g4-curriculum-review 與 OpenCode 技能至 v4.0。
  - **升級四年級教材審查引擎至 v3.0（全文深度實體驗證與合法教科書真理辭典）**：
    - **問題根因修復**：先前引擎僅比對好詞庫欄位，忽略選擇題選項 `(A)(B)(C)(D)`、填空括號 `【】` 與題幹重點，且無各單元標準生字生詞字典，導致生成時常混入看似合理但未學的生詞（如「珍珠、見狀、巡視」）。
    - **全文本實體驗證**：重寫 `scripts/check_curriculum.py` 為 v3.0，深度掃描選擇題選項（全半形括號/選項符號）、填空題與好詞庫；若出現未學詞彙，系統精準標記題號與行號，列出超綱清單並**直接一票否決打回重置**。
    - **建立各科目真理辭典庫**：建立 `scripts/build_lexicon.py`，提煉出南一數、翰林國、康軒社之核心術語、課本生字、重點生詞與句型，產出 [`references/g4_genuine_textbook_lexicon.md`](./references/g4_genuine_textbook_lexicon.md) 與 `.json`，出題前作為嚴格約束真理。
    - **修正分詞滑動視窗與 Unicode \w 陷阱**：修復 Python regex `\w` 誤判中文導致語句切分失效之問題，確保自然文本與專有名詞精準匹配。
    - **全域規則與 chezmoi 同步**：同步更新至全域規則 `curriculum-review-protocol.md`、全域技能 `g4-curriculum-review` 與 OpenCode 技能，並推送到遠端儲存庫。

## 下一步待辦
1. 依據教師需求，批次補充數學（南一）、國語（翰林）、社會（康軒）之段考題庫與各單元學習單。
2. 擴充更多典型四年級迷思概念誘答題型至 `docs/review-protocol.md`。
