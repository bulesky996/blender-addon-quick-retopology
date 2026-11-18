# -*- coding: utf-8 -*-
"""
Quick Retopology v2.0.0
ComfyUI 電商家具重拓撲神器 - Clean Architecture 模組化重構版
"""

bl_info = {
    "name": "Quick Retopology v2",
    "author": "PONG2.0 (bulesky996)",
    "version": (2, 2, 1),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar (N面板) > Quick Retopology",
    "description": "ComfyUI 電商家具重拓撲神器 v2.2.1：三引擎按鈕式切換 + 左側防遮擋 Y 軸標尺",
    "doc_url": "https://github.com/bulesky996/quick-retopology-v2",
    "category": "Mesh",
}

import bpy

# 開發期模組熱重載 (Hot Reloading Support)
if "core" in locals():
    import importlib
    importlib.reload(core)
    importlib.reload(adapters)
    importlib.reload(properties)
    importlib.reload(operators)
    importlib.reload(ui)

from .properties import ComfyRetopoProperties
from .operators import OPERATOR_CLASSES
from .ui import UI_CLASSES, init_viewport_ruler, cleanup_viewport_ruler

ALL_CLASSES = [
    ComfyRetopoProperties,
    *OPERATOR_CLASSES,
    *UI_CLASSES,
]


def register():
    """依序註冊屬性群組、運算元與 UI 面板，並啟動視窗標尺繪製回調"""
    for cls in ALL_CLASSES:
        bpy.utils.register_class(cls)

    bpy.types.Scene.comfy_retopo_props = bpy.props.PointerProperty(type=ComfyRetopoProperties)
    init_viewport_ruler()
    print("[Quick Retopology v2.2.1] 模組註冊完成 (介面體驗優化版啟動成功)")


def unregister():
    """反註冊所有類別並清理繪製回調"""
    cleanup_viewport_ruler()

    if hasattr(bpy.types.Scene, "comfy_retopo_props"):
        del bpy.types.Scene.comfy_retopo_props

    for cls in reversed(ALL_CLASSES):
        bpy.utils.unregister_class(cls)

    print("[Quick Retopology v2.0.0] 模組卸載完成")


if __name__ == "__main__":
    register()
