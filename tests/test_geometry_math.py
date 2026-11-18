# -*- coding: utf-8 -*-
"""
Quick Retopology v2.0.0 - Unit Tests for Core Geometry & Math
可完全脫離 Blender 執行，使用標準 unittest 模組。
"""

import math
import unittest
import sys
import os

# 確保可以 import quick_retopology_v2.core
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from core.geometry_math import (
    convert_length,
    compute_aabb,
    compute_scale_factors,
    rotate_point_euler_xyz,
    eval_point_cloud_bbox_volume,
)


class TestCoreGeometryMath(unittest.TestCase):

    def test_convert_length(self):
        # 1 inch = 0.0254 meters
        self.assertAlmostEqual(convert_length(1.0, 'INCH', 'M'), 0.0254, places=6)
        # 100 cm = 1 meter
        self.assertAlmostEqual(convert_length(100.0, 'CM', 'M'), 1.0, places=6)
        # 1000 mm = 1 meter
        self.assertAlmostEqual(convert_length(1000.0, 'MM', 'M'), 1.0, places=6)
        # 39.3700787 inches ~ 1 meter
        self.assertAlmostEqual(convert_length(1.0, 'M', 'INCH'), 1.0 / 0.0254, places=4)

    def test_compute_aabb_empty(self):
        min_p, max_p, dims = compute_aabb([])
        self.assertEqual(dims, (0.0, 0.0, 0.0))

    def test_compute_aabb_box(self):
        points = [
            (-1.0, -2.0, 0.0),
            (1.0, 2.0, 5.0),
            (0.0, 0.0, 2.5),
        ]
        min_p, max_p, dims = compute_aabb(points)
        self.assertEqual(min_p, (-1.0, -2.0, 0.0))
        self.assertEqual(max_p, (1.0, 2.0, 5.0))
        self.assertAlmostEqual(dims[0], 2.0)
        self.assertAlmostEqual(dims[1], 4.0)
        self.assertAlmostEqual(dims[2], 5.0)

    def test_compute_scale_factors(self):
        curr = (2.0, 4.0, 5.0)
        target = (1.0, 8.0, 5.0)
        sx, sy, sz = compute_scale_factors(curr, target)
        self.assertAlmostEqual(sx, 0.5)
        self.assertAlmostEqual(sy, 2.0)
        self.assertAlmostEqual(sz, 1.0)

    def test_rotate_point_euler_z_90(self):
        # (1, 0, 0) rotated 90 deg around Z becomes (0, 1, 0)
        rx = 0.0
        ry = 0.0
        rz = math.radians(90.0)
        p = (1.0, 0.0, 0.0)
        rp = rotate_point_euler_xyz(p, rx, ry, rz)
        self.assertAlmostEqual(rp[0], 0.0, places=6)
        self.assertAlmostEqual(rp[1], 1.0, places=6)
        self.assertAlmostEqual(rp[2], 0.0, places=6)

    def test_eval_point_cloud_bbox_volume(self):
        points = [
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 3.0, 0.0),
            (0.0, 3.0, 0.0),
            (0.0, 0.0, 4.0),
            (2.0, 0.0, 4.0),
            (2.0, 3.0, 4.0),
            (0.0, 3.0, 4.0),
        ]
        vol, xy_area = eval_point_cloud_bbox_volume(points, 0.0, 0.0, 0.0)
        self.assertAlmostEqual(vol, 24.0, places=4)
        self.assertAlmostEqual(xy_area, 6.0, places=4)


if __name__ == '__main__':
    unittest.main()
