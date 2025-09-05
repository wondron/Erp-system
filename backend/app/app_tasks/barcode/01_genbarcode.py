from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from barcode import Code128
from barcode.writer import ImageWriter
from io import BytesIO
from PIL import Image

# 注册字体
pdfmetrics.registerFont(TTFont('MeiryoUI', './fonts/Meiryo_UI_W53_Regular.ttf'))
pdfmetrics.registerFont(TTFont('GJUN34PRO', './fonts/G-OTF-GJUN34PRO-MEDIUM.ttf'))
pdfmetrics.registerFont(TTFont('ARIAL', './fonts/ARIAL.TTF'))
pdfmetrics.registerFont(TTFont('thic', './fonts/MSGOTHIC.TTC'))
pdfmetrics.registerFont(TTFont('YAHEIL', './fonts/MSYHL.TTC'))
pdfmetrics.registerFont(TTFont('YAHEIBD', './fonts/MSYHBD.TTC'))

PAGE_WIDTH, PAGE_HEIGHT = A4
ROWS, COLS = 5, 4
MARGIN = 8 * mm
CELL_WIDTH = (PAGE_WIDTH - 2*MARGIN) / COLS
CELL_HEIGHT = (PAGE_HEIGHT - 2*MARGIN) / ROWS

# 示例数据
data_list = [
    {"caption":"毛布","品   番":"SG-MH-SP","サイズ":"SD・120×200cm","カラー":"ライトグレー","barcode":"763231705327"}
]
data_list = data_list * 20

c = canvas.Canvas("barcode_stickers_custom_font.pdf", pagesize=A4)

for idx, item in enumerate(data_list):
    row = idx // COLS
    col = idx % COLS
    x = MARGIN + col * CELL_WIDTH
    y = PAGE_HEIGHT - MARGIN - (row+1) * CELL_HEIGHT

    # 绘制文字
    text_y = y + CELL_HEIGHT - 12
    for key, value in item.items():
        if key == 'caption':
            c.setFont("YAHEIBD", 12)
            draw_text = " ".join(value)
            c.drawString(x + 4*mm, text_y-13, f"{draw_text}")
            text_y -= 32
        elif key != "barcode":
            # key 用 Meiryo UI
            c.setFont("YAHEIBD", 10)
            c.drawString(x + 4*mm, text_y, f"{key}：")
            # value 用 GJUN34PRO
            c.setFont("YAHEIL", 10)
            c.drawString(x + 3*mm + 15*mm, text_y, f"{value}")
            text_y -= 14

    # 生成条形码，但不显示默认文字
    barcode_obj = Code128(item["barcode"], writer=ImageWriter())
    buf = BytesIO()
    barcode_obj.write(buf, {
        "module_width":0.3,
        "module_height":25,
        "quiet_zone":0,
        "write_text": False  # 关键：不绘制默认数字
    })
    buf.seek(0)
    img = Image.open(buf)

    # 绘制条形码图片
    c.drawInlineImage(img, x + 5*mm, y + 13*mm, width=CELL_WIDTH-10*mm, height=15*mm)

    # 手动绘制条形码数字，使用 GJUN34PRO 字体
    c.setFont("ARIAL", 8)
    barcode_text = item["barcode"]
    n = len(barcode_text)

    # 条形码宽度（和二维码宽度一致）
    barcode_width = CELL_WIDTH - 8*mm
    start_x = x + 5*mm
    y_text = y + 10*mm  # 和二维码底部平齐

    # 每个数字的间距
    char_spacing = barcode_width / n

    for i, ch in enumerate(barcode_text):
        c.drawString(start_x + i*char_spacing, y_text, ch)

c.save()