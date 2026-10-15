# -*- coding: utf-8 -*-
"""把 sticky.pyw 打包成一个免装 Python 的单文件 exe。

用法
----
在**装了 PyInstaller 的解释器**下运行（构建环境见项目上级目录的 _build_venv）：

    _build_venv/Scripts/python.exe tools/build_exe.py

产物
----
    dist/逍遥便利贴.exe        ← 单文件，拷给谁都能双击运行
    dist/使用说明.txt          ← 给"朋友"看的，讲数据存在哪

为什么要有这个脚本，而不是手敲 pyinstaller
------------------------------------------
那一串参数（单文件 / 无控制台 / 图标 / 版本信息 / 一堆 exclude）改一次忘一次，
而且有两样东西**必须**和源码保持一致，手敲太容易忘：

  · 版本号 —— 从 sticky.pyw 的 APP_VERSION 读，不在这里再抄一份
              （抄两份的下场：程序里显示 1.0.0，exe 属性里是 0.9）
  · 图标   —— 缺了就现调 tools/make_icon.py 生成

★ 数据文件绝对不能打进 exe
  任务数据存在 exe **自己旁边**的 tasks.json（见 sticky.pyw 的 _app_dir()）。
  要是哪天想"顺手"把 tasks.json 用 --add-data 打进去，朋友拿到的就会是
  **你的任务**，而且他还改不动（exe 里的文件是只读的）。所以这里没有
  --add-data，一条都没有。首次运行由程序自己写一份示例数据。
"""

import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "sticky.pyw")
ICON = os.path.join(ROOT, "assets", "app.ico")
DIST = os.path.join(ROOT, "dist")
BUILD = os.path.join(ROOT, "build")
APP_NAME = "逍遥便利贴"

# 程序真正用到的标准库只有这些：
#   os re sys json shutil calendar datetime subprocess
#   tkinter(.font/.filedialog/.messagebox)  ctypes
# 下面这些是 PyInstaller 顺着手边的 import 链子拖进来的，全用不上。
# 分组写清楚"凭什么敢排掉" —— 以后想把哪条加回来，先看它属于哪一组。
EXCLUDES = [
    # ① 测试 / 文档 / 调试器 / 打包工具自己：只在开发和发布时用
    "unittest", "doctest", "pydoc", "pdb", "test",
    "lib2to3", "distutils", "setuptools", "pip", "wheel", "pkg_resources",

    # ② 网络与加密 —— 省得最多的一组
    #    这个程序**一个字节都不联网**（数据全在本地 json 里，帮助文案也
    #    明说了"全部功能都不用联网"）。排掉 ssl 之后，openssl 那两个
    #    dll（libcrypto-3.dll 6.2MB + libssl-3.dll 1.3MB）就不进产物了
    #    —— 光这一条就让 exe 瘦掉一半多。
    "ssl", "_ssl", "hashlib", "_hashlib", "hmac", "secrets",
    "socket", "_socket", "select", "selectors",
    "urllib", "http", "email", "smtplib", "ftplib", "poplib",
    "imaplib", "telnetlib", "xmlrpc", "webbrowser", "uuid",
    "asyncio", "concurrent", "multiprocessing",

    # ③ 数据库 / 结构化格式：数据就是一份明文 json，不碰这些
    "sqlite3", "xml", "html", "csv",

    # ④ 科学计算 / 图像：本机没装，装了也用不上
    #    （Pillow 只在 tools/make_icon.py 生成图标那一步用）
    "numpy", "PIL", "tkinter.test",
]


def log(msg):
    print(msg, flush=True)


def read_version():
    """从源码里读 APP_VERSION —— 单一来源，这里不再写第二份。"""
    with open(SRC, "r", encoding="utf-8") as f:
        src = f.read()
    m = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', src, re.M)
    if not m:
        raise SystemExit("在 sticky.pyw 里找不到 APP_VERSION，先确认改的是同一个文件")
    return m.group(1)


def version_tuple(v):
    parts = [int(x) if x.isdigit() else 0 for x in re.split(r"[.\-+]", v)]
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])


def ensure_icon():
    if os.path.exists(ICON):
        return
    log("图标不存在，先调用 tools/make_icon.py 生成…")
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_icon.py")],
                   check=True)


def write_version_file(version):
    """生成 exe 属性页里那份版本信息（右键 → 属性 → 详细信息）。

    注意编码：PyInstaller 用 PyInstaller.utils.misc.decode() 读这个文件，
    它会认 BOM 或 PEP263 注释。所以这里写 UTF-8 并在首行放 coding 注释 ——
    少了这一行，中文的 ProductName 会按 GBK 解，抛 UnicodeDecodeError。
    """
    fv = version_tuple(version)
    text = '''# -*- coding: utf-8 -*-
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=%(fv)r,
    prodvers=%(fv)r,
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('080404B0', [
        StringStruct('CompanyName', '逍遥便利贴'),
        StringStruct('FileDescription', '逍遥便利贴 · 任务清单'),
        StringStruct('FileVersion', '%(v)s'),
        StringStruct('InternalName', 'sticky-tasks'),
        StringStruct('OriginalFilename', '%(exe)s.exe'),
        StringStruct('ProductName', '逍遥便利贴'),
        StringStruct('ProductVersion', '%(v)s'),
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [0x0804, 1200])])
  ]
)
''' % {"fv": fv, "v": version, "exe": APP_NAME}

    os.makedirs(BUILD, exist_ok=True)
    path = os.path.join(BUILD, "version_info.txt")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return path


def write_readme(version):
    """给"拿到 exe 的朋友"看的一张纸。

    写在 dist/ 里，不写进 exe（exe 是单文件，塞不进旁边的东西），
    分享的时候连着它一起发过去就行。
    """
    text = """逍遥便利贴 · 任务清单  v%(v)s
========================================

怎么打开
    双击「逍遥便利贴.exe」就行。不需要装 Python，不需要联网，
    不需要管理员权限。第一次打开可能要等一两秒（在解压自己）。

你的任务存在哪
    就存在 exe 旁边的 tasks.json 里 —— 记事本就能打开看，
    也能直接复制走当备份。程序不会把你的任务传到任何地方。

    所以：想换电脑，把 exe 和 tasks.json 一起拷过去就行。
    只拷 exe 也可以，那会是一份全新的空白清单。

第一次打开看到的那几条任务
    是示例，用来让你知道每条能填些什么。随便改、随便删，
    全删干净了就是一张白纸。

想找说明书
    程序里点右上角「? 帮助」，或者按 F1。

四个格子是什么意思
    按"重要 / 紧急"分：
        重要且紧急    → 立刻做
        重要不紧急    → 计划做
        紧急不重要    → 委托做
        不紧急不重要  → 有空再做
    把卡片拖到别的格子里，优先级就改了。卡片上半张拖到另一张卡片上，
    会变成它的子任务。
""" % {"v": version}
    path = os.path.join(DIST, "使用说明.txt")
    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(text)
    return path


def main():
    if not os.path.exists(SRC):
        raise SystemExit("找不到 %s" % SRC)

    version = read_version()
    log("=" * 58)
    log("打包 逍遥便利贴  v%s" % version)
    log("=" * 58)

    # 先编译一遍。语法错误在 PyInstaller 那几屏刷屏日志里很难看见，
    # 在这里拦下来的话一眼就知道是哪儿的问题。
    log("\n[1/5] 语法检查…")
    subprocess.run([sys.executable, "-m", "py_compile", SRC], check=True)
    log("      OK")

    log("\n[2/5] 准备图标…")
    ensure_icon()
    log("      " + ICON)

    log("\n[3/5] 生成版本信息…")
    vfile = write_version_file(version)
    log("      " + vfile)

    log("\n[4/5] 调 PyInstaller（第一次会慢一点）…")
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile",                     # 单文件：分享的时候只需要给一个 exe
        "--windowed",                    # 不带黑色控制台窗口
        "--name", APP_NAME,
        "--icon", ICON,
        "--version-file", vfile,
        "--distpath", DIST,              # 产物
        "--workpath", BUILD,             # 中间文件
        "--specpath", BUILD,             # .spec 也丢中间目录，别脏了仓库根
    ]
    for mod in EXCLUDES:
        args += ["--exclude-module", mod]
    args.append(SRC)

    r = subprocess.run(args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        # PyInstaller 爱把错误埋在最后几行，只把这部分打出来
        tail = (r.stdout or "").strip().splitlines()[-25:]
        log("\n".join(tail))
        log((r.stderr or "").strip()[-2000:])
        raise SystemExit("PyInstaller 失败（退出码 %s）" % r.returncode)

    exe = os.path.join(DIST, APP_NAME + ".exe")
    if not os.path.exists(exe):
        raise SystemExit("PyInstaller 说成功了，但 %s 不存在" % exe)

    log("\n[5/5] 收尾…")
    txt = write_readme(version)
    size = os.path.getsize(exe) / 1024.0 / 1024.0
    log("      使用说明.txt")

    log("\n" + "=" * 58)
    log("好了：")
    log("  %s" % exe)
    log("  %.1f MB" % size)
    log("  %s" % txt)
    log("=" * 58)
    log("分享：把 exe（和 使用说明.txt）发给对方就行，对方不用装 Python。")
    log("提醒：exe 别放在 C:\\Program Files 这类要管理员权限的目录里，")
    log("      任务数据存在它旁边，那里写不进去。")


if __name__ == "__main__":
    main()
