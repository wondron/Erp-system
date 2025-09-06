from app.app_tasks.baoGuan.a_extractInfo import ExcelReader
from app.app_tasks.baoGuan.b_gen1file import ExcelASNBuilder
from app.app_tasks.baoGuan.c_gen2file import FaPiaoBuilder
from app.app_tasks.baoGuan.d_gen3file import ZhuangXiangBuilder
from app.app_tasks.baoGuan.e_gen4file import HeTongBuilder
from app.app_tasks.baoGuan.f_gen5file import BaoGuanBuilder
import io, zipfile, os, logging
import shutil
import traceback
import time
from pathlib import Path


# ---- Logging --------------------------------------------------------
logger = logging.getLogger(__name__)

if not logger.handlers:
    h = logging.StreamHandler()
    fmt = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
    h.setFormatter(fmt)
    logger.addHandler(h)
logger.setLevel(logging.INFO)


def _handle_excel_with_baoguan(raw: bytes) -> bytes:
    """
    输入：Excel 原始二进制
    输出：包含 5 个报关资料 xlsx 的 zip 二进制
    """
    logger.info("进入 _handle_excel_with_baoguan")
    logger.info(f"原始 Excel 大小: {len(raw)} bytes")

    # 1) 解析 Excel 数据
    reader = ExcelReader(raw)
    data_dicts = reader.read_as_dicts()
    hetong_no = data_dicts[0].get("合同号码", "") if data_dicts else ""
    logger.info(f"解析完成，共 {len(data_dicts)} 行数据")
    if data_dicts:
        preview = {k: data_dicts[0].get(k) for k in list(data_dicts[0].keys())[:5]}
        logger.info(f"首行预览: {preview}")
    logger.info(f"合同号码: {hetong_no}")

    # 2) 构建 5 个 xlsx 二进制
    outputs: list[tuple[str, bytes]] = []

    def _timeit(label: str, func):
        t0 = time.perf_counter()
        blob = func()
        dt = time.perf_counter() - t0
        logger.info(f"生成 {label} 完成, 大小 {len(blob)} bytes, 用时 {dt:.2f}s")
        return blob

    # ASN
    asn_bytes = _timeit("报关资料1-ASN.xlsx",
                        lambda: ExcelASNBuilder().detect(data_dicts))
    outputs.append(("报关资料1-ASN.xlsx", asn_bytes))

    # 发票
    fapiao_bytes = _timeit("报关资料2-发票.xlsx",
                           lambda: FaPiaoBuilder().detect(
                               data_dicts, hetong_no,
                               gongzhang_source="app/app_tasks/resource/gonzhang.png"))
    outputs.append(("报关资料2-发票.xlsx", fapiao_bytes))

    # 装箱单
    zhuang_bytes = _timeit("报关资料3-装箱单.xlsx",
                           lambda: ZhuangXiangBuilder().detect(
                               data_dicts, hetong_no,
                               gongzhang_source="app/app_tasks/resource/gonzhang.png"))
    outputs.append(("报关资料3-装箱单.xlsx", zhuang_bytes))

    # 合同
    hetong_bytes = _timeit("报关资料4-合同.xlsx",
                           lambda: HeTongBuilder().detect(
                               data_dicts, hetong_no,
                               gongzhang_path="app/app_tasks/resource/gonzhang.png"))
    outputs.append(("报关资料4-合同.xlsx", hetong_bytes))

    # 出口报关单
    baoguan_bytes = _timeit("报关资料5-出口报关单.xlsx",
                            lambda: BaoGuanBuilder("app/app_tasks/resource/baoguan.xlsx").detect(data_dicts))
    outputs.append(("报关资料5-出口报关单.xlsx", baoguan_bytes))

    # 3) 打包成 zip
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fname, blob in outputs:
            zf.writestr(fname, blob)
            logger.info(f"写入 zip: {fname}, 大小 {len(blob)} bytes")

    zip_bytes = bio.getvalue()
    logger.info(f"ZIP 打包完成，总大小 {len(zip_bytes)} bytes, 共 {len(outputs)} 个文件")
    return zip_bytes



if __name__ == '__main__':
    xlsx_path = r'D:\01-code\Erp-system\backend\app\app_tasks\resource\example.xlsx'

    # 1) 读入 Excel 文件的二进制
    with open(xlsx_path, "rb") as f:
        raw = f.read()

    # 2) 调用处理函数，得到 zip 的二进制
    zip_data = _handle_excel_with_baoguan(raw)

    # 3) 保存 zip 文件
    out_path = r"D:/报关资料打包.zip"
    with open(out_path, "wb") as f:
        f.write(zip_data)

    print(f"✅ 已生成 ZIP: {out_path}")