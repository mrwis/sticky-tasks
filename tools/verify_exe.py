# -*- coding: utf-8 -*-
"""验证打包出来的 exe。三件事必须成立：

1. 双击能起来（不依赖本机 Python）
2. 数据落在 **exe 自己旁边**，不是 %TEMP%\\_MEIxxxx 那个临时解压目录
   —— 单文件 exe 最经典的翻车点：除 sys.executable 之外还有个 sys._MEIPASS，
     一旦数据写进后者，重启一次就全没了
3. 读也是从 exe 旁边读（外面改了 tasks.json，重开能看到）

顺便确认产物里**没有**混进仓库里的真实任务。

用法
----
    ../_build_venv/Scripts/python.exe tools/verify_exe.py
（要用**带 Pillow** 的解释器，它要截图。构建环境那个就带。）

它在项目上一级建个 _exetest/ 当"朋友的电脑"，跑完可以随手删。
"""

import ctypes
import json
import os
import shutil
import subprocess
import time
from ctypes import wintypes

u32 = ctypes.windll.user32
Proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)                       # sticky-tasks/
ROOT = os.path.dirname(REPO)                       # 项目根
SRC_EXE = os.path.join(REPO, "dist", "逍遥便利贴.exe")
WORK = os.path.join(ROOT, "_exetest")              # 假装是"朋友的电脑"
SHOTS = REPO
TITLE_KEY = "逍遥便利贴"

FAILS = []


def check(name, ok, extra=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + ("   " + extra if extra else ""))
    if not ok:
        FAILS.append(name)


def wt(h):
    n = u32.GetWindowTextLengthW(h)
    if not n:
        return ""
    b = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(h, b, n + 1)
    return b.value


def find(sub):
    out = []

    def cb(h, l):
        if u32.IsWindowVisible(h):
            t = wt(h)
            if t and sub in t:
                out.append((h, t))
        return True

    u32.EnumWindows(Proc(cb), 0)
    return out


def wait_win(sub, timeout):
    t0 = time.time()
    while time.time() - t0 < timeout:
        hits = find(sub)
        if hits:
            return hits[0][0]
        time.sleep(0.5)
    return None


def shot(hwnd, path):
    from PIL import ImageGrab
    rc = wintypes.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(rc))
    act = u32.GetForegroundWindow()
    img = ImageGrab.grab(bbox=(rc.left, rc.top, rc.right, rc.bottom),
                         all_screens=True)
    img.save(path)
    return act == hwnd, img.size


def read_data(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def kill_all():
    for h, _t in find(TITLE_KEY):
        u32.PostMessageW(h, 0x0010, 0, 0)
    time.sleep(1.5)


def main():
    print("=" * 62)
    print("验证 exe")
    print("=" * 62)

    if not os.path.exists(SRC_EXE):
        raise SystemExit("找不到 exe：%s\n先跑 tools/build_exe.py" % SRC_EXE)

    # ---------- 准备一个干净目录，模拟"朋友拿到一个新文件" ----------
    kill_all()
    if os.path.isdir(WORK):
        shutil.rmtree(WORK)
    os.makedirs(WORK)
    exe = os.path.join(WORK, "逍遥便利贴.exe")
    shutil.copy2(SRC_EXE, exe)
    data = os.path.join(WORK, "tasks.json")

    print("\n[1] 干净目录里只有 exe")
    check("拷进去之前没有 tasks.json", not os.path.exists(data))
    check("目录里现在只有 1 个文件",
          len(os.listdir(WORK)) == 1, "实际 %s" % os.listdir(WORK))

    # ---------- 第一回合：首次运行 ----------
    print("\n[2] 第一次双击（无 Python 依赖）")
    t0 = time.time()
    proc = subprocess.Popen([exe], cwd=WORK)
    hwnd = wait_win(TITLE_KEY, 60)
    boot = time.time() - t0
    check("窗口起来了", hwnd is not None, "%.1f 秒" % boot)
    if hwnd is None:
        proc.kill()
        return report()

    time.sleep(3)
    check("跑起来的是 exe 自己这个进程", proc.poll() is None)

    print("\n[3] 数据落在哪（这轮的重点）")
    check("exe 旁边生成了 tasks.json", os.path.exists(data), data)
    mei = os.path.join(os.environ.get("TEMP", ""), "")
    stray = []
    if os.path.isdir(mei):
        for n in os.listdir(mei):
            if n.startswith("_MEI") and os.path.exists(os.path.join(mei, n, "tasks.json")):
                stray.append(n)
    check("没有写进 %TEMP% 的解压目录", not stray, str(stray))

    seed_titles = []
    if os.path.exists(data):
        d = read_data(data)
        seed_titles = [t["title"] for t in d["tasks"]]
        # 判据用 id 而不是标题 —— 种子示例数据的标题里本来就写着"报销""NAS"，
        # 拿标题当判据会误报（第一版就是这么写错的）。
        repo = read_data(os.path.join(REPO, "tasks.json"))
        repo_ids = {t.get("id") for t in repo["tasks"]}
        new_ids = {t.get("id") for t in d["tasks"]}
        check("首次运行生成的是全新示例数据（id 和仓库里的真实任务不重合）",
              bool(new_ids) and not (new_ids & repo_ids),
              "%d 条：%s" % (len(d["tasks"]),
                            " / ".join(t[:14] for t in seed_titles)))

    first_png = os.path.join(SHOTS, "preview-打包版首次运行.png")
    front, size = shot(hwnd, first_png)
    check("截了图", os.path.exists(first_png),
          "%sx%s 前台=%s" % (size[0], size[1], front))

    u32.PostMessageW(hwnd, 0x0010, 0, 0)
    time.sleep(2.5)
    check("关掉之后进程真的退出了", proc.poll() is not None)

    # ---------- 第二回合：从外面改数据，看它读不读得到 ----------
    print("\n[4] 外面改 tasks.json，再打开一次（验证读取也走同一个位置）")
    d = read_data(data)
    d["tasks"][0]["title"] = "【验证】这条是从 exe 外面读进来的"
    d["tasks"][0]["note"] = "如果卡片上能看到这行字，说明读写都落在 exe 旁边"
    with open(data, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

    proc2 = subprocess.Popen([exe], cwd=WORK)
    hwnd2 = wait_win(TITLE_KEY, 60)
    check("第二次也起来了", hwnd2 is not None)
    if hwnd2:
        time.sleep(3)
        shot(hwnd2, os.path.join(SHOTS, "preview-打包版读取外部数据.png"))
        u32.PostMessageW(hwnd2, 0x0010, 0, 0)
        time.sleep(2)

    # 重开一次，确认改动被**程序自己**保存下来了（写路径也通）
    print("\n[5] 程序自己存盘之后，数据还认得")
    proc3 = subprocess.Popen([exe], cwd=WORK)
    hwnd3 = wait_win(TITLE_KEY, 60)
    if hwnd3:
        time.sleep(3)
        u32.PostMessageW(hwnd3, 0x0010, 0, 0)
        time.sleep(2.5)
    d2 = read_data(data)
    check("程序退出时把数据写回了 exe 旁边",
          d2["tasks"][0]["title"].startswith("【验证】"),
          repr(d2["tasks"][0]["title"]))

    check("目录里仍然只有 exe + tasks.json 两个文件（没到处乱写）",
          sorted(os.listdir(WORK)) == sorted(["逍遥便利贴.exe", "tasks.json"]),
          str(sorted(os.listdir(WORK))))

    kill_all()
    return report()


def report():
    print("\n" + "=" * 62)
    if FAILS:
        print("失败 %d 项：" % len(FAILS))
        for f in FAILS:
            print("  · " + f)
    else:
        print("全部通过")
    print("=" * 62)
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
