# -*- coding: utf-8 -*-
"""生成程序图标 assets/app.ico。

为什么是一个脚本、而不是直接放一个 .ico 文件进来？
因为「图标长什么样」以后多半要改（换个配色、换个造型）。留一个能重跑的
脚本，改两行颜色再跑一次就行；留一个二进制文件，就只能去翻图标工具了。

用法（要一个装了 Pillow 的解释器，构建环境里就有）：
    _build_venv/Scripts/python.exe tools/make_icon.py

依赖：Pillow（只有生成图标时用，程序运行本身不需要）
"""

import os
import sys

from PIL import Image, ImageDraw

# ---------------------------------------------------------------- 配色
# 便签黄。挑它是因为「便利贴」这东西本身就是黄的 —— 小到 16px
# （任务栏 / 桌面图标那个大小）时，色块比线条好认得多。
NOTE   = (255, 214, 92, 255)     # 便签底
NOTE_E = (226, 181, 58, 255)     # 便签描边
BAND   = (229, 72, 77, 255)      # 顶部色带，取的是程序里 P0 的那个红
FOLD   = (255, 238, 178, 255)    # 右下折角（比便签本身亮一档）
INK    = (124, 113, 97, 255)     # 那几条"文字"

SIZE = 1024     # 先在大画布上画，最后缩下去 —— 直接画 16px 会毛边

# 生成的图标要比实际需要的大一圈留边（Windows 会自己缩放）
SIZES = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)]


def build_image():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    m = 84                      # 四周留白
    rad = 110                   # 圆角半径
    x1, y1, x2, y2 = m, m, SIZE - m, SIZE - m

    # 便签本体
    d.rounded_rectangle((x1, y1, x2, y2), radius=rad,
                        fill=NOTE, outline=NOTE_E, width=16)

    # 顶部色带。corners 只圆上面两个角 —— 不然整条色带会变成一个
    # 独立的胶囊，跟便签本身对不上缝。
    band_h = 158
    d.rounded_rectangle((x1 + 16, y1 + 16, x2 - 16, y1 + band_h),
                        radius=rad - 12, fill=BAND,
                        corners=(True, True, False, False))

    # 右下折角。画个三角盖在角上，看起来就像纸被翻起来一角；
    # 那条斜边必须描一下（折痕）—— 不描它只是一块浅色补丁，
    # 不像"角翻了"，倒像图标画脏了。
    f = 210
    d.polygon([(x2 - f, y2 - 16), (x2 - 16, y2 - f), (x2 - 16, y2 - 16)],
              fill=FOLD)
    d.line([(x2 - f, y2 - 16), (x2 - 16, y2 - f)], fill=NOTE_E, width=13)

    # 三条"文字"。最后一条短一点，像一段话写完了。
    lx = x1 + 108
    lw = (x2 - x1) - 216
    ly = y1 + 262
    for frac in (0.80, 0.88, 0.52):
        d.rounded_rectangle((lx, ly, lx + lw * frac, ly + 48),
                            radius=24, fill=INK)
        ly += 116

    return img


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(os.path.dirname(here), "assets")
    out = os.path.join(out_dir, "app.ico")
    if len(sys.argv) > 1:
        out = sys.argv[1]
        out_dir = os.path.dirname(os.path.abspath(out))

    os.makedirs(out_dir, exist_ok=True)

    img = build_image()
    # 缩到 256 再交给 Pillow 生成各尺寸：一次性给全尺寸，Windows
    # 才会在任务栏、Alt+Tab、文件列表里都拿得到清晰的图，而不是
    # 拿 256 硬缩。
    small = img.resize((256, 256), Image.LANCZOS)
    small.save(out, format="ICO", sizes=SIZES)

    # 顺手存一张 png，README 和仓库首页可以直接用（ico 没法预览）
    png = os.path.join(out_dir, "app.png")
    img.resize((512, 512), Image.LANCZOS).save(png)

    print("图标已生成：")
    print("  " + out)
    print("  " + png)
    print("  内嵌尺寸：" + ", ".join("%dx%d" % s for s in SIZES))


if __name__ == "__main__":
    main()
