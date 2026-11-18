# -*- coding: utf-8 -*-
"""
Quick Retopology v2.0.0 - Core Domain Package
純 Python 領域層匯出入口
"""

from .constants import (
    UNIT_TO_METER,
    UNIT_LABELS,
    CHANGELOG_LINES,
    PRIMARY_LOG_DIR,
    LOG_FILENAME,
)
from .logger import QuickRetopoLogger
from .geometry_math import (
    convert_length,
    compute_aabb,
    compute_scale_factors,
    rotate_point_euler_xyz,
    eval_point_cloud_bbox_volume,
)
from .telemetry import (
    calculate_recommended_faces,
    compute_adaptive_voxel_size,
    compute_qem_decimate_ratio,
    compute_instant_meshes_face_arg,
    evaluate_quadriflow_health_gate,
)

__all__ = [
    "UNIT_TO_METER",
    "UNIT_LABELS",
    "CHANGELOG_LINES",
    "PRIMARY_LOG_DIR",
    "LOG_FILENAME",
    "QuickRetopoLogger",
    "convert_length",
    "compute_aabb",
    "compute_scale_factors",
    "rotate_point_euler_xyz",
    "eval_point_cloud_bbox_volume",
    "calculate_recommended_faces",
    "compute_adaptive_voxel_size",
    "compute_qem_decimate_ratio",
    "compute_instant_meshes_face_arg",
    "evaluate_quadriflow_health_gate",
]
