# -*- coding: utf-8 -*-
"""
Quick Retopology v2.0.0 - Alignment Operators
負責模型旋轉、水平擺正、選取面對齊與尺寸讀取。
"""

import math
import bpy
import bmesh
from mathutils import Vector
from ..core.constants import UNIT_TO_METER, UNIT_LABELS
from ..adapters.bmesh_adapter import (
    get_target_mesh_object,
    focus_single_mesh_object,
    tag_redraw_all_view3d,
    get_world_aabb_and_dims,
    align_pivot_bottom_and_lock_size,
    auto_level_tilted_furniture,
)
from ..properties.retopo_props import on_dimension_prop_update


class COMFY_OT_auto_level_obb(bpy.types.Operator):
    bl_idname = "comfy_retopo.auto_level_obb"
    bl_label = "🤖 自動偵測平面擺正 (Auto-Level)"
    bl_description = "極速抽樣計算最小外接盒 (OBB)，0.01 秒把歪斜家具一鍵轉回水平與正交軸"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = get_target_mesh_object(context)
        if not obj:
            self.report({'WARNING'}, "請先點選一個 3D 家具網格模型！")
            return {'CANCELLED'}

        rx, ry, rz = auto_level_tilted_furniture(context, obj)
        self.report({'INFO'}, f"✅ 極速擺正完成！已修正傾角 X:{rx}°, Y:{ry}°, Z:{rz}° 並貼齊地面")
        return {'FINISHED'}


class COMFY_OT_align_selected_face(bpy.types.Operator):
    bl_idname = "comfy_retopo.align_selected_face"
    bl_label = "依選取面對齊方向"
    bl_description = "在編輯模式下點選 1 個面，將該面直接貼平至底部 (Z-) 或轉向正前方 (Y-)"
    bl_options = {'REGISTER', 'UNDO'}

    target_axis: bpy.props.EnumProperty(
        items=[
            ('BOTTOM', "底部貼地 (Z-)", "將選取面視為家具底面，旋轉至完全水平貼地"),
            ('TOP', "頂部朝上 (Z+)", "將選取面視為水平頂面，旋轉至水平朝上"),
            ('FRONT', "轉向正面 (Y-)", "保持水平不變，將選取面轉向正前方 (-Y)"),
        ],
        default='BOTTOM',
    )

    def execute(self, context):
        obj = get_target_mesh_object(context)
        if not obj:
            self.report({'WARNING'}, "請先點選家具模型！")
            return {'CANCELLED'}

        if context.mode != 'EDIT_MESH':
            self.report({'WARNING'}, "請先按 Tab 進入編輯模式，並點選 1 個面！")
            return {'CANCELLED'}

        bm = bmesh.from_edit_mesh(obj.data)
        selected_faces = [f for f in bm.faces if f.select]
        if not selected_faces:
            self.report({'WARNING'}, "你還沒選取任何面！請先按 3 切到面模式點選一個面。")
            return {'CANCELLED'}

        avg_normal = Vector((0.0, 0.0, 0.0))
        for f in selected_faces:
            avg_normal += f.normal * max(f.calc_area(), 1e-6)

        if avg_normal.length < 1e-6:
            avg_normal = selected_faces[0].normal.copy()
        avg_normal.normalize()

        world_rot = obj.matrix_world.to_3x3().normalized()
        world_normal = (world_rot @ avg_normal).normalized()

        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

        if self.target_axis == 'BOTTOM':
            target_vec = Vector((0.0, 0.0, -1.0))
            rot_quat = world_normal.rotation_difference(target_vec)
        elif self.target_axis == 'TOP':
            target_vec = Vector((0.0, 0.0, 1.0))
            rot_quat = world_normal.rotation_difference(target_vec)
        else:
            horiz_n = Vector((world_normal.x, world_normal.y, 0.0))
            if horiz_n.length < 1e-5:
                self.report({'WARNING'}, "選取的面幾乎完全水平，無法判斷正面朝向！")
                return {'CANCELLED'}
            horiz_n.normalize()
            target_vec = Vector((0.0, -1.0, 0.0))
            rot_quat = horiz_n.rotation_difference(target_vec)

        obj.data.transform(rot_quat.to_matrix().to_4x4())
        obj.data.update()

        align_pivot_bottom_and_lock_size(context, obj, ground_and_center=True, lock_size=False)
        self.report({'INFO'}, f"✅ 已依選取面對齊至【{self.target_axis}】並貼平地面！")
        return {'FINISHED'}


class COMFY_OT_rotate_90_z(bpy.types.Operator):
    bl_idname = "comfy_retopo.rotate_90_z"
    bl_label = "順時針轉 90°"
    bl_description = "將選取的家具繞世界 Z 軸旋轉 90 度並凍結旋轉"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = get_target_mesh_object(context)
        if not obj:
            self.report({'WARNING'}, "請先點選一個 3D 家具網格模型！")
            return {'CANCELLED'}

        was_edit = (context.mode == 'EDIT_MESH')
        focus_single_mesh_object(context, obj)
        if obj.parent is not None:
            try:
                bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
            except Exception:
                pass
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        obj.rotation_euler.z += math.radians(90.0)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        if was_edit:
            bpy.ops.object.mode_set(mode='EDIT')
        tag_redraw_all_view3d()
        self.report({'INFO'}, "已繞世界 Z 軸旋轉 90° 並凍結旋轉方向！")
        return {'FINISHED'}


class COMFY_OT_read_current_dimensions(bpy.types.Operator):
    bl_idname = "comfy_retopo.read_dimensions"
    bl_label = "讀取模型目前尺寸"
    bl_description = "讀取目前選取家具在世界座標 X、Y、Z 的真實長寬高，並填入下方欄位"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = get_target_mesh_object(context)
        if not obj:
            self.report({'WARNING'}, "請先點選一個 3D 家具網格模型！")
            return {'CANCELLED'}

        props = context.scene.comfy_retopo_props
        unit_scale = UNIT_TO_METER.get(props.size_unit, 0.0254)
        _, _, _, _, _, _, dx, dy, dz, _ = get_world_aabb_and_dims(obj)

        props.is_internal_updating = True
        try:
            props.target_width_x = round(dx / unit_scale, 2)
            props.target_depth_y = round(dy / unit_scale, 2)
            props.target_height_z = round(dz / unit_scale, 2)
        finally:
            props.is_internal_updating = False

        self.report({'INFO'}, f"已讀取目前世界座標尺寸 ({UNIT_LABELS[props.size_unit]})")
        tag_redraw_all_view3d()
        return {'FINISHED'}


class COMFY_OT_swap_xy_dimensions(bpy.types.Operator):
    bl_idname = "comfy_retopo.swap_xy_dimensions"
    bl_label = "🔀 對調 X 與 Y 目標數值"
    bl_description = "一鍵將下方輸入欄的「寬度 X」與「深度 Y」數值互換"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.comfy_retopo_props
        props.is_internal_updating = True
        try:
            old_x = props.target_width_x
            old_y = props.target_depth_y
            props.target_width_x = old_y
            props.target_depth_y = old_x
        finally:
            props.is_internal_updating = False

        if props.enable_size_lock:
            on_dimension_prop_update(props, context)

        tag_redraw_all_view3d()
        unit_label = UNIT_LABELS.get(props.size_unit, 'in')
        self.report({'INFO'}, f"🔀 已對調 X/Y 目標尺寸: X={props.target_width_x} × Y={props.target_depth_y} {unit_label}")
        return {'FINISHED'}
