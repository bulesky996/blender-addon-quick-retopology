# -*- coding: utf-8 -*-
"""
Quick Retopology v2.0.0 - Core Logger
純 Python 日誌記錄器，提供執行時間遙測與黑盒子輸出。
"""

import os
import time
import datetime
import tempfile
from .constants import PRIMARY_LOG_DIR, LOG_FILENAME


class QuickRetopoLogger:
    """自動黑盒子執行紀錄器 (Auto Black-Box Logger)"""

    def __init__(self, log_dir=None, app_version="2.2.1"):
        self.lines = []
        self.start_time = time.time()

        target_dir = log_dir or PRIMARY_LOG_DIR
        if not target_dir or not os.path.isdir(target_dir):
            try:
                target_dir = tempfile.gettempdir()
            except Exception:
                target_dir = os.path.expanduser("~")

        self.log_path = os.path.join(target_dir, LOG_FILENAME)
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.log("=" * 72)
        self.log(f"[Quick Retopology v{app_version}] 黑盒子執行紀錄 | 時間: {now_str}")
        self.log(f"日誌路徑: {self.log_path}")
        self.log("=" * 72)

    def log(self, msg: str):
        elapsed = time.time() - self.start_time
        line = f"[{elapsed:6.2f}s] {msg}"
        self.lines.append(line)
        print(line)
        self.flush()

    def flush(self):
        try:
            with open(self.log_path, "w", encoding="utf-8") as f:
                f.write("\n".join(self.lines) + "\n")
        except Exception as e:
            print(f"[QuickRetopo Logger] 寫入 Log 失敗: {e}")

    def log_mesh_stats(self, stats: dict, step_label: str):
        self.log(
            f"📊 [{step_label}] "
            f"面數={stats.get('faces', 0):,} (四邊形={stats.get('quad_pct', 0.0):.1f}%) | "
            f"頂點={stats.get('verts', 0):,} | 部件數(Islands)={stats.get('islands', 0)} | "
            f"開放破洞邊={stats.get('boundary_edges', 0)} ({stats.get('boundary_ratio', 0.0)*100:.2f}%) | "
            f"非流形邊={stats.get('non_manifold_edges', 0)} | "
            f"尺寸(m)=({stats.get('bbox', (0,0,0))[0]:.3f} × {stats.get('bbox', (0,0,0))[1]:.3f} × {stats.get('bbox', (0,0,0))[2]:.3f}) | "
            f"表面積={stats.get('area', 0.0):.4f} m²"
        )
