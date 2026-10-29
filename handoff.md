# 交接與進度記錄 (handoff.md)

## 專案狀態
- **日期**：2026-10-04
- **目前進度**：
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

  - **升級四年級教材審查引擎至 v3.0（全文深度實體驗證與合法教科書真理辭典）**：
    - **問題根因修復**：先前引擎僅比對好詞庫欄位，忽略選擇題選項 (A)(B)(C)(D)、填空括號 【】 與題幹重點，且無各單元標準生字生詞字典，導致生成時常混入看似合理但未學的生詞（如「珍珠、見狀、巡視」）。
    - **全文本實體驗證**：重寫 scripts/check_curriculum.py 為 v3.0，深度掃描選擇題選項（全半形括號/選項符號）、填空題與好詞庫；若出現未學詞彙，系統精準標記題號與行號，列出超綱清單並**直接一票否決打回重置**。
    - **建立各科目真理辭典庫**：建立 scripts/build_lexicon.py，提煉出南一數、翰林國、康軒社之核心術語、課本生字、重點生詞與句型，產出 
eferences/g4_genuine_textbook_lexicon.md 與 .json，出題前作為嚴格約束真理。
    - **修正分詞滑動視窗與 Unicode \w 陷阱**：修復 Python regex \w 誤判中文導致語句切分失效之問題，確保自然文本與專有名詞精準匹配。
    - **全域規則與 chezmoi 同步**：同步更新至全域規則 curriculum-review-protocol.md、全域技能 g4-curriculum-review 與 OpenCode 技能，並推送到遠端儲存庫。

## 下一步待辦
1. 依據教師需求，批次補充數學（南一）、國語（翰林）、社會（康軒）之段考題庫與各單元學習單。
2. 擴充更多典型四年級迷思概念誘答題型至 `docs/review-protocol.md`。
