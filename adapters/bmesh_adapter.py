# -*- coding: utf-8 -*-
"""
Quick Retopology v2.0.0 - BMesh & Blender Adapters
負責純 Python 領域層與 Blender bpy/bmesh API 之間的橋接轉換。
"""

import math
import bpy
import bmesh
from mathutils import Vector, Euler, Matrix
from mathutils.bvhtree import BVHTree
from ..core.constants import UNIT_TO_METER
from ..core.telemetry import calculate_recommended_faces


def tag_redraw_all_view3d():
    """通知所有 3D Viewport 區域進行重繪"""
    try:
        wm = bpy.context.window_manager
        if not wm:
            return
        for win in wm.windows:
            for area in win.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    except Exception:
        pass


def get_target_mesh_object(context):
    """自動穿透 GLB Empty 群組找到真正的家具 Mesh"""
    act = context.active_object
    if act and act.type == 'MESH':
        return act

    candidates = []
    if act:
        for child in act.children_recursive:
            if child.type == 'MESH':
                candidates.append(child)

    for sel in getattr(context, "selected_objects", []):
        if sel.type == 'MESH' and sel not in candidates:
            candidates.append(sel)
        elif sel.type == 'EMPTY':
            for child in sel.children_recursive:
                if child.type == 'MESH' and child not in candidates:
                    candidates.append(child)

    if candidates:
        candidates.sort(key=lambda o: len(o.data.polygons), reverse=True)
        return candidates[0]

    return None


def focus_single_mesh_object(context, obj):
    """單獨選取目標模型並設為活躍物件"""
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    context.view_layer.objects.active = obj


def get_world_aabb_and_dims(obj):
    """計算模型在世界座標底下的真實 AABB 與外框尺寸"""
    world_corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [p.x for p in world_corners]
    ys = [p.y for p in world_corners]
    zs = [p.z for p in world_corners]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    dx = max_x - min_x
    dy = max_y - min_y
    dz = max_z - min_z
    pad = max(dx, dy, dz, 0.1) * 0.045
    return (min_x, max_x, min_y, max_y, min_z, max_z, dx, dy, dz, pad)


def inspect_mesh_telemetry(obj) -> dict:
    """透過 BMesh 擷取網格健康狀態與遙測數據 (轉為純資料字典)"""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    n_verts = len(bm.verts)
    n_edges = len(bm.edges)
    n_faces = len(bm.faces)

    if n_verts > 0:
        xs = [v.co.x for v in bm.verts]
        ys = [v.co.y for v in bm.verts]
        zs = [v.co.z for v in bm.verts]
        bbox = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    else:
        bbox = (0.0, 0.0, 0.0)

    quads = sum(1 for f in bm.faces if len(f.verts) == 4)
    quad_pct = (quads / max(n_faces, 1)) * 100.0

    boundary_edges = 0
    non_manifold_edges = 0
    for e in bm.edges:
        lf_count = len(e.link_faces)
        if lf_count == 1:
            boundary_edges += 1
        elif lf_count != 2:
            non_manifold_edges += 1

    visited = set()
    islands = 0
    total_area = 0.0
    for f in bm.faces:
        total_area += f.calc_area()
        if f.index in visited:
            continue
        islands += 1
        queue = [f]
        visited.add(f.index)
        while queue:
            cf = queue.pop()
            for e in cf.edges:
                for lf in e.link_faces:
                    if lf.index not in visited:
                        visited.add(lf.index)
                        queue.append(lf)

    bm.free()
    return {
        "verts": n_verts,
        "edges": n_edges,
        "faces": n_faces,
        "quad_pct": quad_pct,
        "islands": islands,
        "boundary_edges": boundary_edges,
        "boundary_ratio": boundary_edges / max(n_edges, 1),
        "non_manifold_edges": non_manifold_edges,
        "bbox": bbox,
        "area": total_area,
    }


def estimate_smart_face_count(obj) -> int:
    """結合 BMesh 結構特徵與純 Python 智慧面數推薦演算法"""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    total_edges = max(len(bm.edges), 1)
    sharp_edges = 0
    bottom_sharp_edges = 0
    bottom_edges = 0

    zs = [v.co.z for v in bm.verts] if bm.verts else [0.0, 1.0]
    min_z, max_z = min(zs), max(zs)
    height = max(max_z - min_z, 1e-4)
    foot_zone_z = min_z + height * 0.18

    sharp_angle_rad = math.radians(30.0)

    for e in bm.edges:
        is_foot_area = (e.verts[0].co.z <= foot_zone_z or e.verts[1].co.z <= foot_zone_z)
        if is_foot_area:
            bottom_edges += 1

        if len(e.link_faces) == 2:
            angle = e.calc_face_angle(0.0)
            if angle >= sharp_angle_rad:
                sharp_edges += 1
                if is_foot_area:
                    bottom_sharp_edges += 1

    bm.free()
    return calculate_recommended_faces(
        total_edges=total_edges,
        sharp_edges=sharp_edges,
        bottom_edges=bottom_edges,
        bottom_sharp_edges=bottom_sharp_edges,
    )


def align_pivot_bottom_and_lock_size(context, obj, ground_and_center=True, lock_size=False, target_dims_m=None):
    """
    純矩陣底層版——將軸心歸到底部正中心並貼地 (0,0,0) + 100% 強制拉伸長寬高比例。
    不依賴 bpy.ops.object.transform_apply，包在 Main 空物件底下一樣瞬間生效。
    """
    was_edit_mode = (context.mode == 'EDIT_MESH')
    if was_edit_mode:
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except Exception:
            pass

    if obj.data.users > 1:
        obj.data = obj.data.copy()

    mesh = obj.data
    if len(mesh.vertices) == 0:
        if was_edit_mode:
            try:
                bpy.ops.object.mode_set(mode='EDIT')
            except Exception:
                pass
        return

    # 1. 擷取完整世界變換矩陣並寫入頂點
    world_mat = obj.matrix_world.copy()
    rot_scale_mat = world_mat.to_3x3().to_4x4()
    world_loc = world_mat.to_translation()

    if obj.parent is not None:
        obj.parent = None
        obj.matrix_parent_inverse.identity()

    obj.rotation_mode = 'XYZ'
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    obj.scale = (1.0, 1.0, 1.0)
    obj.location = world_loc

    mesh.transform(rot_scale_mat)

    # 2. 計算世界邊界
    xs = [v.co.x for v in mesh.vertices]
    ys = [v.co.y for v in mesh.vertices]
    zs = [v.co.z for v in mesh.vertices]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)

    center_x = (min_x + max_x) * 0.5
    center_y = (min_y + max_y) * 0.5
    bottom_z = min_z

    # 3. 將頂點平移使軸心在底部中心
    trans_mat = Matrix.Translation(Vector((-center_x, -center_y, -bottom_z)))
    mesh.transform(trans_mat)

    if ground_and_center:
        obj.location = Vector((0.0, 0.0, 0.0))

    # 4. 鎖定真實尺寸
    if lock_size and target_dims_m is not None:
        curr_x = max(max_x - min_x, 1e-5)
        curr_y = max(max_y - min_y, 1e-5)
        curr_z = max(max_z - min_z, 1e-5)

        sx = target_dims_m[0] / curr_x
        sy = target_dims_m[1] / curr_y
        sz = target_dims_m[2] / curr_z

        scale_mat = Matrix.Diagonal(Vector((sx, sy, sz, 1.0)))
        mesh.transform(scale_mat)

    mesh.update()
    context.view_layer.update()

    try:
        obj.select_set(True)
        context.view_layer.objects.active = obj
    except Exception:
        pass

    if was_edit_mode:
        try:
            bpy.ops.object.mode_set(mode='EDIT')
        except Exception:
            pass
    tag_redraw_all_view3d()


def keep_only_largest_outer_shell(obj, preserve_exterior_parts=False, logger=None):
    """智慧剝除內層廢殼 (保護多部件桌腳與外框尺寸不縮水)"""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()

    if len(bm.faces) == 0:
        bm.free()
        return 0

    visited_faces = set()
    islands = []

    for f in bm.faces:
        if f.index in visited_faces:
            continue
        comp_faces = []
        queue = [f]
        visited_faces.add(f.index)
        area = 0.0
        verts_set = set()
        weighted_center = Vector((0.0, 0.0, 0.0))

        while queue:
            curr_f = queue.pop()
            comp_faces.append(curr_f)
            fa = curr_f.calc_area()
            area += fa
            weighted_center += curr_f.calc_center_median() * fa
            for v in curr_f.verts:
                verts_set.add(v)
            for e in curr_f.edges:
                for lf in e.link_faces:
                    if lf.index not in visited_faces:
                        visited_faces.add(lf.index)
                        queue.append(lf)

        centroid = weighted_center / max(area, 1e-8)
        signed_vol = 0.0
        for cf in comp_faces:
            signed_vol += (cf.calc_center_median() - centroid).dot(cf.normal) * cf.calc_area()

        xs = [v.co.x for v in verts_set]
        ys = [v.co.y for v in verts_set]
        zs = [v.co.z for v in verts_set]
        bmin = Vector((min(xs), min(ys), min(zs)))
        bmax = Vector((max(xs), max(ys), max(zs)))

        islands.append({
            "area": area,
            "faces": comp_faces,
            "bmin": bmin,
            "bmax": bmax,
            "signed_vol": signed_vol,
        })

    removed_count = 0
    if len(islands) > 1:
        islands.sort(key=lambda x: x["area"], reverse=True)
        main_isl = islands[0]
        main_area = main_isl["area"]
        main_min = main_isl["bmin"].copy()
        main_max = main_isl["bmax"].copy()
        main_size = main_max - main_min
        margin = max(main_size.length * 0.03, 0.005)

        if main_area > 1e-6:
            faces_to_delete = []
            for isl in islands[1:]:
                isl_area = isl["area"]
                ibmin = isl["bmin"]
                ibmax = isl["bmax"]
                svol = isl["signed_vol"]

                is_enclosed = (
                    ibmin.x >= main_min.x - margin and ibmax.x <= main_max.x + margin and
                    ibmin.y >= main_min.y - margin and ibmax.y <= main_max.y + margin and
                    ibmin.z >= main_min.z - margin and ibmax.z <= main_max.z + margin
                )

                expands_bbox = (
                    ibmin.x < main_min.x - margin * 1.5 or ibmax.x > main_max.x + margin * 1.5 or
                    ibmin.y < main_min.y - margin * 1.5 or ibmax.y > main_max.y + margin * 1.5 or
                    ibmin.z < main_min.z - margin * 1.5 or ibmax.z > main_max.z + margin * 1.5
                )

                if preserve_exterior_parts:
                    should_delete = (isl_area < main_area * 0.015) or (svol < 0.0 and is_enclosed) or (is_enclosed and isl_area < main_area * 0.35)
                else:
                    if expands_bbox and isl_area >= main_area * 0.03 and svol > 0.0:
                        should_delete = False
                    else:
                        should_delete = True

                if should_delete:
                    faces_to_delete.extend(isl["faces"])
                    removed_count += 1
                else:
                    main_min.x = min(main_min.x, ibmin.x)
                    main_min.y = min(main_min.y, ibmin.y)
                    main_min.z = min(main_min.z, ibmin.z)
                    main_max.x = max(main_max.x, ibmax.x)
                    main_max.y = max(main_max.y, ibmax.y)
                    main_max.z = max(main_max.z, ibmax.z)

            if faces_to_delete and len(faces_to_delete) < len(bm.faces):
                bmesh.ops.delete(bm, geom=faces_to_delete, context='FACES')
                loose_edges = [e for e in bm.edges if len(e.link_faces) == 0]
                if loose_edges:
                    bmesh.ops.delete(bm, geom=loose_edges, context='EDGES')
                loose_verts = [v for v in bm.verts if len(v.link_faces) == 0]
                if loose_verts:
                    bmesh.ops.delete(bm, geom=loose_verts, context='VERTS')

                bm.to_mesh(obj.data)
                obj.data.update()

    bm.free()
    if logger and removed_count > 0:
        logger.log(f"🧹 剝除內層廢殼/碎屑: 共清除 {removed_count} 個內部部件 (preserve_exterior={preserve_exterior_parts})")
    return removed_count


def check_model_has_color(obj) -> str:
    """檢查模型是否帶有材質貼圖或頂點色彩 ('IMAGE' / 'VERTEX_COLOR' / 'NONE')"""
    mesh = obj.data
    for mat in mesh.materials:
        if mat and mat.use_nodes and mat.node_tree:
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image is not None:
                    return 'IMAGE'

    if hasattr(mesh, "color_attributes") and len(mesh.color_attributes) > 0:
        active_col = mesh.color_attributes.active_color
        if active_col and len(active_col.data) > 0:
            sample_count = min(len(active_col.data), 200)
            for i in range(sample_count):
                c = active_col.data[i].color
                if abs(c[0] - 1.0) > 0.02 or abs(c[1] - 1.0) > 0.02 or abs(c[2] - 1.0) > 0.02:
                    return 'VERTEX_COLOR'

    return 'NONE'


def auto_level_tilted_furniture(context, obj):
    """極速抽樣計算最小外接盒 (OBB)，將歪斜模型自動擺正"""
    focus_single_mesh_object(context, obj)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

    verts = obj.data.vertices
    total_v = len(verts)
    if total_v < 4:
        return (0.0, 0.0, 0.0)

    step = max(total_v // 350, 1)
    sample_pts = [verts[i].co.copy() for i in range(0, total_v, step)]

    def eval_bbox_metric(pts, mat):
        xs = [0.0] * len(pts)
        ys = [0.0] * len(pts)
        zs = [0.0] * len(pts)
        for idx, p in enumerate(pts):
            rp = mat @ p
            xs[idx] = rp.x
            ys[idx] = rp.y
            zs[idx] = rp.z
        dx = max(xs) - min(xs)
        dy = max(ys) - min(ys)
        dz = max(zs) - min(zs)
        return dx * dy * dz, dx * dy

    best_rx, best_ry, best_rz = 0.0, 0.0, 0.0
    best_vol = float('inf')

    for rx_d in range(-30, 31, 6):
        rx = math.radians(rx_d)
        for ry_d in range(-30, 31, 6):
            ry = math.radians(ry_d)
            for rz_d in range(-45, 46, 15):
                rz = math.radians(rz_d)
                mat = Euler((rx, ry, rz), 'XYZ').to_matrix()
                vol, _ = eval_bbox_metric(sample_pts, mat)
                if vol < best_vol:
                    best_vol = vol
                    best_rx, best_ry, best_rz = rx_d, ry_d, rz_d

    c_rx, c_ry, c_rz = best_rx, best_ry, best_rz
    for i in range(-4, 5):
        rx_d = c_rx + i * 1.5
        rx = math.radians(rx_d)
        for j in range(-4, 5):
            ry_d = c_ry + j * 1.5
            ry = math.radians(ry_d)
            for k in range(-4, 5):
                rz_d = c_rz + k * 3.0
                rz = math.radians(rz_d)
                mat = Euler((rx, ry, rz), 'XYZ').to_matrix()
                vol, _ = eval_bbox_metric(sample_pts, mat)
                if vol < best_vol:
                    best_vol = vol
                    best_rx, best_ry, best_rz = rx_d, ry_d, rz_d

    c_rx, c_ry, c_rz = best_rx, best_ry, best_rz
    for i in range(-4, 5):
        rx_d = c_rx + i * 0.25
        rx = math.radians(rx_d)
        for j in range(-4, 5):
            ry_d = c_ry + j * 0.25
            ry = math.radians(ry_d)
            mat = Euler((rx, ry, math.radians(c_rz)), 'XYZ').to_matrix()
            vol, _ = eval_bbox_metric(sample_pts, mat)
            if vol < best_vol:
                best_vol = vol
                best_rx, best_ry = rx_d, ry_d

    best_xy_area = float('inf')
    rx_final = math.radians(best_rx)
    ry_final = math.radians(best_ry)
    for k in range(-20, 21):
        rz_d = c_rz + k * 0.25
        rz = math.radians(rz_d)
        mat = Euler((rx_final, ry_final, rz), 'XYZ').to_matrix()
        _, xy_area = eval_bbox_metric(sample_pts, mat)
        if xy_area < best_xy_area:
            best_xy_area = xy_area
            best_rz = rz_d

    final_mat = Euler((
        math.radians(best_rx),
        math.radians(best_ry),
        math.radians(best_rz),
    ), 'XYZ').to_matrix()

    obj.data.transform(final_mat.to_4x4())
    obj.data.update()

    align_pivot_bottom_and_lock_size(context, obj, ground_and_center=True, lock_size=False)
    return (round(best_rx, 2), round(best_ry, 2), round(best_rz, 2))


def mark_structural_sharp_edges(obj, angle_deg: float = 35.0, filter_isolated: bool = True) -> int:
    """
    依二面夾角 (Dihedral Angle) 主動標記結構性銳利邊 (包含內凹 V 型夾角與外凸轉折)，
    讓 QuadriFlow (use_preserve_sharp=True) 能沿著真實夾角鋪設乾淨的四邊形循環邊。
    filter_isolated=True 會過濾孤立單條噪點邊，僅保留連續的夾角邊鏈。
    """
    angle_rad = math.radians(max(5.0, min(89.0, float(angle_deg))))
    neighbor_rad = angle_rad * 0.7

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # 先計算每條流形邊的二面角
    edge_angles = {}
    candidates = []
    for e in bm.edges:
        if len(e.link_faces) == 2:
            ang = e.calc_face_angle(0.0)
            edge_angles[e.index] = ang
            if ang >= angle_rad:
                candidates.append(e)
        else:
            edge_angles[e.index] = math.pi
            candidates.append(e)

    # 先全部設為平滑，避免殘留雜訊銳邊
    for e in bm.edges:
        e.smooth = True

    marked_count = 0
    for e in candidates:
        if filter_isolated and len(e.link_faces) == 2:
            has_chain_neighbor = False
            for v in e.verts:
                for ne in v.link_edges:
                    if ne is not e and edge_angles.get(ne.index, 0.0) >= neighbor_rad:
                        has_chain_neighbor = True
                        break
                if has_chain_neighbor:
                    break
            if not has_chain_neighbor:
                continue

        e.smooth = False  # 寫入 ME_SHARP / sharp_edge
        marked_count += 1

    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return marked_count


def project_mesh_onto_high_poly(
    obj,
    high_poly_ref,
    max_snap_dist: float,
    normal_dot_min: float = 0.15,
    nearest_dot_min: float = 0.20,
) -> dict:
    """
    BVH 雙向法線投射 + 法線一致性過濾吸附 (Anti-Bridging Precision Conform)：
    1. 優先沿頂點法線 ±v.normal 進行 BVH Ray Cast，精準落入深凹 V 型夾角頂點；
    2. 未命中時回退至 BVH find_nearest，並強制檢驗法線方向一致性 (dot >= nearest_dot_min)，
       徹底杜絕凹槽兩側互吸造成的「鋸齒狀跨溝窗簾」與飛刺破面。
    """
    bm_ref = bmesh.new()
    bm_ref.from_mesh(high_poly_ref.data)

    rel_mat = obj.matrix_world.inverted() @ high_poly_ref.matrix_world
    is_identity = all(
        abs(rel_mat[i][j] - (1.0 if i == j else 0.0)) <= 1e-6
        for i in range(4)
        for j in range(4)
    )
    if not is_identity:
        bmesh.ops.transform(bm_ref, matrix=rel_mat, verts=bm_ref.verts)

    bm_ref.normal_update()
    bvh = BVHTree.FromBMesh(bm_ref)

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    bm.verts.ensure_lookup_table()

    ray_hits = 0
    nearest_hits = 0
    normal_blocked = 0
    out_of_range = 0
    max_observed_disp = 0.0

    for v in bm.verts:
        old_co = v.co.copy()
        vn = v.normal.copy()
        if vn.length_squared < 1e-12:
            continue
        vn.normalize()

        # Pass 1: 雙向法線投射 (-vn 往凹槽深處, +vn 往外表面)
        loc_in, norm_in, _, dist_in = bvh.ray_cast(old_co, -vn, max_snap_dist)
        loc_out, norm_out, _, dist_out = bvh.ray_cast(old_co, vn, max_snap_dist)

        valid_in = (loc_in is not None) and (vn.dot(norm_in) >= normal_dot_min)
        valid_out = (loc_out is not None) and (vn.dot(norm_out) >= normal_dot_min)

        best_loc = None
        best_dist = 0.0
        if valid_in and valid_out:
            if dist_in <= dist_out:
                best_loc, best_dist = loc_in, dist_in
            else:
                best_loc, best_dist = loc_out, dist_out
        elif valid_in:
            best_loc, best_dist = loc_in, dist_in
        elif valid_out:
            best_loc, best_dist = loc_out, dist_out

        if best_loc is not None:
            v.co = best_loc
            ray_hits += 1
            if best_dist > max_observed_disp:
                max_observed_disp = best_dist
            continue

        # Pass 2: 回退至最近表面點，並嚴格檢驗法線一致性避免跨溝亂吸
        loc_n, norm_n, _, dist_n = bvh.find_nearest(old_co, max_snap_dist)
        if loc_n is not None:
            if vn.dot(norm_n) >= nearest_dot_min:
                v.co = loc_n
                nearest_hits += 1
                if dist_n > max_observed_disp:
                    max_observed_disp = dist_n
            else:
                normal_blocked += 1
        else:
            out_of_range += 1

    bm.to_mesh(obj.data)
    bm.free()
    bm_ref.free()
    obj.data.update()

    return {
        "ray_hits": ray_hits,
        "nearest_hits": nearest_hits,
        "normal_blocked": normal_blocked,
        "out_of_range": out_of_range,
        "max_disp": max_observed_disp,
    }


def close_boundary_loops_quad_grid(context, obj, max_hole_sides: int = 64, logger=None) -> int:
    """
    純四邊形優先補洞器 (Pure-Quad Grid Fill + Fallback Fill Holes)：
    焊接微距重疊點、清除懸空幾何後，逐一偵測開放邊界環；
    偶數邊開放洞優先使用 Grid Fill 補成整齊純四邊形，奇數邊洞再以 fill_holes 保底，
    最後統一法線朝外，徹底消滅單點針孔破面。
    """
    focus_single_mesh_object(context, obj)

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='VERT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0002)
    bpy.ops.mesh.delete_loose(use_verts=True, use_edges=True, use_faces=False)
    bpy.ops.object.mode_set(mode='OBJECT')

    bm_chk = bmesh.new()
    bm_chk.from_mesh(obj.data)
    bm_chk.edges.ensure_lookup_table()
    b_edges_init = [e for e in bm_chk.edges if len(e.link_faces) == 1]

    visited_e = set()
    loops = []
    for e in b_edges_init:
        if e.index in visited_e:
            continue
        loop_e = []
        stack = [e]
        visited_e.add(e.index)
        while stack:
            ce = stack.pop()
            loop_e.append(ce.index)
            for v in ce.verts:
                for ne in v.link_edges:
                    if len(ne.link_faces) == 1 and ne.index not in visited_e:
                        visited_e.add(ne.index)
                        stack.append(ne)
        loops.append(loop_e)
    bm_chk.free()

    grid_filled = 0
    for loop_indices in loops:
        if 4 <= len(loop_indices) <= max_hole_sides and (len(loop_indices) % 2 == 0):
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_mode(type='EDGE')
            bpy.ops.mesh.select_all(action='DESELECT')
            bm_ed = bmesh.from_edit_mesh(obj.data)
            bm_ed.edges.ensure_lookup_table()
            for idx in loop_indices:
                if idx < len(bm_ed.edges):
                    bm_ed.edges[idx].select = True
            bmesh.update_edit_mesh(obj.data)
            try:
                bpy.ops.mesh.fill_grid()
                grid_filled += 1
            except Exception:
                pass
            bpy.ops.object.mode_set(mode='OBJECT')

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.fill_holes(sides=max_hole_sides)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')

    if logger and len(b_edges_init) > 0:
        logger.log(
            f"🩹 [Grid Fill 純四邊形補洞] 偵測原始開放邊={len(b_edges_init)} ({len(loops)} 個缺口) | "
            f"Grid Fill 補齊={grid_filled} 個"
        )
    return len(loops)


def transfer_high_poly_normals(context, low_obj, high_obj, angle_deg: float = 35.0, logger=None) -> bool:
    """
    繼承高模光影法線 (Transfer High-Poly Custom Split Normals)：
    先於原高模套用角度平滑著色 (兼顧絲滑曲面與銳利凹槽)，再透過 Data Transfer
    將精準法線投射至低模，讓低面數成品呈現近乎原高模的光影質感。
    """
    if high_obj is None or low_obj is None:
        return False

    try:
        angle_rad = math.radians(max(5.0, min(89.0, float(angle_deg))))

        # 先確保原高模擁有清晰的軟硬邊法線
        focus_single_mesh_object(context, high_obj)
        if hasattr(bpy.ops.object, "shade_smooth_by_angle"):
            bpy.ops.object.shade_smooth_by_angle(angle=angle_rad, keep_sharp_edges=True)
        else:
            bpy.ops.object.shade_smooth()
            if hasattr(high_obj.data, "use_auto_smooth"):
                high_obj.data.use_auto_smooth = True
                high_obj.data.auto_smooth_angle = angle_rad

        focus_single_mesh_object(context, low_obj)
        bpy.ops.object.shade_smooth()
        if hasattr(low_obj.data, "use_auto_smooth"):
            low_obj.data.use_auto_smooth = True
            low_obj.data.auto_smooth_angle = angle_rad

        dt_mod = low_obj.modifiers.new(name="Comfy_Transfer_HighPoly_Normals", type='DATA_TRANSFER')
        dt_mod.object = high_obj
        dt_mod.use_loop_data = True
        dt_mod.data_types_loops = {'CUSTOM_NORMAL'}

        valid_maps = [i.identifier for i in dt_mod.bl_rna.properties['loop_mapping'].enum_items]
        dt_mod.loop_mapping = 'POLYINTERP_NEAREST' if 'POLYINTERP_NEAREST' in valid_maps else valid_maps[0]

        bpy.ops.object.modifier_apply(modifier=dt_mod.name)

        if logger:
            logger.log(f"✨ [高模光影法線繼承] 已從原高模投射 Custom Split Normals (基準角度 {angle_deg:.1f}°)")
        return True
    except Exception as e:
        if logger:
            logger.log(f"⚠️ [高模光影法線繼承略過] {e}")
        return False
