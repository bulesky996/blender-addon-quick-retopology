# -*- coding: utf-8 -*-
"""
Quick Retopology v2.0.0 - Retopology Properties
定義插件狀態資料模型與屬性更新事件回調。
"""

import bpy
from ..core.constants import UNIT_TO_METER
from ..adapters.bmesh_adapter import (
    tag_redraw_all_view3d,
    get_target_mesh_object,
    align_pivot_bottom_and_lock_size,
    get_world_aabb_and_dims,
)


def on_unit_update(self, context):
    """單位切換時自動換算長寬高數值"""
    prev_unit = getattr(self, "prev_unit", 'INCH')
    new_unit = self.size_unit
    if prev_unit != new_unit and prev_unit in UNIT_TO_METER and new_unit in UNIT_TO_METER:
        self.is_internal_updating = True
        try:
            factor = UNIT_TO_METER[prev_unit] / UNIT_TO_METER[new_unit]
            self.target_width_x = round(self.target_width_x * factor, 3)
            self.target_depth_y = round(self.target_depth_y * factor, 3)
            self.target_height_z = round(self.target_height_z * factor, 3)
        finally:
            self.is_internal_updating = False
    self.prev_unit = new_unit
    tag_redraw_all_view3d()


def on_dimension_prop_update(self, context):
    """
    當使用者在面板修改 寬度X / 深度Y / 高度Z 按下 Enter 時：
    - 若開啟「⚡ 輸入時即時拉伸 (live_stretch_on_input)」，立即在視窗拉伸模型！
    - 若關閉（靜態數據模式），僅記錄數值不變形模型。
    """
    if getattr(self, "is_internal_updating", False):
        return
    if not self.enable_size_lock or not getattr(self, "live_stretch_on_input", False):
        tag_redraw_all_view3d()
        return
    obj = get_target_mesh_object(context)
    if not obj:
        return
    u_scale = UNIT_TO_METER.get(self.size_unit, 0.0254)
    target_dims_m = (
        self.target_width_x * u_scale,
        self.target_depth_y * u_scale,
        self.target_height_z * u_scale,
    )
    try:
        align_pivot_bottom_and_lock_size(
            context,
            obj,
            ground_and_center=self.ground_and_center,
            lock_size=True,
            target_dims_m=target_dims_m,
        )
        tag_redraw_all_view3d()
    except Exception as e:
        print(f"[QuickRetopo v2] 即時拉伸略過: {e}")


class ComfyRetopoProperties(bpy.types.PropertyGroup):
    """Quick Retopology 全域與場景狀態屬性群組"""

    is_internal_updating: bpy.props.BoolProperty(default=False)

    auto_level_before_retopo: bpy.props.BoolProperty(
        name="重拓撲前自動水平擺正 (Auto-Level)",
        description="若模型歪斜可勾選，執行重拓撲前自動利用最小包圍盒擺正",
        default=False,
    )
    enable_size_lock: bpy.props.BoolProperty(
        name="重拓撲時鎖定至此目標尺寸",
        description="勾選後，執行重拓撲時會將家具 100% 鎖定至下方設定的寬(X)、深(Y)、高(Z)尺寸",
        default=True,
    )
    live_stretch_on_input: bpy.props.BoolProperty(
        name="⚡ 輸入數值按 Enter 時立即拉伸 (動態模式)",
        description="開啟：修改下方 X/Y/Z 按 Enter 時立即拉伸模型；關閉（靜態數據模式）：僅填寫數值不變形",
        default=False,
        update=on_dimension_prop_update,
    )
    size_unit: bpy.props.EnumProperty(
        name="尺寸單位",
        description="選擇輸入尺寸的單位（預設為歐美電商標準小數英吋 INCH）",
        items=[
            ('INCH', "INCH (小數英吋)", "英吋 Decimal Inches (1 in = 25.4 mm)"),
            ('MM', "MM (公釐)", "公釐 Millimeters (1 mm = 0.001 m)"),
            ('CM', "CM (公分)", "公分 Centimeters (1 cm = 0.01 m)"),
            ('M', "M (公尺)", "公尺 Meters (Blender 原生單位)"),
        ],
        default='INCH',
        update=on_unit_update,
    )
    prev_unit: bpy.props.StringProperty(default='INCH')

    target_width_x: bpy.props.FloatProperty(
        name="寬度 (X / Width)",
        description="家具左右寬度 (對應 X 軸) — 輸入後按 Enter 立即拉伸模型",
        default=29.50,
        min=0.01,
        precision=2,
        update=on_dimension_prop_update,
    )
    target_depth_y: bpy.props.FloatProperty(
        name="深度 (Y / Depth)",
        description="家具前後深度 (對應 Y 軸) — 輸入後按 Enter 立即拉伸模型",
        default=31.25,
        min=0.01,
        precision=2,
        update=on_dimension_prop_update,
    )
    target_height_z: bpy.props.FloatProperty(
        name="高度 (Z / Height)",
        description="家具上下總高度 (對應 Z 軸) — 輸入後按 Enter 立即拉伸模型",
        default=33.75,
        min=0.01,
        precision=2,
        update=on_dimension_prop_update,
    )

    # 重拓撲／減面引擎模式 (v2.2.1 橫向三格按鈕式切換)
    retopo_engine: bpy.props.EnumProperty(
        name="減面引擎 (Engine)",
        description="依模型用途一鍵切換：要最保本體細節選智慧減面；要手動編修循環邊選純四邊 (Instant Meshes)",
        items=[
            (
                'QEM_PRESERVE',
                "⚡ 智慧減面",
                "預設模式：3~5 秒極速智慧減面，自動保留銳利夾角與細節，最適合直接渲染、展示與匯出遊戲引擎",
            ),
            (
                'INSTANT_MESHES',
                "📐 純四邊",
                "Instant Meshes 全品類引擎：3 秒順著稜線鋪出 100% 純四邊形循環邊並自動補洞，最適合手動微調與展 UV",
            ),
            (
                'VOXEL_QUADRIFLOW',
                "🧱 傳統減面",
                "經典體素重建 + QuadriFlow 流程：專治結構碎裂、多部件交錯或內部嚴重破洞的 AI 模型",
            ),
        ],
        default='QEM_PRESERVE',
    )

    # QEM 高模保真減面專屬設定
    qem_transfer_normals: bpy.props.BoolProperty(
        name="✨ 繼承原高模光影法線 (Data Transfer)",
        description="預設開啟：把原始高模的絲滑曲面與銳利夾角法線投射至低模，讓低面數成品呈現原高模光影",
        default=True,
    )
    qem_convert_to_quads: bpy.props.BoolProperty(
        name="嘗試將平坦面轉為四邊形 (Tris to Quads)",
        description="預設關閉（避免曲面導角處轉四邊產生微小陰影凹凸）；若偏好混編四邊形可勾選",
        default=False,
    )

    # Instant Meshes 純四邊形專屬設定
    im_crease_angle: bpy.props.FloatProperty(
        name="銳角特徵對齊角度 (°)",
        description="夾角大於此角度的凹槽與轉折會強制對齊四邊形循環邊（預設 30°）",
        default=30.0,
        min=10.0,
        max=80.0,
        precision=1,
    )
    im_use_voxel_preclean: bpy.props.BoolProperty(
        name="🛡️ 前置超細體素淨化 (防原模非流形裂縫)",
        description="預設開啟：先以 ~0.4 秒超細體素消除原模非流形邊，確保 Instant Meshes 輸出 0 破洞純四邊形",
        default=True,
    )

    # Voxel Remesh 設定
    auto_voxel_size: bpy.props.BoolProperty(
        name="🛡️ 智慧體素防黏死保護 (依尺寸/面數自動細化)",
        description="預設開啟：依據模型表面積與目標面數自動調細 Voxel Size，防止小模型窄凹槽被粗體素黏死橋接",
        default=True,
    )
    voxel_size: bpy.props.FloatProperty(
        name="Voxel Size (體素大小 m)",
        description="手動 Voxel Size 上限（預設 0.01 m）；開啟智慧保護時會視小模型與高面數需求自動再細化",
        default=0.01,
        min=0.001,
        max=0.2,
        step=0.05,
        precision=4,
    )

    # QuadriFlow 設定
    auto_face_count: bpy.props.BoolProperty(
        name="執行時自動估算面數 (覆蓋自訂值)",
        description="不勾選時 100% 依照你填寫的『自訂目標面數』執行；勾選時才會自動重算",
        default=False,
    )
    target_face_count: bpy.props.IntProperty(
        name="自訂目標面數 (Faces)",
        description="指定 QuadriFlow 輸出的四邊形面數",
        default=12000,
        min=500,
        max=100000,
        step=500,
    )
    quad_use_symmetry: bpy.props.BoolProperty(
        name="使用網格對稱 (Use Mesh Symmetry)",
        description="建議不勾選（AI 模型通常非 100% 對稱，勾選容易切歪）；若確定對稱可打勾",
        default=False,
    )
    preserve_sharp: bpy.props.BoolProperty(
        name="保留銳利邊 (Preserve Sharp)",
        description="保護圓柱、直角邊緣與深凹夾角",
        default=True,
    )
    pre_retopo_crease_recovery: bpy.props.BoolProperty(
        name="🔪 重拓撲前夾角還原 (零死鎖幾何貼合)",
        description="預設開啟：在 Voxel 後進 QuadriFlow 前以 BVH 法線投射貼回原高模壓深凹槽，且不觸發 QuadriFlow 銳邊求解器卡死",
        default=True,
    )
    use_shrinkwrap: bpy.props.BoolProperty(
        name="Shrinkwrap 100% 吸附原高模 (法線投射防跨溝)",
        description="在 QuadriFlow 完成後以 BVH 雙向法線投射吸回原始高模表面，保住椅腳與銳利凹槽且不拉出跨溝鋸齒",
        default=True,
    )

    # Maya 風格 Soften / Harden Edges
    auto_soften_harden: bpy.props.BoolProperty(
        name="重拓撲後自動套用 Maya 軟硬邊",
        description="依轉折角度自動設定該軟邊則軟邊、該硬邊則硬邊",
        default=True,
    )
    soft_hard_angle: bpy.props.FloatProperty(
        name="軟硬邊轉折角度 (°)",
        description="夾角大於此角度的邊會成為硬邊 (Hard Edge)，小於此角度的平滑過渡會成為軟邊 (Soft Edge)",
        default=35.0,
        min=5.0,
        max=89.0,
        precision=1,
    )

    ground_and_center: bpy.props.BoolProperty(
        name="軸心歸底置中 + 四腳貼地 (0,0,0)",
        description="自動將軸心點 (Pivot) 設於家具底部正中央，並移至世界座標 (0,0,0)",
        default=True,
    )
    auto_bake_texture: bpy.props.BoolProperty(
        name="自動烘焙原生貼圖 (白模 0 秒跳過)",
        description="預設開啟：自動檢查原模型是否有貼圖或頂點色，有則自動展 UV 並快速烘焙",
        default=True,
    )
    bake_resolution: bpy.props.EnumProperty(
        name="烘焙貼圖解析度",
        items=[
            ('2048', "2K (2048 × 2048)", "標準 2K 貼圖"),
            ('4096', "4K (4096 × 4096)", "高畫質 4K 貼圖"),
        ],
        default='2048',
    )
    show_viewport_dimensions: bpy.props.BoolProperty(
        name="👁️ 3D 視窗顯示紅/綠/藍尺寸標尺",
        description="在 3D 視窗的模型外框即時畫出 🔴X(紅-寬)、🟢Y(綠-深)、🔵Z(藍-高) 三色標尺與浮動尺寸數字",
        default=True,
        update=lambda self, context: tag_redraw_all_view3d(),
    )
    show_changelog: bpy.props.BoolProperty(
        name="顯示版本更新歷程",
        description="展開或收合版本號與更新紀錄",
        default=False,
    )
