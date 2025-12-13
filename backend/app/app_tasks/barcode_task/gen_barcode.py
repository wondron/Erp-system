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
from reportlab.pdfbase import pdfmetrics

import logging
logger = logging.getLogger(__name__)




# ---------------- 字体注册（带兜底） ----------------
try:
    base_dir = Path(__file__).resolve().parent
    font_path = base_dir.parent / "fonts" / "SourceHanSansCN-Medium.ttf"
    logger.info('字体路径：%s', font_path)
    pdfmetrics.registerFont(TTFont("Sans-Medium", str(font_path)))
    FONT_NAME = "Sans-Medium"
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
class LabelRow:
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

# ---------------- 截图 ----------------
def fit_font_size(text: str, font_name: str, max_width_pt: float,
                  max_size: float = 12.0, min_size: float = 8.0, step: float = 0.5) -> float:
    """
    根据字符串实际宽度动态计算可用字号（单位：pt）。
    优先返回 <= max_size 的最大可用字号；若即便 min_size 也放不下，则返回 min_size。
    """
    if not text:
        return max_size
    size = max_size
    while size >= min_size:
        width = pdfmetrics.stringWidth(text, font_name, size)
        if width <= max_width_pt:
            return size
        size -= step
    return min_size

def truncate_to_width(text: str, font_name: str, font_size: float,
                      max_width_pt: float, ellipsis: str = "…") -> str:
    """
    按“实际宽度”截断，并加省略号；尽量保留可见字符。
    """
    if not text:
        return text
    w = pdfmetrics.stringWidth(text, font_name, font_size)
    if w <= max_width_pt:
        return text

    # 先预留省略号宽度
    ell_w = pdfmetrics.stringWidth(ellipsis, font_name, font_size)
    limit = max_width_pt - ell_w
    if limit <= 0:
        return ellipsis

    # 线性裁剪（字符串通常不长，够快）；如需更快可改二分
    buf = []
    cur = 0.0
    for ch in text:
        ch_w = pdfmetrics.stringWidth(ch, font_name, font_size)
        if cur + ch_w > limit:
            break
        buf.append(ch)
        cur += ch_w
    return "".join(buf) + ellipsis

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
def _make_barcode_image(
    btype: str,
    data: str,
    *,
    dpi: int = 600,
    write_text: bool = False,
    quiet_zone: float = 0.0
) -> ImageReader:
    """
    用 python-barcode 生成 PNG，返回 ImageReader。
    - write_text=False：不由库渲染底部数字（我们自己排版）
    - quiet_zone=0：尽量不留左右静区（规范上不推荐，按需调整）
    """
    py_name = _PY_BARCODE_NAME.get(btype, "code128")
    try:
        BarcodeClass = barcode.get_barcode_class(py_name)
    except Exception:
        BarcodeClass = barcode.get_barcode_class("code128")

    bc = BarcodeClass(data, writer=ImageWriter())
    buf = BytesIO()
    bc.write(
        buf,
        {
            "write_text": write_text,
            "quiet_zone": quiet_zone,
            "dpi": dpi,
            # 可按需解注优化条纹粗细/高度：
            # "module_width": 0.2,
            # "module_height": 15.0,
        },
    )
    buf.seek(0)
    return ImageReader(buf)
        

def draw_one_label(c: canvas.Canvas, x: float, y: float, w: float, h: float, data: LabelRow, keep_aspect=False, b_draw_rect= True):
    """
    单格：52.5×49.5mm
    内容区：左右 3.75mm、上下 8mm → 45×33.5mm
    头部区：高 12mm；下方留 2.5mm 间距
    条码区：45×18mm（左对齐），竖条停在数字区上方，数字底部居中
    """
    # ---- 内容区框 ----
    pad_lr = 5.1 * mm
    pad_tb = 8 * mm
    cx, cy = x + pad_lr, y + pad_tb
    cw, ch = w - 2 * pad_lr, h - 2 * pad_tb  # 45 × 33.5mm

    max_line_width = cw
    color_text = _truncate(data.color) if data.color else ""
    color_font_size = fit_font_size(color_text, FONT_NAME, max_line_width, max_size=11, min_size=8, step=0.5)
    color_text_draw = truncate_to_width(color_text, FONT_NAME, color_font_size, max_line_width)
    
    # ---- 头部两行 ----
    c.setFillColor(colors.black)
    c.setFont(FONT_NAME, color_font_size)
    # 你之前用的是绝对数值 30.5 / 26 mm，这里保留但也可用相对计算更稳
    if data.color:
        c.drawString(cx, cy + 30.5 * mm, _truncate(color_text_draw))

    c.setFont(FONT_NAME, 11)   
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
        
    if b_draw_rect:
        draw_rect(c, x, y, w, h)
        draw_rect(c, cx, cy, cw, ch)
        draw_rect(c, cx, cy + 5 * mm, cw, 18.5 * mm)
    
    c.setFillColor(colors.black)
    c.drawString(cx, cy, human_text)
    
# ---------------- 整页生成 ----------------
def build_barcode_pdf(rows: Iterable[LabelRow], drawRects = False) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    cell_w = 52.5 * mm
    cell_h = 49.5 * mm
    cols, rows_cnt = 4, 6
    per_page = cols * rows_cnt

    x_list = [i * cell_w for i in range(cols)]
    y_list = [j * cell_h for j in range(rows_cnt)]  # 页面左下为原点；自下而上
    
    if len(rows) > 1:
        btype, gen_value, human_text = _prepare_barcode_value(rows[0].barcode)
        logger.info('条码信息：%s', rows[0])
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
    test = LabelRow(color="ライトグレー", size="S・100×200cm", barcode="X0017CCYMH")
    data = [test for _ in range(24)]
    pdf_bytes = build_barcode_pdf(data)
    out = os.path.abspath("labels_test.pdf")
    with open(out, "wb") as f:
        f.write(pdf_bytes)
    print(f"✅ 已生成: {out}")
