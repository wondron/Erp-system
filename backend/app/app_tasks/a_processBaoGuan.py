from baoGuan.a_extractInfo import ExcelReader
from baoGuan.b_gen1file import ExcelASNBuilder
from baoGuan.c_gen2file import FaPiaoBuilder
from baoGuan.d_gen3file import ZhuangXiangBuilder
from baoGuan.e_gen4file import HeTongBuilder
from baoGuan.f_gen5file import BaoGuanBuilder
import os, shutil
import traceback, time
from pathlib import Path



def processBaoGuan(filepath, save_folder):
    t0 = time.perf_counter()
    print("\n" + "=" * 56)
    print("🚀 开始生成报关资料")
    print(f"📂 源文件：{filepath}")
    print(f"📁 输出目录：{save_folder}")
    print("=" * 56)

    ok, fail = [], []

    try:
        # 1) 准备环境与数据
        os.makedirs(save_folder, exist_ok=True)
        print("▶️  读取源数据…")
        t = time.perf_counter()
        extractInfo = ExcelReader(filepath)
        data_dicts = extractInfo.read_as_dicts()
        print(f"   ✔️ 已读取 {len(data_dicts)} 行数据，用时 {time.perf_counter() - t:.2f}s")

        # 关键字段检查
        hetong_no = (data_dicts[0].get('预约号') if data_dicts and isinstance(data_dicts[0], dict) else None)
        if not hetong_no:
            print("   ⚠️ 未找到关键字段：预约号（后续文件名/内容可能受影响）")

        # 2) 逐个文件生成
        # file1
        try:
            name = "报关资料1-ASN.xlsx"
            print(f"▶️  生成 {name} …")
            t = time.perf_counter()
            file1_path = os.path.join(save_folder, name)
            builder = ExcelASNBuilder()
            builder.detect(data_dicts, file1_path)
            print(f"   ✔️ 完成：{file1_path}（{time.perf_counter() - t:.2f}s）")
            ok.append(name)
        except Exception as e:
            print(f"   ❌ 失败（{name}）：{e}")
            traceback.print_exc()
            fail.append(("报关资料1-ASN.xlsx", e))

        # file2
        try:
            name = "报关资料2-发票.xlsx"
            print(f"▶️  生成 {name} …")
            t = time.perf_counter()
            gongzhang_path = r".\resource\gonzhang.png"
            file2_path = os.path.join(save_folder, name)
            builder = FaPiaoBuilder()
            builder.detect(data_dicts, hetong_no, file2_path, gongzhang_path)
            print(f"   ✔️ 完成：{file2_path}（{time.perf_counter() - t:.2f}s）")
            ok.append(name)
        except Exception as e:
            print(f"   ❌ 失败（{name}）：{e}")
            traceback.print_exc()
            fail.append((name, e))

        # file3
        try:
            name = "报关资料3-装箱单.xlsx"
            print(f"▶️  生成 {name} …")
            t = time.perf_counter()
            file3_path = os.path.join(save_folder, name)
            builder = ZhuangXiangBuilder()
            builder.detect(data_dicts, hetong_no, file3_path, gongzhang_path)
            print(f"   ✔️ 完成：{file3_path}（{time.perf_counter() - t:.2f}s）")
            ok.append(name)
        except Exception as e:
            print(f"   ❌ 失败（{name}）：{e}")
            traceback.print_exc()
            fail.append((name, e))

        # file4
        try:
            name = "报关资料4-合同.xlsx"
            print(f"▶️  生成 {name} …")
            t = time.perf_counter()
            file4_path = os.path.join(save_folder, name)
            builder = HeTongBuilder()
            builder.detect(data_dicts, hetong_no, file4_path, gongzhang_path)
            print(f"   ✔️ 完成：{file4_path}（{time.perf_counter() - t:.2f}s）")
            ok.append(name)
        except Exception as e:
            print(f"   ❌ 失败（{name}）：{e}")
            traceback.print_exc()
            fail.append((name, e))

        # file5
        try:
            name = "报关资料5-出口报关单.xlsx"
            print(f"▶️  生成 {name} …")
            t = time.perf_counter()
            moban_path = r".\resource\baoguan.xlsx"
            file5_path = os.path.join(save_folder, name)
            builder = BaoGuanBuilder(moban_path)
            builder.detect(data_dicts, file5_path)
            print(f"   ✔️ 完成：{file5_path}（{time.perf_counter() - t:.2f}s）")
            ok.append(name)
        except Exception as e:
            print(f"   ❌ 失败（{name}）：{e}")
            traceback.print_exc()
            fail.append((name, e))

        # 3) 汇总
        dt = time.perf_counter() - t0
        print("-" * 56)
        print(f"✅ 处理完成：成功 {len(ok)} 个，失败 {len(fail)} 个，总用时 {dt:.2f}s")
        if ok:
            print("   ✅ 成功文件：")
            for n in ok:
                print(f"     • {n}")
        if fail:
            print("   ❌ 失败文件：")
            for n, e in fail:
                print(f"     • {n}  ——  {e}")

        print("=" * 56 + "\n")
        # 成功与否返回布尔
        return len(fail) == 0

    except Exception as e:
        print("❌ 生成报关文件失败（致命错误）：", e)
        traceback.print_exc()
        print("=" * 56 + "\n")
        return False





def gen_template(file_path: str) -> bool:
    """
    生成模板文件到指定路径。

    Args:
        file_path (str): 目标文件路径（包含文件名）

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        src = Path("resource") / "template.xlsx"
        dst = Path(file_path)

        # 确保目标目录存在
        dst.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy(src, dst)
        print(f"✅ 模板文件已复制到: {dst}")
        return True
    except Exception:
        print("❌ 生成模板文件失败：")
        traceback.print_exc()
        return False




if __name__ == '__main__':
    xlsx_path = 'C:/Users/wondron/Documents/WeChat Files/wz-offensive/FileStorage/File/2025-08/项目1报关资料输出/1.输入/DI信息.xlsx'
    processBaoGuan(xlsx_path, f"D:\\data")