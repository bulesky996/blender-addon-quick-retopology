# -*- coding: utf-8 -*-
"""
Quick Retopology v2.2.0 - Instant Meshes CLI Adapter
封裝 ETH Zurich 開源 Instant Meshes 外部執行檔的 OBJ 匯出、靜默呼叫與無縫回寫。
"""

import os
import sys
import time
import tempfile
import subprocess
import bpy
import bmesh
from ..core.telemetry import compute_instant_meshes_face_arg
from .bmesh_adapter import focus_single_mesh_object


def find_instant_meshes_executable(custom_path: str = "") -> str:
    """尋找內建或使用者指定的 Instant Meshes 執行檔路徑"""
    if custom_path and os.path.isfile(custom_path):
        return custom_path

    addon_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(addon_root, "bin", "Instant Meshes.exe"),
        os.path.join(addon_root, "bin", "InstantMeshes.exe"),
        os.path.join(addon_root, "bin", "Instant Meshes"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return ""


def _export_selected_to_obj(filepath: str):
    """相容 Blender 4.x (wm.obj_export) 與 3.6 (export_scene.obj) 的 OBJ 匯出"""
    if hasattr(bpy.ops.wm, "obj_export"):
        bpy.ops.wm.obj_export(
            filepath=filepath,
            export_selected_objects=True,
            export_uv=False,
            export_normals=False,
            export_materials=False,
            forward_axis='Y',
            up_axis='Z',
        )
    else:
        bpy.ops.export_scene.obj(
            filepath=filepath,
            use_selection=True,
            use_uvs=False,
            use_normals=False,
            use_materials=False,
            axis_forward='Y',
            axis_up='Z',
        )


def _import_obj(filepath: str):
    """相容 Blender 4.x (wm.obj_import) 與 3.6 (import_scene.obj) 的 OBJ 匯入"""
    if hasattr(bpy.ops.wm, "obj_import"):
        bpy.ops.wm.obj_import(
            filepath=filepath,
            forward_axis='Y',
            up_axis='Z',
        )
    else:
        bpy.ops.import_scene.obj(
            filepath=filepath,
            axis_forward='Y',
            axis_up='Z',
        )


def run_instant_meshes_remesh(
    context,
    obj,
    target_faces: int,
    crease_angle_deg: float = 30.0,
    smooth_iters: int = 0,
    deterministic: bool = True,
    timeout_sec: int = 180,
    logger=None,
) -> bool:
    """
    透過 Instant Meshes CLI 執行全品類銳角對齊純四邊形重拓撲，
    並將結果幾何無縫寫回原物件 (保留物件名稱與世界矩陣)。
    """
    exe_path = find_instant_meshes_executable()
    if not exe_path:
        if logger:
            logger.log("❌ [Instant Meshes] 找不到內建 bin/Instant Meshes.exe 執行檔！")
        return False

    focus_single_mesh_object(context, obj)

    tmp_dir = tempfile.gettempdir()
    stamp = f"{os.getpid()}_{int(time.time() * 1000)}"
    in_obj = os.path.join(tmp_dir, f"qr_im_in_{stamp}.obj")
    out_obj = os.path.join(tmp_dir, f"qr_im_out_{stamp}.obj")

    saved_loc = obj.location.copy()
    obj.location = (0.0, 0.0, 0.0)
    context.view_layer.update()

    try:
        t0 = time.time()
        _export_selected_to_obj(in_obj)
        t_exp = time.time() - t0

        im_face_arg = compute_instant_meshes_face_arg(target_faces)
        cmd = [
            exe_path,
            "-o", out_obj,
            "-f", str(im_face_arg),
            "-c", f"{float(crease_angle_deg):.1f}",
            "-S", str(int(max(0, smooth_iters))),
        ]
        if deterministic:
            cmd.append("-d")
        cmd.append(in_obj)

        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        t1 = time.time()
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            creationflags=creation_flags,
        )
        t_im = time.time() - t1

        if proc.returncode != 0 or not os.path.isfile(out_obj):
            if logger:
                err_txt = (proc.stderr or proc.stdout or "").strip()[:300]
                logger.log(f"❌ [Instant Meshes 失敗] rc={proc.returncode} | {err_txt}")
            return False

        # 匯入暫存 OBJ 並將 Mesh 資料無縫搬回原物件 obj
        before_objs = set(bpy.data.objects)
        _import_obj(out_obj)
        new_meshes = [o for o in bpy.data.objects if o not in before_objs and o.type == 'MESH']
        if not new_meshes:
            if logger:
                logger.log("❌ [Instant Meshes] 匯入結果為空！")
            return False

        tmp_imported = new_meshes[0]
        focus_single_mesh_object(context, tmp_imported)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

        bm_new = bmesh.new()
        bm_new.from_mesh(tmp_imported.data)
        bm_new.to_mesh(obj.data)
        bm_new.free()
        obj.data.update()

        # 清理暫存匯入物件與空 Mesh
        for o in list(bpy.data.objects):
            if o not in before_objs:
                o_data = o.data if o.type == 'MESH' else None
                bpy.data.objects.remove(o, do_unlink=True)
                if o_data and o_data.users == 0:
                    bpy.data.meshes.remove(o_data)

        focus_single_mesh_object(context, obj)
        if logger:
            logger.log(
                f"📐 [Instant Meshes 引擎完成] CLI 參數(-f {im_face_arg}, -c {crease_angle_deg:.0f}°, -S {smooth_iters}) | "
                f"匯出={t_exp:.2f}s | 求解={t_im:.2f}s | 實際輸出={len(obj.data.polygons):,} 面"
            )
        return True

    except Exception as e:
        if logger:
            logger.log(f"⚠️ [Instant Meshes 執行例外] {e}")
        return False

    finally:
        obj.location = saved_loc
        context.view_layer.update()
        for p in (in_obj, out_obj):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
