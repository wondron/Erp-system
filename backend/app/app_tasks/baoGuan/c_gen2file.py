from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from enum import Enum
from baoGuan.z_tools import Direction
from . import z_tools
from typing import List, Any
from .a_extractInfo import ExcelReader
from openpyxl.drawing.image import Image


class FaPiaoBuilder:
    def __init__(self, title="fapiao"):
        self.wb = Workbook()
        self.ws = self.wb.active
        self.ws.title = title

        # 默认样式：细边框、黄色填充
        self.thin_border = Border(
            left=Side(style='thin', color="000000"),
            right=Side(style='thin', color="000000"),
            top=Side(style='thin', color="000000"),
            bottom=Side(style='thin', color="000000"),
        )
        self.yellow_fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
        self.row_height = [33, 33, 16.1, 16.1, 16.1, 16.1, 16.1, 33, 16.1]
        self.col_weight = [16, 38.44, 14, 14, 22, 22]


    def change_sheet_size(self, max_row):
        if len(self.row_height) < max_row:
            self.row_height += (max_row - len(self.row_height)-2) * [16.1]
            self.row_height.append(33)
        aaa = self.row_height
        z_tools.set_sheet_size(self.ws, self.col_weight, self.row_height)

    
    def get_fix_content(self, heyuestr=" "):
        # 2. 表头内容设置
        header1 = [["发票", "", "", '', '', '']]
        header2 = [["INVOICE", "", "", '', '', '']]

        content1 = [
            ["卖方：", "91330110MA28TYA536杭州同尘家居有限公司", ''],
            ["地址：", "浙江省杭州市余杭区余杭经济技术开发区北沙东路7号2幢324室",''],
            ["买方：", " ", ''],
            ["地址：", " ", ""]
        ]

        content2 = [
            ['日期 Date:', ' '],
            ['发票编号 Invoice No:', ' '],
            ['合约号 Contract No:', heyuestr],
        ]

        contente3 = [
            ['箱号\nCtn.No.', '货物名称及规格\nDescription', '数量\nQuantity', '单位\nUnit ', '单价\nUnit price', '总金额\nAmount']
        ]


        titlefont = Font(name="等线", size=22)
        title_alignment = Alignment(horizontal="center", vertical="center")
        rowindex = z_tools.record_sheet(self.ws, header1, 1, 1, titlefont, title_alignment)

        contentfont = Font(name="等线", size=20)
        rowindex = z_tools.record_sheet(self.ws, header2, rowindex, 1, contentfont, title_alignment)

        titlefont = Font(name="等线", size=10)
        title_alignment = Alignment(horizontal="left", vertical="center")
        _ = z_tools.record_sheet(self.ws, content1, rowindex, 1, titlefont, title_alignment, border=self.thin_border)
        rowindex = z_tools.record_sheet(self.ws, content2, rowindex, 5, titlefont, title_alignment, border=self.thin_border)
        # self.ws.cell(row=rowindex-1, column=6).fill = self.yellow_fill

        titlefont = Font(name="等线", size=11)
        title_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        rowindex = z_tools.record_sheet(self.ws, contente3, rowindex + 2, 1, titlefont, title_alignment, border=self.thin_border)



        return rowindex

    def input_data(self, data, startRow):
        contentfont = Font(name="微软雅黑", size=10)
        title_alignment = Alignment(horizontal="center", vertical="center")
        rowNum = z_tools.record_sheet(self.ws, data, startRow, 1, contentfont, title_alignment, Direction.VERTICAL, border=self.thin_border, isMerge=False)
        return rowNum

    def get_fapiao_data(self, extract_info):
        total_data = extract_info
        show_data = { 
            '箱号': {"yinshe": ['ASIN'], 'type': 'str'},
            '货物名称': {"yinshe": ['英文品名'], 'type': 'str'},
            '数量': {"yinshe": ['数量'], 'type': 'int'},
            '单位': {"yinshe": ['呵呵'], 'type': 'str'},
            '单价': {"yinshe": ['单价'], 'type': 'int'},
            '总数额': {"yinshe": ['总价'], 'type': 'int'},
        }

        erwei_data = z_tools.change_data_type(show_data, extract_info)

        for row in erwei_data:
            # 第三列索引是 2（Python 从 0 开始）
            if len(row) > 3 and row[3] == '':
                row[3] = 'JPY'

        return erwei_data


    def save_data(self, save_path):
        # 保存文件
        self.wb.save(save_path)

    def calculate_total_data(self, start_row, data):
        show_data= {
            '箱号': False,
            '货物名称': False,
            '数量': ['总数额'],
            '单位': False,
            '单价': False,
            '总数额': ['总数额'],
        }
        cal_index = []
        for index, item in enumerate(show_data):
            if show_data[item] != False:
                cal_index.append(index)
        if not data:
            return []

        n_cols = len(data[0])
        result = [''] * n_cols  # 其他列默认空字符串

        def to_number(s: str):
            """尝试把字符串转成 int 或 float，失败则返回 0"""
            try:
                if "." in s:   # 有小数点 → float
                    return float(s)
                return int(s)   # 否则 int
            except Exception:
                return 0

        for c in cal_index:
            total = 0.0
            for row in data:
                if c < len(row) and isinstance(row[c], str):
                    total += to_number(row[c])
                else:
                    total += row[c]
            # 判断是整数还是小数
            if abs(total - int(total)) < 1e-9:
                result[c] = int(total)  # 保持整数
            else:
                result[c] = round(total, 2)  # 保留两位小数
        result[0] = "合计 TOTAL"
        result[1] = ""
        result[3] = " "
        result[4] = " "

        contentfont = Font(name="等线", size=12, bold=True)
        title_alignment = Alignment(horizontal="center", vertical="center")
        rowNum = z_tools.record_sheet(self.ws, [result], start_row, 1, contentfont, title_alignment, Direction.HORIZONTAL, border=self.thin_border)
        self.ws.cell(row=rowNum-1, column=1).alignment = Alignment(horizontal="right", vertical="center")

        datalist = [['唛头\nMarks', '3V6S7', '', '', '', '']]
        contentfont = Font(name="等线", size=12)
        title_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        rowNum = z_tools.record_sheet(self.ws, datalist, rowNum + 1, 1, contentfont, title_alignment, Direction.HORIZONTAL, border=self.thin_border)

        return rowNum
    
    def insert_image(self, row_index, image_path):
        stamp = Image(image_path)
        stamp.width = 320
        stamp.height = 320
        posite = f"E{row_index-4}"
        self.ws.add_image(stamp, posite)



    def detect(self, oridata, hetongstr, save_path, gongzhang_path):
        rowNum = self.get_fix_content(hetongstr)
        total_data = self.get_fapiao_data(oridata)
        rowNum = self.input_data(total_data, rowNum)
        rowNum = self.calculate_total_data(rowNum, total_data)
        self.change_sheet_size(rowNum)
        self.insert_image(rowNum, gongzhang_path)
        self.save_data(save_path)



if __name__ == "__main__":
    save_path = '报关资料样板.xlsx'
    filepath = r'C:\Users\wondron\Documents\WeChat Files\wz-offensive\FileStorage\File\2025-08\项目1报关资料输出\1.输入\DI信息.xlsx'
    reader = ExcelReader(filepath)
    data_dicts = reader.read_as_dicts()
    save_path = '报关资料样板.xlsx'
    builder = FaPiaoBuilder()
    builder.detect(data_dicts, data_dicts[0]['预约号'], save_path)