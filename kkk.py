# otf_to_ttf.py
import sys
import fontforge  # 需要已安装 FontForge 的 Python 绑定

def otf_to_ttf(src_path: str, dst_path: str):
    font = fontforge.open(src_path)
    # 统一规范化（可选但强烈建议）
    font.selection.all()
    font.correctDirection()
    font.removeOverlap()
    # 核心：将三次贝塞尔(CFF)转成二次贝塞尔(TrueType)
    font.layers[font.activeLayer].is_quadratic = True  # 旧接口可用 font.emulateTTF()
    # 也可：font.convertToTTF()（新版本别名）

    # 生成 TTF（打开 GPOS/GSUB 保留，自动补 cmap 等）
    font.generate(dst_path, flags=("opentype"))  # 可加 "omit-instructions" 降复杂度
    font.close()
    print(f"✅ Converted: {src_path} -> {dst_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python otf_to_ttf.py input.otf output.ttf")
        sys.exit(1)
    otf_to_ttf(sys.argv[1], sys.argv[2])
