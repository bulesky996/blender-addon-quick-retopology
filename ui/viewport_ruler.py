# -*- coding: utf-8 -*-
"""
Quick Retopology v2.0.0 - Viewport Ruler
3D 視窗即時三色工程尺寸標尺與 2D 浮動標籤 (GPU + BLF 渲染)。
"""

import bpy
import gpu
import blf
from mathutils import Vector
from gpu_extras.batch import batch_for_shader
from bpy_extras.view3d_utils import location_3d_to_region_2d
from ..core.constants import UNIT_TO_METER, UNIT_LABELS
from ..adapters.bmesh_adapter import get_target_mesh_object, get_world_aabb_and_dims

_draw_handle_3d = None
_draw_handle_2d = None


def get_uniform_color_shader():
    try:
        return gpu.shader.from_builtin('UNIFORM_COLOR')
    except Exception:
        return gpu.shader.from_builtin('3D_UNIFORM_COLOR')


def draw_viewport_dimension_lines_3d():
    context = bpy.context
    if not context or not getattr(context, "scene", None):
        return
    props = getattr(context.scene, "comfy_retopo_props", None)
    if not props or not getattr(props, "show_viewport_dimensions", True):
        return

    obj = get_target_mesh_object(context)
    if not obj or obj.type != 'MESH':
        return

    try:
        min_x, max_x, min_y, max_y, min_z, max_z, dx, dy, dz, pad = get_world_aabb_and_dims(obj)
        shader = get_uniform_color_shader()

        c000 = Vector((min_x, min_y, min_z))
        c100 = Vector((max_x, min_y, min_z))
        c110 = Vector((max_x, max_y, min_z))
        c010 = Vector((min_x, max_y, min_z))
        c001 = Vector((min_x, min_y, max_z))
        c101 = Vector((max_x, min_y, max_z))
        c111 = Vector((max_x, max_y, max_z))
        c011 = Vector((min_x, max_y, max_z))

        cage_lines = [
            c000, c100, c100, c110, c110, c010, c010, c000,
            c001, c101, c101, c111, c111, c011, c011, c001,
            c000, c001, c100, c101, c110, c111, c010, c011,
        ]

        # 🔴 X 軸
        px0 = Vector((min_x, min_y - pad, min_z))
        px1 = Vector((max_x, min_y - pad, min_z))
        x_lines = [px0, px1, c000, px0, c100, px1]

        # 🟢 Y 軸 (v2.2.1: 移至左側 min_x - pad，徹底避開右側 +X 紅色移動軸 Gizmo)
        py0 = Vector((min_x - pad, min_y, min_z))
        py1 = Vector((min_x - pad, max_y, min_z))
        y_lines = [py0, py1, c000, py0, c010, py1]

        # 🔵 Z 軸
        pz0 = Vector((min_x - pad, min_y - pad, min_z))
        pz1 = Vector((min_x - pad, min_y - pad, max_z))
        z_lines = [pz0, pz1, c000, pz0, c001, pz1]

        gpu.state.blend_set('ALPHA')

        gpu.state.line_width_set(1.2)
        shader.bind()
        shader.uniform_float("color", (0.90, 0.92, 0.96, 0.30))
        batch_cage = batch_for_shader(shader, 'LINES', {"pos": cage_lines})
        batch_cage.draw(shader)

        # 🔴 X
        gpu.state.line_width_set(3.2)
        shader.uniform_float("color", (1.0, 0.22, 0.25, 0.96))
        batch_x = batch_for_shader(shader, 'LINES', {"pos": x_lines})
        batch_x.draw(shader)

        # 🟢 Y
        shader.uniform_float("color", (0.20, 0.92, 0.36, 0.96))
        batch_y = batch_for_shader(shader, 'LINES', {"pos": y_lines})
        batch_y.draw(shader)

        # 🔵 Z
        shader.uniform_float("color", (0.25, 0.68, 1.0, 0.96))
        batch_z = batch_for_shader(shader, 'LINES', {"pos": z_lines})
        batch_z.draw(shader)

    except Exception:
        pass
    finally:
        try:
            gpu.state.line_width_set(1.0)
            gpu.state.blend_set('NONE')
        except Exception:
            pass


def draw_viewport_dimension_labels_2d():
    context = bpy.context
    if not context or not getattr(context, "scene", None):
        return
    props = getattr(context.scene, "comfy_retopo_props", None)
    if not props or not getattr(props, "show_viewport_dimensions", True):
        return

    obj = get_target_mesh_object(context)
    if not obj or obj.type != 'MESH':
        return

    region = getattr(context, "region", None)
    rv3d = getattr(context, "region_data", None)
    if not region or not rv3d:
        return

    try:
        min_x, max_x, min_y, max_y, min_z, max_z, dx, dy, dz, pad = get_world_aabb_and_dims(obj)
        u_scale = UNIT_TO_METER.get(props.size_unit, 0.0254)
        unit_suffix = UNIT_LABELS.get(props.size_unit, 'in')

        val_x = dx / u_scale
        val_y = dy / u_scale
        val_z = dz / u_scale

        mid_x = Vector(((min_x + max_x) * 0.5, min_y - pad * 1.15, min_z))
        mid_y = Vector((min_x - pad * 1.15, (min_y + max_y) * 0.5, min_z))
        mid_z = Vector((min_x - pad * 1.15, min_y - pad * 1.15, (min_z + max_z) * 0.5))

        labels = [
            (mid_x, f"X (寬): {val_x:.2f} {unit_suffix}", (1.0, 0.42, 0.42, 1.0), (0.55, 0.08, 0.08, 0.85)),
            (mid_y, f"Y (深): {val_y:.2f} {unit_suffix}", (0.40, 1.0, 0.52, 1.0), (0.06, 0.42, 0.14, 0.85)),
            (mid_z, f"Z (高): {val_z:.2f} {unit_suffix}", (0.48, 0.82, 1.0, 1.0), (0.08, 0.28, 0.55, 0.85)),
        ]

        font_id = 0
        try:
            blf.size(font_id, 15)
        except TypeError:
            blf.size(font_id, 15, 72)

        shader_2d = get_uniform_color_shader()
        gpu.state.blend_set('ALPHA')

        for pos_3d, text_str, text_col, bg_col in labels:
            pos_2d = location_3d_to_region_2d(region, rv3d, pos_3d)
            if not pos_2d:
                continue

            tw, th = blf.dimensions(font_id, text_str)
            x0 = pos_2d.x - tw * 0.5 - 7
            y0 = pos_2d.y - th * 0.5 - 5
            x1 = pos_2d.x + tw * 0.5 + 7
            y1 = pos_2d.y + th * 0.5 + 5

            verts_bg = [
                (x0, y0, 0.0), (x1, y0, 0.0), (x1, y1, 0.0),
                (x0, y0, 0.0), (x1, y1, 0.0), (x0, y1, 0.0),
            ]
            shader_2d.bind()
            shader_2d.uniform_float("color", bg_col)
            batch_bg = batch_for_shader(shader_2d, 'TRIS', {"pos": verts_bg})
            batch_bg.draw(shader_2d)

            blf.position(font_id, pos_2d.x - tw * 0.5 + 1, pos_2d.y - th * 0.5 - 1, 0)
            blf.color(font_id, 0.0, 0.0, 0.0, 0.9)
            blf.draw(font_id, text_str)

            blf.position(font_id, pos_2d.x - tw * 0.5, pos_2d.y - th * 0.5, 0)
            blf.color(font_id, text_col[0], text_col[1], text_col[2], text_col[3])
            blf.draw(font_id, text_str)

    except Exception:
        pass
    finally:
        try:
            gpu.state.blend_set('NONE')
        except Exception:
            pass


def init_viewport_ruler():
    global _draw_handle_3d, _draw_handle_2d
    if _draw_handle_3d is None:
        _draw_handle_3d = bpy.types.SpaceView3D.draw_handler_add(
            draw_viewport_dimension_lines_3d, (), 'WINDOW', 'POST_VIEW'
        )
    if _draw_handle_2d is None:
        _draw_handle_2d = bpy.types.SpaceView3D.draw_handler_add(
            draw_viewport_dimension_labels_2d, (), 'WINDOW', 'POST_PIXEL'
        )


def cleanup_viewport_ruler():
    global _draw_handle_3d, _draw_handle_2d
    if _draw_handle_3d is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handle_3d, 'WINDOW')
        _draw_handle_3d = None
    if _draw_handle_2d is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handle_2d, 'WINDOW')
        _draw_handle_2d = None
