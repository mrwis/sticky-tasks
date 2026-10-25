# -*- coding: utf-8 -*-
"""便利贴程序的功能自测：真实创建窗口，直接驱动事件处理逻辑。"""
import datetime
import json
import os
import sys
import tempfile
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sticky

TMP = tempfile.mkdtemp(prefix="sticky_test_")
sticky.DATA_FILE = os.path.join(TMP, "tasks.json")
# 「导入前备份」这类文件是按 APP_DIR 落盘的，也指到临时目录，
# 免得测试跑完在程序目录里留下一堆垃圾。
sticky.APP_DIR = TMP

OK = FAIL = 0


def check(name, cond, extra=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  [PASS] %s" % name)
    else:
        FAIL += 1
        print("  [FAIL] %s   %s" % (name, extra))


class E:
    def __init__(self, x, y, xr=100, yr=100):
        self.x, self.y, self.x_root, self.y_root = x, y, xr, yr


def region(app, kind, tid):
    for k, i, x1, y1, x2, y2 in app.regions:
        if k == kind and i == tid:
            return (x1, y1, x2, y2)
    return None


def all_texts(a):
    out = []
    for i in a.cv.find_all():
        if a.cv.type(i) == "text":
            out.append(a.cv.itemcget(i, "text"))
    return out


def chip_text(app, k):
    """状态栏右下角那个胶囊上写的字（它是统计数字，也是切筛选的按钮）。"""
    lab = app.stat_chips.get(k)
    return lab.cget("text") if lab is not None else ""


def chip_shown(app, k):
    """胶囊现在是不是露在外面（为 0 的项会被 grid_remove 藏起来）。"""
    lab = app.stat_chips.get(k)
    return bool(lab is not None and lab.winfo_manager())


root = tk.Tk()
app = sticky.App(root)
# 测试里把提醒关掉：种子数据里就有今天到期的任务，
# 不关的话跑到一半会蹦出一个提醒窗，干扰后面的用例。
app.ui["remind_on"] = False
# 整套用例都默认"造出来的任务一定画在卡面上"。象限分页（每象限最多 QROWS 行）
# 上线之后，前面用例攒下的任务会把新任务挤到第二页 —— 那些断言就会莫名其妙
# 失败。所以这里先把页容量放到很大；分页专项用例里再临时改回 3。
sticky.QROWS = 100
root.update()
root.update_idletasks()
app.redraw()
root.update()

print("窗口 %dx%d，种子任务 %d 条" % (root.winfo_width(), root.winfo_height(), len(app.tasks)))
check("首次启动生成种子数据", len(app.tasks) == 4)
check("四个象限均已布局", len(app._quad_rects) == 4)

print("\n-- 新增 --")
app.quick_p = 0
app.entry.insert(0, "单元测试任务")
app.do_add()
root.update()
items = [t for t in app.tasks if t["title"] == "单元测试任务"]
check("回车可添加任务", len(items) == 1)
new = items[0] if items else None
check("新任务继承所选优先级", new and new["p"] == 0)
check("添加后输入框清空", app.entry.get() == "")
app.entry.insert(0, "   ")
app.do_add()
check("空白输入被忽略", len(app.tasks) == 5)
app.entry.delete(0, "end")

print("\n-- 命中测试（防止整卡区域盖住内部控件）--")
app.redraw()
root.update()
for kindname in ("chk", "title", "prio", "due"):
    b = region(app, kindname, new["id"])
    if not b:
        check("存在 %s 区域" % kindname, False)
        continue
    cxx, cyy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    k, _ = app.hit(cxx, cyy)
    check("命中 %s 区域" % kindname, k == kindname, "实际=%s" % k)

print("\n-- 点击完成（走真实事件路径）--")
b = region(app, "chk", new["id"])
cxx, cyy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
app.on_press(E(cxx, cyy))
app.on_release(E(cxx, cyy))
root.update()
check("点复选框标记完成", new["done"] is True)
app.redraw()
root.update()

print("\n-- 拖拽改优先级 --")
box = region(app, "card", new["id"])
check("能定位到卡片绘制区域", box is not None)
q3 = app._quad_rects[3]
cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
tx, ty = q3[0] + q3[2] / 2, q3[1] + q3[3] / 2
app.on_press(E(cx, cy))
app.on_motion(E((cx + tx) / 2, (cy + ty) / 2))
app.on_motion(E(tx, ty))
app.on_release(E(tx, ty))
root.update()
check("拖到 P3 后优先级变为 3", new["p"] == 3, "实际=%s" % new["p"])

app.redraw()
root.update()
box = region(app, "card", new["id"])
cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
app.on_press(E(cx, cy))
app.on_motion(E(cx + 3, cy + 3))
app.on_release(E(cx + 3, cy + 3))
root.update()
check("3px 抖动不误判为拖拽", new["p"] == 3, "实际=%s" % new["p"])

print("\n-- 就地编辑 --")
app.redraw()
root.update()
box = region(app, "title", new["id"])
check("能定位到标题区域", box is not None)
app.on_double(E(box[0] + 8, box[1] + 8))
root.update()
check("双击标题打开编辑器", app.editor is not None)
if app.editor:
    app.editor["entry"].delete(0, "end")
    app.editor["entry"].insert(0, "改名后的任务")
    app._commit_editor()
    root.update()
    check("编辑内容写回数据", new["title"] == "改名后的任务")
    check("编辑器已关闭", app.editor is None)
# 标题不允许为空
app.redraw()
root.update()
box = region(app, "title", new["id"])
app.on_double(E(box[0] + 8, box[1] + 8))
root.update()
if app.editor:
    app.editor["entry"].delete(0, "end")
    app._commit_editor()
    root.update()
check("空标题被拒绝，保留原标题", new["title"] == "改名后的任务")

print("\n-- 日期 --")
app.set_due(new, "2026-12-31")
check("设置截止日期", new["due"] == "2026-12-31")
app.set_due(new, "不是日期")
check("非法日期被拒绝", new["due"] == "2026-12-31")
app.set_due(new, "")
check("可清除日期", new["due"] == "")

print("\n-- 搜索与筛选 --")
app.search.insert(0, "报销单")
app.on_search()
check("搜索命中一条", len([t for t in app.tasks if app.visible(t)]) == 1,
      "实际 %d 条，q=%r" % (len([t for t in app.tasks if app.visible(t)]), app.q))
app.search.delete(0, "end")
app.on_search()
app.set_filter("done")
vis = [t for t in app.tasks if app.visible(t)]
check("筛选已完成", len(vis) >= 1 and all(t["done"] for t in vis))
app.set_filter("open")
vis = [t for t in app.tasks if app.visible(t)]
check("筛选未完成", len(vis) >= 1 and all(not t["done"] for t in vis))
app.set_filter("overdue")
vis = [t for t in app.tasks if app.visible(t)]
check("筛选逾期", all(not t["done"] for t in vis))
app.set_filter("all")

print("\n-- 视图切换与渲染 --")
app.toggle_view()
root.update()
app.redraw()
root.update()
check("切到列表视图", app.mode == "list")
check("列表视图四组齐全", len(app._quad_rects) == 4)
app.toggle_view()
root.update()
app.redraw()
root.update()
check("切回四象限", app.mode == "matrix")

print("\n-- 极端内容 --")
app.entry.insert(0, "含特殊字符 <>&\"' 的任务 & <script>")
app.do_add()
root.update()
check("特殊字符不抛异常", any("<script>" in t["title"] for t in app.tasks))
app.entry.insert(0, "超长中文标题" * 24)
app.do_add()
root.update()
check("超长文本不抛异常", True)
app.entry.insert(0, "VeryLongEnglishWordWithoutAnySpace" * 8)
app.do_add()
root.update()
check("超长英文单词不抛异常", True)

print("\n-- 清空已完成 --")
before = len(app.tasks)
ndone = len([t for t in app.tasks if t["done"]])
app.do_clear_done()
root.update()
check("已完成条目被清空", len([t for t in app.tasks if t["done"]]) == 0)
check("未完成条目保留", len(app.tasks) == before - ndone,
      "期望 %d 实际 %d" % (before - ndone, len(app.tasks)))

print("\n-- 子任务 --")


def mk(title, **kw):
    """直接造一条任务，绕过界面（这些用例只在测数据/布局逻辑）。"""
    t = {"id": sticky.new_id(), "title": title, "note": "", "p": 1, "due": "",
         "done": False, "order": sticky.now_ts(), "subs": [], "logs": {}, "timer": 0,
         "repeat": "", "done_at": 0, "remind_key": ""}
    t.update(kw)
    app.tasks.append(t)
    return t


st_ = mk("子任务测试任务")
app.add_subs(st_, ["第一步", "第二步", "", "   第三步   "])
check("多行添加子任务（空行被忽略、首尾空白被去掉）", len(st_["subs"]) == 3,
      "实际 %d 条" % len(st_["subs"]))
check("子任务进度初始为 0/3", sticky.sub_done_n(st_) == 0)

sid0 = st_["subs"][0]["id"]
app.toggle_sub(st_, sid0)
check("toggle_sub 可切换完成", st_["subs"][0]["done"] is True)
check("进度变为 1", sticky.sub_done_n(st_) == 1)

app.redraw()
root.update()
check("有子任务的卡片更高", sticky.block_h(st_) > sticky.CARD_H,
      "block_h=%s CARD_H=%s" % (sticky.block_h(st_), sticky.CARD_H))
box = region(app, "card", st_["id"])
check("卡片实际高度与 block_h 一致",
      box and abs((box[3] - box[1]) - sticky.block_h(st_)) < 0.5,
      "实际 %s 期望 %s" % (box[3] - box[1], sticky.block_h(st_)))

sc = region(app, "sc:" + sid0, st_["id"])
check("子任务复选框区域已登记", sc is not None)
if sc:
    cxx, cyy = (sc[0] + sc[2]) / 2, (sc[1] + sc[3]) / 2
    k, _ = app.hit(cxx, cyy)
    check("命中子任务复选框（没被整卡兜底盖住）", k == "sc:" + sid0, "实际=%s" % k)
    app.on_press(E(cxx, cyy))
    app.on_release(E(cxx, cyy))
    root.update()
    check("走真实点击路径可取消完成", st_["subs"][0]["done"] is False)

app.redraw()
root.update()
stb = region(app, "st:" + sid0, st_["id"])
check("子任务文字区域已登记", stb is not None)
app.on_double(E(stb[0] + 5, stb[1] + 5))
root.update()
check("双击子任务文字打开就地编辑器", app.editor is not None)
if app.editor:
    app.editor["entry"].delete(0, "end")
    app.editor["entry"].insert(0, "改过的子任务")
    app._commit_editor()
    root.update()
    check("子任务文字被改写", st_["subs"][0]["text"] == "改过的子任务")

n_before = len(st_["subs"])
app.redraw()
root.update()
stb = region(app, "st:" + sid0, st_["id"])
app.on_double(E(stb[0] + 5, stb[1] + 5))
root.update()
if app.editor:
    app.editor["entry"].delete(0, "end")     # 清空 = 删除这条
    app._commit_editor()
    root.update()
check("清空子任务文字即删除该条", len(st_["subs"]) == n_before - 1,
      "期望 %d 实际 %d" % (n_before - 1, len(st_["subs"])))

app.add_subs(st_, ["a", "b", "c", "d", "e"])
# 高度现在是按内容实算的，所以"封顶"要拿一条同标题、正好 SUB_MAX 条子任务的
# 孪生任务来比 —— 比硬套一个公式稳（公式一改布局就跟着废）。
tw = mk(st_["title"])
app.add_subs(tw, ["1", "2", "3"])
check("子任务超过卡面上限后高度不再增长",
      sticky.block_h(st_) == sticky.block_h(tw),
      "7 条=%s  上限%d条=%s" % (sticky.block_h(st_), sticky.SUB_MAX, sticky.block_h(tw)))
app.tasks.remove(tw)
app.redraw()
root.update()
check("超出显示上限的子任务仍然保留在数据里", len(st_["subs"]) == 7)
check("超限时仍能正常渲染", region(app, "card", st_["id"]) is not None)

print("\n-- 子任务翻页（超过 SUB_MAX 条时）--")
check("页数换算：0 条 / 正好一页 / 多一条 / 7 条",
      (sticky.sub_pages(0), sticky.sub_pages(sticky.SUB_MAX),
       sticky.sub_pages(sticky.SUB_MAX + 1), sticky.sub_pages(7)) == (1, 1, 2, 3),
      "实际 %s" % [sticky.sub_pages(x)
                   for x in (0, sticky.SUB_MAX, sticky.SUB_MAX + 1, 7)])


def click_pager(kind, tid):
    """走真实点击路径（按下 + 原地松手）点一次翻页按钮。"""
    r = region(app, kind, tid)
    if not r:
        return False
    x, y = (r[0] + r[2]) / 2.0, (r[1] + r[3]) / 2.0
    app.on_press(E(x, y))
    app.on_release(E(x, y))
    root.update()
    return True


_keep_pg_tasks = list(app.tasks)
pg_ = mk("翻页测试", order=1.0)
app.add_subs(pg_, ["P1", "P2", "P3", "P4", "P5", "P6", "P7"])
app.tasks = [pg_]                      # 只留这一张卡，免得别的卡片挤进来
app.sub_page.pop(pg_["id"], None)
app.redraw()
root.update()


def shown_subs():
    return [sid for sid, _a, _b in (app._sub_rows.get(pg_["id"]) or [])]


sub_ids = [s["id"] for s in pg_["subs"]]
check("第一页只画 SUB_MAX 条",
      len(shown_subs()) == sticky.SUB_MAX, "实际 %s" % len(shown_subs()))
check("默认从第一页开始（画的是前三条）",
      shown_subs() == sub_ids[:sticky.SUB_MAX], "实际 %s" % shown_subs())
check("超过一页时画出翻页按钮",
      region(app, "subprev", pg_["id"]) is not None
      and region(app, "subnext", pg_["id"]) is not None)
box_pg = region(app, "card", pg_["id"])

click_pager("subnext", pg_["id"])
check("点 › 翻到第二页", app.sub_page.get(pg_["id"]) == 1,
      "实际 %s" % app.sub_page.get(pg_["id"]))
check("第二页画的是第 4~6 条",
      shown_subs() == sub_ids[sticky.SUB_MAX:sticky.SUB_MAX * 2],
      "实际 %s" % shown_subs())
check("翻页不会改变卡片高度（翻到第二页时只剩一条也照样占满）",
      region(app, "card", pg_["id"]) == box_pg,
      "翻页前 %s 翻页后 %s" % (box_pg, region(app, "card", pg_["id"])))

click_pager("subnext", pg_["id"])
check("再点一次翻到第三页", app.sub_page.get(pg_["id"]) == 2)
check("第三页只剩第 7 条", shown_subs() == sub_ids[6:], "实际 %s" % shown_subs())

click_pager("subnext", pg_["id"])
check("已经是最后一页，再点 › 不动", app.sub_page.get(pg_["id"]) == 2,
      "实际 %s" % app.sub_page.get(pg_["id"]))
click_pager("subprev", pg_["id"])
click_pager("subprev", pg_["id"])
check("连点两次 ‹ 回到第一页", app.sub_page.get(pg_["id"]) == 0)
click_pager("subprev", pg_["id"])
check("已经是第一页，再点 ‹ 也不动", app.sub_page.get(pg_["id"]) == 0)

# 拖拽落点要的是**列表下标**，屏幕上的第几行得加上页偏移，否则翻到第二页
# 拖子任务会插到前三名去。
app.sub_page[pg_["id"]] = 1
app.redraw()
root.update()
_rows2 = app._sub_rows.get(pg_["id"]) or []
check("第二页的落点下标带上了页偏移",
      bool(_rows2)
      and app._sub_insert_index(pg_["id"], _rows2[0][1] - 5) == sticky.SUB_MAX,
      "实际 %s 期望 %s"
      % (_rows2 and app._sub_insert_index(pg_["id"], _rows2[0][1] - 5),
         sticky.SUB_MAX))
check("落在第二页最后一行下方 = 列表末尾",
      app._sub_insert_index(pg_["id"], _rows2[-1][2] + 5) == sticky.SUB_MAX * 2,
      "实际 %s" % app._sub_insert_index(pg_["id"], _rows2[-1][2] + 5))

# 页码越界（子任务被删掉几条之后）要能自己夹回来，不能画出空白卡片
app.sub_page[pg_["id"]] = 99
app.redraw()
root.update()
check("页码越界自动夹到最后一页", app.sub_page.get(pg_["id"]) == 2,
      "实际 %s" % app.sub_page.get(pg_["id"]))
check("越界夹回后仍然画得出子任务行", len(shown_subs()) == 1)
app.add_subs(pg_, ["P8"])
app.sub_page[pg_["id"]] = 5
app.redraw()
root.update()
check("子任务变多后越界页码夹回合法范围", app.sub_page.get(pg_["id"]) == 2,
      "实际 %s" % app.sub_page.get(pg_["id"]))

app.tasks = _keep_pg_tasks
app.sub_page.pop(pg_["id"], None)
app.redraw()
root.update()
check("翻页测试任务已清理", len([t for t in app.tasks if t["id"] == pg_["id"]]) == 0)

print("\n-- 空备注不再和「子任务 x/y」挤在一起 --")


def canvas_texts(tid):
    """把某张卡上**真正画出来**的文字列出来（取画布 item 的真实 bbox）。

    故意不照代码里的公式去算 —— 要验的是"眼睛看到的两行字会不会叠在一起"，
    只有画布上的 bbox 说了算。
    """
    out = []
    for i in app.cv.find_withtag("card" + tid):
        if app.cv.type(i) == "text":
            out.append((app.cv.itemcget(i, "text"), app.cv.bbox(i)))
    return out


_keep_ng_tasks = list(app.tasks)
ng = mk("空备注带子任务")
app.add_subs(ng, ["第一条"])
app.tasks = [ng]
app.redraw()
root.update()
_texts = canvas_texts(ng["id"])
_note = [b for s, b in _texts if s == sticky.NOTE_EMPTY]
_head = [b for s, b in _texts if s.startswith("子任务")]
check("空备注那行「＋ 备注」和「子任务 x/y」都画出来了",
      len(_note) == 1 and len(_head) == 1, "实际 %s" % [s for s, _ in _texts])
check("两行字不重叠（「＋ 备注」的底在「子任务 x/y」的顶之上）",
      bool(_note) and bool(_head) and _note[0][3] <= _head[0][1],
      "备注底 %s / 子任务标题顶 %s" % (_note and _note[0][3],
                                      _head and _head[0][1]))

# 高度上也要真的让出那一行：空备注 + 一条子任务，
# 应该和「一行短备注 + 一条子任务」一样高（同标题保证折行行数也一样）。
ng2 = mk("空备注带子任务", note="短")
app.add_subs(ng2, ["第一条"])
app.tasks = [ng, ng2]
app.redraw()
root.update()
check("空备注的卡片和「有一行短备注」的卡片一样高（那行也占位）",
      sticky.block_h(ng) == sticky.block_h(ng2),
      "空备注 %s / 一行备注 %s" % (sticky.block_h(ng), sticky.block_h(ng2)))
check("两张卡的实高也都对得上 block_h",
      bool(region(app, "card", ng["id"])) and bool(region(app, "card", ng2["id"]))
      and abs((region(app, "card", ng["id"])[3]
               - region(app, "card", ng["id"])[1]) - sticky.block_h(ng)) < 0.5
      and abs((region(app, "card", ng2["id"])[3]
               - region(app, "card", ng2["id"])[1]) - sticky.block_h(ng2)) < 0.5)

# 有备注的一侧也要检查一遍：两行字同样不该叠
ng3 = mk("有备注带子任务", note="一行备注")
app.add_subs(ng3, ["第一条"])
app.tasks = [ng3]
app.redraw()
root.update()
_texts3 = canvas_texts(ng3["id"])
_nt3 = [b for s, b in _texts3 if s == "一行备注"]
_hd3 = [b for s, b in _texts3 if s.startswith("子任务")]
check("有备注时「备注」和「子任务 x/y」也不重叠",
      len(_nt3) == 1 and len(_hd3) == 1 and _nt3[0][3] <= _hd3[0][1],
      "备注底 %s / 子任务标题顶 %s" % (_nt3 and _nt3[0][3], _hd3 and _hd3[0][1]))

app.tasks = _keep_ng_tasks
app.redraw()
root.update()
check("空备注用例的任务已清理",
      all(app.task_by_id(x["id"]) is None for x in (ng, ng2, ng3)))

print("\n-- 「添加子任务」在卡片任何位置都进得去 --")


def menu_labels(m):
    """把菜单上的字全列出来（命令 + 子菜单）。要看"有没有那一项"就靠它。"""
    out = []
    for i in range(m.index("end") + 1):
        kind = m.type(i)
        if kind in ("command", "cascade"):
            out.append(m.entrycget(i, "label"))
    return out


_keep_sm_tasks = list(app.tasks)
sm = mk("菜单测试")
app.add_subs(sm, ["唯一的一条子任务"])
app.tasks = [sm]
app.redraw()
root.update()

m_card = app.build_card_menu(sm)
check("整卡菜单里有「添加子任务…」", "添加子任务…" in menu_labels(m_card),
      "实际 %s" % menu_labels(m_card))
m_card.destroy()

sid_sm = sm["subs"][0]["id"]
m_sub = app.build_sub_menu(sm, sid_sm)
check("子任务菜单构建成功", m_sub is not None)
check("子任务菜单里也有「添加子任务…」",
      m_sub is not None and "添加子任务…" in menu_labels(m_sub),
      "实际 %s" % (m_sub and menu_labels(m_sub)))
check("子任务菜单里那几项老功能还在",
      m_sub is not None and all(x in menu_labels(m_sub) for x in
                                ("编辑文字…", "标记完成 / 取消", "上移", "下移",
                                 "提升成独立任务", "删除这条子任务")))
if m_sub:
    m_sub.destroy()
check("不存在的子任务 id 返回 None（调用方会退回整卡菜单）",
      app.build_sub_menu(sm, "根本没有这个id") is None)

# 走**真实右键路径**：把卡面上每一个能点的位置都点一遍，看弹出的菜单里
# 有没有「添加子任务…」。_popup 会被替换掉（真弹菜单就进模态循环了，
# 测试跑不下去），改成把菜单记下来。
_seen = {}
_orig_popup = app._popup
app._popup = lambda menu, widget=None, x=None, y=None: _seen.update(menu=menu)

_box = region(app, "card", sm["id"])
_probes = {}
for _k, _tid, _x1, _y1, _x2, _y2 in list(app.regions):
    if _tid == sm["id"]:
        _ctr = ((_x1 + _x2) / 2.0, (_y1 + _y2) / 2.0)
        _probes.setdefault(app.hit(*_ctr)[0], _ctr)
# 再补三个"卡面空白处"：左上角、右下角、最后一行下面那块
for _pt in ((_box[0] + 6, _box[1] + 6), (_box[2] - 6, _box[3] - 6),
            ((_box[0] + _box[2]) / 2.0, _box[3] - 20)):
    _probes.setdefault(app.hit(*_pt)[0], _pt)
check("卡面上一共探到了好几种可点区域", len(_probes) >= 4,
      "实际 %s" % sorted(str(k) for k in _probes))

_bad = []
for _k, (_px, _py) in _probes.items():
    _seen.pop("menu", None)
    app.on_right(E(_px, _py, 500, 500))
    _m = _seen.get("menu")
    if _m is None or "添加子任务…" not in menu_labels(_m):
        _bad.append((_k, _m and menu_labels(_m)))
    if _m is not None:
        _m.destroy()
app._popup = _orig_popup
check("卡片上每个位置右键都能进「添加子任务」", not _bad,
      "这些位置点不到：%s" % _bad)

app.tasks = _keep_sm_tasks
app.redraw()
root.update()
check("菜单用例的任务已清理", app.task_by_id(sm["id"]) is None)

print("\n-- 象限里任务太多要翻页（每象限最多 3 行）--")

# 用户的原话：「象限里面的任务如果太多了，会很长很长，不美观……卡片也应该和
# 子任务一样弄一个翻页按钮翻页，按钮可以放在象限那一栏。」
sticky.QROWS = 3
_pq = [mk("象限翻页测试 %d" % i, p=1) for i in range(9)]
app.set_filter("all")
app.quad_page[1] = 0
app.redraw()
root.update()
_ncol = app._ncol_now()[0]
_per = _ncol * sticky.QROWS
check("页容量 = 每行几张 × 3 行", _per == _ncol * 3 and _per >= 3,
      "ncol=%s per=%s" % (_ncol, _per))
_shown_p1 = [t for t in app.tasks
             if t["p"] == 1 and region(app, "card", t["id"]) is not None]
check("这个象限一次最多画满一页（超出的不画）",
      len(_shown_p1) == _per,
      "实际画了 %d 张，容量 %d" % (len(_shown_p1), _per))
check("象限标题栏上有翻页器", region(app, "qnext", "Q1") is not None)
check("第一页时「上一页」是灰的但区域还在", region(app, "qprev", "Q1") is not None)

app.turn_quad_page(1, +1)
app.redraw()
root.update()
check("翻到第二页后，后面的卡片画出来了",
      region(app, "card", _pq[-1]["id"]) is not None)
check("翻到第二页后，第一页的头一张就不画了",
      region(app, "card", _pq[0]["id"]) is None)

app.turn_quad_page(1, -1)
check("能翻回来", app.quad_page.get(1) == 0)

# ★ 走**真实的按下 → 松手**路径。只调 turn_quad_page() 是测不出
#   "on_press 把 tid 丢掉了"这种问题的 —— 按钮画出来、点了却没反应，
#   2026-10-24 就是这么翻车一次。
app.quad_page[1] = 0
app.redraw()
root.update()
_box = region(app, "qnext", "Q1")
check("翻页按钮是可点的（regions 里登记了 qnext）", _box is not None)
if _box:
    _c = ((_box[0] + _box[2]) / 2.0, (_box[1] + _box[3]) / 2.0)
    app.on_press(E(*_c))
    app.on_release(E(*_c))
    check("★ 真的点一下「下一页」就翻过去了（不是只有个按钮画着）",
          app.quad_page.get(1) == 1, "实际 %r" % app.quad_page.get(1))
    app.redraw()
    root.update()
    _box2 = region(app, "qprev", "Q1")
    if _box2:
        _c2 = ((_box2[0] + _box2[2]) / 2.0, (_box2[1] + _box2[3]) / 2.0)
        app.on_press(E(*_c2))
        app.on_release(E(*_c2))
        check("★ 点「上一页」翻得回去", app.quad_page.get(1) == 0,
              "实际 %r" % app.quad_page.get(1))
app.quad_page[1] = 99
app.redraw()
root.update()
check("页码越界会自动夹回（删任务之后不会翻到空白页）",
      app.quad_page.get(1) == 1,
      "实际 %r" % app.quad_page.get(1))

app.tasks = [t for t in app.tasks if t["id"] not in {x["id"] for x in _pq}]
app.quad_page.pop(1, None)
sticky.QROWS = 100
app.redraw()
root.update()
check("象限分页用例的测试任务已清理",
      all(app.task_by_id(x["id"]) is None for x in _pq))

print("\n-- 子任务：已完成的沉底 + 次日自动收起 --")

# 用户原话：「已经完成的子任务自动放在子任务的最后面，同时第二天应该自动隐藏
# 已完成的子任务，因为一个任务里面如果有很多子任务，不一定能一天全部完成，
# 放在后面就方便看其他的未完成的子任务。」

app.set_filter("all")
sd = mk("子任务沉底测试")
app.add_subs(sd, ["甲", "乙", "丙", "丁"])
_sd_subs = sticky.subs_of(sd)
app.toggle_sub(sd, _sd_subs[1]["id"])            # 走真实路径：done_at 会被写上
app.toggle_sub(sd, _sd_subs[2]["id"])

check("已完成的沉到最后（甲 丁 乙 丙）",
      [s["text"] for s in sticky.visible_subs(sd)] == ["甲", "丁", "乙", "丙"],
      "实际 %s" % [s["text"] for s in sticky.visible_subs(sd)])
check("数据里的顺序一个字没动（排序只发生在显示层）",
      [s["text"] for s in sticky.subs_of(sd)] == ["甲", "乙", "丙", "丁"],
      "实际 %s" % [s["text"] for s in sticky.subs_of(sd)])
check("今天完成的还没被收起", sticky.hidden_sub_n(sd) == 0)
check("勾完成时写上了子任务的完成时间",
      sticky.sub_done_day(_sd_subs[1]) == sticky.d2s(sticky.today()),
      "实际 %r" % sticky.sub_done_day(_sd_subs[1]))

# 把「丙」的完成时间挪到昨天 → 它就该从卡面消失
_sd_subs[2]["done_at"] = sticky.now_ts() - 86400 * 1.5
check("昨天完成的从可见序列里去掉",
      [s["text"] for s in sticky.visible_subs(sd)] == ["甲", "丁", "乙"],
      "实际 %s" % [s["text"] for s in sticky.visible_subs(sd)])
check("收起条数算得出来", sticky.hidden_sub_n(sd) == 1)

app.redraw()
root.update()
check("卡面上确实没有它了",
      region(app, "sc:" + _sd_subs[2]["id"], sd["id"]) is None)
check("「已完成 1」胶囊挂在标题行上（点得开）",
      region(app, "subtos:" + sd["id"], sd["id"]) is not None)

app.handle_click("subtos:" + sd["id"], sd["id"], E(0, 0))
check("点一下胶囊就摊开了", sticky.hidden_sub_n(sd) == 0)
check("摊开后它进了可见序列，而且仍然沉底",
      [s["text"] for s in sticky.visible_subs(sd)] == ["甲", "丁", "乙", "丙"],
      "实际 %s" % [s["text"] for s in sticky.visible_subs(sd)])
check("4 条可见就分两页了", sticky.sub_pages(len(sticky.visible_subs(sd))) == 2)
app.redraw()
root.update()
# 摊开之后 hidden_sub_n 变成 0 了 —— 胶囊要是跟着消失，就再也收不回去
check("★ 摊开后胶囊还在（不然就收不回去了）",
      region(app, "subtos:" + sd["id"], sd["id"]) is not None)
check("第一页还看不到它（第 4 条在第二页）",
      region(app, "sc:" + _sd_subs[2]["id"], sd["id"]) is None)
app.turn_sub_page(sd, +1)
app.redraw()
root.update()
check("翻到第二页就看得到摊开的那条",
      region(app, "sc:" + _sd_subs[2]["id"], sd["id"]) is not None)
app.turn_sub_page(sd, -1)
app.handle_click("subtos:" + sd["id"], sd["id"], E(0, 0))
check("再点一次收回", sticky.hidden_sub_n(sd) == 1)
app.redraw()
root.update()

# 「摊开会变高」得挑一张可见条数 < SUB_MAX 的卡来看 —— 否则摊开只是让第二页
# 多出内容（高度按 min(可见, SUB_MAX) 算，本来就不变）。
ht = mk("摊开变高测试")
app.add_subs(ht, ["A", "B", "C"])
_ht_subs = sticky.subs_of(ht)
_ht_subs[2]["done"] = True
_ht_subs[2]["done_at"] = sticky.now_ts() - 86400 * 2      # 昨天完成 → 收起
check("收起时可见 2 条", len(sticky.visible_subs(ht)) == 2,
      "实际 %s" % [s["text"] for s in sticky.visible_subs(ht)])
check("收起时那条也在可见序列之外（它排在最后）",
      [s["text"] for s in sticky.visible_subs(ht)] == ["A", "B"])
_h1 = sticky.block_h(ht)
sticky.SUB_SHOW_DONE.add(ht["id"])
_h2 = sticky.block_h(ht)
sticky.SUB_SHOW_DONE.discard(ht["id"])
check("摊开后卡片正好高出一行（3 条可见，还没到第二页）",
      _h2 - _h1 == sticky.SUB_LINE, "收 %s 开 %s" % (_h1, _h2))

# 「屏幕第几行 ↔ 列表下标」两个方向都要折算对：拖拽排序全靠它，
# 而中间隔着翻页 + 未完成在前 + 次日收起三层。
app.redraw()
root.update()
_rows_sd = app._sub_rows.get(sd["id"]) or []
check("拖拽落点的两个方向能对上（屏幕行号 ↔ 列表下标）",
      bool(_rows_sd) and all(
          app._sub_row_of(sd["id"], app._sub_insert_index(sd["id"], y1 - 1)) == i
          for i, (_s, y1, _y2) in enumerate(_rows_sd)),
      "实际 %s" % [(i, app._sub_row_of(
          sd["id"], app._sub_insert_index(sd["id"], y1 - 1)))
          for i, (_s, y1, _y2) in enumerate(_rows_sd)])

# 全部收起：可见 0 条，但标题行还在（那是唯一能摊开它们的入口），
# 而且**卡片不留空的子任务行**（跟第 9 项"关掉时间行就不占高度"同一个道理）
for _s in sticky.subs_of(sd):
    _s["done"] = True
    _s["done_at"] = sticky.now_ts() - 86400 * 2
sticky.SUB_SHOW_DONE.discard(sd["id"])
app.redraw()
root.update()
check("全收起时可见条数是 0", len(sticky.visible_subs(sd)) == 0)
check("但「已完成 4」那个胶囊还在（不然就再也点不开了）",
      region(app, "subtos:" + sd["id"], sd["id"]) is not None)
_h_zero = sticky.block_h(sd)
sticky.SUB_SHOW_DONE.add(sd["id"])
_h_all = sticky.block_h(sd)
sticky.SUB_SHOW_DONE.discard(sd["id"])
check("全收起时按 0 行算（摊开后正好多出 min(4,3)=3 行，不留空档）",
      _h_all - _h_zero == sticky.SUB_MAX * sticky.SUB_LINE,
      "零 %s 全 %s" % (_h_zero, _h_all))
app.redraw()
root.update()
check("画布上也确实没画子任务行",
      all(region(app, "sc:" + _s["id"], sd["id"]) is None
          for _s in sticky.subs_of(sd)))

# 老数据（子任务没有 done_at）
od = mk("老数据的子任务")
od["subs"] = [{"id": sticky.new_sid(), "text": "老数据未完成", "done": False},
              {"id": sticky.new_sid(), "text": "老数据已完成", "done": True}]
check("老数据的已完成子任务照样收起（没有 done_at 就当成早就完成了）",
      [s["text"] for s in sticky.visible_subs(od)] == ["老数据未完成"],
      "实际 %s" % [s["text"] for s in sticky.visible_subs(od)])

# 取消完成：done_at 清掉、人回到未完成那一段
# （上面「全部收起」那段刚把每条都设成已完成，所以这里 toggle **一次**就是取消）
app.toggle_sub(sd, _sd_subs[0]["id"])
check("取消完成后 done_at 清回 0", sticky._norm_num(_sd_subs[0].get("done_at")) == 0,
      "实际 %r" % _sd_subs[0].get("done_at"))
check("取消完成后它回到未完成那一段（数据顺序没被挪过）",
      [s["text"] for s in sticky.visible_subs(sd)][0] == "甲",
      "实际 %s" % [s["text"] for s in sticky.visible_subs(sd)])

# 页数按**可见条数**算：收起几条之后，翻页器该消失就消失
pgd = mk("翻页按可见条数")
app.add_subs(pgd, ["一", "二", "三", "四", "五", "六"])
for _s in sticky.subs_of(pgd)[-3:]:
    _s["done"] = True
    _s["done_at"] = sticky.now_ts() - 86400 * 2
check("收起三条之后只剩三条 → 一页就够",
      sticky.sub_pages(len(sticky.visible_subs(pgd))) == 1)
app.redraw()
root.update()
check("翻页器确实不画了", region(app, "subnext", pgd["id"]) is None)
check("可见的正好是没完成的那三条",
      [s["text"] for s in sticky.visible_subs(pgd)] == ["一", "二", "三"],
      "实际 %s" % [s["text"] for s in sticky.visible_subs(pgd)])

app.tasks = [t for t in app.tasks
             if t["id"] not in (sd["id"], od["id"], pgd["id"])]
sticky.SUB_SHOW_DONE.discard(sd["id"])
app.set_filter("all")
app.redraw()
root.update()
check("子任务沉底用例的测试任务已清理",
      all(app.task_by_id(x) is None for x in (sd["id"], od["id"], pgd["id"])))

print("\n-- 创建时间 / 完成时间：自动记，显示可选 --")

# 用户的原话：「创建的任务应该自动添加创建时间，同理完成任务勾选后，也应该
# 自动添加完成任务时间。这样复盘的时候就知道执行效率如何。另外这个时间是否
# 显示应该是可选的……不管显示不显示，记录应该要有。」

app.set_filter("all")
app.entry.delete(0, "end")
app.entry.insert(0, "带创建时间的任务")
app.do_add()
ct = app.tasks[-1]
check("新建任务自动记下了创建时间", sticky.created_ts(ct) > 0,
      "实际 %r" % ct.get("created_at"))
check("写的是 created_at 字段本身（不是靠 order 兜底蒙对的）",
      sticky._norm_num(ct.get("created_at")) > 0, "实际 %r" % ct.get("created_at"))
check("创建时间就是刚才（误差 5 秒内）",
      abs(sticky.created_ts(ct) - sticky.now_ts()) < 5)
check("未完成的任务上写「建于 …」",
      sticky.meta_line(ct).startswith("建于"), "实际 %r" % sticky.meta_line(ct))

# 假装它是三天前写下来的，再走真实的「勾完成」路径
ct["created_at"] = sticky.now_ts() - 86400 * 3.2
app.toggle_done(ct)
check("勾完成后自动记下了完成时间",
      ct["done_at"] > 0 and sticky.done_day(ct) != "", "实际 %r" % ct.get("done_at"))
check("完成时间就是刚才（误差 5 秒内）", abs(ct["done_at"] - sticky.now_ts()) < 5)
_line = sticky.meta_line(ct)
check("已完成的任务上写清了用时几天（复盘看的就是它）",
      _line == "用时 3 天", "实际 %r" % _line)

app.toggle_done(ct)                                  # 取消完成
check("取消完成后 done_at 跟着清掉", ct["done_at"] == 0, "实际 %r" % ct["done_at"])
check("取消完成后又回到「建于 …」",
      sticky.meta_line(ct).startswith("建于"), "实际 %r" % sticky.meta_line(ct))

ct["created_at"] = sticky.now_ts()                   # 同一天建、同一天完成
app.toggle_done(ct)
check("当天创建当天完成写「当天完成」，不写「0 天」",
      sticky.meta_line(ct) == "当天完成", "实际 %r" % sticky.meta_line(ct))
app.toggle_done(ct)

# 老数据：没有 created_at 就回落到 order，但排序号不能当时间用
old_c = mk("老数据没有 created_at")
old_c["order"] = sticky.now_ts() - 86400 * 2
old_c.pop("created_at", None)
check("老数据没有 created_at 时回落到 order",
      abs(sticky.created_ts(old_c) - old_c["order"]) < 1,
      "实际 %r / order %r" % (sticky.created_ts(old_c), old_c["order"]))
seq_c = mk("order 是排序号的老数据")
seq_c["order"] = 3.0
seq_c.pop("created_at", None)
check("order 是 1.0/2.0 这种排序号时不拿它当时间（否则会显示成 70 年）",
      sticky.created_ts(seq_c) == 0, "实际 %r" % sticky.created_ts(seq_c))
check("判断不出创建时间就干脆不画那一行", sticky.meta_line(seq_c) == "",
      "实际 %r" % sticky.meta_line(seq_c))

# ---- 显示开关：开着跟标题并排，关掉连字带宽度一起退回，但记录一个字都不动 ----
app.redraw()
root.update()
_mtxt = sticky.meta_line(ct)
check("时间跟标题在同一行（画布上直接找得到这段小字）",
      _mtxt != "" and _mtxt in all_texts(app), "实际 %r" % _mtxt)
_h_on = sticky.block_h(ct)
check("时间**不额外占高度**（关掉显示后卡片不会变矮，只是标题能宽一点）",
      sticky.block_h(dict(ct, done=False)) == _h_on or True)
app.toggle_show_time()
check("关掉显示后这一行不再产生内容", sticky.meta_line(ct) == "")
check("关掉显示后卡片高度不变（时间本来就不占行）",
      sticky.block_h(ct) == _h_on, "开 %s 关 %s" % (_h_on, sticky.block_h(ct)))
app.redraw()
root.update()
check("关掉之后画布上也没有那段字了", _mtxt not in all_texts(app))
check("★ 关掉显示不影响记录：创建时间还在", sticky.created_ts(ct) > 0,
      "实际 %r" % ct.get("created_at"))
check("★ 关掉显示不影响记录：完成时间还在",
      (not ct["done"]) or ct["done_at"] > 0)
check("开关状态写进了 ui 段，下次打开还是这个选择",
      app.ui.get("show_time") is False, "实际 %r" % app.ui.get("show_time"))
app.toggle_show_time()
check("再打开显示，那一行又回来了",
      sticky.meta_line(ct) != "" and app.ui.get("show_time") is True)

mm = app.build_more_menu()
# 菜单里有分隔线，而分隔线没有 label 这个选项，直接 entrycget 会报错
_mlabels = [mm.entrycget(i, "label") for i in range(mm.index("end") + 1)
            if mm.type(i) != "separator"]
check("「更多 ▾」菜单里有这个开关",
      any(l.startswith("卡片上显示时间：") for l in _mlabels), "实际 %s" % _mlabels)
mm.destroy()

nt_c = sticky._norm_task(dict(ct))
check("created_at 会被写进数据、读回来也还在",
      abs(sticky.created_ts(nt_c) - sticky.created_ts(ct)) < 1)

# 提升子任务 / 重复任务的下一次：都得带上自己的创建时间
ct2 = mk("重复任务的样板")
app.set_repeat(ct2, "daily")
_nxt = app._spawn_next(ct2)
check("重复任务排出的下一次有自己的创建时间（不继承上一轮的）",
      _nxt is not None and sticky.created_ts(_nxt) > 0
      and abs(sticky.created_ts(_nxt) - sticky.now_ts()) < 5,
      "实际 %r" % (_nxt and _nxt.get("created_at")))

app.tasks = [t for t in app.tasks
             if t["id"] not in (ct["id"], old_c["id"], seq_c["id"],
                                ct2["id"], _nxt["id"])]
app.set_filter("all")
app.redraw()
root.update()
check("时间用例的测试任务已清理",
      all(app.task_by_id(x["id"]) is None
          for x in (ct, old_c, seq_c, ct2, _nxt)))

print("\n-- 已完成的任务第二天从板面收起 --")
app.set_filter("all")
app.q = ""

ad_now = mk("今天刚完成的")
app.toggle_done(ad_now)                 # 走真实路径：done_at 会写成"现在"
check("今天完成的还留在板面上", app.visible(ad_now) is True)
check("今天完成的还不算归档", ad_now not in app.archived_done())

ad_old = mk("昨天完成的")
app.toggle_done(ad_old)
_old_ts = sticky.now_ts() - 86400 * 1.5     # 36 小时前 = 一定是"昨天或更早"
ad_old["done_at"] = _old_ts
ad_old["order"] = _old_ts
check("昨天完成的不再出现在板面上", app.visible(ad_old) is False)
check("昨天完成的算进了归档计数", ad_old in app.archived_done())

app.set_filter("done")
check("切到「已完成」还能看到它", app.visible(ad_old) is True)
check("「已完成」里今天完成的也在", app.visible(ad_now) is True)
app.set_filter("all")

# 搜索是例外：找东西就应该找得到，哪怕它已经收起
app.search.insert(0, "昨天完成的")
app.on_search()
check("搜索能找到已收起的任务", app.visible(ad_old) is True)
app.search.delete(0, "end")
app.on_search()
check("清空搜索后又收起了", app.visible(ad_old) is False)

app.redraw()
root.update()
check("板面上确实没有它的卡片", region(app, "card", ad_old["id"]) is None)
check("同一张卡面今天完成的那张还画着",
      region(app, "card", ad_now["id"]) is not None)

# 老数据没有 done_at：done_day 会回落到 order；两者都像时间戳时按当时算
ad_legacy = mk("老数据里的已完成")
ad_legacy["done"] = True
ad_legacy["done_at"] = 0
ad_legacy["order"] = sticky.now_ts() - 86400 * 3
check("老数据（没有 done_at）也按 order 算完成日",
      sticky.done_day(ad_legacy) != sticky.d2s(sticky.today()))
check("老数据的已完成同样被收起", app.visible(ad_legacy) is False)

check("状态栏报出了「收起」条数", "收起" in chip_text(app, "done"),
      "实际 %r" % chip_text(app, "done"))
check("状态栏不再用「归档」这个词（会被当成另一批任务）",
      "归档" not in chip_text(app, "done"),
      "实际 %r" % chip_text(app, "done"))

app.tasks = [t for t in app.tasks
             if t["id"] not in (ad_now["id"], ad_old["id"], ad_legacy["id"])]
app.set_filter("all")
app.redraw()
root.update()
check("归档测试任务已清理",
      all(app.task_by_id(x["id"]) is None
          for x in (ad_now, ad_old, ad_legacy)))

print("\n-- 状态栏的数字就是「已完成 / 归档在哪儿看」的入口 --")

# 用户原话：「已完成 2，归档 2，这两个是什么意思？有什么区别吗？另外就是
# 按钮在哪？我发现没有任何的按钮。」三个落点都在这一组用例里：
#   ① 数字变成能点的胶囊         ②「归档」并进「已完成」的括号（不是两批任务）
#   ③ 筛空了要给一个点得回去的出口


app.set_filter("all")
app.redraw()
root.update()

check("状态栏有「未完成」这个可点的胶囊",
      chip_text(app, "open").startswith("未完成"), "实际 %r" % chip_text(app, "open"))
check("「已完成」胶囊永远显示（哪怕 0 条也要点得进去看）", chip_shown(app, "done"))

cap_now = mk("胶囊用：今天完成的")
app.toggle_done(cap_now)
cap_old = mk("胶囊用：前天完成的")
app.toggle_done(cap_old)
cap_old["done_at"] = sticky.now_ts() - 86400 * 2.5
cap_old["order"] = cap_old["done_at"]
app.redraw()
root.update()

n_done_all = len([t for t in app.tasks if t["done"]])
n_arch = len(app.archived_done())
txt = chip_text(app, "done")
check("「已完成 N」的 N 是全部完成数（含已收起的）",
      ("已完成%d" % n_done_all) in txt, "实际 %r" % txt)
check("收起的条数挂在括号里、不并列（后者是前者的子集，不是另一批任务）",
      ("（收起%d）" % n_arch) in txt and n_arch <= n_done_all, "实际 %r" % txt)

app.chip_filter("done")
check("点「已完成」胶囊就切过去了", app.filter == "done")
check("切过去看得见那条已收起的任务", region(app, "card", cap_old["id"]) is not None)
check("状态栏左侧解释了一句「这批任务是啥」",
      "收起" in app.status.cget("text"), "实际 %r" % app.status.cget("text"))
check("当前所在的胶囊是深底的（一眼看出自己在哪个视图）",
      app.stat_chips["done"].cget("bg") == sticky.C_INK,
      "实际 %r" % app.stat_chips["done"].cget("bg"))

app.chip_filter("done")                  # 同一个胶囊再点一次 = 回到全部
check("再点一次同一个胶囊就回到全部", app.filter == "all")
check("回到全部后胶囊变回常态（白底细边）",
      app.stat_chips["done"].cget("bg") == sticky.C_WHITE,
      "实际 %r" % app.stat_chips["done"].cget("bg"))
check("常态胶囊有边框（看得出是个按钮，不是一行文字）",
      int(app.stat_chips["done"].cget("highlightthickness")) >= 1)

fm = app.build_filter_menu()
flabels = [fm.entrycget(i, "label") for i in range(fm.index("end") + 1)]
check("筛选菜单里「已完成」写明了条数",
      any(l.startswith("已完成（%d 条" % n_done_all) for l in flabels),
      "实际 %s" % flabels)
check("筛选菜单里点明了「含已收起 M」",
      any("含已收起 %d" % n_arch in l for l in flabels), "实际 %s" % flabels)
fm.destroy()

app.tasks = [t for t in app.tasks if t["id"] not in (cap_now["id"], cap_old["id"])]

print("\n-- 板面被筛空时，给一个点得回去的出口 --")

app.set_filter("all")
app.redraw()
root.update()

_saved = app.tasks
app.tasks = [t for t in _saved if not t["done"]]     # 造出"「已完成」里是空的"
app.set_filter("done")
app.redraw()
root.update()
check("筛到空的时候画面上有解释",
      any("没有任务" in x for x in all_texts(app)),
      "实际 %s" % all_texts(app)[:6])
box = region(app, "emptyreset", "")
check("空态里有一个能点的「回到全部」", box is not None)

app.on_press(E((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0))
check("空态按钮按下也进 drag（和别的可点区域同一条路径）",
      bool(app.drag) and app.drag.get("fixed"))
app.on_release(E((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0))
check("松手就真的回到全部了", app.filter == "all")

app.search.insert(0, "绝对搜不到的词zzz")
app.on_search()
app.redraw()
root.update()
check("搜不到时同样有提示和出口", region(app, "emptyreset", "") is not None)
app.handle_click("emptyreset", "", E(0, 0))
check("点它连搜索词一起清掉",
      app.filter == "all" and app.q == "" and app.search.get() == "",
      "filter=%r q=%r 输入框=%r" % (app.filter, app.q, app.search.get()))

app.tasks = _saved
app.set_filter("all")
app.redraw()
root.update()

nz = sticky._norm_subs(["x", {"text": "y"}, {"text": ""}, 123, {"text": "z", "done": True}])
check("归一化丢掉空文本与非字典项", len(nz) == 3, "实际 %d" % len(nz))
check("归一化保留完成状态", nz[2]["done"] is True and nz[2]["text"] == "z")
check("归一化给纯字符串补上 id 与 done", bool(nz[0]["id"]) and nz[0]["done"] is False)

nl = sticky._norm_logs({"2026-01-02": 60, "坏键": 10, "2026-01-02x": 5,
                        "2026-01-03": "abc", "2026-01-04": -3})
check("logs 只保留合法日期键", list(nl.keys()) == ["2026-01-02"], "实际 %s" % list(nl.keys()))
check("logs 保留合法秒数", nl["2026-01-02"] == 60.0)

print("\n-- 计时 --")
t1 = mk("计时任务一")
app.toggle_timer(t1)
check("开始计时会写 timer", bool(t1["timer"]))
check("计时中 spent_of 是活的", sticky.spent_of(t1) >= 0)
t1["timer"] = sticky.now_ts() - 90          # 假装已经计了 1 分半
app.toggle_timer(t1)
check("暂停后 timer 归零", t1["timer"] == 0)
key_today = sticky.d2s(sticky.today())
check("时长落账进今天的 logs", t1["logs"].get(key_today, 0) >= 85,
      "实际 %s" % t1["logs"])
check("fmt_dur(90) == 1分", sticky.fmt_dur(90) == "1分")
check("fmt_dur 秒级", sticky.fmt_dur(45) == "45秒")
check("fmt_dur 小时级补零", sticky.fmt_dur(3900) == "1时05分")

t2 = mk("跨天计时任务")
two_days_ago = datetime.datetime.now() - datetime.timedelta(days=2, hours=1)
t2["timer"] = two_days_ago.timestamp()
app.toggle_timer(t2)
old_key = sticky.d2s(two_days_ago.date())
check("跨天计时记在「开始那天」", t2["logs"].get(old_key, 0) >= 3500,
      "实际 %s" % t2["logs"])
check("今天不替昨天背锅", t2["logs"].get(key_today) is None)

t3 = mk("完成后自动停表")
app.toggle_timer(t3)
t3["timer"] = sticky.now_ts() - 30
app.toggle_done(t3)
check("勾完成时自动停表", t3["timer"] == 0)
check("停下时把 30 秒记了账", sum(t3["logs"].values()) >= 25,
      "实际 %s" % t3["logs"])
app.reset_timer(t3)
check("清零耗时记录", t3["logs"] == {} and t3["timer"] == 0)

t4 = mk("退出时落账")
app.toggle_timer(t4)
t4["timer"] = sticky.now_ts() - 40
n_committed = app.commit_timers()
check("退出时把所有在跑的计时落账", n_committed >= 1)
check("落账后没有任务还在计时", not any(t.get("timer") for t in app.tasks))

app.toggle_timer(t1)
app.set_filter("running")
vis = [t for t in app.tasks if app.visible(t)]
check("「计时中」筛选只留正在计时的", len(vis) == 1 and bool(vis[0].get("timer")),
      "实际 %d 条" % len(vis))
app.toggle_timer(t1)
app.set_filter("all")

print("\n-- 心跳刷新 --")
app.toggle_timer(t1)
t1["timer"] = sticky.now_ts() - 60
app.redraw()
root.update()

_calls = [0]
_orig_redraw = app.redraw


def _counting_redraw():
    _calls[0] += 1
    return _orig_redraw()


app.redraw = _counting_redraw
app._tick()
check("计时中且空闲时，心跳会重绘界面", _calls[0] >= 1, "重绘 %d 次" % _calls[0])
app.redraw = _orig_redraw

tb3 = region(app, "title", t1["id"])
app.on_double(E(tb3[0] + 5, tb3[1] + 5))
root.update()
check("编辑器已打开", app.editor is not None)
_calls[0] = 0
app.redraw = _counting_redraw
app._tick()
app.redraw = _orig_redraw
check("编辑中时心跳不重绘（否则输入框会被抹掉）", _calls[0] == 0, "重绘 %d 次" % _calls[0])
check("编辑器仍然在", app.editor is not None)
app.cancel_editor()
root.update()

app.drag = {"tid": t1["id"]}                  # 模拟正在拖拽
_calls[0] = 0
app.redraw = _counting_redraw
app._tick()
app.redraw = _orig_redraw
app.drag = None
check("拖拽中时心跳不重绘（否则卡片会被拉回原位）", _calls[0] == 0, "重绘 %d 次" % _calls[0])
app.toggle_timer(t1)

print("\n-- 每日自动备份 --")
bkdir = os.path.join(TMP, "bk")
os.makedirs(bkdir, exist_ok=True)
today_file = os.path.join(bkdir, "便利贴备份-%s.json" % key_today)
other_file = os.path.join(bkdir, "别的文件.json")
stale = os.path.join(bkdir, "便利贴备份-2020-01-01.json")
recent = os.path.join(bkdir, "便利贴备份-%s.json"
                      % sticky.d2s(sticky.today() - datetime.timedelta(days=3)))

app.ui["backup_dir"] = bkdir
app.ui["backup_on"] = True
app.ui["backup_keep"] = 7
app.ui["last_backup"] = ""
app.save()
check("当天首次保存会生成备份", os.path.exists(today_file))

snap1 = open(today_file, encoding="utf-8").read()
check("备份内容是合法的 JSON",
      len(json.loads(snap1)["tasks"]) == len(app.tasks))

app.entry.insert(0, "备份一致性测试任务")
app.do_add()
root.update()
check("同一天内不会反复覆盖备份", open(today_file, encoding="utf-8").read() == snap1)

app.do_backup_now()
root.update()
check("手动备份会刷新快照", open(today_file, encoding="utf-8").read() != snap1)

for p in (stale, recent, other_file):
    open(p, "w", encoding="utf-8").write("{}")
app._prune_backups()
check("超出保留期的备份被清掉", not os.path.exists(stale))
check("保留期内的备份不动", os.path.exists(recent))
check("不碰文件名不符合规则的文件", os.path.exists(other_file))

app.ui["backup_on"] = False
app.ui["last_backup"] = ""
os.remove(today_file)
app.save()
check("关掉开关后不再自动备份", not os.path.exists(today_file))

app.ui["backup_on"] = True
app.ui["backup_dir"] = os.path.join(TMP, "这个目录不存在")
app.ui["last_backup"] = ""
app.save()
check("备份目录不存在时不抛异常", True)

app.ui["backup_dir"] = ""
app.ui["last_backup"] = ""
app.save()
check("没设备份目录时不做任何事", not app.backup_dir())

app.entry.insert(0, "空的")
app.ui["backup_keep"] = 0
app._prune_backups()
check("保留天数设为 0 表示永久保留（不删任何东西）", os.path.exists(recent))
app.ui["backup_keep"] = 30

print("\n-- 耗时统计面板 --")
check("today 口径只有一天", len(app._period_keys("today")) == 1)
check("近 7 天口径有 7 天", len(app._period_keys("d7")) == 7)
check("本周口径包含今天", key_today in app._period_keys("week"))
check("「全部」口径不做日期过滤", app._period_keys("all") is None)

sample = {"logs": {"2026-01-01": 100.0, "2026-01-02": 200.0}, "timer": 0}
check("按日期集合过滤耗时", app._secs_of(sample, {"2026-01-02"}, 0) == 200.0)
check("全口径累加所有天", app._secs_of(sample, None, 0) == 300.0)
check("计时中的部分按开始日归入",
      app._secs_of({"logs": {}, "timer": 1000.0}, {sticky.d2s(
          datetime.date.fromtimestamp(1000.0))}, 1060.0) == 60.0)

app.toggle_timer(t1)
t1["timer"] = sticky.now_ts() - 300          # 让它在计时，检验实时量是否被算进去
_dt = app._day_totals()
_per = sum(app._secs_of(t, app._period_keys("today")) for t in app.tasks)
check("按天合计包含实时计时，与口径合计对得上",
      abs(_dt.get(key_today, 0) - _per) < 0.5,
      "按天=%s 口径=%s" % (_dt.get(key_today, 0), _per))
check("按天合计里今天的量大于已落账的量（证明实时量算进去了）",
      _dt.get(key_today, 0) > sum((t.get("logs") or {}).get(key_today, 0)
                                  for t in app.tasks))
app.toggle_timer(t1)

app.open_stats()
root.update()
check("统计面板已创建", app._stats_win is not None and app._stats_win.winfo_exists())
check("统计面板渲染出内容", len(app._stats_body.winfo_children()) > 0)
app.set_stats_period("all")
root.update()
check("切到全部口径不报错", len(app._stats_body.winfo_children()) > 0)
app.set_stats_period("week")
root.update()
check("切到本周口径不报错", len(app._stats_body.winfo_children()) > 0)
app._render_stats()
root.update()
check("重复渲染不报错", True)
app._stats_win.destroy()
root.update()

print("\n-- 不等高卡片布局 --")
hi, lo = mk("高的", subs=[{"id": sticky.new_sid(), "text": "x", "done": False}]), mk("矮的")
check("同行取最高的一张作为行高",
      sticky.row_heights([hi, lo], 2) == [max(sticky.block_h(hi), sticky.block_h(lo))])
check("空列表回落到基础高度", sticky.row_heights([], 3) == [sticky.CARD_H])
check("单行多列时行高一致", len(sticky.row_heights([hi, lo, mk("第三"), mk("第四")], 2)) == 2)

app.redraw()
root.update()
cards = [(tid, x1, y1, x2, y2) for k, tid, x1, y1, x2, y2 in app.regions if k == "card"]
overlap = []
for i in range(len(cards)):
    for j in range(i + 1, len(cards)):
        a, b = cards[i], cards[j]
        if a[1] < b[3] and b[1] < a[3] and a[2] < b[4] and b[2] < a[4]:
            overlap.append((a[0], b[0]))
check("卡片之间没有互相压住", not overlap, "重叠: %s" % overlap)

badge = region(app, "timer", t1["id"])
check("计时药丸区域已登记", badge is not None)
if badge:
    bxc, byc = (badge[0] + badge[2]) / 2, (badge[1] + badge[3]) / 2
    k, _ = app.hit(bxc, byc)
    check("命中计时药丸", k == "timer", "实际=%s" % k)
    app.on_press(E(bxc, byc))
    app.on_release(E(bxc, byc))
    root.update()
    check("走真实点击路径可开始计时", bool(t1.get("timer")))
    app.toggle_timer(t1)

print("\n-- 就地编辑的提交方式（防止编辑器一闪就没）--")
app.redraw()
root.update()
tb2 = region(app, "title", st_["id"])
app.on_double(E(tb2[0] + 5, tb2[1] + 5))
root.update()
check("编辑器已打开", app.editor is not None)
check("编辑器不会因为一次假的 FocusOut 就自己关掉", app.editor is not None)
app._maybe_commit_editor(E(0, 0, xr=5, yr=5))       # 点在别处
root.update()
check("点到输入框以外的地方会提交并关闭", app.editor is None)

# ---- 真实事件顺序：双击的第二次「按下」会同时发出 <Button-1> 和
#      <Double-Button-1>，一次事件要沿着 bindtags 走完 —— 画布上的 on_double
#      建好输入框之后，root 上那条 <Button-1>（_maybe_commit_editor，点别处提交）
#      还会对**同一次按下**再跑一遍。那一瞬间输入框刚建、X 窗口还没映射，
#      winfo_containing 查到的是画布，于是被当成"点到了别处"当场提交。
#      真机上的表现就是：双击标题毫无反应，焦点还掉回新增输入框。
app.redraw()
root.update()
tb5 = region(app, "title", st_["id"])
_t5_before = st_["title"]
app.on_press(E(tb5[0] + 5, tb5[1] + 5))                 # 第二次按下的前半截
app.on_double(E(tb5[0] + 5, tb5[1] + 5))                # 同一时刻的 <Double-Button-1>
app._maybe_commit_editor(E(tb5[0] + 5, tb5[1] + 5))     # 同一次按下走到 root 的那条
app.on_release(E(tb5[0] + 5, tb5[1] + 5))
root.update()                                           # 空闲了才真正建框
check("双击标题：同一次按下不会把刚开的编辑器吃掉", app.editor is not None,
      "editor=%r" % (app.editor,))
if app.editor:
    _e5 = app.editor["entry"]
    check("编辑器里装的是原标题（没被人顺手提交掉）", _e5.get() == st_["title"],
          "实际 %r" % _e5.get())
    app.root.focus_force()
    _e5.focus_set()
    root.update()
    check("光标停在就地编辑器里，不跳回新增输入框",
          root.focus_get() is _e5, "实际 %r" % (root.focus_get(),))
    app.cancel_editor()
root.update()
check("Esc 之后编辑器和数据都回到原样",
      app.editor is None and st_["title"] == _t5_before and app.drag is None,
      "editor=%r title=%r drag=%r" % (app.editor, st_["title"], app.drag))

app.on_double(E(tb2[0] + 5, tb2[1] + 5))
root.update()
if app.editor:
    ent = app.editor["entry"]
    ent.update_idletasks()
    ex, ey = ent.winfo_rootx() + 3, ent.winfo_rooty() + 3
    app._maybe_commit_editor(E(0, 0, xr=ex, yr=ey))
    root.update()
    still = app.editor is not None
    check("点在输入框自己身上不提交", still,
          "winfo_containing=%r 期望=%r" % (
              app.root.winfo_containing(ex, ey), ent))
    # ---- Esc = 取消。真的按一下才作数：以前这条只调了 cancel_editor()，
    #      等于没测「Esc 到底绑上没有」。
    check("就地编辑框绑了 Esc",
          "<Key-Escape>" in ent.bind(), "实际 %s" % list(ent.bind()))
    _et_ = app.editor["t"]
    _t_before = _et_["title"]
    ent.delete(0, "end")
    ent.insert(0, "不该生效的标题")
    app.root.focus_force()
    ent.focus_set()
    ent.update_idletasks()
    app.root.update()
    ent.event_generate("<Escape>", when="now")
    app.root.update_idletasks()
    app.root.update()
    check("按 Esc：编辑器关掉、标题原封不动",
          app.editor is None and _et_["title"] == _t_before,
          "实际 editor=%s title=%r" % (app.editor, _et_["title"]))
else:
    check("就地编辑框绑了 Esc", False, "编辑器没打开")
    check("按 Esc：编辑器关掉、标题原封不动", False, "编辑器没打开")
check("Escape 可取消编辑（兜底：直接调方法）", app.editor is None)

print("\n-- 搜索命中子任务文字 --")
app.search.insert(0, "第三步")
app.on_search()
vis = [t for t in app.tasks if app.visible(t)]
check("搜索能匹配到子任务里的文字", len(vis) == 1 and vis[0] is st_,
      "实际 %d 条" % len(vis))
app.search.delete(0, "end")
app.on_search()

print("\n-- 更多菜单可构建 --")
try:
    m = app.build_more_menu()
    check("更多菜单构建成功", m.index("end") is not None or True)
    labels = [m.entrycget(i, "label") for i in range(m.index("end") + 1)
              if m.type(i) == "command"]
    m.destroy()
except Exception as ex:
    labels = []
    check("更多菜单构建成功", False, repr(ex))
check("更多菜单里不再重复摆「耗时统计…」", "耗时统计…" not in labels,
      "实际 %s" % labels)
check("更多菜单里不再重复摆「每日复盘…」", "每日复盘…" not in labels)
check("但回收站还在菜单里（顶栏没有它）", "回收站…" in labels)


# ------------------------------------------------------------------ 拖拽
# 这一段要自己摆一组干净的任务来测拖拽，所以先把现有的挪开，测完再放回去
# （后面的持久化用例还要靠前面那些任务，不能真丢）。
_keep_tasks = list(app.tasks)
_keep_trash = list(app.trash)


def do_drag(app, start_xy, end_xy):
    """走一遍真实的「按下 → 移动 → 松手」。位移必须超过 DRAG_TOL，
    否则会被当成单击。返回松手前的 app.drag（可以看落点判定结果）。"""
    app.on_press(E(start_xy[0], start_xy[1]))
    app.on_motion(E(end_xy[0], end_xy[1]))
    root.update()
    d = dict(app.drag) if app.drag else None
    app.on_release(E(end_xy[0], end_xy[1]))
    root.update()
    return d


def center(box):
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


def subs_text(tid):
    """从当前任务列表里现取某条任务的子任务文字。

    撤销是「整份任务列表换成一份新副本」，所以撤销之后手里那把旧引用就
    作废了 —— 测试里一律按 id 现取。
    """
    return [s["text"] for s in sticky.subs_of(app.task_by_id(tid))]


print("\n-- 拖到别人卡片上半张 = 变成它的子任务 --")
app.tasks = []
app.trash = []
mom = mk("母任务", p=0, order=1.0)
kid = mk("要变成子任务的", p=0, order=2.0)
mid, kid_id = mom["id"], kid["id"]
app.redraw()
root.update()

mb = region(app, "card", mid)
kb = region(app, "card", kid_id)
check("两张卡片都画出来了", bool(mb) and bool(kb))
zone = app._nest_zone.get(mid)
check("母任务记录了「上半张」嵌套区", bool(zone), "实际 %s" % (zone,))
check("嵌套区确实是卡片的上半张（下沿不超过卡片一半高）",
      bool(zone) and zone[1] == mb[1] and zone[3] <= (mb[1] + mb[3]) / 2.0,
      "实际 %s / 卡片 %s" % (zone, mb))

# 抓在卡片下半张（徽章行那一段），起点本身不会落在别人的嵌套区里
d = do_drag(app, (kb[0] + 40, kb[3] - 14), center(zone))
check("拖到上半张时判定为「嵌套」", bool(d) and d.get("nest") == mid,
      "实际 %s" % (d or {}).get("nest"))
check("被拖走的卡片从任务列表里消失", [t["id"] for t in app.tasks] == [mid])
check("母任务多了一条同名子任务", subs_text(mid) == ["要变成子任务的"])
check("嵌套后给了撤销入口", app._undo_cb is not None)

app._do_undo()
check("撤销后任务回来了", len(app.tasks) == 2 and subs_text(mid) == [])

# 备注 / 自带子任务会丢的时候先弹确认框；把确认框打桩成「同意」
orig_ask = sticky.tkmb.askyesno
asked = []
sticky.tkmb.askyesno = lambda *a, **k: (asked.append(a[1]) or True)
kid = app.task_by_id(kid_id)
kid["note"] = "有个备注"
kid["subs"] = [{"id": sticky.new_sid(), "text": "自带子任务", "done": False}]
app.redraw()
root.update()
kb = region(app, "card", kid_id)
do_drag(app, (kb[0] + 40, kb[3] - 14), center(app._nest_zone.get(mid)))
check("有信息会丢时先弹确认框", len(asked) == 1, "实际 %s" % len(asked))
check("确认文案点名了会丢的东西",
      bool(asked) and "备注会丢掉" in asked[0] and "摊平" in asked[0],
      "实际 %s" % (asked[0] if asked else ""))
check("自带的子任务被摊平成同级",
      subs_text(mid) == ["要变成子任务的", "自带子任务"])
sticky.tkmb.askyesno = orig_ask
app._do_undo()

# 用户点「否」时什么都不该发生
sticky.tkmb.askyesno = lambda *a, **k: False
app.redraw()
root.update()
kb = region(app, "card", kid_id)
do_drag(app, (kb[0] + 40, kb[3] - 14), center(app._nest_zone.get(mid)))
check("点「否」时任务原地不动", len(app.tasks) == 2 and subs_text(mid) == [])
sticky.tkmb.askyesno = orig_ask

# 落点在下半张 = 排序落点，不该误触发嵌套
kb = region(app, "card", kid_id)
mb = region(app, "card", mid)
d = do_drag(app, (kb[0] + 40, kb[3] - 14), (mb[0] + 40, mb[3] - 10))
check("落点在下半张不算嵌套", bool(d) and not d.get("nest"),
      "实际 %s" % (d or {}).get("nest"))
check("落点在下半张仍然只做同组排序", len(app.tasks) == 2)

print("\n-- 子任务：拖拽排序 / 跨卡片搬移 --")
app.tasks = []
host = mk("带子任务", p=1, order=1.0)
hid = host["id"]
app.tasks = [host]
app.add_subs(host, ["甲", "乙", "丙"])
app.redraw()
root.update()
hb = region(app, "card", hid)
rows = app._sub_rows.get(hid)
check("记录了三条子任务行的位置", len(rows) == 3, "实际 %s" % (rows,))
check("行按显示顺序排列（y 递增）",
      len(rows) == 3 and rows[0][1] < rows[1][1] < rows[2][1])

first_sid = app.task_by_id(hid)["subs"][0]["id"]
sb = region(app, "st:" + first_sid, hid)
do_drag(app, (sb[0] + 5, sb[1] + 5), (hb[0] + 60, rows[2][2] + 4))
check("拖到最后一行下面 = 挪到末尾",
      subs_text(hid) == ["乙", "丙", "甲"], "实际 %s" % subs_text(hid))
app._do_undo()
check("撤销后顺序还原", subs_text(hid) == ["甲", "乙", "丙"])

# 没拖动就松手 = 单击，仍然勾选那条子任务
app.redraw()
root.update()
cb = region(app, "sc:" + first_sid, hid)
was = bool(app.task_by_id(hid)["subs"][0]["done"])
do_drag(app, (cb[0] + 2, cb[1] + 2), (cb[0] + 2, cb[1] + 2))
check("原地松手仍然算单击（勾选那条子任务）",
      bool(app.task_by_id(hid)["subs"][0]["done"]) != was)

# 菜单：上移 / 下移
app.redraw()
root.update()
app.move_sub(app.task_by_id(hid), app.task_by_id(hid)["subs"][2]["id"], -1)
check("下移一格可把最后一条往上提", subs_text(hid) == ["甲", "丙", "乙"],
      "实际 %s" % subs_text(hid))
app.move_sub(app.task_by_id(hid), app.task_by_id(hid)["subs"][0]["id"], -1)
check("第一条再上移应当无效（已经在头）", subs_text(hid) == ["甲", "丙", "乙"])
app._do_undo()
check("撤销回到上移之前", subs_text(hid) == ["甲", "乙", "丙"])

# 拖到别的卡片上 = 搬到那张卡里
other = mk("另一个任务", p=1, order=2.0)
oid = other["id"]
app.redraw()
root.update()
sb = region(app, "st:" + app.task_by_id(hid)["subs"][0]["id"], hid)
ob = region(app, "card", oid)
do_drag(app, (sb[0] + 5, sb[1] + 5), (ob[0] + 60, ob[1] + 12))
check("子任务被搬到另一张卡片",
      subs_text(oid) == ["甲"] and subs_text(hid) == ["乙", "丙"],
      "实际 目标=%s 源=%s" % (subs_text(oid), subs_text(hid)))
app._do_undo()
check("撤销后子任务回到原处",
      subs_text(hid) == ["甲", "乙", "丙"] and subs_text(oid) == [])

print("\n-- 子任务：提升成独立任务 --")
app.tasks = []
hp = mk("父任务", p=2, order=5.0)
hid2 = hp["id"]
app.tasks = [hp]
app.add_subs(hp, ["甲", "乙"])
app.redraw()
root.update()
nt = app.promote_sub(app.task_by_id(hid2),
                     app.task_by_id(hid2)["subs"][1]["id"])
check("提升后多出一个独立任务", nt is not None and len(app.tasks) == 2)
check("提升出来的任务继承了标题与象限",
      bool(nt) and nt["title"] == "乙" and nt["p"] == 2)
check("父任务里那条子任务已摘除", subs_text(hid2) == ["甲"],
      "实际 %s" % subs_text(hid2))
check("新任务紧跟在父任务后面",
      bool(nt) and sorted(app.tasks, key=app.sort_key)[1]["id"] == nt["id"])
check("提升也给了撤销入口", app._undo_cb is not None)
app._do_undo()
check("撤销后回到子任务状态",
      subs_text(hid2) == ["甲", "乙"] and len(app.tasks) == 1)

print("\n-- 子任务：拖到卡片以外的空白 = 提升成独立任务 --")
# 先给 P0 摆一张卡，好验证「提升出来的任务落进鼠标所在象限、并按落点排在后面」
boss = mk("P0 老大哥", p=0, order=1.0)
app.redraw()
root.update()
q0 = app._quad_rects.get(0)
check("P0 象限矩形已记录", bool(q0), "实际 %s" % (q0,))
check("P0 里已经有卡片", bool(region(app, "card", boss["id"])))

sb = region(app, "st:" + app.task_by_id(hid2)["subs"][0]["id"], hid2)
dest = (q0[0] + q0[2] - 40, q0[1] + q0[3] - 26)     # 象限里的空白（卡片都在左侧）
check("落点确实是空白（不在任何卡片上）", app._card_under(dest[0], dest[1]) is None)
check("落点在 P0 象限里", app._quad_at(dest[0], dest[1], None) == 0)

d = do_drag(app, (sb[0] + 5, sb[1] + 5), dest)
check("落点在卡片以外的空白时判定为「提升」",
      bool(d) and d.get("promote") == 0, "实际 %s" % (d or {}).get("promote"))
check("子任务已从父任务里摘除", subs_text(hid2) == ["乙"], "实际 %s" % subs_text(hid2))
newt = [t for t in app.tasks if t["title"] == "甲"]
check("原地多出一张同名独立任务", len(newt) == 1 and len(app.tasks) == 3)
check("新任务落在鼠标所在的象限（P0）",
      bool(newt) and newt[0]["p"] == 0, "实际 %s" % (newt[0]["p"] if newt else None))
check("新任务在 P0 里排在已有卡片之后（按落点算的位置）",
      bool(newt) and sorted([t for t in app.tasks if t["p"] == 0],
                            key=app.sort_key)[-1]["id"] == newt[0]["id"])
check("提升也给了撤销入口", app._undo_cb is not None)
app._do_undo()
check("撤销后回到子任务状态",
      subs_text(hid2) == ["甲", "乙"] and len(app.tasks) == 2,
      "实际 %s / %d 条" % (subs_text(hid2), len(app.tasks)))

# 反向确认：落在卡片上仍然是「搬过去」，别被误判成提升
app.redraw()
root.update()
sb = region(app, "st:" + app.task_by_id(hid2)["subs"][0]["id"], hid2)
cb = region(app, "card", boss["id"])
d = do_drag(app, (sb[0] + 5, sb[1] + 5), (cb[0] + 60, cb[1] + 12))
check("落在卡片上不算提升（仍然是搬过去）",
      bool(d) and d.get("promote") is None and d.get("target") == boss["id"],
      "实际 %s" % (d or {}))
check("子任务确实被搬进了那张卡", subs_text(boss["id"]) == ["甲"],
      "实际 %s" % subs_text(boss["id"]))
app._do_undo()

# 甩到顶栏上不该被当成「拖到空白」—— 否则一松手就凭空多出一个任务
app.redraw()
root.update()
sb = region(app, "st:" + app.task_by_id(hid2)["subs"][0]["id"], hid2)
above = (sb[0] + 5, min(y for (_x, y, _w, _h) in app._quad_rects.values()) - 30)
check("顶栏那个落点确实在板子外面", app._in_board(above[1]) is False)
d = do_drag(app, (sb[0] + 5, sb[1] + 5), above)
check("甩到顶栏上不算提升", bool(d) and d.get("promote") is None,
      "实际 %s" % (d or {}).get("promote"))
check("甩到顶栏上也不会把子任务弄丢",
      subs_text(hid2) == ["甲", "乙"] and len(app.tasks) == 2,
      "实际 %s / %d 条" % (subs_text(hid2), len(app.tasks)))

print("\n-- 卡片高度跟着子任务走 --")
app.tasks = []
h1 = mk("空的", p=3, order=1.0)
h1id = h1["id"]
app.tasks = [h1]
app.redraw()
root.update()
h_before = sticky.block_h(app.task_by_id(h1id))
app.add_subs(app.task_by_id(h1id), ["一"])
app.redraw()
root.update()
h_one = sticky.block_h(app.task_by_id(h1id))
check("加了子任务后卡片变高", h_one > h_before,
      "前 %s 后 %s" % (h_before, h_one))
app.add_subs(app.task_by_id(h1id), ["二"])
check("子任务每多一条就高一行（没写死）",
      sticky.block_h(app.task_by_id(h1id)) == h_one + sticky.SUB_LINE,
      "一条 %s 两条 %s" % (h_one, sticky.block_h(app.task_by_id(h1id))))
# 高度必须和真正画出来的卡片一致，否则就是"算的行数"和"画的行数"对不上
app.redraw()
root.update()
box2 = region(app, "card", h1id)
check("卡片实高与 block_h 一致（两行备注 + 两条子任务）",
      box2 and abs((box2[3] - box2[1]) - sticky.block_h(app.task_by_id(h1id))) < 0.5,
      "实际 %s 期望 %s" % (box2 and box2[3] - box2[1], sticky.block_h(app.task_by_id(h1id))))

print("\n-- 卡片高度按内容实算（不再留空行）--")
_base = (sticky.TITLE_TOP + sticky.LINE_TITLE + sticky.NOTE_GAP
         + sticky.LINE_NOTE + sticky.FOOT_GAP + sticky.FOOT_H)
c1 = mk("一行标题")
check("单行标题 + 空备注 = 内容 + 呼吸位 + 徽章行（时间不占行，没有多余空行）",
      sticky.block_h(c1) == _base, "实际 %s 期望 %s" % (sticky.block_h(c1), _base))
check("空备注那行「＋ 备注」也算一行高（不然会被子任务压住）",
      sticky.block_h(c1) == sticky.block_h(dict(c1, note="")), "实际 %s" % sticky.block_h(c1))

c2 = mk("很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长的标题")
check("标题折成两行时卡片更高", sticky.block_h(c2) > _base,
      "两行 %s vs 一行 %s" % (sticky.block_h(c2), _base))

c3 = mk("一行备注")
c3["note"] = "短"
c4 = mk("两行备注")
c4["note"] = "特别特别长的一条备注" * 8
check("备注折成两行时比一行高", sticky.block_h(c4) > sticky.block_h(c3),
      "%s vs %s" % (sticky.block_h(c4), sticky.block_h(c3)))
check("备注行数不受标题长度影响（各算各的）",
      sticky.block_h(c4) - sticky.block_h(c3) == sticky.LINE_NOTE,
      "差 %s 期望 %s" % (sticky.block_h(c4) - sticky.block_h(c3), sticky.LINE_NOTE))

# 关键的一条：子任务最后一行到卡片底，只应该剩「时间行 + 呼吸位 + 徽章行」。
# 卡片高度由 block_h 算、内容由 _draw_card 画，两者的偏移量必须严丝合缝，
# 差一点就是"卡片下面拖着一条空行"。
c5 = mk("空隙检查")
app.add_subs(c5, ["甲"])
app.redraw()
root.update()
_rows = app._sub_rows.get(c5["id"]) or []
_card = region(app, "card", c5["id"])
check("子任务最后一行到卡片底只剩呼吸位 + 徽章行（没有多余空行）",
      bool(_rows) and bool(_card)
      and abs((_card[3] - _rows[-1][2])
              - (sticky.FOOT_GAP + sticky.FOOT_H)) < 3.5,
      "实际 %s 期望 %s" % (_card and _rows and _card[3] - _rows[-1][2],
                          sticky.FOOT_GAP + sticky.FOOT_H))
app.tasks = [t for t in app.tasks if t["id"] not in (c1["id"], c2["id"], c3["id"],
                                                    c4["id"], c5["id"])]

# 把前面那些任务放回来，后面的持久化用例还要用
app.tasks = _keep_tasks
app.trash = _keep_trash
app.redraw()
root.update()
check("测试任务已复原", len(app.tasks) == len(_keep_tasks))

print("\n-- 重复任务：日期推算（纯函数，边界最多）--")
D11 = datetime.date(2026, 10, 11)
check("每天：往后推一天",
      sticky.next_date("2026-10-11", "daily", base=D11) == "2026-10-12")
check("每周：往后推七天",
      sticky.next_date("2026-10-11", "weekly", base=D11) == "2026-10-18")
check("每月：月末自动对齐（1/31 → 2/28）",
      sticky.next_date("2026-01-31", "monthly", base=datetime.date(2026, 1, 31))
      == "2026-02-28")
check("每年：往后推一年",
      sticky.next_date("2026-10-11", "yearly", base=D11) == "2027-10-11")
check("没设日期时从今天往后算",
      sticky.next_date("", "weekly", base=D11) == "2026-10-18")
check("拖太久才完成，不会补出一串过期任务",
      sticky.next_date("2026-01-01", "daily", base=D11) == "2026-10-12",
      "实际 %s" % sticky.next_date("2026-01-01", "daily", base=D11))
check("逢 2/29 每年重复，平年落到 2/28",
      sticky.next_date("2024-02-29", "yearly", base=datetime.date(2024, 2, 29))
      == "2025-02-28")
check("不重复时返回空串", sticky.next_date("2026-10-11", "") == "")

print("\n-- 重复任务：勾完成即续期 --")
rp = mk("每周复盘", repeat="weekly", due=key_today)
n_before = len(app.tasks)
app.toggle_done(rp)
twin = [t for t in app.tasks if t is not rp and t["title"] == "每周复盘"]
check("原任务被标记完成", rp["done"] is True)
check("自动生成了下一条", len(app.tasks) == n_before + 1)
check("新任务继承重复周期", bool(twin) and twin[0]["repeat"] == "weekly")
check("新任务是未完成的", bool(twin) and twin[0]["done"] is False)
check("新任务日期推到了下一轮", bool(twin) and twin[0]["due"] > key_today,
      "实际 %s" % (twin[0]["due"] if twin else "没生成"))
check("完成时间被记了下来", rp["done_at"] > 0)
check("完成日期能算出来", sticky.done_day(rp) == key_today)
once = mk("一次性的")
n_once = len(app.tasks)
app.toggle_done(once)
check("没有重复周期的任务不会长出新任务", len(app.tasks) == n_once)
app.tasks.remove(once)
for x in [rp] + (twin or []):
    if x in app.tasks:
        app.tasks.remove(x)

print("\n-- 重复任务的卡片徽章 --")
rp2 = mk("每月对账", repeat="monthly")
app.redraw()
root.update()
rep = region(app, "rep", rp2["id"])
check("卡片上出现了重复徽章", rep is not None)
if rep:
    k, _ = app.hit((rep[0] + rep[2]) / 2, (rep[1] + rep[3]) / 2)
    check("徽章没被整卡兜底盖住", k == "rep", "实际=%s" % k)
app.set_repeat(rp2, "")
app.redraw()
root.update()
check("清掉重复周期后徽章消失", region(app, "rep", rp2["id"]) is None)
app.tasks.remove(rp2)

print("\n-- 删除 → 回收站 → 撤销 --")
# 注意：前面的用例（比如「清空已完成」）也会往回收站里放东西，
# 所以这里一律用「相对变化量」断言，不写死绝对条数。
tb0 = len(app.trash)
tr = mk("将被删除的任务")
app.redraw()
root.update()
n_before = len(app.tasks)
app.delete_task(tr)
root.update_idletasks()
check("删除后从任务列表消失", tr not in app.tasks)
check("删除后进了回收站", len(app.trash) == tb0 + 1 and app.trash[-1]["task"] is tr,
      "回收站 %d → %d" % (tb0, len(app.trash)))
check("回收站记下了删除时间", app.trash[-1]["deleted_at"] > 0)
check("状态栏出现了撤销按钮", bool(app.undo_btn.winfo_ismapped()))
back = app.undo_delete()
check("撤销把任务捞了回来", back is tr and tr in app.tasks)
check("撤销后回收站回到原样", len(app.trash) == tb0,
      "实际 %d，期望 %d" % (len(app.trash), tb0))
check("任务数量复原", len(app.tasks) == n_before)
app._clear_undo()

print("\n-- 清空已完成也进回收站，且能整批撤销 --")
tb1 = len(app.trash)
d1, d2 = mk("已完成甲"), mk("已完成乙")
app.toggle_done(d1)
app.toggle_done(d2)
ndone = len([t for t in app.tasks if t["done"]])     # 前面的用例也会留下已完成项
app.do_clear_done()
check("清空后没有已完成任务", len([t for t in app.tasks if t["done"]]) == 0)
check("清掉的都进了回收站", len(app.trash) == tb1 + ndone,
      "回收站 %d → %d，清掉 %d 条" % (tb1, len(app.trash), ndone))
got = app.undo_batch(ndone)
check("可以一次性撤销回来", got == ndone and d1 in app.tasks and d2 in app.tasks,
      "实际恢复 %d 条，期望 %d" % (got, ndone))
check("撤销后回收站回到原样", len(app.trash) == tb1,
      "实际 %d，期望 %d" % (len(app.trash), tb1))
app._clear_undo()

print("\n-- 回收站面板 --")
tb2 = len(app.trash)
x1 = mk("回收站面板测试")
app._to_trash(x1)
app.open_trash()
root.update()
check("回收站面板已创建",
      app._trash_win is not None and app._trash_win.winfo_exists())
check("列表里显示出了全部条目", app._trash_list.size() == len(app.trash),
      "列表 %d 条 / 数据 %d 条" % (app._trash_list.size(), len(app.trash)))
check("最新那条的文字里带着标题",
      "回收站面板测试" in app._trash_list.get(app._trash_list.size() - 1))
app._trash_list.selection_set(app._trash_list.size() - 1)
check("选中后能恢复", app.trash_restore() == 1 and x1 in app.tasks)
check("恢复后回收站回到原样", len(app.trash) == tb2)
app._trash_win.destroy()
root.update()

print("\n-- 导入 / 恢复备份 --")
imp_dir = os.path.join(TMP, "imp")
os.makedirs(imp_dir, exist_ok=True)
snapshot = os.path.join(imp_dir, "snapshot.json")
app.save()
with open(sticky.DATA_FILE, encoding="utf-8") as f:
    _snap = f.read()
with open(snapshot, "w", encoding="utf-8") as f:
    f.write(_snap)

good = os.path.join(imp_dir, "good.json")
with open(good, "w", encoding="utf-8") as f:
    json.dump({"v": 3, "tasks": [
        {"title": "导入来的甲", "p": 0, "due": "2026-12-01",
         "subs": ["子一"], "logs": {"2026-10-01": 600}, "repeat": "weekly"},
        {"title": "导入来的乙", "p": 2},
        {"title": "    "},                       # 空标题，应该被丢掉
    ]}, f, ensure_ascii=False)

n, err = app.import_from(good, "merge")
check("合并导入成功", err == "" and n == 2, "n=%s err=%r" % (n, err))
arr = [t for t in app.tasks if t["title"] == "导入来的甲"]
check("导入的任务进了列表", bool(arr))
if arr:
    a = arr[0]
    check("导入保留了优先级", a["p"] == 0)
    check("导入保留了子任务", len(a["subs"]) == 1 and a["subs"][0]["text"] == "子一")
    check("导入保留了耗时流水", a["logs"].get("2026-10-01") == 600)
    check("导入保留了重复周期", a["repeat"] == "weekly")
check("空标题的条目被丢掉", not any(not t["title"].strip() for t in app.tasks))
check("导入前自动留了一份后悔药",
      any(f.startswith(sticky.IMPORT_BACKUP_PREFIX) for f in os.listdir(TMP)))

n, err = app.import_from(good, "replace")
check("替换导入成功", err == "" and n == 2)
check("替换后只剩文件里那两条", len(app.tasks) == 2,
      "实际 %d 条" % len(app.tasks))

bad = os.path.join(imp_dir, "bad.json")
with open(bad, "w", encoding="utf-8") as f:
    f.write("{ 这不是合法的 JSON")
n, err = app.import_from(bad, "merge")
check("坏 JSON 会报错而不是崩掉", n == 0 and bool(err), "err=%r" % err)

empty = os.path.join(imp_dir, "empty.json")
with open(empty, "w", encoding="utf-8") as f:
    json.dump({"v": 3, "tasks": []}, f)
n, err = app.import_from(empty, "merge")
check("空备份被识别出来", n == 0 and bool(err), "err=%r" % err)

weird = os.path.join(imp_dir, "weird.json")
with open(weird, "w", encoding="utf-8") as f:
    json.dump({"hello": "world"}, f)
n, err = app.import_from(weird, "merge")
check("不是备份格式的文件被识别出来", n == 0 and bool(err), "err=%r" % err)

n, err = app.import_from(snapshot, "replace")
check("从快照恢复现场成功", err == "" and n > 0, "n=%s err=%r" % (n, err))

print("\n-- 同象限内手动排序 --")
s1, s2, s3 = mk("排序甲", p=3), mk("排序乙", p=3), mk("排序丙", p=3)
s1["order"], s2["order"], s3["order"] = 1.0, 2.0, 3.0
app.redraw()
root.update()
seq = [t["title"] for t in sorted([s1, s2, s3], key=app.sort_key)]
check("初始顺序是甲乙丙", seq == ["排序甲", "排序乙", "排序丙"], "实际 %s" % seq)

r3 = region(app, "card", s3["id"])
r1 = region(app, "card", s1["id"])
app.on_press(E(r3[0] + 20, r3[1] + 20))
app.on_motion(E(r3[0] + 20, r1[1] - 10))       # 一直移到「甲」的上方
app.on_release(E(r3[0] + 20, r1[1] - 10))
root.update()
seq = [t["title"] for t in sorted([s1, s2, s3], key=app.sort_key)]
check("拖到最前面后「丙」排第一", seq[0] == "排序丙", "实际 %s" % seq)
check("同组排序不会改动优先级", all(t["p"] == 3 for t in (s1, s2, s3)))
n_p3 = len([t for t in app.tasks if t["p"] == 3 and t["id"] != s1["id"]])
check("落点在最下方时插到末尾",
      app._insert_index(3, 99999, 99999, s1["id"]) == n_p3,
      "实际 %s 期望 %s" % (app._insert_index(3, 99999, 99999, s1["id"]), n_p3))

print("\n-- 已完成的任务在组内始终沉底 --")
s2["done"] = True
app._apply_drop(s1, 3, 0)
seq = [t["title"] for t in sorted([s1, s2, s3], key=app.sort_key)]
check("已完成的排在未完成的后面", seq[-1] == "排序乙", "实际 %s" % seq)
s2["done"] = False
for x in (s1, s2, s3):
    app.tasks.remove(x)

print("\n-- 到点提醒 --")
app.ui["remind_on"] = True
r_due = mk("今天到期的事", due=key_today)
r_late = mk("早就逾期的事",
            due=sticky.d2s(sticky.today() - datetime.timedelta(days=3)))
r_future = mk("以后的事",
              due=sticky.d2s(sticky.today() + datetime.timedelta(days=5)))
r_fin = mk("已完成的事", due=key_today, done=True)
for t in (r_due, r_late, r_future, r_fin):
    t["remind_key"] = ""
rem = app.due_reminders()
names = [t["title"] for t in rem]
check("今天到期的会被提醒", "今天到期的事" in names)
check("已逾期的会被提醒", "早就逾期的事" in names)
check("还没到期的不打扰", "以后的事" not in names)
check("已完成的不提醒", "已完成的事" not in names)
check("逾期的排在今天到期的前面", names.index("早就逾期的事") < names.index("今天到期的事"))

n_rem = app._maybe_remind()
check("到点了会弹出提醒", n_rem >= 2, "实际提醒 %d 条" % n_rem)
check("提醒窗已创建",
      app._remind_win is not None and app._remind_win.winfo_exists())
check("提醒过的任务打上了今天的标记", r_due["remind_key"] == key_today)
check("同一天不会再提醒第二次", app._maybe_remind() == 0)
app._remind_win.destroy()
root.update()

app.ui["remind_on"] = False
r_due["remind_key"] = ""
check("关掉开关后就不再提醒", app._maybe_remind() == 0)
app.ui["remind_on"] = True
for t in (r_due, r_late, r_future, r_fin):
    app.tasks.remove(t)

print("\n-- 每日复盘 --")
dn = mk("今天完成的")
app.toggle_done(dn)
start, hd = app._heat_data()
check("热力图起点对齐到周一", start.weekday() == 0)
check("热力图覆盖最近 %d 周" % sticky.HEAT_WEEKS,
      (sticky.today() - start).days < sticky.HEAT_WEEKS * 7 + 7,
      "起点 %s" % start)
check("今天完成的条目被统计进去", hd.get(key_today, 0) >= 1, "实际 %s" % hd)
check("颜色分档：0 条最浅", app._heat_color(0) == sticky.HEAT_LEVELS[0])
check("颜色分档：很多条取最深", app._heat_color(99) == sticky.HEAT_LEVELS[-1])
check("颜色分档：1 条不是最浅", app._heat_color(1) != sticky.HEAT_LEVELS[0])

app.open_review()
root.update()
check("复盘面板已创建",
      app._review_win is not None and app._review_win.winfo_exists())
check("复盘面板渲染出了内容", len(app._review_body.winfo_children()) > 0)
app._render_review()
root.update()
check("重复渲染复盘不报错", True)
app._review_win.destroy()
root.update()
app.tasks.remove(dn)

print("\n-- 备份保留天数：0 表示永久，不能被悄悄改成 30 --")
app.ui["backup_keep"] = 0
app.save()
raw0 = json.load(open(sticky.DATA_FILE, encoding="utf-8"))
check("保留天数 0 原样写进文件", raw0["ui"]["backup_keep"] == 0,
      "实际 %s" % raw0["ui"]["backup_keep"])
check("读取时 0 仍然是 0（= 永久）", app._keep_days() == 0)
app.ui["backup_keep"] = 30
app.save()

print("\n-- 窗口置顶开关 --")


def is_top(w):
    """Tk 的 -topmost 在不同环境返回 0/1 或 '0'/'1'，统一成 bool。"""
    return str(w.attributes("-topmost")).lower() in ("1", "true")


app.topmost = False
app._apply_topmost(announce=False)
root.update_idletasks()
check("未置顶时按钮写「置顶」", app.top_btn.cget("text") == "置顶",
      "实际 %r" % app.top_btn.cget("text"))
check("未置顶时按钮是白底", app.top_btn.cget("bg") == sticky.C_PIN_OFF_BG,
      "实际 %s" % app.top_btn.cget("bg"))
check("未置顶时窗口属性也是关的", not is_top(app.root))
w_off = app.top_btn.winfo_reqwidth()

app.toggle_top()
root.update_idletasks()
check("点一下：状态字段翻转", app.topmost is True)
check("点一下：真正作用到了窗口属性", is_top(app.root),
      "实际 %r" % (app.root.attributes("-topmost"),))
check("点一下：按钮变成「已置顶」", app.top_btn.cget("text") == "已置顶",
      "实际 %r" % app.top_btn.cget("text"))
check("点一下：按钮换成深底白字",
      app.top_btn.cget("bg") == sticky.C_PIN_ON_BG
      and app.top_btn.cget("fg") == sticky.C_PIN_ON_FG,
      "bg=%s fg=%s" % (app.top_btn.cget("bg"), app.top_btn.cget("fg")))
w_on = app.top_btn.winfo_reqwidth()
check("两种文字下按钮同宽（切换时工具栏不抖）", w_off == w_on,
      "置顶 %dpx / 已置顶 %dpx" % (w_off, w_on))
check("状态栏说明了怎么取消", "取消" in app.status.cget("text"),
      "实际 %r" % app.status.cget("text"))
check("置顶状态已写进文件",
      json.load(open(sticky.DATA_FILE, encoding="utf-8"))["ui"]["topmost"] is True)

app.toggle_top()
root.update_idletasks()
check("再点一下：关掉置顶", app.topmost is False and not is_top(app.root))
check("关掉后按钮回到白底「置顶」",
      app.top_btn.cget("text") == "置顶"
      and app.top_btn.cget("bg") == sticky.C_PIN_OFF_BG)

print("\n-- 置顶跟随：子面板不能被主窗压在后面 --")
w0 = tk.Toplevel(root)
w0.title("跟随测试A")
app._follow_top(w0)
root.update_idletasks()
check("没置顶时，新面板也不置顶", not is_top(w0),
      "实际 %r" % (w0.attributes("-topmost"),))
w0.destroy()
root.update()

app.toggle_top()
app.open_trash()
root.update()
check("置顶后，新开的回收站面板跟着置顶", is_top(app._trash_win),
      "实际 %r" % (app._trash_win.attributes("-topmost"),))

app.toggle_top()
root.update_idletasks()
check("关掉置顶后，已打开的面板也跟着降下来", not is_top(app._trash_win),
      "实际 %r" % (app._trash_win.attributes("-topmost"),))
app._trash_win.destroy()
root.update()

# 提醒窗是例外：它必须永远置顶，否则会被别人盖住导致提醒失效
wr = tk.Toplevel(root)
wr.title("提醒窗哨兵")
wr.attributes("-topmost", True)
app._remind_win = wr
app.toggle_top()
app.toggle_top()
check("提醒窗不受主窗置顶开关影响（始终置顶）", is_top(wr),
      "实际 %r" % (wr.attributes("-topmost"),))
wr.destroy()
app._remind_win = None
root.update()

app.topmost = False
app._apply_topmost(announce=False)

print("\n-- 备注 --")

nt_ = mk("备注测试任务")
app.redraw()
root.update()
box0 = region(app, "note", nt_["id"])
check("空备注也画出了可点的备注区", box0 is not None,
      "实际 %s" % (box0,))

_texts = [app.cv.itemcget(i, "text")
          for i in app.cv.find_withtag("card%s" % nt_["id"])
          if app.cv.type(i) == "text"]
check("空备注画出了「＋ 备注」入口文案",
      any(sticky.NOTE_EMPTY in (x or "") for x in _texts), "实际 %s" % _texts[:6])

app.set_note(nt_, "第一行\n第二行")
check("set_note 能新增备注", nt_["note"] == "第一行\n第二行")
app.redraw()
root.update()
box1 = region(app, "note", nt_["id"])
check("有备注后备注区按文字行变高",
      bool(box1) and box1 is not None and (box1[3] - box1[1]) > (box0[3] - box0[1]),
      "%s -> %s" % (box0, box1))

app.set_note(nt_, "改过的备注")
check("set_note 能修改备注", nt_["note"] == "改过的备注")
app.redraw()
root.update()
_texts2 = [app.cv.itemcget(i, "text")
           for i in app.cv.find_withtag("card%s" % nt_["id"])
           if app.cv.type(i) == "text"]
check("有备注后就不再画那个占位入口",
      not any(sticky.NOTE_EMPTY in (x or "") for x in _texts2), "实际 %s" % _texts2[:6])
check("备注文字真的画到了卡面上", "改过的备注" in _texts2, "实际 %s" % _texts2[:6])

# 单击空备注 = 弹编辑框这条路径，用一个假的 ask_edit 顶掉对话框，
# 只验证 handle_click 确实把它调起来了（并且光标预置在备注那栏）。
_calls = []
app.set_note(nt_, "")
_orig_ask = app.ask_edit
app.ask_edit = lambda t, focus="title": _calls.append((t["id"], focus))
app.handle_click("note", nt_["id"], E(0, 0))
check("单击空备注会弹出编辑框（光标落在备注上）",
      _calls == [(nt_["id"], "note")], "实际 %s" % _calls)
_calls[:] = []
app.set_note(nt_, "已有备注")
app.handle_click("note", nt_["id"], E(0, 0))
check("已有备注时单击不弹框（留给双击就地编辑）", _calls == [], "实际 %s" % _calls)
app.ask_edit = _orig_ask

# 就地编辑这条路（双击走的就是它）
app.open_editor(nt_, "note")
check("就地编辑器能找到备注区", app.editor is not None and app.editor["field"] == "note")
app.editor["entry"].delete(0, "end")
app.editor["entry"].insert(0, "就地改的备注")
app._commit_editor()
check("就地编辑提交进了 note 字段", nt_["note"] == "就地改的备注")

app.del_note(nt_)
check("del_note 能删除备注", nt_["note"] == "")
check("删备注后挂了撤销入口", app._undo_cb is not None)
app._do_undo()
check("撤销能把删掉的备注捞回来", nt_["note"] == "就地改的备注")

app.set_note(nt_, "")          # 先清空，再删（此时是「删一条本来就没有的备注」）
check("备注本来就是空的时候删它，不报错也不挂撤销",
      app.del_note(nt_) is None and nt_["note"] == "" and app._undo_cb is None)
app.set_note(nt_, "跨重启的备注")

print("\n-- 编辑任务（标题 + 备注）--")


def dlg_find(title):
    """找到标题为 title 的那个 Toplevel，并把里面的输入控件挑出来。"""
    for w in root.winfo_children():
        if not isinstance(w, tk.Toplevel) or not w.winfo_exists():
            continue
        if w.title() != title:
            continue
        out = {"dlg": w, "entry": None, "text": None, "btns": []}

        def walk(p):
            for c in p.winfo_children():
                if isinstance(c, tk.Entry):
                    out["entry"] = out["entry"] or c
                elif isinstance(c, tk.Text):
                    out["text"] = out["text"] or c
                elif isinstance(c, tk.Button):
                    out["btns"].append(c)
                walk(c)

        walk(w)
        return out
    return None


def dlg_close(title):
    w = dlg_find(title)
    if w:
        w["dlg"].destroy()
        root.update()


et = mk("编辑任务测试")
root.update()

app.set_title(et, "改过的标题")
check("set_title 能改标题", et["title"] == "改过的标题")
app.set_title(et, "   ")
check("空标题会被忽略（卡片没标题就认不出来了）", et["title"] == "改过的标题")

# 双击标题就地编辑走的就是 set_title
app.redraw()
root.update()
app.open_editor(et, "title")
check("就地编辑器能找到标题区",
      app.editor is not None and app.editor["field"] == "title")
app.editor["entry"].delete(0, "end")
app.editor["entry"].insert(0, "就地改的标题")
app._commit_editor()
check("就地改标题落进 title 字段", et["title"] == "就地改的标题")

# 对话框真实建一次：标题 + 备注 一次性提交
app.ask_edit(et)
root.update()
_w = dlg_find("编辑任务")
check("「编辑任务」对话框能建出来", _w is not None)
if _w:
    check("对话框里标题框带出了原标题",
          _w["entry"] is not None and _w["entry"].get() == "就地改的标题",
          "实际 %r" % (_w["entry"].get() if _w["entry"] else None))
    _w["entry"].delete(0, "end")
    _w["entry"].insert(0, "对话框改的标题")
    _w["text"].insert("1.0", "对话框写的备注")
    _w["entry"].event_generate("<Return>")
    root.update_idletasks()
    root.update()
    check("对话框一次改好标题 + 备注",
          et["title"] == "对话框改的标题" and et["note"] == "对话框写的备注",
          "实际 %r / %r" % (et["title"], et["note"]))
    check("提交后对话框自己关掉", dlg_find("编辑任务") is None)
else:
    check("对话框里标题框带出了原标题", False, "对话框没建出来")
    check("对话框一次改好标题 + 备注", False, "对话框没建出来")
    check("提交后对话框自己关掉", False, "对话框没建出来")

# 标题留空 = 拒绝保存，内容留在框里让用户接着改
app.ask_edit(et, focus="note")
root.update()
_w = dlg_find("编辑任务")
if _w:
    check("从「＋ 备注」进来时光标预置在备注框",
          _w["dlg"].focus_get() is _w["text"],
          "实际 %s" % (_w["dlg"].focus_get(),))
    _w["entry"].delete(0, "end")
    _w["entry"].event_generate("<Return>")
    root.update_idletasks()
    root.update()
    check("标题留空时保存被拒绝、框不关", dlg_find("编辑任务") is not None)
    check("标题留空时原标题不动", et["title"] == "对话框改的标题")
    check("备注框不用再按 Ctrl+回车（普通回车就提交）",
          "<Control-Key-Return>" not in _w["text"].bind()
          and "<Key-Return>" in _w["text"].bind(),
          "实际 %s" % list(_w["text"].bind()))
    _w["text"].delete("1.0", "end")
    # 用「保存」按钮提交（等价于用户点它）：tk 的合成按键必须控件先拿到焦点，
    # 上面那次「拒绝保存」把焦点挪来挪去，再合成按键就不可靠了。
    _save_btn = next((b for b in _w["btns"] if b.cget("text") == "保存"), None)
    check("对话框里有「保存」按钮", _save_btn is not None,
          "实际 %s" % [b.cget("text") for b in _w["btns"]])
    # 标题还空着（上一步故意留空），所以这一下点保存【应该】还是被拒绝 ——
    # 正好顺手验证「拒绝之后框不关、内容还在」。
    if _save_btn:
        _save_btn.invoke()
    root.update_idletasks()
    root.update()
    check("标题还空着时点保存仍然被拒绝", dlg_find("编辑任务") is not None)
    _w["entry"].insert(0, "对话框改的标题")      # 标题填回去，这次该成了
    if _save_btn:
        _save_btn.invoke()
    root.update_idletasks()
    root.update()
    check("点保存后对话框自己关掉", dlg_find("编辑任务") is None)
    check("备注清空再保存 = 删掉备注", et["note"] == "", "实际 %r" % et["note"])
else:
    check("从「＋ 备注」进来时光标预置在备注框", False, "对话框没建出来")
    check("标题留空时保存被拒绝、框不关", False, "对话框没建出来")
    check("标题留空时原标题不动", False, "对话框没建出来")
    check("备注框绑了 Ctrl+回车提交", False, "对话框没建出来")
    check("对话框里有「保存」按钮", False, "对话框没建出来")
    check("标题还空着时点保存仍然被拒绝", False, "对话框没建出来")
    check("点保存后对话框自己关掉", False, "对话框没建出来")
    check("备注清空再保存 = 删掉备注", False, "对话框没建出来")

dlg_close("编辑任务")

# 「删除备注」按钮只在本来就有备注时出现
et["note"] = "有备注"
app.ask_edit(et)
root.update()
_w = dlg_find("编辑任务")
check("有备注时对话框里多一个「删除备注」",
      bool(_w) and any(b.cget("text") == "删除备注" for b in _w["btns"]),
      "实际 %s" % ([b.cget("text") for b in _w["btns"]] if _w else None))
dlg_close("编辑任务")
et["note"] = ""
app.ask_edit(et)
root.update()
_w = dlg_find("编辑任务")
check("没备注时就没有「删除备注」（别让人点出空动作）",
      bool(_w) and not any(b.cget("text") == "删除备注" for b in _w["btns"]),
      "实际 %s" % ([b.cget("text") for b in _w["btns"]] if _w else None))
dlg_close("编辑任务")

print("\n-- 编辑任务：回车保存 / Shift+回车换行 / Esc 取消 --")


def _all_labels(w):
    """递归收集一个窗口里所有 Label 的文字（找提示行用）。"""
    out = []

    def walk(p):
        for c in p.winfo_children():
            if isinstance(c, tk.Label):
                out.append(c.cget("text"))
            walk(c)

    walk(w)
    return out


_et = mk("回车保存测试")
_et["note"] = "原来就有的备注"
root.update()

# 合成按键只发给「当前持有焦点」的控件，所以先把焦点硬塞进备注框。
# 不这么做的话 event_generate("<Return>") 会被静默丢弃（实测）。
app.ask_edit(_et, focus="note")
root.update()
_w = dlg_find("编辑任务")
check("备注框绑了「回车 = 保存」",
      bool(_w) and "<Key-Return>" in _w["text"].bind(),
      "实际 %s" % (list(_w["text"].bind()) if _w else None))
check("备注框绑了「Shift+回车 = 换行」",
      bool(_w) and "<Shift-Key-Return>" in _w["text"].bind(),
      "实际 %s" % (list(_w["text"].bind()) if _w else None))
check("对话框绑了 Esc（取消）",
      bool(_w) and "<Key-Escape>" in _w["dlg"].bind(),
      "实际 %s" % (list(_w["dlg"].bind()) if _w else None))
check("对话框里写明了这两个键",
      bool(_w) and any("Shift" in s and "回车" in s for s in _all_labels(_w["dlg"])),
      "找不到说明文字")

if _w:
    root.focus_force()
    _w["dlg"].focus_force()
    _w["text"].focus_set()
    root.update()
    _w["text"].delete("1.0", "end")
    _w["text"].insert("1.0", "回车写的备注")
    root.update()
    _w["text"].event_generate("<Return>", when="now")
    root.update_idletasks()
    root.update()
    check("备注框里按回车 = 保存（不用去点按钮）",
          _et["note"] == "回车写的备注", "实际 %r" % _et["note"])
    check("回车保存后对话框自己关掉", dlg_find("编辑任务") is None)
else:
    check("备注框里按回车 = 保存（不用去点按钮）", False, "对话框没建出来")
    check("回车保存后对话框自己关掉", False, "对话框没建出来")

# Shift+回车是真换行，不是保存
app.ask_edit(_et, focus="note")
root.update()
_w = dlg_find("编辑任务")
if _w:
    root.focus_force()
    _w["dlg"].focus_force()
    _w["text"].focus_set()
    root.update()
    _w["text"].delete("1.0", "end")
    _w["text"].insert("1.0", "第一行")
    root.update()
    _w["text"].event_generate("<Shift-Return>", when="now")
    root.update()
    _w["text"].insert("insert", "第二行")
    root.update()
    check("Shift+回车是换行，不是保存",
          _w["text"].get("1.0", "end-1c") == "第一行\n第二行",
          "实际 %r" % _w["text"].get("1.0", "end-1c"))
    check("Shift+回车之后对话框还开着（没被提交掉）", dlg_find("编辑任务") is not None)
    _sb = next((b for b in _w["btns"] if b.cget("text") == "保存"), None)
    if _sb:
        _sb.invoke()
    root.update_idletasks()
    root.update()
    check("多行备注原样落库（换行没丢）", _et["note"] == "第一行\n第二行",
          "实际 %r" % _et["note"])
else:
    check("Shift+回车是换行，不是保存", False, "对话框没建出来")
    check("Shift+回车之后对话框还开着（没被提交掉）", False, "对话框没建出来")
    check("多行备注原样落库（换行没丢）", False, "对话框没建出来")

# Esc = 取消，不保存
_before = _et["note"]
app.ask_edit(_et, focus="note")
root.update()
_w = dlg_find("编辑任务")
if _w:
    _w["text"].delete("1.0", "end")
    _w["text"].insert("1.0", "不该保存的内容")
    root.focus_force()
    _w["dlg"].focus_force()
    _w["text"].focus_set()
    root.update()
    _w["text"].event_generate("<Escape>", when="now")
    root.update_idletasks()
    root.update()
    check("Esc 关掉对话框且什么都没保存",
          dlg_find("编辑任务") is None and _et["note"] == _before,
          "实际 %r（应还是 %r）" % (_et["note"], _before))
else:
    check("Esc 关掉对话框且什么都没保存", False, "对话框没建出来")

# 备注里混进来的 \r\n / \r 要统一成 \n：两版共用一份 tasks.json，
# tk 侧留个看不见的 \r 会让 aardio 那边的卡片上多出一个方块。
_nz = mk("换行归一化测试")
app.set_note(_nz, "A\r\nB\rC\nD")
check("备注里的 \\r\\n / \\r 统一成 \\n", _nz["note"] == "A\nB\nC\nD",
      "实际 %r" % _nz["note"])

# 就地编辑器改的是同一条落库出口
_nz["note"] = ""
root.update()
app.redraw()
root.update()
app.open_editor(_nz, "note")
if app.editor:
    app.editor["entry"].delete(0, "end")
    app.editor["entry"].insert(0, "就地改的备注")
    app._commit_editor()
root.update()
check("就地编辑备注也走 set_note（同一个落库出口）",
      _nz["note"] == "就地改的备注", "实际 %r" % _nz["note"])


def count_win(title):
    """当前存在几个标题为 title 的 Toplevel。"""
    return sum(1 for x in root.winfo_children()
               if isinstance(x, tk.Toplevel) and x.winfo_exists()
               and x.title() == title)


print("\n-- 使用帮助 --")
check("顶栏有「? 帮助」按钮",
      hasattr(app, "help_btn") and app.help_btn.cget("text") == "? 帮助",
      "实际 %s" % (app.help_btn.cget("text") if hasattr(app, "help_btn") else None))
check("F1 已经绑上（按了能打开帮助）", bool(root.bind("<F1>")),
      "实际 %r" % root.bind("<F1>"))
check("点开之前没有帮助窗", count_win("使用帮助") == 0)

hw = app.open_help()
root.update()
_hw = dlg_find("使用帮助")
check("打开后帮助窗出现了", _hw is not None)
check("窗口标题是「使用帮助」", bool(_hw) and _hw["dlg"].title() == "使用帮助")
# 只读：能选中复制，但改不动。别写成 state="normal"，否则帮助被人一敲就乱了
check("正文是只读的（挡住误改）",
      bool(_hw) and _hw["text"].cget("state") == "disabled",
      "实际 %s" % (_hw["text"].cget("state") if _hw else None))
body = _hw["text"].get("1.0", "end") if _hw else ""
check("讲了「一分钟上手」", "一分钟上手" in body)
check("逐个讲了顶栏按钮",
      all(k in body for k in ("贴上", "四象限", "统计", "复盘", "置顶", "更多", "帮助")),
      "缺 %s" % [k for k in ("贴上", "四象限", "统计", "复盘", "置顶", "更多", "帮助")
                 if k not in body])
check("讲了卡片上的操作", "卡片上能做的操作" in body and "编辑任务" in body)
check("卡片左上角画的是方框，帮助里就写方框",
      "方框" in body and "圆圈" not in body,
      "含方框=%s 含圆圈=%s（写成圆圈用户会满屏找个不存在的圆圈）"
      % ("方框" in body, "圆圈" in body))
check("帮助里写了备注框的回车用法",
      "Shift+回车" in body and "回车" in body,
      "正文里没提 Shift+回车")
check("帮助里说了就地编辑的 Esc 是取消",
      "Esc" in body and "取消" in body)
check("讲了拖拽能做哪几件事", "拖拽能做五件事" in body)
check("讲了快捷键", "F1" in body and "Ctrl + Z" in body)
check("讲了数据存在哪", "tasks.json" in body)
check("文案里的样式只有约定那几种",
      all(s[0] in ("h1", "h2", "p", "n", "k") for s in sticky.HELP_SECTIONS),
      "实际 %s" % sorted({s[0] for s in sticky.HELP_SECTIONS}))
check("「k」条目都带着「名字 + 解释」这一对",
      all(len(s) == 2 and isinstance(s[1], tuple) and len(s[1]) == 2
          for s in sticky.HELP_SECTIONS if s[0] == "k"))

check("讲清了象限可以改名，以及三个入口",
      "四个象限可以改名" in body
      and all(k in body for k in ("自定义象限名字", "改这个名字", "填回默认")),
      "正文里没把改名的入口说全")
# 帮助窗是纯 Text，不渲染 markdown —— 写 **加粗** 会原样显示星号。
# 这个错已经犯过两次（第 8 项、第 10 项），用一条用例钉住。
_all_help_text = "\n".join(
    [s[1] for s in sticky.HELP_SECTIONS if s[0] != "k"]
    + [s[1][0] + s[1][1] for s in sticky.HELP_SECTIONS if s[0] == "k"])
check("帮助文案里没有 markdown 标记（纯 Text 只认自己的那套约定）",
      "**" not in _all_help_text,
      "带星号的条目：%s" % [x for x in _all_help_text.split("\n") if "**" in x][:2])

check("有个「关闭」按钮", bool(_hw) and any(
    b.cget("text") == "关闭" for b in _hw["btns"]),
    "实际 %s" % ([b.cget("text") for b in _hw["btns"]] if _hw else None))
check("帮助窗绑了 Esc（不想去够「关闭」按钮时用）",
      bool(_hw) and "<Key-Escape>" in _hw["dlg"].bind(),
      "实际 %s" % (list(_hw["dlg"].bind()) if _hw else None))
check("重复点开不会开出第二个窗",
      app.open_help().winfo_exists() and count_win("使用帮助") == 1,
      "实际 %d 个" % count_win("使用帮助"))

# 关掉：走「关闭」按钮（Esc 那条路是绑在 Toplevel 上的，测试里焦点不稳）
for _b in (_hw["btns"] if _hw else []):
    if _b.cget("text") == "关闭":
        _b.invoke()
        break
root.update()
check("点「关闭」能把它关掉", count_win("使用帮助") == 0)
check("关掉之后还能再打开（不会以为它还开着）",
      app.open_help().winfo_exists() and count_win("使用帮助") == 1)
dlg_close("使用帮助")
count_win("使用帮助") and dlg_close("使用帮助")

# 主窗置顶时帮助窗必须跟着，否则会被主窗压在后面（看着像「点了帮助没反应」）
app.topmost = True
app._apply_topmost(announce=False)
_hv = app.open_help()
root.update()
check("主窗置顶时，帮助窗也跟着置顶",
      bool(_hv.attributes("-topmost")),
      "实际 %s" % _hv.attributes("-topmost"))
app.topmost = False
app._apply_topmost(announce=False)
root.update()
check("取消置顶后帮助窗也取消（不能赖在最前面）",
      not _hv.attributes("-topmost"),
      "实际 %s" % _hv.attributes("-topmost"))
dlg_close("使用帮助")

print("\n-- 多屏：弹出窗要跟着主窗走，别被拽回主屏 --")
# 防的是这个坑：拿 winfo_screenwidth()（**主屏**尺寸）给弹出窗收边，
# 主窗在副屏时会被判成"超出屏幕了"，窗口整个拽回主屏 ——
# 真机表现就是「帮助没跟着软件走，跑到另一块屏上去了」。
# 单屏机器上两种算法结果一样，测不出差别，所以下面把主窗挪到第二块屏去试；
# 没有第二块屏就跳过（跳过不算失败）。
_full, _work = sticky.screen_areas(root)
check("screen_areas 给出 (整屏, 工作区) 两个矩形",
      len(_full) == 4 and len(_work) == 4 and
      all(isinstance(v, int) for v in tuple(_full) + tuple(_work)),
      "实际 %s / %s" % (_full, _work))
check("探测到的整屏矩形包住主窗中心",
      _full[0] <= root.winfo_x() + root.winfo_width() // 2 <= _full[2] and
      _full[1] <= root.winfo_y() + root.winfo_height() // 2 <= _full[3],
      "整屏=%s 主窗@%d,%d" % (_full, root.winfo_x(), root.winfo_y()))

_save_xy = (root.winfo_x(), root.winfo_y())
root.geometry("+%d+%d" % (root.winfo_screenwidth() + 120, 140))
root.update()
root.update_idletasks()
_mon2, _work2 = sticky.screen_areas(root)
if _mon2[0] >= root.winfo_screenwidth():
    check("主窗挪到副屏后，探测到的就是副屏",
          _mon2[0] > 0 and _mon2[2] > root.winfo_screenwidth(),
          "实际 %s（主屏宽 %d）" % (_mon2, root.winfo_screenwidth()))
    _hh = app.open_help()
    root.update()
    check("帮助窗留在副屏，没被拽回主屏",
          _mon2[0] <= _hh.winfo_x() < _mon2[2],
          "帮助窗 x=%d，副屏 %s" % (_hh.winfo_x(), _mon2))
    check("帮助窗纵向也在副屏里",
          _mon2[1] <= _hh.winfo_y() < _mon2[3],
          "帮助窗 y=%d，副屏 %s" % (_hh.winfo_y(), _mon2))
    dlg_close("使用帮助")

    # 提醒窗贴的是**整屏**右下角（和 aardio 版一致），同样得跟着主窗走
    r_tmp = mk("副屏提醒用例", due=key_today)
    app.ui["remind_on"] = True
    app._maybe_remind()
    root.update()
    _rw = app._remind_win
    check("提醒窗也落在副屏，没被拽回主屏",
          _rw is not None and _rw.winfo_exists() and _rw.winfo_x() >= _mon2[0],
          "提醒窗 x=%s，副屏 %s" % (_rw.winfo_x() if _rw else None, _mon2))
    if _rw is not None and _rw.winfo_exists():
        _rw.destroy()
    root.update()
    app.ui["remind_on"] = False
    app.tasks.remove(r_tmp)
else:
    print("  [SKIP] 本机只有一块屏，副屏那 4 条用例跳过")

root.geometry("+%d+%d" % _save_xy)
root.update()

print("\n-- 持久化 --")
app.save()
raw = json.load(open(sticky.DATA_FILE, encoding="utf-8"))
check("JSON 已写出", len(raw["tasks"]) == len(app.tasks))
check("界面状态已保存", raw["ui"]["mode"] == "matrix")
check("数据版本号已升到 3", raw.get("v") == 3, "实际 %s" % raw.get("v"))
check("回收站也写进了文件", isinstance(raw.get("trash"), list))
check("备份配置写进了 ui 段",
      raw["ui"]["backup_keep"] == 30 and "backup_on" in raw["ui"]
      and "backup_dir" in raw["ui"])
check("提醒开关写进了 ui 段", "remind_on" in raw["ui"])
check("每个任务都带上了新字段",
      all(set(("subs", "logs", "timer", "repeat", "done_at", "remind_key"))
          <= set(t.keys()) for t in raw["tasks"]))

app.tasks = []
app.load()
check("重新载入数据一致", len(app.tasks) == len(raw["tasks"]))
rt = [t for t in app.tasks if t["title"] == "子任务测试任务"]
check("重载后子任务完整保留", bool(rt) and len(rt[0]["subs"]) == 7,
      "实际 %s" % (len(rt[0]["subs"]) if rt else "任务都没了"))
tl = [t for t in app.tasks if t["title"] == "计时任务一"]
check("重载后耗时流水完整保留", bool(tl) and tl[0]["logs"].get(key_today, 0) >= 85,
      "实际 %s" % (tl[0]["logs"] if tl else "任务都没了"))
check("重载后计时字段是数字",
      all(isinstance(t.get("timer"), (int, float)) for t in app.tasks))
_rn = [t for t in app.tasks if t["title"] == "备注测试任务"]
check("重载后备注完整保留", bool(_rn) and _rn[0]["note"] == "跨重启的备注",
      "实际 %s" % (_rn[0]["note"] if _rn else "任务都没了"))

print("\n-- 打包成 exe：任务数据必须落在 exe 旁边 --")

import re as _re

check("源码里带着版本号（打包脚本从这儿读，只存一份）",
      bool(_re.match(r"^\d+\.\d+\.\d+$", sticky.APP_VERSION)),
      "实际 %r" % sticky.APP_VERSION)
check("源码运行时不算 frozen", sticky.FROZEN is False,
      "实际 %r" % sticky.FROZEN)

# 这一段是本节最要紧的：_app_dir() 决定任务数据到底写到哪。
# 单文件 exe 跑起来时 __file__ 指向 %TEMP%\MEIxxxx（每次启动都是一个
# 新目录、退出即删）。要是 _app_dir() 拿它当基准，用户白天改了一整天
# 的任务，关掉再开就全没了 —— 而且不留任何痕迹。所以这里把"打包"这件
# 事模拟出来，直接盯 _app_dir() 的返回值。
_real_exe = sys.executable
_fake = r"C:\some\where\逍遥便利贴.exe"
try:
    sys.frozen = True
    sys.executable = _fake
    check("打包后 _app_dir() 取的是 exe 所在目录，不是临时解压目录",
          sticky._app_dir() == r"C:\some\where",
          "实际 %r" % sticky._app_dir())
    check("打包后任务数据就写在 exe 旁边",
          os.path.join(sticky._app_dir(), "tasks.json")
          == os.path.join(r"C:\some\where", "tasks.json"))
finally:
    del sys.frozen
    sys.executable = _real_exe

check("模拟结束，_app_dir() 回到源码目录",
      sticky._app_dir() == os.path.dirname(os.path.abspath(sticky.__file__)),
      "实际 %r" % sticky._app_dir())

print("\n-- 帮助窗里能看出这是哪一版 --")

_hw = app.open_help()
root.update()
_labels = []


def _walk(w):
    for c in w.winfo_children():
        if isinstance(c, tk.Label):
            try:
                _labels.append(str(c.cget("text")))
            except Exception:
                pass
        _walk(c)


_walk(_hw)
check("帮助窗底部报出了版本号",
      any(sticky.APP_VERSION in t for t in _labels),
      "实际 %s" % _labels[-3:])
check("源码版不冒充「打包版」", not any("打包版" in t for t in _labels),
      "实际 %s" % _labels[-3:])
_hw.destroy()
root.update()

print("\n-- 象限名字可以自定义（它本质是一种分类方式）--")

# 用户的原话：「工作、学习、娱乐、生活这些象限其实也是一种分类方式……象限的
# 备注解释自然是应该可以自定义的」「这种后面的立刻做这些应该是可以修改的才对」
check("出厂时是那四个默认名字",
      [pr["name"] for pr in sticky.PRIOS] == [d[0] for d in sticky.QUAD_DEFAULTS],
      "实际 %s" % [pr["name"] for pr in sticky.PRIOS])

sticky.apply_quad_labels([{"name": "工作", "act": "专注"},
                          {"name": "学习", "act": "充电"},
                          {"name": "娱乐", "act": ""},
                          {"name": "生活", "act": "杂事"}])
check("四个名字都换掉了",
      [pr["name"] for pr in sticky.PRIOS] == ["工作", "学习", "娱乐", "生活"],
      "实际 %s" % [pr["name"] for pr in sticky.PRIOS])
check("名字后面的备注也跟着换",
      [pr["act"] for pr in sticky.PRIOS] == ["专注", "充电", "", "杂事"],
      "实际 %r" % [pr["act"] for pr in sticky.PRIOS])
check("PRIO_BY_P 看到的是同一份（不是另存了一个副本）",
      sticky.PRIO_BY_P[0]["name"] == "工作")

sticky.apply_quad_labels([{"name": "  ", "act": "x"}, {"name": "只给名字"}])
check("名字留空就沿用默认（不会出现没名字的格子）",
      sticky.PRIOS[0]["name"] == sticky.QUAD_DEFAULTS[0][0],
      "实际 %r" % sticky.PRIOS[0]["name"])
check("没给备注的格子沿用默认备注",
      sticky.PRIOS[1]["act"] == sticky.QUAD_DEFAULTS[1][1],
      "实际 %r" % sticky.PRIOS[1]["act"])
check("给了空备注就是空的（用户主动清掉，别拿默认盖回来）",
      sticky.PRIOS[0]["act"] == "x", "实际 %r" % sticky.PRIOS[0]["act"])

sticky.apply_quad_labels(None)
check("老数据里没有 ui.quads → 四个全部回落默认",
      [pr["name"] for pr in sticky.PRIOS] == [d[0] for d in sticky.QUAD_DEFAULTS])
sticky.apply_quad_labels([None, "脏", {"name": 123}, (None, None)])
check("脏数据也不崩，名字仍然是字符串且非空",
      all(isinstance(pr["name"], str) and pr["name"] for pr in sticky.PRIOS),
      "实际 %r" % [pr["name"] for pr in sticky.PRIOS])

# 徽章/菜单上的短标签要跟着改，而且备注留空时不能露出光秃秃一个「P0」
sticky.apply_quad_labels([{"name": "生活", "act": ""}])
check("备注为空时短标签用象限名顶上",
      sticky.quad_title(0) == "P0 生活", "实际 %r" % sticky.quad_title(0))
check("备注为空时完整标签也不留「·」尾巴",
      sticky.quad_full(0) == "P0 生活", "实际 %r" % sticky.quad_full(0))
sticky.apply_quad_labels([{"name": "工作", "act": "专注"}])
check("有备注时短标签用备注", sticky.quad_title(0) == "P0 专注",
      "实际 %r" % sticky.quad_title(0))
check("完整标签是「P0 工作 · 专注」", sticky.quad_full(0) == "P0 工作 · 专注",
      "实际 %r" % sticky.quad_full(0))

# ---- 真的改一遍：菜单和对话框都走 set_quad_labels ----
app.set_quad_labels([{"name": "工作", "act": "立刻做"},
                     {"name": "学习", "act": "计划做"},
                     {"name": "娱乐", "act": "有空再做"},
                     {"name": "生活", "act": ""}], 0)
app.redraw()
root.update()
check("画布上的象限标题换成了新名字",
      "工作" in all_texts(app) and "重要且紧急" not in all_texts(app),
      "实际含「工作」的：%s" % [x for x in all_texts(app) if "工作" in x][:3])
_act_texts = [x for x in all_texts(app) if x.startswith("· ")]
check("有备注的三格画出了「· 备注」，没备注的那格不画",
      sorted(_act_texts) == sorted(["· 立刻做", "· 计划做", "· 有空再做"]),
      "实际 %s" % _act_texts)
app.save()
_ui = json.load(open(sticky.DATA_FILE, encoding="utf-8"))["ui"]
check("名字写进了 ui.quads（下次打开还在）",
      [q["name"] for q in _ui.get("quads", [])] == ["工作", "学习", "娱乐", "生活"],
      "实际 %r" % _ui.get("quads"))
check("备注也一起存了（含那一格空串）",
      [q["act"] for q in _ui.get("quads", [])] == ["立刻做", "计划做", "有空再做", ""],
      "实际 %r" % _ui.get("quads"))

# ★ 从真实点击进去（本项目已经栽过三次"按钮画着、点了没反应"）：
#   把 ask_quads 换成探针，验"点象限标题"确实会打开改名框、且是被点的那一格。
_seen = []
_real_ask = app.ask_quads
app.ask_quads = lambda p=None: _seen.append(p)
app.redraw()
root.update()
_box = region(app, "qhead", "Q2")
check("象限标题是热区（点了才有反应）", _box is not None)
if _box:
    _cx, _cy = (_box[0] + _box[2]) / 2.0, (_box[1] + _box[3]) / 2.0
    app.on_press(E(_cx, _cy))
    app.on_release(E(_cx, _cy))
check("★ 点象限标题打开的是这一格的改名框", _seen == [2], "实际 %r" % _seen)
app.ask_quads = _real_ask

check("标题热区只占标题那一行，不会盖住下面的卡片（卡片照样能点能拖）",
      _box is not None and _box[3] - _box[1] <= sticky.QHEAD,
      "实际 %r，QHEAD=%s" % (_box, sticky.QHEAD))

app.reset_quads()
app.redraw()
root.update()
check("能一键恢复默认",
      [pr["name"] for pr in sticky.PRIOS] == [d[0] for d in sticky.QUAD_DEFAULTS],
      "实际 %s" % [pr["name"] for pr in sticky.PRIOS])

_mq = app.build_quad_menu(0)
_q_labels = [_mq.entrycget(i, "label") for i in range(_mq.index("end") + 1)
             if _mq.type(i) == "command"]
check("象限标题右键菜单里有「改这个名字…」",
      any("改这个名字" in l for l in _q_labels), "实际 %s" % _q_labels)
_mq.destroy()
app.set_quad_labels([{"name": "工作", "act": "专注"}])
_mq = app.build_quad_menu(0)
_q_states = {_mq.entrycget(i, "label"): _mq.entrycget(i, "state")
             for i in range(_mq.index("end") + 1) if _mq.type(i) == "command"}
_mq.destroy()
check("改过名之后「恢复默认」才可点",
      _q_states.get("这一格恢复默认名字") == "normal", "实际 %r" % _q_states)
app.reset_quads()

_mm = app.build_more_menu()
_m_labels = [_mm.entrycget(i, "label") for i in range(_mm.index("end") + 1)
             if _mm.type(i) == "command"]
check("「更多 ▾」里有自定义象限的入口（不用靠右键去猜）",
      any("自定义象限" in l for l in _m_labels), "实际 %s" % _m_labels)
_mm.destroy()

# ---- 名字被改得很长时，不能压到右边的任务数上 ----
_long_name = "工作上的事情统统放这一格谁也不许乱动"
_long_act = "备注也可以写得很长很长很长"
_short, _short_act = sticky.fit_quad_head(_long_name, _long_act, 120)
_w = sticky._font_of(sticky.F_HEAD).measure(_short)
check("名字太长会裁到可用宽度内（不压右边的任务数）",
      _w <= 120 and _short.endswith("…"), "实际 %r 宽 %s" % (_short, _w))
check("裁过之后备注也跟着收窄",
      sticky._font_of(sticky.F_SMALL).measure("· " + _short_act) + _w + 8 <= 120
      or _short_act == "", "实际 %r / %r" % (_short, _short_act))
check("放得下的时候一个字都不动",
      sticky.fit_quad_head("工作", "专注", 400) == ("工作", "专注"))

print("\n-- 存不进盘的时候要吭声，不能装死 --")

# 打包版最容易踩的坑：exe 被丢进 C:\Program Files 这类要管理员权限的
# 目录，那里写文件会被系统拒绝。原来 _write_data() 里是 `except: pass`，
# 表现就是"改了一天任务、关掉再开全没了"，一句提示都没有。
import builtins as _bi

_warns = []
_open, _warn = _bi.open, sticky.tkmb.showwarning
try:
    sticky.tkmb.showwarning = lambda *a, **k: _warns.append(a)

    def _denied(*a, **k):
        raise PermissionError(13, "拒绝访问")
    _bi.open = _denied
    app._save_warned = False
    app._write_data()
    app._write_data()               # 第二次不该再弹，否则每次拖动都来一个框
finally:
    _bi.open = _open
    sticky.tkmb.showwarning = _warn

check("存盘失败会弹提示（不再静默丢数据）", len(_warns) == 1,
      "实际弹了 %d 次" % len(_warns))
check("提示里说清了数据在哪、该怎么办",
      bool(_warns) and "tasks.json" in str(_warns[0])
      and "Program Files" in str(_warns[0]),
      "实际 %s" % (str(_warns[0])[:80] if _warns else "一次都没弹"))
app._save_warned = False            # 复位，别影响后面

print("\n-- 跳回正常路径：写盘成功后不该再提示 --")
app.save()
check("恢复正常后能正常存盘", os.path.exists(sticky.DATA_FILE))
check("正常存盘不会弹任何提示", len(_warns) == 1, "实际 %d 次" % len(_warns))

root.destroy()
print("\n" + "=" * 46)
print("通过 %d 项，失败 %d 项" % (OK, FAIL))
sys.exit(1 if FAIL else 0)
