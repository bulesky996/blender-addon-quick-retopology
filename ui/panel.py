# -*- coding: utf-8 -*-
"""
Quick Retopology v2.0.0 - Main UI Panel
N-Panel 側邊欄面板介面定義 (純表現層)。
"""

import bpy
from ..core.constants import UNIT_LABELS, UNIT_TO_METER, CHANGELOG_LINES
from ..adapters.bmesh_adapter import get_target_mesh_object, get_world_aabb_and_dims


class COMFY_PT_furniture_retopo_panel(bpy.types.Panel):
    """Quick Retopology 主控制面板 (View3D > Sidebar > Quick Retopology)"""
    bl_label = "🛋️ Quick Retopology v2.2.1"
    bl_idname = "COMFY_PT_furniture_retopo_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Quick Retopology"

    def draw(self, context):
        layout = self.layout
        props = context.scene.comfy_retopo_props
        obj = get_target_mesh_object(context)
        unit_suffix = UNIT_LABELS.get(props.size_unit, 'in')
        u_scale = UNIT_TO_METER.get(props.size_unit, 0.0254)

        # 頂部：版本號與更新歷程展開盒 + 當前選取模型狀態
        header_box = layout.box()
        row_ver = header_box.row(align=True)
        row_ver.label(text="版本: v2.2.1 (✨ 介面體驗優化版)", icon='CHECKMARK')
        row_ver.prop(
            props,
            "show_changelog",
            text="更新歷程",
            icon='TRIA_DOWN' if props.show_changelog else 'TRIA_RIGHT',
            emboss=True,
        )
        if props.show_changelog:
            log_col = header_box.column(align=True)
            for line in CHANGELOG_LINES:
                log_col.label(text=line)

        if obj:
            poly_count = len(obj.data.polygons)
            quad_count = sum(1 for p in obj.data.polygons if len(p.vertices) == 4)
            quad_pct = (quad_count / max(poly_count, 1)) * 100.0
            header_box.label(
                text=f"已鎖定: {obj.name} ({poly_count:,} 面 | 四邊形 {quad_pct:.0f}%)",
                icon='MESH_DATA',
            )

            _, _, _, _, _, _, dx, dy, dz, _ = get_world_aabb_and_dims(obj)
            cur_w = dx / u_scale
            cur_d = dy / u_scale
            cur_h = dz / u_scale

            dim_box = header_box.box()
            dim_box.label(
                text=f"📐 目前實際外框尺寸 ({unit_suffix}):",
                icon='DRIVER_DISTANCE',
            )
            row_xyz = dim_box.row(align=True)
            row_xyz.label(text=f"🔴 X(寬): {cur_w:.2f}")
            row_xyz.label(text=f"🟢 Y(深): {cur_d:.2f}")
            row_xyz.label(text=f"🔵 Z(高): {cur_h:.2f}")

            dim_box.prop(
                props,
                "show_viewport_dimensions",
                text="👁️ 在 3D 視窗顯示紅(X)/綠(Y)/藍(Z)標尺",
                toggle=True,
            )
        else:
            header_box.label(text="請在視窗點選一個 3D 家具模型", icon='ERROR')

        # 區塊 0：歪斜模型水平擺正
        box0 = layout.box()
        box0.label(text="0. 歪斜模型水平擺正 (選用)", icon='ORIENTATION_GLOBAL')
        row_lvl = box0.row(align=True)
        row_lvl.operator("comfy_retopo.auto_level_obb", icon='MOD_ARRAY')

        box0.label(text="手動指定面 (按 Tab 選 1 個面後點選):")
        row_face = box0.row(align=True)
        op_btm = row_face.operator("comfy_retopo.align_selected_face", text="🎯 設為底部")
        op_btm.target_axis = 'BOTTOM'
        op_top = row_face.operator("comfy_retopo.align_selected_face", text="🔝 設為頂面")
        op_top.target_axis = 'TOP'
        op_frt = row_face.operator("comfy_retopo.align_selected_face", text="🧭 設為正面")
        op_frt.target_axis = 'FRONT'

        box0.prop(props, "auto_level_before_retopo")

        # 區塊 1：朝向微調與電商尺寸鎖定
        box1 = layout.box()
        box1.label(text="1. 朝向微調與電商尺寸鎖定", icon='DRIVER_DISTANCE')
        row_rot = box1.row(align=True)
        row_rot.operator("comfy_retopo.rotate_90_z", icon='FILE_REFRESH')
        row_rot.operator("comfy_retopo.read_dimensions", text="讀取目前尺寸", icon='EYEDROPPER')

        box1.prop(props, "enable_size_lock")
        if props.enable_size_lock:
            row_u = box1.row(align=True)
            row_u.prop(props, "size_unit", text="單位")
            row_u.operator("comfy_retopo.swap_xy_dimensions", text="🔀 對調 X/Y 數值")

            col_dim = box1.column(align=True)
            col_dim.prop(props, "target_width_x", text=f"🔴 寬度 X (紅軸 / {unit_suffix})")
            col_dim.prop(props, "target_depth_y", text=f"🟢 深度 Y (綠軸 / {unit_suffix})")
            col_dim.prop(props, "target_height_z", text=f"🔵 高度 Z (藍軸 / {unit_suffix})")

            live_row = box1.row(align=True)
            live_row.scale_y = 1.25
            live_label = (
                "⚡ 立即套用長寬高拉伸: 開啟中 (動態即時)"
                if props.live_stretch_on_input
                else "🔒 立即套用長寬高拉伸: 關閉中 (靜態填表)"
            )
            live_row.prop(
                props,
                "live_stretch_on_input",
                text=live_label,
                icon='FULLSCREEN_ENTER' if props.live_stretch_on_input else 'LOCKED',
                toggle=True,
            )

        box1.prop(props, "ground_and_center")

        # 區塊 2：三引擎減面／重拓撲核心設定 (v2.2.1 橫向三格按鈕式切換 + 動態說明)
        box2 = layout.box()
        box2.label(text="2. 減面／重拓撲引擎 (一鍵切換)", icon='MOD_REMESH')
        eng_row = box2.row(align=True)
        eng_row.scale_y = 1.35
        eng_row.prop(props, "retopo_engine", expand=True)

        engine_hints = {
            'QEM_PRESERVE': "💡 最保銳利夾角與本體細節 (99.96%)，適合電商渲染交件",
            'INSTANT_MESHES': "💡 全品類 100% 純四邊形循環邊，適合手動微調與展 UV",
            'VOXEL_QUADRIFLOW': "💡 傳統體素重拓撲保底，專治嚴重破洞／多部件 AI 模型",
        }
        hint_row = box2.row()
        hint_row.label(text=engine_hints.get(props.retopo_engine, ""))

        col_face = box2.column(align=True)
        col_face.scale_y = 1.25
        col_face.prop(props, "target_face_count", text="目標面數 (Target Faces)")
        box2.operator("comfy_retopo.estimate_faces", icon='MESH_GRID')
        box2.prop(props, "auto_face_count")

        box2.separator()
        if props.retopo_engine == 'QEM_PRESERVE':
            box2.prop(props, "qem_transfer_normals")
            box2.prop(props, "qem_convert_to_quads")
            box2.prop(props, "quad_use_symmetry")
        elif props.retopo_engine == 'INSTANT_MESHES':
            box2.prop(props, "im_crease_angle")
            box2.prop(props, "im_use_voxel_preclean")
            box2.prop(props, "use_shrinkwrap")
        else:
            box2.prop(props, "auto_voxel_size")
            box2.prop(
                props,
                "voxel_size",
                text="步驟2 Voxel Size 上限 (m)" if props.auto_voxel_size else "步驟2 Voxel Size (m)",
            )
            box2.prop(props, "quad_use_symmetry")
            box2.prop(props, "preserve_sharp")
            if props.preserve_sharp:
                box2.prop(props, "pre_retopo_crease_recovery")
            box2.prop(props, "use_shrinkwrap")

        # 區塊 3：Maya 式自動軟硬邊
        box3 = layout.box()
        box3.label(text="3. Maya 式自動軟硬邊 (Soften/Harden)", icon='MOD_EDGESPLIT')
        box3.prop(props, "auto_soften_harden")
        row_sh = box3.row(align=True)
        row_sh.prop(props, "soft_hard_angle", text="硬邊角度閾值 (°)")
        box3.operator("comfy_retopo.apply_soften_harden", icon='SHADING_RENDERED')

        # 區塊 4：智慧貼圖烘焙
        box4 = layout.box()
        box4.label(text="4. 智慧貼圖烘焙 (白模 0 秒跳過)", icon='RENDER_STILL')
        box4.prop(props, "auto_bake_texture")
        if props.auto_bake_texture:
            box4.prop(props, "bake_resolution", text="解析度")

        # 主執行大按鈕 (全域唯一主按鈕，杜絕重複)
        layout.separator()
        run_row = layout.row(align=True)
        run_row.scale_y = 1.8
        run_row.operator("comfy_retopo.execute_pipeline", icon='PLAY')
