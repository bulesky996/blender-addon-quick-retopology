# -*- coding: utf-8 -*-
"""
Quick Retopology v2.0.0 - Operators Package
"""

from .alignment_ops import (
    COMFY_OT_auto_level_obb,
    COMFY_OT_align_selected_face,
    COMFY_OT_rotate_90_z,
    COMFY_OT_read_current_dimensions,
    COMFY_OT_swap_xy_dimensions,
)
from .shading_ops import (
    COMFY_OT_estimate_face_count,
    COMFY_OT_apply_soften_harden_now,
)
from .pipeline_op import (
    COMFY_OT_auto_retopo_furniture,
)

OPERATOR_CLASSES = [
    COMFY_OT_auto_level_obb,
    COMFY_OT_align_selected_face,
    COMFY_OT_rotate_90_z,
    COMFY_OT_read_current_dimensions,
    COMFY_OT_swap_xy_dimensions,
    COMFY_OT_estimate_face_count,
    COMFY_OT_apply_soften_harden_now,
    COMFY_OT_auto_retopo_furniture,
]

__all__ = [
    "OPERATOR_CLASSES",
    "COMFY_OT_auto_level_obb",
    "COMFY_OT_align_selected_face",
    "COMFY_OT_rotate_90_z",
    "COMFY_OT_read_current_dimensions",
    "COMFY_OT_swap_xy_dimensions",
    "COMFY_OT_estimate_face_count",
    "COMFY_OT_apply_soften_harden_now",
    "COMFY_OT_auto_retopo_furniture",
]
