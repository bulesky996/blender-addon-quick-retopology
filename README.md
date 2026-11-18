# 🧩 [Blender Add-on / Blender 插件] Quick Retopology v2 (`v2.2.1`)

> **Blender 3.6 – 4.5+ 通用插件｜一鍵讀取與調整尺寸、校準位置、智慧減面與重拓撲工具**  
> All-in-One **Blender 3.6 – 4.5+** add-on for cleaning up messy AI-generated 3D models (ComfyUI / Trellis / Tripo / Meshy) or any high-poly mesh: read & resize real-world dimensions, auto-align pivot, and run one-click decimation / quad retopology.

[![Blender](https://img.shields.io/badge/Blender-3.6%20~%204.5%2B-orange?logo=blender)](https://www.blender.org/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](./LICENSE)
[![Tests](https://img.shields.io/badge/Unit%20Tests-20%2F20%20Passed-brightgreen)](#執行單元測試-run-unit-tests)

---

## 💡 開發初衷 (Why I Built This)

當初在嘗試使用 **ComfyUI 圖像轉 3D 模型** 時，生成的模型往往面數動輒幾十萬面、佈線雜亂、軸心歪斜，而且長寬高比例也不準確。為了把這些 AI 生成的高模快速整理成乾淨、尺寸精準、可以直接投入後續流程的模型，才動手開發了這套工具。

雖然最初是因應個人工作標準而誕生，但核心功能對**任何需要清理高模、校準尺寸或快速減面的 Blender 創作者**都非常實用，因此整理開源分享給大家！

---

## ✨ 4 大核心功能 (Core Features)

### 1. 📐 讀取與即時顯示真實尺寸 (Read Dimensions & 3D Ruler)
- 一鍵讀取選取模型的真實寬 (`X`)、深 (`Y`)、高 (`Z`) 外框尺寸。
- 內建 **3D 視窗紅 / 綠 / 藍三色標尺**與浮動尺寸標籤，支援 **INCH (英吋) / MM / CM / M** 即時換算（綠色 Y 軸標尺配置於左側，不遮擋紅色 `+X` 移動軸控點）。

### 2. 🎯 重新校準位置與自動擺正 (Auto-Align & Ground Pivot)
- **自動水平擺正 (Auto-Level)**：針對生成後歪斜的模型，自動計算最小包圍盒擺正。
- **手動指定基準面**：按 `Tab` 選取任意一個面，即可一鍵將它設為模型的底面、頂面或正面。
- **軸心歸底置中**：自動將軸心點移至模型底部正中央，並貼齊世界座標 `(0, 0, 0)` 地面。

### 3. 📏 依目標尺寸重新調整模型大小 (Resize to Target Dimensions)
- 輸入想要的目標寬 (`X`)、深 (`Y`)、高 (`Z`) 數值（支援一鍵對調 X/Y），在執行清理時自動縮放至精準尺寸。
- 支援切換 **動態即時拉伸**（輸入按 Enter 立刻看變形）或 **靜態填表模式**（僅填寫數值，按主按鈕才套用）。

### 4. 🛠️ 三種減面／重拓撲方式一鍵切換 (3 Retopology / Decimation Modes)
在右側 `N 面板 (Sidebar)` 區塊 2，直接透過橫向三格按鈕依需求切換：

| 按鈕選項 | 白話說明：它是做什麼的？ | 什麼時候選它？ |
| :--- | :--- | :--- |
| **⚡ 智慧減面 (預設)** | **智慧保角減面**：底層採用 Blender 原生減面演算法，自動刪掉不重要的平坦面，把頂點全部留在銳利邊角與細節上，並把原高模的光影質感投射過來。 | **不打算大幅手動改模型**，只想要「面數壓得很低、外型與銳角幾乎跟高模一模一樣」（適合直接渲染、展示、匯出遊戲引擎）。 |
| **📐 純四邊** | **稜線對齊純四邊形**：內建瑞士蘇黎世聯邦理工學院 (ETH Zurich) 開源的 [Instant Meshes](https://github.com/wjakob/instant-meshes) 運算引擎，會順著模型的轉折線鋪出整齊的四角面，萬一邊角有小破洞還會自動用四邊形網格 (`Grid Fill`) 補平。 | **後續還需要進編輯模式手動微調**（用 `Alt+點選` 整圈選邊、加導角、拉點修型或展 UV）時的首選！ |
| **🧱 傳統減面** | **傳統體素重建重拓撲**：先把破爛或交錯的模型重新包成實心水密殼，再用 Blender 內建 QuadriFlow 重算四邊形並貼回原高模。 | 遇到**結構非常碎裂、內部充滿破洞或多部件重疊**的 AI 破模時的終極保底方案。 |

> **🎁 附加自動化整理**：內建一鍵 **Maya 風格軟硬邊**（依轉折角度自動區分平滑與銳利邊），並自動偵測貼圖／頂點色——**無貼圖白模 0 秒跳過**，有色模型自動展 UV 並透過 Cycles 烘焙 `2K / 4K` 貼圖。

---

## 📦 安裝方式 (Installation)

1. 前往右側 **[Releases](https://github.com/bulesky996/blender-addon-quick-retopology/releases)** 下載最新安裝包 `quick_retopology_v2_v2.2.1.zip`（已內建 Windows 64-bit 版 `Instant Meshes.exe`，免額外設定）。
2. 開啟 Blender（支援 `3.6` ～ `4.5+`），點選左上角：  
   `編輯 (Edit)` ➔ `偏好設定 (Preferences)` ➔ `附加元件 (Add-ons)` ➔ 右上角選單 `從磁碟安裝 (Install from Disk...)`。
3. 選擇下載的 `.zip` 檔並勾選啟用 **`Mesh: Quick Retopology v2`**。
4. 在 3D 視窗按鍵盤 **`N`** 打開右側側邊欄，切換至 **`Quick Retopology`** 分頁即可使用！

> **💡 macOS / Linux 使用者提示**：內建的 `bin/Instant Meshes.exe` 為 Windows 執行檔；若在 macOS / Linux 上使用「📐 純四邊」模式，請從 [Instant Meshes 官方頁面](https://github.com/wjakob/instant-meshes) 下載對應平台執行檔並放至插件目錄下的 `bin/Instant Meshes`。

---

## 🏗️ 專案結構與單元測試 (Architecture & Tests)

本專案將純 Python 幾何與運算邏輯 (`core/`) 與 Blender API (`adapters/`、`operators/`、`ui/`) 完全解耦，核心邏輯可在**不開啟 Blender 的環境下獨立執行單元測試**：

```text
quick_retopology_v2/
├── __init__.py                     # Add-on 註冊入口與熱重載管理
├── bin/
│   └── Instant Meshes.exe          # 內建開源 Instant Meshes 執行檔 (BSD 3-Clause)
├── core/                           # 純 Python 領域層 (零 bpy 依賴)
│   ├── constants.py                # 單位換算常數與版本更新歷程
│   ├── geometry_math.py            # 外框尺寸、縮放係數與歐拉旋轉數學
│   ├── logger.py                   # 黑盒子執行紀錄器 (輸出至系統暫存目錄)
│   └── telemetry.py                # 自適應體素、減面比例、Instant Meshes 參數與健康檢查
├── adapters/                       # Blender bpy/bmesh 與外部 CLI 轉接層
│   ├── bmesh_adapter.py            # 網格檢測、BVH 雙向法線投射、補洞與法線傳遞
│   └── instant_meshes_adapter.py   # Instant Meshes 靜默 CLI 橋接與 OBJ 交換
├── properties/
│   └── retopo_props.py             # 面板屬性狀態與單位換算回調
├── operators/
│   ├── alignment_ops.py            # 自動擺正、指定面貼齊、90° 旋轉與尺寸讀取
│   ├── pipeline_op.py              # 三引擎減面與重拓撲主流水線
│   └── shading_ops.py              # 軟硬邊設定與 Cycles 貼圖烘焙
├── ui/
│   ├── panel.py                    # N-Panel 動態三引擎按鈕式介面
│   └── viewport_ruler.py           # 3D 視窗紅/綠/藍尺寸標尺與浮動標籤
└── tests/                          # 純 Python 單元測試 (20/20 Passed)
    ├── test_geometry_math.py
    └── test_telemetry.py
```

### 執行單元測試 (Run Unit Tests)
```bash
python -m unittest discover -s tests -v
```

---

## 📝 版本更新歷程 (Changelog)

- **v2.2.1** — 🟢 Y 軸標尺移至左側避開 `+X` 移動軸控點；減面引擎改為橫向 3 格按鈕式切換與白話提示；開源標準化（GPL-3.0 + 通用說明文件 + 零本機硬編碼路徑）。
- **v2.2.0** — 推出三引擎架構：新增 `⚡ 智慧減面 (預設)` 與 `📐 純四邊 (Instant Meshes)` 引擎、自動四邊形補洞 (`Grid Fill`) 與高模法線繼承。
- **v2.1.1** — 修正 Blender QuadriFlow C++ 銳邊求解器卡死問題，導入 BVH 雙向法線投射保護。
- **v2.0.0** — Clean Architecture 模組化重構，導入純 Python 單元測試與 3D 三色尺寸標尺。

---

## 📄 授權與致謝 (License & Credits)

- **Author**：**PONG2.0** ([@bulesky996](https://github.com/bulesky996))
- **License**：Licensed under the **GNU General Public License v3.0** ([LICENSE](./LICENSE)).
- **Third-Party**：Uses **Instant Meshes** ([THIRD_PARTY_LICENSES.md](./THIRD_PARTY_LICENSES.md)).
- *Co-crafted with Antigravity AI.*
