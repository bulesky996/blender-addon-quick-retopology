# -*- coding: utf-8 -*-
"""
Quick Retopology v2.0.0 - Pipeline Operator
負責一鍵清洗、Voxel Remesh、多階段 QuadriFlow、防飛刺 Shrinkwrap 與貼圖烘焙的核心流程。
"""

import math
import traceback
import bpy
import bmesh
from ..core.constants import UNIT_TO_METER, UNIT_LABELS
from ..core.logger import QuickRetopoLogger
from ..core.telemetry import (
    compute_adaptive_voxel_size,
    compute_qem_decimate_ratio,
    evaluate_quadriflow_health_gate,
)
from ..adapters.bmesh_adapter import (
    get_target_mesh_object,
    focus_single_mesh_object,
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
from ..adapters.instant_meshes_adapter import run_instant_meshes_remesh
from .shading_ops import apply_maya_soften_harden_edges, bake_color_from_high_to_low


def clean_mesh_pure_manual_sop(
    context,
    obj,
    remove_inner_shells=True,
    pre_voxel=False,
    clear_sharp=True,
    logger=None,
):
    """先焊接重疊頂點、補洞、統一法線朝外，再剝除內殼"""
    focus_single_mesh_object(context, obj)

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='VERT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0001)
    bpy.ops.mesh.delete_loose(use_verts=True, use_edges=True, use_faces=False)

    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.fill_holes(sides=32 if pre_voxel else 0)
    bpy.ops.object.mode_set(mode='OBJECT')

    removed = keep_only_largest_outer_shell(
        obj,
        preserve_exterior_parts=pre_voxel,
        logger=logger,
    ) if remove_inner_shells else 0

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    if clear_sharp:
        bpy.ops.mesh.mark_sharp(clear=True)
    bpy.ops.object.mode_set(mode='OBJECT')

    return removed


def check_quadriflow_health(obj, base_stats, target_faces, stage_name, logger=None):
    """調用 Core 領域層驗證幾何完整性守門員"""
    stats = inspect_mesh_telemetry(obj)
    is_ok, reasons = evaluate_quadriflow_health_gate(base_stats, stats, target_faces)

    if logger:
        if is_ok:
            bx_ratio = stats["bbox"][0] / max(base_stats["bbox"][0], 1e-4)
            by_ratio = stats["bbox"][1] / max(base_stats["bbox"][1], 1e-4)
            bz_ratio = stats["bbox"][2] / max(base_stats["bbox"][2], 1e-4)
            area_ratio = stats["area"] / max(base_stats["area"], 1e-4)
            logger.log(
                f"✅ [{stage_name} 守門員通過] 面數={stats['faces']:,} | 開放邊={stats['boundary_edges']} | "
                f"尺寸保留=({bx_ratio*100:.0f}%,{by_ratio*100:.0f}%,{bz_ratio*100:.0f}%) | 面積保留={area_ratio*100:.1f}%"
            )
        else:
            area_ratio = stats["area"] / max(base_stats["area"], 1e-4)
            logger.log(
                f"❌ [{stage_name} 守門員攔截並退回!] 原因: {'; '.join(reasons)} | "
                f"當時面數={stats['faces']:,}, 開放邊={stats['boundary_edges']}, 面積保留={area_ratio*100:.1f}%"
            )
    return is_ok


def apply_safe_shrinkwrap_no_spikes(
    context,
    obj,
    high_poly_ref,
    max_snap_dist,
    stage_label="Step 4b Shrinkwrap BVH法線投射吸附",
    logger=None,
):
    """
    防跨溝窗簾 + 防飛刺安全版 Shrinkwrap：
    優先沿頂點法線 ±v.normal 進行 BVH 精準投射（讓頂點直接落入深凹 V 型夾角頂點），
    未命中時才回退至法線一致性過濾的最近表面點，杜絕凹槽兩側互吸產生鋸齒毛刺。
    """
    focus_single_mesh_object(context, obj)
    res = project_mesh_onto_high_poly(
        obj=obj,
        high_poly_ref=high_poly_ref,
        max_snap_dist=max_snap_dist,
        normal_dot_min=0.15,
        nearest_dot_min=0.20,
    )

    if logger:
        logger.log(
            f"🧲 [{stage_label}] 法線投射命中={res['ray_hits']:,} | 最近點回退={res['nearest_hits']:,} | "
            f"防跨溝法線攔截={res['normal_blocked']:,} | 超距略過={res['out_of_range']:,} | "
            f"最大位移={res['max_disp']:.4f}m (上限={max_snap_dist:.4f}m)"
        )
    return res


def run_quadriflow_guaranteed(
    context,
    obj,
    high_poly_ref,
    props,
    target_faces,
    effective_voxel=None,
    pre_sharpened=False,
    logger=None,
):
    """四階段防破面 QuadriFlow 重拓撲流水線"""
    focus_single_mesh_object(context, obj)
    base_stats = inspect_mesh_telemetry(obj)
    used_voxel = effective_voxel if effective_voxel is not None else props.voxel_size

    voxel_backup_bm = bmesh.new()
    voxel_backup_bm.from_mesh(obj.data)

    def restore_from_voxel_backup():
        voxel_backup_bm.to_mesh(obj.data)
        obj.data.update()

    # 階段 1：若已完成 Step 3b 夾角還原與銳邊鎖定，不可再做 Smooth 以免糊掉夾角
    if not pre_sharpened and base_stats["faces"] > 25000:
        sm1 = obj.modifiers.new(name="QF_Step1_Relax", type='SMOOTH')
        sm1.factor = 0.35
        sm1.iterations = 1
        bpy.ops.object.modifier_apply(modifier=sm1.name)

    try:
        # 嚴禁在體素網格上開啟 use_preserve_sharp=True（體素鋸齒銳邊會觸發 QuadriFlow C++ MCF 求解器死鎖）
        # 夾角精準度改由 Step 3b 幾何還原 + Step 4b BVH 雙向法線投射 + Step 5 Maya 軟硬邊安全達成
        bpy.ops.object.quadriflow_remesh(
            use_mesh_symmetry=props.quad_use_symmetry,
            use_preserve_sharp=False,
            use_preserve_boundary=False,
            smooth_normals=True,
            mode='FACES',
            target_faces=target_faces,
        )
    except Exception as e:
        if logger:
            logger.log(f"⚠️ [STAGE_1 例外] {e}")

    if check_quadriflow_health(obj, base_stats, target_faces, "STAGE_1 (標準模式)", logger):
        voxel_backup_bm.free()
        return "STAGE_1"

    # 階段 2
    restore_from_voxel_backup()
    focus_single_mesh_object(context, obj)

    sm2 = obj.modifiers.new(name="QF_Step2_Relax", type='SMOOTH')
    sm2.factor = 0.5
    sm2.iterations = 3
    bpy.ops.object.modifier_apply(modifier=sm2.name)

    try:
        bpy.ops.object.quadriflow_remesh(
            use_mesh_symmetry=False,
            use_preserve_sharp=False,
            use_preserve_boundary=False,
            smooth_normals=True,
            mode='FACES',
            target_faces=target_faces,
        )
    except Exception as e:
        if logger:
            logger.log(f"⚠️ [STAGE_2 例外] {e}")

    if check_quadriflow_health(obj, base_stats, target_faces, "STAGE_2 (無銳邊防撕裂模式)", logger):
        voxel_backup_bm.free()
        return "STAGE_2"

    # 階段 3
    if high_poly_ref is not None:
        bm_restore = bmesh.new()
        bm_restore.from_mesh(high_poly_ref.data)
        bm_restore.to_mesh(obj.data)
        bm_restore.free()
        obj.data.update()

        focus_single_mesh_object(context, obj)
        sweet_ratio = math.sqrt(max(base_stats["faces"], 35000) / 35000.0) if base_stats["faces"] > 45000 else 1.15
        obj.data.remesh_voxel_size = max(used_voxel * sweet_ratio, 0.001)
        obj.data.remesh_voxel_adaptivity = 0.0
        obj.data.use_remesh_fix_poles = True
        obj.data.use_remesh_preserve_volume = True
        bpy.ops.object.voxel_remesh()

        clean_mesh_pure_manual_sop(context, obj, remove_inner_shells=True, pre_voxel=False, logger=logger)

        sm3 = obj.modifiers.new(name="QF_Step3_Relax", type='SMOOTH')
        sm3.factor = 0.5
        sm3.iterations = 3
        bpy.ops.object.modifier_apply(modifier=sm3.name)

        try:
            bpy.ops.object.quadriflow_remesh(
                use_mesh_symmetry=False,
                use_preserve_sharp=False,
                use_preserve_boundary=False,
                smooth_normals=True,
                mode='FACES',
                target_faces=target_faces,
            )
        except Exception as e:
            if logger:
                logger.log(f"⚠️ [STAGE_3 例外] {e}")

        if check_quadriflow_health(obj, base_stats, target_faces, "STAGE_3 (FixPoles甜蜜點模式)", logger):
            voxel_backup_bm.free()
            return "STAGE_3"

    # 階段 4
    if logger:
        logger.log("🛡️ 啟動 [STAGE_4 終極防破面純四邊形保底]：直接打造 100% 水密純四邊形！")

    if high_poly_ref is not None:
        bm_restore = bmesh.new()
        bm_restore.from_mesh(high_poly_ref.data)
        bm_restore.to_mesh(obj.data)
        bm_restore.free()
        obj.data.update()
    else:
        restore_from_voxel_backup()

    focus_single_mesh_object(context, obj)
    pre_unsub_target = target_faces * 2.0
    ratio = math.sqrt(max(base_stats["faces"], 500) / float(max(pre_unsub_target, 600)))
    adaptive_voxel_size = max(used_voxel * ratio, 0.001)

    obj.data.remesh_voxel_size = adaptive_voxel_size
    obj.data.remesh_voxel_adaptivity = 0.0
    obj.data.use_remesh_fix_poles = True
    obj.data.use_remesh_preserve_volume = True
    bpy.ops.object.voxel_remesh()

    clean_mesh_pure_manual_sop(context, obj, remove_inner_shells=True, pre_voxel=False, logger=logger)

    now_polys = len(obj.data.polygons)
    if now_polys > target_faces * 1.35:
        dec_mod = obj.modifiers.new(name="Quad_Target_Unsubdiv", type='DECIMATE')
        dec_mod.decimate_type = 'UNSUBDIV'
        dec_mod.iterations = 1 if now_polys < target_faces * 3.0 else 2
        bpy.ops.object.modifier_apply(modifier=dec_mod.name)

    sm4 = obj.modifiers.new(name="QF_Step4_SmoothFlow", type='SMOOTH')
    sm4.factor = 0.5
    sm4.iterations = 3
    bpy.ops.object.modifier_apply(modifier=sm4.name)

    if logger:
        logger.log_mesh_stats(inspect_mesh_telemetry(obj), "STAGE_4 保底完成狀態")

    voxel_backup_bm.free()
    return "STAGE_4"


class COMFY_OT_auto_retopo_furniture(bpy.types.Operator):
    bl_idname = "comfy_retopo.execute_pipeline"
    bl_label = "✨ 一鍵清洗 + 減面重拓撲 + 鎖定尺寸"
    bl_description = "執行三引擎旗艦流程：置中鎖尺寸 ➔ 清洗備份高模 ➔ QEM 保真 / Instant Meshes 純四邊形 / QuadriFlow ➔ 軟硬邊與貼圖烘焙"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        logger = QuickRetopoLogger()
        obj = get_target_mesh_object(context)
        if not obj:
            logger.log("❌ 錯誤：找不到 3D 網格模型！")
            self.report({'ERROR'}, "找不到 3D 網格模型！請先在視窗中點選你要處理的家具。")
            return {'CANCELLED'}

        props = context.scene.comfy_retopo_props
        engine_mode = getattr(props, "retopo_engine", "QEM_PRESERVE")
        unit_label = UNIT_LABELS.get(props.size_unit, 'in')
        logger.log(
            f"🎯 目標物件: {obj.name} | 引擎: {engine_mode} | 目標面數: {props.target_face_count:,} | "
            f"Voxel Size: {props.voxel_size:.4f}m | 尺寸鎖定: {props.enable_size_lock} "
            f"({props.target_width_x}×{props.target_depth_y}×{props.target_height_z} {unit_label})"
        )

        high_poly_ref = None
        try:
            focus_single_mesh_object(context, obj)

            if obj.parent is not None:
                bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')

            if obj.data.users > 1:
                obj.data = obj.data.copy()

            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            logger.log_mesh_stats(inspect_mesh_telemetry(obj), "Step 0a 原始輸入狀態")

            # 步驟 0
            if props.auto_level_before_retopo:
                rx, ry, rz = auto_level_tilted_furniture(context, obj)
                logger.log(f"📐 Auto-Level 自動擺正: rx={rx}°, ry={ry}°, rz={rz}°")

            target_dims_m = None
            if props.enable_size_lock:
                u_scale = UNIT_TO_METER.get(props.size_unit, 0.0254)
                target_dims_m = (
                    props.target_width_x * u_scale,
                    props.target_depth_y * u_scale,
                    props.target_height_z * u_scale,
                )

            align_pivot_bottom_and_lock_size(
                context,
                obj,
                ground_and_center=props.ground_and_center,
                lock_size=props.enable_size_lock,
                target_dims_m=target_dims_m,
            )
            logger.log_mesh_stats(inspect_mesh_telemetry(obj), "Step 0b 尺寸拉伸與置中後")

            # 步驟 1
            removed_pre = clean_mesh_pure_manual_sop(
                context,
                obj,
                remove_inner_shells=True,
                pre_voxel=True,
                clear_sharp=True,
                logger=logger,
            )
            pre_voxel_stats = inspect_mesh_telemetry(obj)
            logger.log_mesh_stats(pre_voxel_stats, "Step 1 基礎清洗後 (準備備份高模)")

            color_mode = check_model_has_color(obj) if props.auto_bake_texture else 'NONE'

            high_poly_ref = obj.copy()
            high_poly_ref.data = obj.data.copy()
            high_poly_ref.name = f"{obj.name}_HighPoly_Temp"
            context.collection.objects.link(high_poly_ref)

            focus_single_mesh_object(context, obj)

            if props.auto_face_count:
                target_faces = estimate_smart_face_count(obj)
                props.target_face_count = target_faces
            else:
                target_faces = props.target_face_count

            total_removed_shells = removed_pre
            engine_tag = engine_mode
            custom_normals_applied = False

            # =====================================================================
            # 引擎 1：⚡ QEM 高模保真減面 (預設・99.96% 保留銳利夾角與細節)
            # =====================================================================
            if engine_mode == 'QEM_PRESERVE':
                focus_single_mesh_object(context, obj)
                curr_faces = len(obj.data.polygons)
                dec_ratio = compute_qem_decimate_ratio(
                    current_faces=curr_faces,
                    target_faces=target_faces,
                    convert_to_quads=props.qem_convert_to_quads,
                )
                logger.log(
                    f"⚡ [引擎 1: QEM 高模保真減面] 目前 {curr_faces:,} 面 ➔ 目標 {target_faces:,} 面 "
                    f"(Decimate Ratio={dec_ratio:.5f} | 轉四邊={props.qem_convert_to_quads})"
                )

                if dec_ratio < 0.9999:
                    dec_mod = obj.modifiers.new(name="Comfy_QEM_Preserve", type='DECIMATE')
                    dec_mod.decimate_type = 'COLLAPSE'
                    dec_mod.ratio = dec_ratio
                    dec_mod.use_symmetry = props.quad_use_symmetry
                    bpy.ops.object.modifier_apply(modifier=dec_mod.name)

                if props.qem_convert_to_quads:
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.select_all(action='SELECT')
                    bpy.ops.mesh.tris_convert_to_quads(
                        face_threshold=math.radians(30.0),
                        shape_threshold=math.radians(35.0),
                        sharp=True,
                    )
                    bpy.ops.object.mode_set(mode='OBJECT')

                logger.log_mesh_stats(inspect_mesh_telemetry(obj), "Step 2 QEM 保真減面完成後")

                if props.qem_transfer_normals and high_poly_ref is not None:
                    custom_normals_applied = transfer_high_poly_normals(
                        context=context,
                        low_obj=obj,
                        high_obj=high_poly_ref,
                        angle_deg=props.soft_hard_angle,
                        logger=logger,
                    )
                engine_tag = "QEM_PRESERVE"

            # =====================================================================
            # 引擎 2：📐 Instant Meshes (全品類 100% 純四邊形銳角對齊)
            # =====================================================================
            elif engine_mode == 'INSTANT_MESHES':
                focus_single_mesh_object(context, obj)
                im_voxel = props.voxel_size
                if props.im_use_voxel_preclean:
                    # 動態計算 O(1) ~240K 面的超細水密體素，消除原模非流形邊且約 0.4 秒完成
                    im_voxel = compute_adaptive_voxel_size(
                        surface_area=pre_voxel_stats["area"],
                        target_faces=120000,
                        user_voxel_size=max(props.voxel_size, 0.01),
                        auto_adapt=True,
                        oversample_factor=2.0,
                        min_voxel_faces=180000,
                        max_voxel_faces=320000,
                        min_voxel_size=0.0018,
                        max_voxel_size=0.025,
                    )
                    logger.log(
                        f"🛡️ [Step 2 Instant Meshes 前置超細體素] 表面積={pre_voxel_stats['area']:.4f}m² "
                        f"➔ Voxel Size={im_voxel:.4f}m (防非流形裂縫)"
                    )
                    obj.data.remesh_voxel_size = im_voxel
                    obj.data.remesh_voxel_adaptivity = 0.0
                    obj.data.use_remesh_fix_poles = False
                    obj.data.use_remesh_preserve_volume = True
                    bpy.ops.object.voxel_remesh()
                    total_removed_shells += keep_only_largest_outer_shell(
                        obj, preserve_exterior_parts=False, logger=logger
                    )
                    logger.log_mesh_stats(inspect_mesh_telemetry(obj), f"Step 2 超細體素淨化 ({im_voxel:.4f}m) 完成")

                im_ok = run_instant_meshes_remesh(
                    context=context,
                    obj=obj,
                    target_faces=target_faces,
                    crease_angle_deg=props.im_crease_angle,
                    smooth_iters=0,
                    deterministic=True,
                    logger=logger,
                )

                if im_ok:
                    close_boundary_loops_quad_grid(context, obj, max_hole_sides=64, logger=logger)
                    total_removed_shells += keep_only_largest_outer_shell(
                        obj, preserve_exterior_parts=False, logger=logger
                    )
                    logger.log_mesh_stats(inspect_mesh_telemetry(obj), "Step 3 Instant Meshes 純四邊形與補洞完成")

                    if props.use_shrinkwrap and high_poly_ref is not None:
                        max_snap_dist = max(im_voxel * 3.5, 0.008)
                        apply_safe_shrinkwrap_no_spikes(
                            context=context,
                            obj=obj,
                            high_poly_ref=high_poly_ref,
                            max_snap_dist=max_snap_dist,
                            stage_label="Step 4b Shrinkwrap BVH法線投射壓深",
                            logger=logger,
                        )
                        logger.log_mesh_stats(inspect_mesh_telemetry(obj), "Step 4b BVH 貼合原高模後")
                    engine_tag = "INSTANT_MESHES"
                else:
                    logger.log("⚠️ Instant Meshes 執行失敗，自動降級切回 QuadriFlow 保底流程！")
                    # 還原高模狀態給 QuadriFlow 保底流程
                    bm_back = bmesh.new()
                    bm_back.from_mesh(high_poly_ref.data)
                    bm_back.to_mesh(obj.data)
                    bm_back.free()
                    obj.data.update()
                    engine_mode = 'VOXEL_QUADRIFLOW'

            # =====================================================================
            # 引擎 3：🧱 QuadriFlow 體素重拓撲 (傳統四階段防破面保底)
            # =====================================================================
            if engine_mode == 'VOXEL_QUADRIFLOW':
                effective_voxel = compute_adaptive_voxel_size(
                    surface_area=pre_voxel_stats["area"],
                    target_faces=target_faces,
                    user_voxel_size=props.voxel_size,
                    auto_adapt=props.auto_voxel_size,
                )
                if effective_voxel < props.voxel_size - 1e-6:
                    logger.log(
                        f"🛡️ [Step 2 智慧體素防黏死保護] 表面積={pre_voxel_stats['area']:.4f}m² | "
                        f"目標面數={target_faces:,} ➔ 自動細化 Voxel Size: {props.voxel_size:.4f}m ➔ {effective_voxel:.4f}m"
                    )

                obj.data.remesh_voxel_size = effective_voxel
                obj.data.remesh_voxel_adaptivity = 0.0
                obj.data.use_remesh_fix_poles = True
                obj.data.use_remesh_preserve_volume = True
                if hasattr(obj.data, "use_remesh_preserve_attributes"):
                    obj.data.use_remesh_preserve_attributes = True

                bpy.ops.object.voxel_remesh()
                logger.log_mesh_stats(inspect_mesh_telemetry(obj), f"Step 2 Voxel Remesh ({effective_voxel:.4f}m) 完成後")

                removed_post_voxel = clean_mesh_pure_manual_sop(
                    context,
                    obj,
                    remove_inner_shells=True,
                    pre_voxel=False,
                    clear_sharp=True,
                    logger=logger,
                )
                total_removed_shells += removed_post_voxel
                logger.log_mesh_stats(inspect_mesh_telemetry(obj), "Step 3 Voxel 後剝除內殼完成")

                pre_sharpened = False
                if props.preserve_sharp and props.pre_retopo_crease_recovery and high_poly_ref is not None:
                    focus_single_mesh_object(context, obj)
                    sm_pre = obj.modifiers.new(name="PreQF_StairStep_Relax", type='SMOOTH')
                    sm_pre.factor = 0.35
                    sm_pre.iterations = 1
                    bpy.ops.object.modifier_apply(modifier=sm_pre.name)

                    pre_snap_dist = max(effective_voxel * 1.8, 0.004)
                    apply_safe_shrinkwrap_no_spikes(
                        context=context,
                        obj=obj,
                        high_poly_ref=high_poly_ref,
                        max_snap_dist=pre_snap_dist,
                        stage_label="Step 3b 重拓撲前夾角還原貼合",
                        logger=logger,
                    )
                    pre_sharpened = True
                    logger.log("⚡ [Step 3b 零死鎖保護] 已保留平滑銳利幾何曲率且清空體素鋸齒銳邊，安全移交 QuadriFlow")
                    logger.log_mesh_stats(inspect_mesh_telemetry(obj), "Step 3b 夾角還原完成 (準備進入 QuadriFlow)")

                qf_stage = run_quadriflow_guaranteed(
                    context=context,
                    obj=obj,
                    high_poly_ref=high_poly_ref,
                    props=props,
                    target_faces=target_faces,
                    effective_voxel=effective_voxel,
                    pre_sharpened=pre_sharpened,
                    logger=logger,
                )
                logger.log(f"🏁 QuadriFlow 最終採用階段: {qf_stage}")
                engine_tag = f"QF/{qf_stage}"

                keep_only_largest_outer_shell(obj, preserve_exterior_parts=False, logger=logger)
                logger.log_mesh_stats(inspect_mesh_telemetry(obj), "Step 4 重拓撲完成後")

                if props.use_shrinkwrap and high_poly_ref is not None:
                    max_snap_dist = max(effective_voxel * 2.5, 0.012)
                    apply_safe_shrinkwrap_no_spikes(
                        context=context,
                        obj=obj,
                        high_poly_ref=high_poly_ref,
                        max_snap_dist=max_snap_dist,
                        stage_label="Step 4b Shrinkwrap BVH法線投射吸附",
                        logger=logger,
                    )
                    logger.log_mesh_stats(inspect_mesh_telemetry(obj), "Step 4b Shrinkwrap 防跨溝吸附後")

            # 步驟 5：智慧貼圖烘焙 + 最終尺寸校準 + 軟硬邊著色
            bake_status_msg = "無貼圖(0秒跳過)"
            if props.auto_bake_texture and color_mode != 'NONE':
                baked = bake_color_from_high_to_low(
                    context=context,
                    high_obj=high_poly_ref,
                    low_obj=obj,
                    color_mode=color_mode,
                    resolution=int(props.bake_resolution),
                )
                bake_status_msg = f"已烘焙 {props.bake_resolution}px 貼圖" if baked else "烘焙略過"
                logger.log(f"🎨 貼圖烘焙狀態: {bake_status_msg}")

            focus_single_mesh_object(context, obj)

            align_pivot_bottom_and_lock_size(
                context,
                obj,
                ground_and_center=props.ground_and_center,
                lock_size=props.enable_size_lock,
                target_dims_m=target_dims_m,
            )

            # 若 QEM 已透過 Data Transfer 繼承高模 Custom Split Normals，則不可再覆寫破壞
            if not custom_normals_applied:
                if props.auto_soften_harden:
                    apply_maya_soften_harden_edges(context, obj, angle_deg=props.soft_hard_angle)
                else:
                    bpy.ops.object.shade_smooth()

            final_stats = inspect_mesh_telemetry(obj)
            logger.log_mesh_stats(final_stats, "Step 5 最終完成狀態")
            final_polys = final_stats["faces"]
            quad_pct = final_stats["quad_pct"]

            size_msg = (
                f"尺寸: {props.target_width_x}×{props.target_depth_y}×{props.target_height_z} {unit_label}"
                if props.enable_size_lock else "維持原尺寸"
            )

            summary_msg = (
                f"✅ 完成({engine_tag})！目標: {target_faces:,} 面 ➔ 實際: {final_polys:,} 面 "
                f"(四邊形率: {quad_pct:.1f}%) | 清除內殼: {total_removed_shells} | {bake_status_msg} | {size_msg}"
            )
            logger.log(summary_msg)
            logger.log("=" * 72)

            self.report({'INFO'}, summary_msg)
            return {'FINISHED'}

        except Exception as e:
            err_trace = traceback.format_exc()
            logger.log(f"💥 執行期間發生未預期例外:\n{err_trace}")
            self.report({'ERROR'}, f"執行發生異常 (詳見 Log): {e}")
            return {'CANCELLED'}

        finally:
            if high_poly_ref is not None and high_poly_ref.name in bpy.data.objects:
                temp_mesh = high_poly_ref.data
                bpy.data.objects.remove(high_poly_ref, do_unlink=True)
                if temp_mesh and temp_mesh.users == 0:
                    bpy.data.meshes.remove(temp_mesh)
