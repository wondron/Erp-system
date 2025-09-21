#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A4 条码贴纸生成器（24枚/页）
- A4: 210×297mm，4列×6行
- 单枚贴纸: 52.5mm × 49.5mm
- 内容区: 左右 3.75mm、上下 8mm → 45mm × 33.5mm
- 头部文本区: 高 12mm（两行），与条码区间距 2.5mm
- 条码区: 45×18mm，左对齐；竖条停止在数字上方；数字在底部留白区居中显示
"""
from dataclasses import dataclass
from typing import Iterable, Tuple
from io import BytesIO
import os
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from io import BytesIO
from reportlab.lib.utils import ImageReader
import barcode  
from barcode.writer import ImageWriter

import logging
logger = logging.getLogger(__name__)




# ---------------- 字体注册（带兜底） ----------------
try:
    base_dir = Path(__file__).resolve().parent
    font_path = base_dir.parent / "fonts" / "SourceHanSansCN-Medium.ttf"
    pdfmetrics.registerFont(TTFont("Sans-Medium", str(font_path)))
    FONT_NAME = "Sans-Medium"
    font_path = base_dir.parent / "fonts" / "SourceHanSansCN-Heavy.ttf"
    pdfmetrics.registerFont(TTFont("SourceHanSansCN-Heavy", str(font_path)))
    FONT_NAME_TITLE = "SourceHanSansCN-Heavy"
except Exception as e:
    logger.error("字体加载失败，使用默认字体: %s", e)
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))  # 日文ゴシック
        FONT_NAME = "HeiseiKakuGo-W5"
    except Exception:
        # 优先尝试微软雅黑
        try:
            pdfmetrics.registerFont(TTFont("MicrosoftYaHei", "msyh.ttc"))
            FONT_NAME = "MicrosoftYaHei"
        except Exception:
            FONT_NAME = "Helvetica"  # 最后兜底（不保证 CJK）



# ---------------- 数据结构 ----------------
@dataclass
class xLabelRow:
    carton_mark: str
    color: str
    size: str
    barcode: str
    

_PY_BARCODE_NAME = {
    "EAN13": "ean13",
    "EAN8": "ean8",
    "UPCA": "upca",
    "UPCE": "upce",          # 如用到
    "Code128": "code128",
    "CODE128": "code128",
    "CODE39": "code39",
}


# ---------------- 小工具 ----------------
def _truncate(s: str, max_chars: int = 36) -> str:
    """简单截断，避免超宽文本溢出 45mm 内容宽度。"""
    s = s or ""
    return s if len(s) <= max_chars else (s[:max_chars - 1] + "…")


def _prepare_barcode_value(raw: str) -> Tuple[str, str, str]:
    """
    返回 (barcode_type, value_for_generator, human_text)
    - EAN13: 传 12 位数据，库自动算第 13 位校验；human_text 显示完整 13 位（由库生成的条纹+我们自绘数字）
      * 若用户传 >=13 位数字，取前 12 位给库；human_text 用原始 digits（或你也可用库算出的完整值）
    - UPCA : 传 11 位数据，库自动算第 12 位校验；human_text 显示完整 12 位
      * 若用户传 12 位数字，取前 11 位给库
    - 其他 : Code128 原样传；human_text = 原始 raw
    """
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if len(digits) >= 13:     # 当作 EAN13
        return "EAN13", digits[:12], digits[:13]
    if len(digits) == 12:     # 当作 UPCA（给 11 位数据）
        return "UPCA", digits[:11], digits[:12]
    if len(digits) == 11:     # 当作 UPCA
        return "UPCA", digits[:11], digits
    return "Code128", (raw or ""), (raw or "")


def draw_rect(c, x, y, w, h, color=colors.black):
    c.saveState()
    c.setLineWidth(0.6)
    c.setStrokeColor(color)
    c.rect(x, y, w, h, stroke=1, fill=0)
    c.restoreState()


# ---------------- 单格贴纸 ----------------
# ---------------- 单格贴纸 ----------------
def _make_barcode_image(
    btype: str,
    data: str,
    *,
    dpi: int = 600,
    write_text: bool = False,
    quiet_zone: float = 0.0
) -> ImageReader:
    """
    用 python-barcode 生成条形码 PNG，返回可喂给 reportlab 的 ImageReader。
    - write_text=False：不让库绘制底部数字（我们自己排版）
    - quiet_zone=0：左右静区最小化（如需规范，请调大）
    """
    py_name = _PY_BARCODE_NAME.get(btype, "code128")

    # 某些制式（EAN/UPC）要求数字-only；这里对 data 进行修正以减少报错
    norm_data = data or ""
    if py_name in {"ean13", "ean8", "upca", "upce"}:
        digits = "".join(ch for ch in norm_data if ch.isdigit())
        if py_name == "ean13":
            norm_data = digits[:12] or "000000000000"   # 传 12 位，库自动补校验位
        elif py_name == "ean8":
            norm_data = digits[:7] or "0000000"         # 传 7 位
        elif py_name == "upca":
            norm_data = digits[:11] or "00000000000"    # 传 11 位
        elif py_name == "upce":
            norm_data = digits[:7] or "0000000"         # 传 7 位
    # 其他（code128/code39）允许任意字符

    try:
        BarcodeClass = barcode.get_barcode_class(py_name)
    except Exception:
        # 万一制式名异常，回退 Code128
        BarcodeClass = barcode.get_barcode_class("code128")
        norm_data = data or ""

    bc = BarcodeClass(norm_data, writer=ImageWriter())
    buf = BytesIO()
    bc.write(
        buf,
        {
            "write_text": write_text,
            "quiet_zone": quiet_zone,
            "dpi": dpi,
            # 如需更细条纹或更高条高，可解开以下参数：
            # "module_width": 0.2,
            # "module_height": 15.0,
        },
    )
    buf.seek(0)
    return ImageReader(buf)

        

def draw_one_label(c: canvas.Canvas, x: float, y: float, w: float, h: float, data: xLabelRow, keep_aspect=False, b_draw_rect= True):
    """
    单格：52.5×49.5mm
    内容区：左右 3.75mm、上下 8mm → 45×33.5mm
    头部区：高 12mm；下方留 2.5mm 间距
    条码区：45×18mm（左对齐），竖条停在数字区上方，数字底部居中
    """
    # ---- 内容区框 ----
    pad_lr = 8 * mm
    pad_tb = 20 * mm
    mx, my = x + pad_lr, y + pad_tb
    mw, mh = w - 2 * pad_lr, h - 2 * pad_tb  # 45 × 33.5mm
    
    ch = 33.5 * mm
    cw = 45 * mm
    cx = mx + (mw - cw) / 2.0
    cy = my
    
    font_scale = 11
    
    # ---- 头部两行 ----
    c.setFillColor(colors.black)
    c.setFont(FONT_NAME, font_scale)
    # 你之前用的是绝对数值 30.5 / 26 mm，这里保留但也可用相对计算更稳
    if data.color:
        c.drawString(cx, cy + 30.5 * mm, _truncate(data.color))
    if data.size:
        c.drawString(cx, cy + 26.0 * mm, _truncate(data.size))

    btype, gen_value, human_text = _prepare_barcode_value(data.barcode)
    bx, by = cx, cy + 4 * mm
    bw, bh = cw, 20.5 * mm

    img = _make_barcode_image(btype, gen_value, dpi=600, write_text=False, quiet_zone=0.0)

    # 计算保持比例还是拉伸
    if keep_aspect:
        # 读取原图尺寸（像素），转换成宽高比即可；具体缩放由 drawImage 的 width/height 决定
        iw, ih = img.getSize()
        img_ratio = iw / float(ih)
        box_ratio = bw / float(bh)

        if img_ratio >= box_ratio:
            # 以宽为基准
            new_w = bw
            new_h = bw / img_ratio
        else:
            # 以高为基准
            new_h = bh
            new_w = bh * img_ratio

        dx = bx + (bw - new_w) / 2.0
        dy = by + (bh - new_h) / 2.0

        # preserveAspectRatio=False，因为我们已经手动算过 new_w/new_h
        c.drawImage(img, dx, dy, width=new_w, height=new_h, preserveAspectRatio=False, mask='auto')
    else:
        # 直接拉伸填满目标框
        c.drawImage(img, bx, by, width=bw, height=bh, preserveAspectRatio=False, mask='auto')
        
    c.setFillColor(colors.black)
    c.drawString(cx, cy, human_text)


    def split_first_dash(s: str):
        idx = s.find('-')
        if idx == -1:
            return s, ""   # 如果没有'-'，第二个字符串为空
        return s[:idx], s[idx:]
    carton_mark = data.carton_mark
    carton1, carton2 = split_first_dash(carton_mark)
    c.setFont(FONT_NAME_TITLE, 24)
    c.drawCentredString(mx + 44.5 * mm, my + 42 * mm, carton2)
    c.drawCentredString(mx + 44.5 * mm, my + 51 * mm, carton1)
    
    
        
    if b_draw_rect:
        draw_rect(c, x, y, w, h)
        draw_rect(c, cx, cy, cw, ch)
        draw_rect(c, cx, cy + 5 * mm, cw, 18.5 * mm)
        draw_rect(c, mx, my, mw, mh)
    
    


# ---------------- 整页生成 ----------------
def build_carton_mark_pdf(rows: Iterable[xLabelRow], drawRects = False) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    cell_w = 105 * mm
    cell_h = 99 * mm
    cols, rows_cnt = 2, 3
    per_page = cols * rows_cnt

    x_list = [i * cell_w for i in range(cols)]
    y_list = [j * cell_h for j in range(rows_cnt)]  # 页面左下为原点；自下而上
    
    if len(rows) > 1:
        btype, gen_value, human_text = _prepare_barcode_value(rows[0].barcode)
        logger.info("条形码格式: %s", btype)
        logger.info("使用字体名称: %s", FONT_NAME)
    for idx, lab in enumerate(rows):
        if idx and idx % per_page == 0:
            c.showPage()
        slot = idx % per_page
        col = slot % cols
        row = slot // cols
        draw_one_label(c, x_list[col], y_list[row], cell_w, cell_h, lab, b_draw_rect = drawRects)

    c.save()
    return buf.getvalue()


# ---------------- 自测 ----------------
if __name__ == "__main__":
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)  # 默认 INFO 级别
    
    # 生成 24 枚同款贴纸到当前目录（示例条码 13 位：将按 EAN13 处理，取前 12 位给库）
    test = xLabelRow(carton_mark='SXDFSJMCL-MS-100', color="ライトグレー", size="S・100×200cm", barcode="810101407796")
    data = [test for _ in range(6)]
    pdf_bytes = build_carton_mark_pdf(data, False)
    out = os.path.abspath("labels_test.pdf")
    with open(out, "wb") as f:
        f.write(pdf_bytes)
    print(f"✅ 已生成: {out}")
