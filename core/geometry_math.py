# -*- coding: utf-8 -*-
"""
Quick Retopology v2.0.0 - Core Geometry & Math
純 Python 幾何與數學運算層，不包含任何 bpy 依賴，保證可獨立單元測試。
"""

import math
from typing import List, Tuple, Sequence
from .constants import UNIT_TO_METER


def convert_length(val: float, from_unit: str, to_unit: str) -> float:
    """轉換長度單位 (支援 INCH, MM, CM, M)"""
    scale_from = UNIT_TO_METER.get(from_unit.upper(), 0.0254)
    scale_to = UNIT_TO_METER.get(to_unit.upper(), 0.0254)
    if scale_to == 0:
        return val
    meters = val * scale_from
    return meters / scale_to


def compute_aabb(points: Sequence[Sequence[float]]) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]:
    """
    從 3D 點集計算軸向對齊包圍盒 (AABB)。
    回傳: (min_point, max_point, dimensions(dx, dy, dz))
    """
    if not points:
        return ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]

    min_pt = (min(xs), min(ys), min(zs))
    max_pt = (max(xs), max(ys), max(zs))
    dims = (max_pt[0] - min_pt[0], max_pt[1] - min_pt[1], max_pt[2] - min_pt[2])
    return (min_pt, max_pt, dims)


def compute_scale_factors(current_dims: Tuple[float, float, float], target_dims: Tuple[float, float, float], eps: float = 1e-6) -> Tuple[float, float, float]:
    """計算從目前尺寸變更至目標尺寸所需的 XYZ 縮放係數"""
    sx = target_dims[0] / max(current_dims[0], eps)
    sy = target_dims[1] / max(current_dims[1], eps)
    sz = target_dims[2] / max(current_dims[2], eps)
    return (sx, sy, sz)


def rotate_point_euler_xyz(point: Tuple[float, float, float], rx_rad: float, ry_rad: float, rz_rad: float) -> Tuple[float, float, float]:
    """以純 Python 執行 Euler XYZ 順序旋轉單一 3D 點"""
    x, y, z = point

    # Rx
    cx, sx = math.cos(rx_rad), math.sin(rx_rad)
    y1 = y * cx - z * sx
    z1 = y * sx + z * cx
    x1 = x

    # Ry
    cy, sy = math.cos(ry_rad), math.sin(ry_rad)
    x2 = x1 * cy + z1 * sy
    z2 = -x1 * sy + z1 * cy
    y2 = y1

    # Rz
    cz, sz = math.cos(rz_rad), math.sin(rz_rad)
    x3 = x2 * cz - y2 * sz
    y3 = x2 * sz + y2 * cz
    z3 = z2

    return (x3, y3, z3)


def eval_point_cloud_bbox_volume(points: List[Tuple[float, float, float]], rx_deg: float, ry_deg: float, rz_deg: float) -> Tuple[float, float]:
    """
    評估點雲在指定歐拉角旋轉後的 AABB 體積與 XY 底面積。
    回傳: (volume, xy_area)
    """
    rx = math.radians(rx_deg)
    ry = math.radians(ry_deg)
    rz = math.radians(rz_deg)

    rotated = [rotate_point_euler_xyz(p, rx, ry, rz) for p in points]
    _, _, (dx, dy, dz) = compute_aabb(rotated)
    return (dx * dy * dz, dx * dy)
