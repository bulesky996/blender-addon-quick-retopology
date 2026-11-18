# -*- coding: utf-8 -*-
"""
Quick Retopology v2.0.0 - Core Constants
純 Python 常數定義層，嚴禁依賴 bpy。
"""

UNIT_TO_METER = {
    'INCH': 0.0254,
    'MM': 0.001,
    'CM': 0.01,
    'M': 1.0,
}

UNIT_LABELS = {
    'INCH': 'in',
    'MM': 'mm',
    'CM': 'cm',
    'M': 'm',
}

CHANGELOG_LINES = [
    "v2.2.1 (介面體驗優化版) - 🎨 防遮擋標尺 + 按鈕式引擎切換",
    " • 🟢 Y 軸 (深度) 3D 標尺與標籤改至左側顯示，徹底避開右側 +X 紅色移動軸 Gizmo",
    " • 減面引擎改為橫向 3 格常駐高亮按鈕 (⚡ QEM保真 / 📐 純四邊 / 🧱 體素保底) + 動態白話說明",
    "v2.2.0 (三引擎全品類旗艦版) - 🚀 QEM 保真預設 + Instant Meshes 純四邊形",
    " • 新增三引擎切換：⚡ QEM 高模保真 (預設) / 📐 Instant Meshes 純四邊形 / 🧱 QuadriFlow",
    " • QEM 保真引擎：99.96% 保留銳利夾角與本體結構 + 繼承高模光影法線 (3~5秒極速)",
    " • 內建 ETH Zurich Instant Meshes：全品類 100% 純四邊形 + Grid Fill 零破洞 + 30° 銳角對齊",
    " • 維持 Clean Architecture 分層架構，新增 instant_meshes_adapter 與完整單元測試",
    "v2.1.1 (零死鎖極速夾角版) - ⚡ 根治 QuadriFlow C++ 銳邊求解器卡死",
    " • 拔除進 QuadriFlow 前的體素鋸齒銳邊硬約束，改由曲率對齊極速出圖 (3~8秒)",
    " • 優化智慧體素面數甜區 (30K~65K)，兼顧深凹夾角解析度與重拓撲流暢度",
    " • 保留 BVH 雙向法線投射壓回深凹夾角 + 跨溝法線攔截保護",
    "v2.1.0 (銳利夾角保護版) - 🔪 根治凹槽橋接與鋸齒破面",
    " • 智慧體素防黏死保護 (Adaptive Voxel)：依表面積與目標面數自動細化體素，杜絕凹槽黏死",
    " • 重拓撲前夾角還原與連續銳邊鎖定：進 QuadriFlow 前自動壓回深凹夾角並標記 Sharp Edge",
    " • 升級 BVH 雙向法線投射 Shrinkwrap：精準落入 V 型凹槽頂點，杜絕跨溝鋸齒窗簾",
    "v2.0.0 (Clean Architecture 重構版) - 🏗️ 模組化分層架構",
    " • 幾何運算與 bpy 完全解耦，支援純 Python 單元測試 (pytest/unittest)",
    " • UI Panel 效能最佳化，移除 draw() 耗時重算，改用屬性快取機制",
    " • 移除頂部狀態區重複按鈕，統一由底部主按鈕一鍵觸發",
    " • 模組自動註冊器與安全熱重載機制",
    "v1.3.9 - 🧹 移除頂部重複按鈕，介面精簡直覺",
    "v1.3.8 - ⚡ 極簡拉伸開關 + 純矩陣穿透父層",
    "v1.3.7 - 🎯 頂部尺寸/3D標尺/下方輸入 100% 對齊世界軸",
    "v1.3.6 - 📐 3D 視窗紅(X)/綠(Y)/藍(Z)尺規與對調鈕",
    "v1.3.5 - 🛡️ 桌類防破面守門員 + 防飛刺鎖 + 黑盒子 Log",
]

PRIMARY_LOG_DIR = ""
LOG_FILENAME = "Quick_Retopology_LastRun.log"
