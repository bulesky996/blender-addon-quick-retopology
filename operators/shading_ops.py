# -*- coding: utf-8 -*-
"""
Quick Retopology v2.0.0 - Shading & Baking Operators
負責 Maya 風格軟硬邊處理、智慧面數估算與材質貼圖烘焙。
"""

import math
import bpy
import bmesh
from ..adapters.bmesh_adapter import (
    get_target_mesh_object,
    focus_single_mesh_object,
    estimate_smart_face_count,
)


def apply_maya_soften_harden_edges(context, obj, angle_deg=35.0):
    """Maya 風格 Soften / Harden Edges (依轉折角度自動標記軟硬邊)"""
    focus_single_mesh_object(context, obj)
    angle_rad = math.radians(angle_deg)

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    for f in bm.faces:
        f.smooth = True

    for e in bm.edges:
        if len(e.link_faces) == 2:
            if e.calc_face_angle(0.0) >= angle_rad:
                e.smooth = False  # Hard Edge (硬邊)
            else:
                e.smooth = True   # Soft Edge (軟邊)
        else:
            e.smooth = False

    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()

    bpy.ops.object.shade_smooth()

    if hasattr(bpy.ops.object, "shade_smooth_by_angle"):
        try:
            bpy.ops.object.shade_smooth_by_angle(angle=angle_rad, keep_sharp_edges=True)
        except Exception:
            pass
    elif hasattr(obj.data, "use_auto_smooth"):
        obj.data.use_auto_smooth = True
        obj.data.auto_smooth_angle = angle_rad


def bake_color_from_high_to_low(context, high_obj, low_obj, color_mode, resolution=2048):
    """自動展 UV 與高低模貼圖烘焙 (Cycles Selected to Active)"""
    scene = context.scene
    prev_engine = scene.render.engine

    try:
        if color_mode == 'VERTEX_COLOR':
            if len(high_obj.data.materials) == 0 or high_obj.data.materials[0] is None:
                vc_mat = bpy.data.materials.new(name="HighPoly_VertexColor_Mat")
                vc_mat.use_nodes = True
                high_obj.data.materials.append(vc_mat)
            else:
                vc_mat = high_obj.data.materials[0]
                vc_mat.use_nodes = True

            nodes = vc_mat.node_tree.nodes
            links = vc_mat.node_tree.links
            bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if bsdf:
                attr_node = nodes.new(type='ShaderNodeVertexColor')
                if high_obj.data.color_attributes.active_color:
                    attr_node.layer_name = high_obj.data.color_attributes.active_color.name
                links.new(attr_node.outputs['Color'], bsdf.inputs['Base Color'])

        focus_single_mesh_object(context, low_obj)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.02)
        bpy.ops.object.mode_set(mode='OBJECT')

        img_name = f"{low_obj.name}_Baked_{resolution}"
        bake_img = bpy.data.images.new(img_name, width=resolution, height=resolution, alpha=False)

        low_mat = bpy.data.materials.new(name=f"{low_obj.name}_Mat")
        low_mat.use_nodes = True
        low_obj.data.materials.clear()
        low_obj.data.materials.append(low_mat)

        nodes = low_mat.node_tree.nodes
        links = low_mat.node_tree.links
        bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)

        tex_node = nodes.new(type='ShaderNodeTexImage')
        tex_node.image = bake_img
        nodes.active = tex_node

        scene.render.engine = 'CYCLES'
        try:
            scene.cycles.device = 'GPU'
        except Exception:
            pass
        scene.cycles.samples = 1
        scene.cycles.bake_type = 'DIFFUSE'
        scene.render.bake.use_pass_direct = False
        scene.render.bake.use_pass_indirect = False
        scene.render.bake.use_pass_color = True
        scene.render.bake.use_selected_to_active = True
        scene.render.bake.cage_extrusion = max(low_obj.dimensions.length * 0.02, 0.01)

        bpy.ops.object.select_all(action='DESELECT')
        high_obj.select_set(True)
        low_obj.select_set(True)
        context.view_layer.objects.active = low_obj

        bpy.ops.object.bake(type='DIFFUSE')

        if bsdf:
            links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])

        return True
    except Exception as e:
        print(f"[QuickRetopo v2] 貼圖烘焙發生例外已略過: {e}")
        return False
    finally:
        scene.render.engine = prev_engine


class COMFY_OT_estimate_face_count(bpy.types.Operator):
    bl_idname = "comfy_retopo.estimate_faces"
    bl_label = "🧠 智慧估算最佳面數並填入"
    bl_description = "掃描模型的轉折邊與椅腳密度，自動算出建議面數並填入下方自定義欄位"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = get_target_mesh_object(context)
        if not obj:
            self.report({'WARNING'}, "請先點選一個 3D 家具網格模型！")
            return {'CANCELLED'}

        est = estimate_smart_face_count(obj)
        context.scene.comfy_retopo_props.target_face_count = est
        self.report({'INFO'}, f"🧠 智慧分析完成！建議目標面數為 {est:,} 面")
        return {'FINISHED'}


class COMFY_OT_apply_soften_harden_now(bpy.types.Operator):
    bl_idname = "comfy_retopo.apply_soften_harden"
    bl_label = "✨ 立即套用軟硬邊 (Soften/Harden)"
    bl_description = "大於指定角度的邊設為硬邊 (Hard)，小於的設為軟邊 (Soft)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = get_target_mesh_object(context)
        if not obj:
            self.report({'WARNING'}, "請先點選一個 3D 家具網格模型！")
            return {'CANCELLED'}

        props = context.scene.comfy_retopo_props
        apply_maya_soften_harden_edges(context, obj, angle_deg=props.soft_hard_angle)
        self.report({'INFO'}, f"已套用 Maya 風格軟硬邊（閥值 {props.soft_hard_angle}°）")
        return {'FINISHED'}
