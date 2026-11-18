# -*- coding: utf-8 -*-
"""
Quick Retopology v2.0.0 - Adapters Package
"""

from .bmesh_adapter import (
    tag_redraw_all_view3d,
    get_target_mesh_object,
    focus_single_mesh_object,
    get_world_aabb_and_dims,
    inspect_mesh_telemetry,
    estimate_smart_face_count,
    align_pivot_bottom_and_lock_size,
    keep_only_largest_outer_shell,
    check_model_has_color,
    auto_level_tilted_furniture,
    mark_structural_sharp_edges,
    project_mesh_onto_high_poly,
    close_boundary_loops_quad_grid,
    transfer_high_poly_normals,
)
from .instant_meshes_adapter import (
    find_instant_meshes_executable,
    run_instant_meshes_remesh,
)

__all__ = [
    "tag_redraw_all_view3d",
    "get_target_mesh_object",
    "focus_single_mesh_object",
    "get_world_aabb_and_dims",
    "inspect_mesh_telemetry",
    "estimate_smart_face_count",
    "align_pivot_bottom_and_lock_size",
    "keep_only_largest_outer_shell",
    "check_model_has_color",
    "auto_level_tilted_furniture",
    "mark_structural_sharp_edges",
    "project_mesh_onto_high_poly",
    "close_boundary_loops_quad_grid",
    "transfer_high_poly_normals",
    "find_instant_meshes_executable",
    "run_instant_meshes_remesh",
]
