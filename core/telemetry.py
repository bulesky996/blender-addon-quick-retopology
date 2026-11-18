# -*- coding: utf-8 -*-
"""
Quick Retopology v2.0.0 - Core Telemetry & Mesh Health Gate
純 Python 網格健康度守門員與面數估算演算法。
"""

import math
from typing import Tuple, List, Dict, Any


def compute_adaptive_voxel_size(
    surface_area: float,
    target_faces: int,
    user_voxel_size: float,
    auto_adapt: bool = True,
    oversample_factor: float = 2.0,
    min_voxel_faces: int = 30000,
    max_voxel_faces: int = 65000,
    min_voxel_size: float = 0.0015,
    max_voxel_size: float = 0.05,
) -> float:
    """
    智慧防倒掛體素大小計算 (純 Python 核心演算法)：
    依據模型表面積與目標四邊形面數，確保 Step 2 Voxel Remesh 產出的體素網格
    落在 QuadriFlow 高速甜區 (30K ~ 65K 面)，避免小模型窄凹槽被粗體素黏死，
    同時防止體素過密導致 QuadriFlow 計算卡頓。

    經驗公式：OpenVDB 曲面體素面數 N ≈ 1.3 * surface_area / (voxel_size ** 2)
    """
    clamped_user = max(min_voxel_size, min(max_voxel_size, float(user_voxel_size)))
    if not auto_adapt or surface_area <= 1e-6:
        return round(clamped_user, 5)

    desired_faces = int(max(target_faces * oversample_factor, min_voxel_faces))
    desired_faces = min(desired_faces, max_voxel_faces)

    ideal_voxel = math.sqrt((1.3 * surface_area) / float(max(desired_faces, 1000)))
    ideal_voxel = max(min_voxel_size, min(max_voxel_size, ideal_voxel))

    # 只往更精細方向保護（不把使用者手動調細的體素變粗）
    effective_voxel = min(clamped_user, ideal_voxel)
    return round(effective_voxel, 5)


def compute_qem_decimate_ratio(
    current_faces: int,
    target_faces: int,
    convert_to_quads: bool = False,
) -> float:
    """
    計算 QEM 保角減面 (Decimate Collapse) 精準比例 (純 Python)：
    - 若不轉四邊：直接依 target_faces / current_faces 計算比例。
    - 若啟用後續 Tris-to-Quads：預留 1.35x 三角面裕度，讓合併後最終面數落在目標值附近。
    """
    if current_faces <= 0 or target_faces <= 0:
        return 1.0
    effective_target = int(target_faces * 1.35) if convert_to_quads else int(target_faces)
    if current_faces <= effective_target:
        return 1.0
    ratio = float(effective_target) / float(current_faces)
    return max(0.001, min(1.0, round(ratio, 6)))


def compute_instant_meshes_face_arg(target_faces: int) -> int:
    """
    計算 Instant Meshes CLI 的 `-f` 參數值 (純 Python)：
    Instant Meshes 在純四邊形模式 (-r 4 -p 4，不加 -D) 提取網格時會將每個四邊單元
    細分 2×2 (實際輸出面數約為 `-f` 的 4 倍)，因此傳入 target_faces / 4 即可精準命中目標面數。
    """
    safe_target = max(500, int(target_faces))
    return max(125, int(round(safe_target / 4.0)))


def calculate_recommended_faces(
    total_edges: int,
    sharp_edges: int,
    bottom_edges: int,
    bottom_sharp_edges: int,
) -> int:
    """
    智慧面數估算核心演算法 (純 Python 實作)：
    依銳邊比例 (Sharp Ratio) 與底層椅腳密集度 (Foot Density) 推算最佳四邊形面數。
    """
    if total_edges <= 0:
        return 8000

    sharp_ratio = sharp_edges / max(total_edges, 1)
    foot_density_ratio = bottom_edges / max(total_edges, 1)

    complexity_score = min((sharp_ratio * 7.5) + (foot_density_ratio * 2.5), 1.0)
    recommended_faces = int(8000 + complexity_score * 12000)

    # 若椅腳有密集銳邊結構，拉高保底面數至 12,500
    if bottom_sharp_edges > 20 and recommended_faces < 12000:
        recommended_faces = 12500

    recommended_faces = int(round(recommended_faces / 500.0) * 500)
    return max(4000, min(25000, recommended_faces))


def evaluate_quadriflow_health_gate(
    base_stats: Dict[str, Any],
    current_stats: Dict[str, Any],
    target_faces: int,
) -> Tuple[bool, List[str]]:
    """
    幾何完整性守門員 (Mesh Health Gate) 驗證核心演算法：
    1. 面數必須落在 [target_faces * 0.68, target_faces * 1.48 + 600] 內
    2. 開放破洞邊界率 (boundary_ratio) 必須 <= 0.8%
    3. 外框尺寸 (X, Y, Z) 保留率各 >= 88%
    4. 總表面積保留率 >= 78%
    """
    now_faces = current_stats.get("faces", 0)
    base_faces = base_stats.get("faces", 0)

    min_ok = max(int(target_faces * 0.68), 250)
    max_ok = int(target_faces * 1.48) + 600

    base_bbox = base_stats.get("bbox", (1.0, 1.0, 1.0))
    curr_bbox = current_stats.get("bbox", (0.0, 0.0, 0.0))

    bx_ratio = curr_bbox[0] / max(base_bbox[0], 1e-4)
    by_ratio = curr_bbox[1] / max(base_bbox[1], 1e-4)
    bz_ratio = curr_bbox[2] / max(base_bbox[2], 1e-4)

    base_area = max(base_stats.get("area", 1.0), 1e-4)
    curr_area = current_stats.get("area", 0.0)
    area_ratio = curr_area / base_area

    b_edges = current_stats.get("boundary_edges", 0)
    b_ratio = current_stats.get("boundary_ratio", 0.0)
    base_b_edges = base_stats.get("boundary_edges", 0)

    reasons = []
    if now_faces == base_faces and now_faces > 0:
        reasons.append(f"面數未改變 ({now_faces})")
    if now_faces < min_ok or now_faces > max_ok:
        reasons.append(f"面數偏離目標 ({now_faces:,} 不在 {min_ok:,}~{max_ok:,})")
    if b_ratio > 0.008 and b_edges > base_b_edges + 15:
        reasons.append(f"發生破洞撕裂 (開放邊={b_edges}, 佔比={b_ratio*100:.2f}%)")
    if bx_ratio < 0.88 or by_ratio < 0.88 or bz_ratio < 0.88:
        reasons.append(f"外框尺寸縮水 (X={bx_ratio*100:.0f}%, Y={by_ratio*100:.0f}%, Z={bz_ratio*100:.0f}%)")
    if area_ratio < 0.78:
        reasons.append(f"表面積大量流失 (僅剩 {area_ratio*100:.1f}%)")

    is_ok = (len(reasons) == 0)
    return is_ok, reasons
