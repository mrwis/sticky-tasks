# -*- coding: utf-8 -*-
"""真机验证：窗口建在本进程里，但按键走**系统级注入**（keybd_event），
鼠标点击也走系统级注入 —— 这才是用户手指按下去的那条路径。

用系统 Python 跑（有 tkinter）：python tools/realkey_delete.py

为什么值得单独做一个：2026-10-27 报"选中后按 Delete 没反应"，根因是键盘焦点
留在顶栏输入框上（tk 点 Canvas 不动焦点，Entry 的 <Delete> 类绑定 return "break"，
事件到不了 toplevel）。进程内 event_generate 能测出来，但那是"事件直接生成"，
不是"真的按了一下"。同类问题（任何"按了没反应"的键 / 鼠标）都可以照这个改。

自测里已经用 event_generate 覆盖了这条路径，这个脚本是**额外**的一道：
真要怀疑"事件到底传没传到"，就跑它。
"""
import ctypes
import ctypes.wintypes as wt
import importlib.util
import os
import shutil
import sys
import tempfile
import time
import tkinter as tk

u32 = ctypes.windll.user32
REPO = r"F:\workbuddy\2026-10-10-20-45-09\sticky-tasks"
VK_DELETE = 0x2E


def hwnd_of(w):
    h = w.winfo_id()
    return u32.GetAncestor(h, 2) or h


def activate(hwnd):
    tid_me = ctypes.windll.kernel32.GetCurrentThreadId()
    tid_t = u32.GetWindowThreadProcessId(hwnd, None)
    fg = u32.GetForegroundWindow()
    tid_fg = u32.GetWindowThreadProcessId(fg, None)
    if tid_t != tid_me:
        u32.AttachThreadInput(tid_me, tid_t, True)
    if tid_fg != tid_t:
        u32.AttachThreadInput(tid_fg, tid_t, True)
    u32.BringWindowToTop(hwnd)
    u32.SetForegroundWindow(hwnd)
    if tid_t != tid_me:
        u32.AttachThreadInput(tid_me, tid_t, False)
    if tid_fg != tid_t:
        u32.AttachThreadInput(tid_fg, tid_t, False)


def pump(root, sec=0.5):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.02)


def main():
    tmp = tempfile.mkdtemp(prefix="realkey_")
    shutil.copy(os.path.join(REPO, "sticky.pyw"), os.path.join(tmp, "sticky.pyw"))
    spec = importlib.util.spec_from_file_location(
        "sticky", os.path.join(tmp, "sticky.pyw"))
    sticky = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sticky)
    sticky.DATA_FILE = os.path.join(tmp, "tasks.json")
    sticky.APP_DIR = tmp

    root = tk.Tk()
    app = sticky.App(root)
    root.geometry("1000x700+80+60")
    pump(root, 0.8)

    now = sticky.now_ts()
    t = {"id": sticky.new_id(), "title": "真机按键删除测试", "note": "",
         "p": 0, "due": "", "done": False, "order": 1.0, "subs": [],
         "logs": {}, "timer": 0, "repeat": "", "done_at": 0,
         "created_at": now, "remind_key": ""}
    app.tasks = [t]
    app.save()
    app.redraw()
    pump(root, 0.4)

    hwnd = hwnd_of(root)
    u32.SetWindowPos(hwnd, -1, 80, 60, 1000, 700, 0x0040)
    activate(hwnd)
    pump(root, 0.8)
    app.redraw()
    pump(root, 0.3)

    print("窗口置前：", u32.GetForegroundWindow() == hwnd)
    print("焦点在：", root.focus_get())

    # 卡片左上角（画布坐标）→ 屏幕坐标
    r = [x for x in app.regions if x[0] == "card" and x[1] == t["id"]][0]
    others = [(a, b, c, d) for (k, i, a, b, c, d) in app.regions if k != "card"]
    px = py = None
    for ax, ay in ((r[4] - 14, r[5] - 8), (r[4] - 14, (r[3] + r[5]) / 2.0)):
        if not any(a <= ax <= c and b <= ay <= d for (a, b, c, d) in others):
            px, py = ax, ay
            break
    sx = app.cv.winfo_rootx() + int(px)
    sy = app.cv.winfo_rooty() + int(py)
    print("点屏幕坐标", sx, sy)

    u32.SetCursorPos(sx, sy)
    pump(root, 0.2)
    u32.mouse_event(2, 0, 0, 0, 0)        # LEFTDOWN
    pump(root, 0.1)
    u32.mouse_event(4, 0, 0, 0, 0)        # LEFTUP
    pump(root, 0.5)

    selected = app.sel_tid == t["id"]
    print("真的选中了吗：", selected, "| 点完焦点在：", root.focus_get())

    # 系统级按一下 Delete
    u32.keybd_event(VK_DELETE, 0, 0, 0)
    pump(root, 0.1)
    u32.keybd_event(VK_DELETE, 0, 0x0002, 0)
    pump(root, 0.6)

    gone = app.task_by_id(t["id"]) is None
    n_trash = len(app.trash)
    print("任务没了吗：", gone, "| 回收站：", n_trash, "条")
    print("状态栏：", app.status.cget("text"))

    # 落盘也看一眼（用户看到的是"关掉再开还在不在"）
    import json
    with open(sticky.DATA_FILE, encoding="utf-8") as f:
        disk = json.load(f)
    print("磁盘上：任务 %d 条 / 回收站 %d 条"
          % (len(disk.get("tasks") or []), len(disk.get("trash") or [])))

    ok = selected and gone and n_trash >= 1
    print("真机按键删除：", "通过" if ok else "失败")
    root.destroy()
    shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
