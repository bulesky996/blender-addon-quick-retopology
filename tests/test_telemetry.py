# -*- coding: utf-8 -*-
"""
Quick Retopology v2.0.0 - Unit Tests for Core Telemetry & Health Gate
驗證智慧面數估算與幾何完整性守門員演算法。
"""

import unittest
import sys
import os

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from core.telemetry import (
    calculate_recommended_faces,
    compute_adaptive_voxel_size,
    compute_qem_decimate_ratio,
    compute_instant_meshes_face_arg,
    evaluate_quadriflow_health_gate,
)


class TestCoreTelemetry(unittest.TestCase):

    def test_calculate_recommended_faces_simple(self):
        # 簡單模型（無銳邊、無複雜底座）
        faces = calculate_recommended_faces(
            total_edges=1000,
            sharp_edges=10,
            bottom_edges=50,
            bottom_sharp_edges=0,
        )
        # 應落在基礎面數範圍
        self.assertTrue(4000 <= faces <= 12000)

    def test_calculate_recommended_faces_complex_chair(self):
        # 複雜帶椅腳模型（多銳邊、椅腳密集）
        faces = calculate_recommended_faces(
            total_edges=5000,
            sharp_edges=1500,
            bottom_edges=1000,
            bottom_sharp_edges=80,
        )
        # 有豐富椅腳銳邊時，保底應 >= 12500
        self.assertGreaterEqual(faces, 12500)

    def test_health_gate_pass(self):
        base_stats = {
            "faces": 20000,
            "boundary_edges": 0,
            "boundary_ratio": 0.0,
            "bbox": (1.0, 1.0, 1.0),
            "area": 5.0,
        }
        curr_stats = {
            "faces": 12000,
            "boundary_edges": 0,
            "boundary_ratio": 0.0,
            "bbox": (0.98, 0.98, 0.99),
            "area": 4.8,
        }
        is_ok, reasons = evaluate_quadriflow_health_gate(
            base_stats=base_stats,
            current_stats=curr_stats,
            target_faces=12000,
        )
        self.assertTrue(is_ok)
        self.assertEqual(len(reasons), 0)

    def test_health_gate_intercept_mesh_collapse(self):
        # 攔截面數崩潰 (例如目標 12000 卻只出 3000 面)
        base_stats = {
            "faces": 20000,
            "boundary_edges": 0,
            "boundary_ratio": 0.0,
            "bbox": (1.0, 1.0, 1.0),
            "area": 5.0,
        }
        curr_stats = {
            "faces": 3000,
            "boundary_edges": 0,
            "boundary_ratio": 0.0,
            "bbox": (1.0, 1.0, 1.0),
            "area": 5.0,
        }
        is_ok, reasons = evaluate_quadriflow_health_gate(
            base_stats=base_stats,
            current_stats=curr_stats,
            target_faces=12000,
        )
        self.assertFalse(is_ok)
        self.assertTrue(any("面數偏離目標" in r for r in reasons))

    def test_health_gate_intercept_torn_boundaries(self):
        # 攔截破洞撕裂 (開放邊大幅增加)
        base_stats = {
            "faces": 20000,
            "boundary_edges": 0,
            "boundary_ratio": 0.0,
            "bbox": (1.0, 1.0, 1.0),
            "area": 5.0,
        }
        curr_stats = {
            "faces": 12000,
            "boundary_edges": 250,
            "boundary_ratio": 0.015,  # 1.5% > 0.8%
            "bbox": (1.0, 1.0, 1.0),
            "area": 4.9,
        }
        is_ok, reasons = evaluate_quadriflow_health_gate(
            base_stats=base_stats,
            current_stats=curr_stats,
            target_faces=12000,
        )
        self.assertFalse(is_ok)
        self.assertTrue(any("破洞撕裂" in r for r in reasons))

    def test_health_gate_intercept_dimension_shrink(self):
        # 攔截掉椅腳 (外框尺寸縮水 > 12%)
        base_stats = {
            "faces": 20000,
            "boundary_edges": 0,
            "boundary_ratio": 0.0,
            "bbox": (1.0, 1.0, 1.0),
            "area": 5.0,
        }
        curr_stats = {
            "faces": 12000,
            "boundary_edges": 0,
            "boundary_ratio": 0.0,
            "bbox": (1.0, 1.0, 0.70),  # Z 高度只剩 70%
            "area": 4.0,
        }
        is_ok, reasons = evaluate_quadriflow_health_gate(
            base_stats=base_stats,
            current_stats=curr_stats,
            target_faces=12000,
        )
        self.assertFalse(is_ok)
        self.assertTrue(any("外框尺寸縮水" in r for r in reasons))

    def test_adaptive_voxel_small_high_detail_model(self):
        # 21 吋小模型 (表面積 0.772 m², 目標 43,000 面, 使用者預設 0.01m)
        # 應自動細化至甜區上限 (65K 體素面 ➔ ~0.00393m)，避免 1cm 體素黏死窄凹槽又防卡頓
        v = compute_adaptive_voxel_size(
            surface_area=0.7720,
            target_faces=43000,
            user_voxel_size=0.01,
            auto_adapt=True,
        )
        self.assertLess(v, 0.005)
        self.assertGreaterEqual(v, 0.003)

    def test_adaptive_voxel_large_sofa_respects_user_fine_limit(self):
        # 大型沙發 (表面積 8.0 m², 目標 15,000 面, 使用者設 0.01m)
        # 理想值 ~0.0186m > 0.01m，因此保留使用者較細的 0.01m
        v = compute_adaptive_voxel_size(
            surface_area=8.0,
            target_faces=15000,
            user_voxel_size=0.01,
            auto_adapt=True,
        )
        self.assertAlmostEqual(v, 0.01, places=5)

    def test_adaptive_voxel_disabled_returns_clamped_user(self):
        v = compute_adaptive_voxel_size(
            surface_area=0.7720,
            target_faces=43000,
            user_voxel_size=0.01,
            auto_adapt=False,
        )
        self.assertAlmostEqual(v, 0.01, places=5)

    def test_adaptive_voxel_clamps_extreme_tiny_surface(self):
        # 極小表面積不應低於安全下限 0.0015m
        v = compute_adaptive_voxel_size(
            surface_area=0.01,
            target_faces=50000,
            user_voxel_size=0.01,
            auto_adapt=True,
        )
        self.assertAlmostEqual(v, 0.0015, places=5)

    def test_qem_decimate_ratio_direct(self):
        # 572,646 面壓至 15,000 面 (不轉四邊)
        r = compute_qem_decimate_ratio(572646, 15000, convert_to_quads=False)
        self.assertAlmostEqual(r, 15000 / 572646, places=5)

    def test_qem_decimate_ratio_with_quads_headroom(self):
        # 啟用轉四邊時預留 1.35x 裕度
        r_no_quad = compute_qem_decimate_ratio(100000, 10000, convert_to_quads=False)
        r_quad = compute_qem_decimate_ratio(100000, 10000, convert_to_quads=True)
        self.assertAlmostEqual(r_no_quad, 0.1, places=5)
        self.assertAlmostEqual(r_quad, 0.135, places=5)

    def test_qem_decimate_ratio_no_upsample(self):
        # 目前面數已小於目標時應回傳 1.0 不動作
        r = compute_qem_decimate_ratio(8000, 15000, convert_to_quads=False)
        self.assertEqual(r, 1.0)

    def test_instant_meshes_face_arg_quarter_rule(self):
        # 純四邊形模式會 2x2 細分 (4x)，因此 16,000 目標應傳入 4,000
        self.assertEqual(compute_instant_meshes_face_arg(16000), 4000)
        self.assertEqual(compute_instant_meshes_face_arg(15000), 3750)
        self.assertGreaterEqual(compute_instant_meshes_face_arg(200), 125)


if __name__ == '__main__':
    unittest.main()
