import pandas as pd

class ExcelReader:
    def __init__(self, filepath):
        self.filepath = filepath

    def read_as_dicts(self, sheet_name=0):
        """
        读取 Excel 文件，返回一个 list[dict]
        :param sheet_name: sheet 名称或索引，默认第一个
        """
        df = pd.read_excel(self.filepath, sheet_name=sheet_name, dtype=str)  # 全部读成字符串，避免 NaN
        df = df.fillna("")  # 空值替换为空字符串
        res = df.to_dict(orient="records")
        numDict = {
            '数量': int,
            '系数': int,
            '箱数': int,
            '体积': float,
            '净重': float,
            '毛重': float,
            '项目': int,
            '单价': int,
            '总价': int,
            '长': int,
            '宽': int,
            '高': int
        }
        for row in res:
            for key, target_type in numDict.items():
                if key in row:
                    val = row[key]
                    if val is None or val == "":
                        # 如果值为空，可以给默认值
                        if target_type == int:
                            row[key] = 0
                        elif target_type == float:
                            row[key] = 0.0
                        else:
                            row[key] = ""
                        continue
                    try:
                        # 转换类型
                        row[key] = target_type(val)
                    except Exception:
                        # 转换失败保持原值或给默认值
                        if target_type == int:
                            row[key] = 0
                        elif target_type == float:
                            row[key] = 0.0
                        else:
                            row[key] = str(val)

        return res


# 使用示例
if __name__ == "__main__":
    filepath = r'E:\01-code\02-erp\resource\DI信息.xlsx'
    reader = ExcelReader(filepath)
    data_dicts = reader.read_as_dicts()
    print(data_dicts)