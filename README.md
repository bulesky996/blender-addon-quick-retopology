# 🛋️ Quick Retopology v2 (`v2.2.1`)

> **One-Click Tri-Engine Retopology, Dimension Locking & 3D Ruler Add-on for Blender 3.6 – 4.5+**  
> 專為 AI 生成 3D 模型（ComfyUI / Trellis / Tripo / Meshy）與電商家具產線打造的一鍵清洗、減面重拓撲、真實尺寸鎖定與貼圖烘焙工具。

[![Blender](https://img.shields.io/badge/Blender-3.6%20~%204.5%2B-orange?logo=blender)](https://www.blender.org/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](./LICENSE)
[![Architecture](https://img.shields.io/badge/Architecture-Clean%20Architecture-brightgreen)](#architecture--架構設計)

---

## ✨ 核心特色 (Key Features)

### 🚀 1. 三引擎一鍵按鈕式切換 (Tri-Engine Switcher)
不用再二選一！在 `N 面板 (Sidebar)` 區塊 2 直接以橫向三格按鈕切換最合適的處理引擎：

| 引擎模式 (Engine) | 定位與強項 (Best For) | 實測速度 (Speed) | 結構與夾角特色 (Quality) |
| :--- | :--- | :---: | :--- |
| **⚡ QEM 保真 (預設)** | 電商展示、WebGL/GLB、渲染、遊戲引擎 | `~3–5 秒` | **99.96%** 保留原始銳利凹槽與細節 + 繼承原高模光影法線 (`Data Transfer`) |
| **📐 純四邊 (Instant Meshes)** | 需進編輯模式 `Alt+Click` 微調、展 UV | `~3 秒` | 全品類家具適用！內建 ETH Zurich 開源特徵對齊 + `Grid Fill` 補洞，產出 **100% 純四邊形** |
| **🧱 體素保底 (QuadriFlow)** | 多部件交錯、內部充滿破洞的 AI 爛模 | `~10–30 秒` | 智慧防倒掛體素 + BVH 雙向法線投射 + 四階段幾何守門員保底 |

### 📐 2. 電商真實尺寸鎖定與 3D 三色標尺 (Real-World Size Lock & 3D Ruler)
- 支援 **INCH (小數英吋) / MM / CM / M** 即時單位換算與 X/Y 對調。
- 內建 **3D 視窗紅 (X 寬) / 綠 (Y 深) / 藍 (Z 高) 即時工程標尺**（綠色 Y 標尺位於左側，徹底避開右側紅色 `+X` 移動軸控點）。
- 支援 **Auto-Level 歪斜自動擺正**、手動指定底面／頂面／正面，以及一鍵軸心歸底貼地 `(0, 0, 0)`。

### 🎨 3. 自動軟硬邊與貼圖烘焙 (Maya Soften/Harden & Auto Texture Bake)
- 內建 **Maya 風格軟硬邊**，依二面轉折角度自動切換軟邊與硬邊。
- 自動偵測模型是否帶有材質貼圖或頂點色：**白模 0 秒跳過**，有色模型自動展 UV 並透過 Cycles 快速烘焙 `2K / 4K` 貼圖。

---

## 📦 安裝方式 (Installation)

1. 前往本倉庫的 **Releases** 頁面下載最新安裝包 `quick_retopology_v2_v2.2.1.zip`（已內建 Windows 版 `Instant Meshes.exe`，免額外設定）。
2. 開啟 Blender（支援 `3.6` ～ `4.5+`），前往左上角：  
   `編輯 (Edit)` ➔ `偏好設定 (Preferences)` ➔ `附加元件 (Add-ons)` ➔ 右上角選單 `從磁碟安裝 (Install from Disk...)`。
3. 選擇下載的 `.zip` 檔並勾選啟用 **`Mesh: Quick Retopology v2`**。
4. 在 3D 視窗按鍵盤 **`N`** 打開右側側邊欄，切換至 **`Quick Retopology`** 分頁即可使用！

> **💡 macOS / Linux 使用者提示**：內建的 `bin/Instant Meshes.exe` 為 Windows 64-bit 執行檔；若在 macOS / Linux 上使用「📐 純四邊」模式，請從 [Instant Meshes 官方頁面](https://github.com/wjakob/instant-meshes) 下載對應平台執行檔並放至插件目錄下的 `bin/Instant Meshes`。

---

## 🏗️ 架構設計 (Clean Architecture)

本專案採用純 Python 領域層與 Blender API 完全解耦的模組化架構，核心幾何與健康度邏輯可在**不啟動 Blender 的環境下執行純 Python 單元測試**：

```text
quick_retopology_v2/
├── __init__.py                     # Add-on 註冊入口與熱重載管理
├── bin/
│   └── Instant Meshes.exe          # 內建 ETH Zurich 開源特徵對齊執行檔 (BSD 3-Clause)
├── core/                           # 純 Python 領域層 (零 bpy 依賴)
│   ├── constants.py                # 單位換算常數與版本更新歷程
│   ├── geometry_math.py            # AABB、縮放係數與歐拉旋轉數學
│   ├── logger.py                   # 黑盒子執行紀錄器 (輸出至系統暫存目錄)
│   └── telemetry.py                # 自適應體素、QEM 比例、Instant Meshes 參數與健康守門員
├── adapters/                       # Blender bpy/bmesh 與外部 CLI 轉接層
│   ├── bmesh_adapter.py            # 網格遙測、BVH 雙向法線投射、Grid Fill 補洞、高模法線傳遞
│   └── instant_meshes_adapter.py   # Instant Meshes 靜默 CLI 橋接與 OBJ 交換
├── properties/
│   └── retopo_props.py             # PropertyGroup 狀態管理與單位換算回調
├── operators/
│   ├── alignment_ops.py            # OBB 擺正、指定面貼齊、90° 旋轉與尺寸讀取
│   ├── pipeline_op.py              # 三引擎重拓撲主流水線
│   └── shading_ops.py              # Maya 軟硬邊與 Cycles 貼圖烘焙
├── ui/
│   ├── panel.py                    # N-Panel 動態三引擎按鈕式介面
│   └── viewport_ruler.py           # GPU + BLF 3D 彩色尺寸標尺與標籤
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

- **v2.2.1** — 🟢 Y 軸標尺移至左側避開 `+X` 移動軸 Gizmo；減面引擎升級為橫向 3 格按鈕式切換與動態提示；清除本機路徑並整理為標準開源規格。
- **v2.2.0** — 正式推出三引擎旗艦架構：新增 `⚡ QEM 高模保真 (預設)` 與 `📐 Instant Meshes 全品類純四邊形` 引擎、`Grid Fill` 純四邊補洞與高模法線繼承。
- **v2.1.1** — 根治 Blender QuadriFlow C++ 銳邊求解器死鎖問題，優化體素甜區並保留 BVH 雙向法線投射。
- **v2.0.0** — Clean Architecture 模組化重構，導入純 Python 單元測試與 3D 三色標尺。

---

## 📄 授權與致謝 (License & Credits)

- **Author**：**PONG2.0** ([@bulesky996](https://github.com/bulesky996))
- **License**：Licensed under the **GNU General Public License v3.0** ([LICENSE](./LICENSE)).
- **Third-Party**：Uses **Instant Meshes** by ETH Zurich ([THIRD_PARTY_LICENSES.md](./THIRD_PARTY_LICENSES.md)).
- *Co-crafted with Antigravity AI.*
