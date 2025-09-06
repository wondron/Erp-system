import pandas as pd
from io import BytesIO
from typing import Dict, Callable, Any, List

class ExcelReader:
    def __init__(self, data: bytes):
        """
        :param data: Excel 二进制内容（例如 FastAPI 的 UploadFile.file.read() 的结果）
        """
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("data 必须是 bytes/bytearray")
        self.data = data

    def read_as_dicts(self, sheet_name: Any = 0) -> List[Dict[str, Any]]:
        """
        读取 Excel 二进制数据，返回 list[dict]
        :param sheet_name: sheet 名称或索引，默认第一个
        """
        # 用 BytesIO 包装二进制
        bio = BytesIO(self.data)

        # 全部读成字符串，避免 NaN 带来的类型问题
        df = pd.read_excel(bio, sheet_name=sheet_name, dtype=str)
        df = df.fillna("")  # 空值替换为空字符串
        res = df.to_dict(orient="records")

        num_dict: Dict[str, Callable[[str], Any]] = {
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
            for key, target_type in num_dict.items():
                if key in row:
                    val = row[key]
                    if val is None or val == "":
                        row[key] = 0 if target_type is int else (0.0 if target_type is float else "")
                        continue
                    try:
                        # 直接转换
                        row[key] = target_type(val)
                    except Exception:
                        # 转换失败给默认值或保留原值的字符串形态
                        row[key] = 0 if target_type is int else (0.0 if target_type is float else str(val))
        return res


# 使用示例（以二进制为输入）
if __name__ == "__main__":
    # 假设你还是从磁盘读，但只为得到 bytes；在真实场景可来自网络/内存等
    with open(r'D:\01-code\Erp-system\backend\app\app_tasks\resource\example.xlsx', 'rb') as f:
        blob = f.read()

    reader = ExcelReader(blob)
    data_dicts = reader.read_as_dicts()  # 默认第一个 sheet
    print(data_dicts)
