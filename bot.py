"""
家庭 LINE Bot — 主程式
醫院：雙和醫院（新北市中和區）
語言：繁體中文
"""

import os
import hmac
import base64
import hashlib
import json
import requests as http_requests
from datetime import datetime, timezone, timedelta

TW = timezone(timedelta(hours=8))

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError

from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, JoinEvent
)

app = Flask(__name__)

# 這兩行照你原本的，不要動
LINE_CHANNEL_ACCESS_TOKEN = "7EaTRaTJNUiIOZTokqgGqFgfkGS+I8LOUz7S0Q4sHjQLQau32soh4uki8OOoajE3+LGr9+mLXgbRlts3vUpNefO1JMOfp3jQZ2hWgIMNxxt7L0amov61ZaQw8ygOjujihph0wK1zEWXhb3J2D8jGrQdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "bc6a476a09e7b22b577b8a6c3d85b879"

print("[env] token exists:", bool(LINE_CHANNEL_ACCESS_TOKEN))
print("[env] secret exists:", bool(LINE_CHANNEL_SECRET))
print("[env] secret len:", len(LINE_CHANNEL_SECRET))

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Supabase 設定
SUPABASE_URL = "https://oqydathbpfnigrhxgplb.supabase.co"
SUPABASE_KEY = "sb_publishable_Hw2ErHE0YQD3S14JB5pXiQ_pHQFNmWc"

# 記憶體快取（加速讀取，Supabase 為持久備份）
step_data = {}
GROUP_ID = os.environ.get("LINE_GROUP_ID", "")


# ════════════════════════════════════════════════
#  Supabase 資料庫操作
# ════════════════════════════════════════════════
def _supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def db_insert_step(name, steps, date, time_str):
    """寫入一筆步數紀錄到 Supabase"""
    if not SUPABASE_URL:
        return
    try:
        http_requests.post(
            f"{SUPABASE_URL}/rest/v1/steps",
            headers=_supabase_headers(),
            json={"name": name, "steps": steps, "date": date, "time": time_str},
            timeout=5,
        )
    except Exception as e:
        print(f"[db] insert error: {e}")


def db_get_today_records(date, name=None):
    """從 Supabase 取得某天步數紀錄，可選角色"""
    if not SUPABASE_URL:
        return []
    try:
        params = {"date": f"eq.{date}", "order": "id.asc"}
        if name:
            params["name"] = f"eq.{name}"
        resp = http_requests.get(
            f"{SUPABASE_URL}/rest/v1/steps",
            headers=_supabase_headers(),
            params=params,
            timeout=5,
        )
        return resp.json() if resp.status_code == 200 else []
    except Exception as e:
        print(f"[db] query error: {e}")
        return []


def db_get_date_range(start_date, end_date, name=None):
    """從 Supabase 取得日期範圍內的紀錄，可選角色"""
    if not SUPABASE_URL:
        return []
    try:
        conditions = f"(date.gte.{start_date},date.lte.{end_date})"
        if name:
            conditions = f"(date.gte.{start_date},date.lte.{end_date},name.eq.{name})"
        resp = http_requests.get(
            f"{SUPABASE_URL}/rest/v1/steps",
            headers=_supabase_headers(),
            params={"and": conditions, "order": "id.asc"},
            timeout=5,
        )
        return resp.json() if resp.status_code == 200 else []
    except Exception as e:
        print(f"[db] range query error: {e}")
        return []


def db_get_latest_all(date):
    """從 Supabase 取得某天每個人的最新步數"""
    if not SUPABASE_URL:
        return []
    try:
        resp = http_requests.get(
            f"{SUPABASE_URL}/rest/v1/steps",
            headers=_supabase_headers(),
            params={"date": f"eq.{date}", "order": "id.asc"},
            timeout=5,
        )
        rows = resp.json() if resp.status_code == 200 else []
        # 每個人取最後一筆
        latest = {}
        for row in rows:
            latest[row["name"]] = row
        return list(latest.values())
    except Exception as e:
        print(f"[db] latest error: {e}")
        return []


# ── 行程資料庫操作 ──

def db_insert_event(title, date, time_str, end_time, recurring, weekday, remind_hours):
    if not SUPABASE_URL:
        return None
    try:
        resp = http_requests.post(
            f"{SUPABASE_URL}/rest/v1/events",
            headers={**_supabase_headers(), "Prefer": "return=representation"},
            json={
                "title": title, "date": date, "time": time_str,
                "end_time": end_time, "recurring": recurring,
                "weekday": weekday, "remind_hours": remind_hours,
            },
            timeout=5,
        )
        rows = resp.json() if resp.status_code == 201 else []
        return rows[0] if rows else None
    except Exception as e:
        print(f"[db] event insert error: {e}")
        return None


def db_get_events():
    if not SUPABASE_URL:
        return []
    try:
        resp = http_requests.get(
            f"{SUPABASE_URL}/rest/v1/events",
            headers=_supabase_headers(),
            params={"order": "id.asc"},
            timeout=5,
        )
        return resp.json() if resp.status_code == 200 else []
    except Exception as e:
        print(f"[db] event query error: {e}")
        return []


def db_delete_event(event_id):
    if not SUPABASE_URL:
        return False
    try:
        resp = http_requests.delete(
            f"{SUPABASE_URL}/rest/v1/events?id=eq.{event_id}",
            headers=_supabase_headers(),
            timeout=5,
        )
        return resp.status_code == 204
    except Exception as e:
        print(f"[db] event delete error: {e}")
        return False


def db_mark_event_notified(event_id, date_str):
    if not SUPABASE_URL:
        return
    try:
        http_requests.patch(
            f"{SUPABASE_URL}/rest/v1/events?id=eq.{event_id}",
            headers=_supabase_headers(),
            json={"last_notified": date_str},
            timeout=5,
        )
    except Exception as e:
        print(f"[db] event notify error: {e}")


# ════════════════════════════════════════════════
#  健康檢查
# ════════════════════════════════════════════════
@app.route("/", methods=["GET"])
def health():
    return {
        "status": "running",
        "steps": step_data,
        "group_id": GROUP_ID,
    }, 200


# ════════════════════════════════════════════════
#  Webhook 入口
# ════════════════════════════════════════════════
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    raw_body = request.get_data()
    body = raw_body.decode("utf-8")

    expected_signature = base64.b64encode(
        hmac.new(
            LINE_CHANNEL_SECRET.encode("utf-8"),
            raw_body,
            hashlib.sha256
        ).digest()
    ).decode("utf-8")

    print("[callback] signature from LINE:", signature)
    print("[callback] expected signature  :", expected_signature)
    print("[callback] signature match     :", signature == expected_signature)
    print("[callback] body:", body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError as e:
        print("[callback] InvalidSignatureError:", str(e))
        abort(400)
    except Exception as e:
        print("[callback] Exception:", repr(e))
        abort(400)

    return "OK", 200


# ════════════════════════════════════════════════
#  Bot 加入群組事件
# ════════════════════════════════════════════════
@handler.add(JoinEvent)
def handle_join(event):
    global GROUP_ID

    if hasattr(event.source, "group_id"):
        GROUP_ID = event.source.group_id
        print(f"[Bot] 加入群組，記錄 GROUP_ID: {GROUP_ID}")

    welcome_text = (
        "大家好，我是家庭助理 🤖\n\n"
        "目前可以使用這些功能：\n"
        "• /幫助 — 查看所有指令\n"
        "• /步數 — 今日步數\n"
        "• /步數紀錄 — 詳細紀錄\n"
        "• /行程 — 行程管理與提醒"
    )

    try:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=welcome_text)
        )
        print("[join] welcome message sent")
    except Exception as e:
        print("[join] reply error:", repr(e))


# ════════════════════════════════════════════════
#  接收文字訊息
# ════════════════════════════════════════════════
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global GROUP_ID

    text = event.message.text.strip()
    reply_token = event.reply_token

    if hasattr(event.source, "group_id") and not GROUP_ID:
        GROUP_ID = event.source.group_id
        print(f"[Bot] 記錄群組 ID: {GROUP_ID}")

    print(f"[message] source_type={event.source.type}, text={text}")

    # 去掉開頭的 / 並統一比對
    cmd = text.lstrip("/")

    try:
        if cmd in ["幫助", "help"]:
            do_reply(reply_token, build_help())

        elif cmd in ["步數", "媽媽步數"]:
            do_reply(reply_token, build_steps_message())

        elif cmd.startswith("步數紀錄"):
            date_arg = cmd.replace("步數紀錄", "").strip()
            do_reply(reply_token, build_steps_history(date_arg))

        elif cmd.startswith("行程"):
            arg = cmd.replace("行程", "").strip()
            do_reply(reply_token, handle_event_command(arg))

        else:
            do_reply(
                reply_token,
                "我有收到你的訊息："
                f"{text}\n\n"
                "可輸入 /幫助 查看目前可用功能。"
            )

    except Exception as e:
        print("[message] handler error:", repr(e))
        do_reply(reply_token, "⚠️ 抱歉，剛剛處理訊息時發生錯誤，請再試一次。")


# ════════════════════════════════════════════════
#  接收 Android App 步數
# ════════════════════════════════════════════════
@app.route("/steps", methods=["POST"])
def receive_steps():
    global step_data

    data = request.get_json(silent=True) or {}
    steps = int(data.get("steps", 0))
    name = data.get("name", "").strip() or "媽媽"
    now = datetime.now(TW)
    today = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")

    step_data.update({
        "steps": steps,
        "name": name,
        "date": today,
        "time": time_str,
    })

    # 寫入 Supabase
    db_insert_step(name, steps, today, time_str)

    print(f"[步數] {name} {steps} 步 @ {time_str}")

    if now.hour == 16 and now.minute < 31 and GROUP_ID:
        try:
            line_bot_api.push_message(
                GROUP_ID,
                TextSendMessage(text=build_steps_message())
            )
            print("[步數] 自動推播成功")
        except Exception as e:
            print("[步數] 自動推播失敗:", repr(e))

    return {"status": "ok", "steps": steps}, 200


@app.route("/push-steps", methods=["GET"])
def manual_push():
    if GROUP_ID:
        try:
            line_bot_api.push_message(
                GROUP_ID,
                TextSendMessage(text=build_steps_message())
            )
            return "推播成功", 200
        except Exception as e:
            print("[push-steps] error:", repr(e))
            return "推播失敗", 500
    return "尚未設定 GROUP_ID", 400


# ════════════════════════════════════════════════
#  行程提醒（由外部 cron 呼叫）
# ════════════════════════════════════════════════
@app.route("/check-reminders", methods=["GET"])
def check_reminders():
    if not GROUP_ID:
        return "no group", 200

    now = datetime.now(TW)
    today = now.strftime("%Y-%m-%d")
    current_weekday = now.weekday()  # 0=週一 ... 6=週日
    current_minutes = now.hour * 60 + now.minute
    sent = 0

    events = db_get_events()
    for ev in events:
        # 已經今天通知過了
        if ev.get("last_notified") == today:
            continue

        event_time = ev["time"]
        eh, em = int(event_time.split(":")[0]), int(event_time.split(":")[1])
        event_minutes = eh * 60 + em
        remind_hours = ev.get("remind_hours", 2)
        remind_at = event_minutes - remind_hours * 60

        should_notify = False

        if ev.get("recurring") == "weekly":
            if current_weekday == ev.get("weekday") and current_minutes >= remind_at and current_minutes < event_minutes:
                should_notify = True
        elif ev.get("date") == today:
            if current_minutes >= remind_at and current_minutes < event_minutes:
                should_notify = True

        if should_notify:
            time_display = event_time
            if ev.get("end_time"):
                time_display = f"{event_time}～{ev['end_time']}"
            msg = f"⏰ 行程提醒\n\n📌 {ev['title']}\n🕐 {time_display}"
            try:
                line_bot_api.push_message(GROUP_ID, TextSendMessage(text=msg))
                db_mark_event_notified(ev["id"], today)
                sent += 1
                print(f"[提醒] 已推播: {ev['title']}")
            except Exception as e:
                print(f"[提醒] 推播失敗: {e}")

    # 清理過期的一次性行程
    for ev in events:
        if not ev.get("recurring") and ev.get("date") and ev["date"] < today:
            db_delete_event(ev["id"])

    return {"checked": len(events), "sent": sent}, 200


# ════════════════════════════════════════════════
#  行程指令處理
# ════════════════════════════════════════════════
WEEKDAY_MAP = {
    "週一": 0, "周一": 0, "星期一": 0,
    "週二": 1, "周二": 1, "星期二": 1,
    "週三": 2, "周三": 2, "星期三": 2,
    "週四": 3, "周四": 3, "星期四": 3,
    "週五": 4, "周五": 4, "星期五": 4,
    "週六": 5, "周六": 5, "星期六": 5,
    "週日": 6, "周日": 6, "星期日": 6, "週天": 6, "周天": 6,
}

WEEKDAY_NAMES = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]


def handle_event_command(arg):
    if not arg or arg == "查詢":
        return build_event_list()

    if arg.startswith("刪除"):
        eid = arg.replace("刪除", "").strip()
        if eid.isdigit():
            ok = db_delete_event(int(eid))
            return f"✅ 已刪除行程 #{eid}" if ok else f"❌ 找不到行程 #{eid}"
        return "格式：/行程 刪除 編號\n例：/行程 刪除 23"

    return parse_and_create_event(arg)


def parse_and_create_event(arg):
    parts = arg.split()
    if len(parts) < 2:
        return event_help()

    # 解析「提前N小時」
    remind_hours = 2
    filtered = []
    for p in parts:
        if p.startswith("提前") and p.endswith("小時"):
            num = p.replace("提前", "").replace("小時", "")
            if num.isdigit():
                remind_hours = int(num)
        else:
            filtered.append(p)
    parts = filtered

    # 判斷是否為每週重複
    first = parts[0]
    recurring_key = None
    for key in WEEKDAY_MAP:
        if first.endswith(key):
            # 支援「每週五」或「週五」
            recurring_key = key
            break

    if recurring_key:
        weekday = WEEKDAY_MAP[recurring_key]
        rest = parts[1:]
        if len(rest) < 2:
            return event_help()

        time_str = rest[0]
        # 判斷第二個是結束時間還是標題
        if len(rest) >= 3 and ":" in rest[1]:
            end_time = rest[1]
            title = " ".join(rest[2:])
        else:
            end_time = None
            title = " ".join(rest[1:])

        ev = db_insert_event(title, None, time_str, end_time, "weekly", weekday, remind_hours)
        if not ev:
            return "❌ 新增失敗，請稍後再試"

        time_display = time_str
        if end_time:
            time_display = f"{time_str}～{end_time}"
        return (
            f"✅ 已新增重複行程\n\n"
            f"📌 {title}\n"
            f"📅 每{WEEKDAY_NAMES[weekday]} {time_display}\n"
            f"⏰ 提前 {remind_hours} 小時提醒"
        )

    # 一次性行程：0401 14:00 標題
    date_str = _parse_date_short(parts[0])
    if not date_str:
        return event_help()

    rest = parts[1:]
    if len(rest) < 2:
        return event_help()

    time_str = rest[0]
    if len(rest) >= 3 and ":" in rest[1]:
        end_time = rest[1]
        title = " ".join(rest[2:])
    else:
        end_time = None
        title = " ".join(rest[1:])

    ev = db_insert_event(title, date_str, time_str, end_time, None, None, remind_hours)
    if not ev:
        return "❌ 新增失敗，請稍後再試"

    time_display = time_str
    if end_time:
        time_display = f"{time_str}～{end_time}"
    return (
        f"✅ 已新增行程\n\n"
        f"📌 {title}\n"
        f"📅 {date_str} {time_display}\n"
        f"⏰ 提前 {remind_hours} 小時提醒"
    )


def _parse_date_short(s):
    """支援 0401 → 2026-04-01，或 20260401 → 2026-04-01"""
    clean = s.replace("-", "").replace("/", "")
    if len(clean) == 4 and clean.isdigit():
        year = datetime.now(TW).strftime("%Y")
        return f"{year}-{clean[:2]}-{clean[2:4]}"
    if len(clean) == 8 and clean.isdigit():
        return f"{clean[:4]}-{clean[4:6]}-{clean[6:8]}"
    return None


def build_event_list():
    events = db_get_events()
    if not events:
        return "📅 目前沒有任何行程"

    lines = ["📅 行程列表\n"]

    recurring_events = [e for e in events if e.get("recurring")]
    onetime_events = [e for e in events if not e.get("recurring")]

    if recurring_events:
        lines.append("🔁 重複行程")
        for ev in recurring_events:
            wd = WEEKDAY_NAMES[ev["weekday"]] if ev.get("weekday") is not None else "?"
            time_display = ev["time"]
            if ev.get("end_time"):
                time_display = f"{ev['time']}～{ev['end_time']}"
            lines.append(f"  #{ev['id']} 每{wd} {time_display} {ev['title']}（提前{ev.get('remind_hours', 2)}小時）")

    if onetime_events:
        if recurring_events:
            lines.append("")
        lines.append("📌 單次行程")
        for ev in onetime_events:
            time_display = ev["time"]
            if ev.get("end_time"):
                time_display = f"{ev['time']}～{ev['end_time']}"
            lines.append(f"  #{ev['id']} {ev.get('date', '?')} {time_display} {ev['title']}（提前{ev.get('remind_hours', 2)}小時）")

    lines.append("\n刪除請輸入：/行程 刪除 編號")
    return "\n".join(lines)


def event_help():
    return (
        "📅 行程指令格式\n\n"
        "單次行程：\n"
        "  /行程 0401 18:00 哥哥不回家吃飯\n"
        "  /行程 0405 14:00 15:00 媽媽復健\n\n"
        "重複行程：\n"
        "  /行程 每週五 14:00 15:00 爸媽運動時間\n\n"
        "自訂提前提醒：\n"
        "  /行程 每週五 14:00 15:00 運動 提前5小時\n\n"
        "查詢/刪除：\n"
        "  /行程 查詢\n"
        "  /行程 刪除 23"
    )


# ════════════════════════════════════════════════
#  訊息內容建構
# ════════════════════════════════════════════════
def build_help():
    return (
        "🤖 家庭助理指令表\n\n"
        "👟 步數\n"
        "  /步數 — 今日步數\n"
        "  /步數紀錄 — 今日詳細\n"
        "  /步數紀錄 媽媽 — 指定人\n"
        "  /步數紀錄 7天 — 最近 7 天\n"
        "  /步數紀錄 媽媽 7天\n"
        "  /步數紀錄 20260325 20260329\n\n"
        "📅 行程\n"
        "  /行程 查詢 — 查看所有行程\n"
        "  /行程 0401 18:00 哥哥不回家吃飯\n"
        "  /行程 0405 14:00 15:00 媽媽復健\n"
        "  /行程 每週五 14:00 15:00 爸媽運動\n"
        "  /行程 每週五 14:00 運動 提前8小時\n"
        "  /行程 刪除 編號\n\n"
        "💡 指令前面 / 可加可不加\n"
        "輸入 /幫助 隨時查看此列表"
    )


def _step_emoji(steps):
    if steps >= 5000:
        return "🎉"
    elif steps >= 3000:
        return "👍"
    elif steps >= 1000:
        return "🚶"
    return "💕"


def build_steps_message():
    today = datetime.now(TW).strftime("%Y-%m-%d")

    people = db_get_latest_all(today)
    if not people:
        return (
            "📱 尚未收到步數資料\n\n"
            "請確認手機的步數 App 是否正在執行。\n"
            "App 每 30 分鐘自動更新一次。"
        )

    lines = [f"👟 今日步數報告（{today}）\n"]

    for data in people:
        steps = data.get("steps", 0)
        name = data.get("name", "?")
        emoji = _step_emoji(steps)
        lines.append(f"  {emoji} {name}：{steps:,} 步（{data['time']} 更新）")

    return "\n".join(lines)


def _parse_date(s):
    """將 20260331 或 2026-03-31 或 2026/03/31 轉成 2026-03-31，失敗回 None"""
    clean = s.replace("-", "").replace("/", "")
    if len(clean) == 8 and clean.isdigit():
        return f"{clean[:4]}-{clean[4:6]}-{clean[6:8]}"
    return None


def build_steps_history(date_arg=""):
    # 解析參數：分離出 name 和其他部分
    # 規則：不是日期、不是「N天」的就當作 name
    parts = date_arg.strip().split() if date_arg else []
    name = None
    tokens = []

    for p in parts:
        if p.endswith("天"):
            tokens.append(p)
        elif _parse_date(p):
            tokens.append(p)
        else:
            name = p  # 當作角色名稱

    name_label = name if name else "全部"

    # /步數紀錄 mama 7天
    for t in tokens:
        if t.endswith("天"):
            num = t.replace("天", "").strip()
            if num.isdigit() and int(num) > 0:
                return _build_summary_days(int(num), name)
            return "格式錯誤，請用：/步數紀錄 7天"

    # /步數紀錄 mama 20260325 20260329
    dates = [_parse_date(t) for t in tokens if _parse_date(t)]
    if len(dates) == 2:
        return _build_summary_range(dates[0], dates[1], name)

    # /步數紀錄 mama 20260329
    if len(dates) == 1:
        return _build_detail(dates[0], name)

    # /步數紀錄 mama（沒有日期 → 今天）
    # /步數紀錄（沒有任何參數 → 今天全部人）
    today = datetime.now(TW).strftime("%Y-%m-%d")
    return _build_detail(today, name)


def _build_detail(query_date, name=None):
    """某天的詳細紀錄（每筆 30 分鐘）"""
    records = db_get_today_records(query_date, name)
    if not records:
        label = name if name else "任何人"
        return f"📊 {query_date} 沒有 {label} 的步數紀錄"

    # 如果沒指定 name，按人分組顯示
    if not name:
        people = {}
        for rec in records:
            people.setdefault(rec["name"], []).append(rec)

        lines = [f"📊 步數紀錄（{query_date}）\n"]
        for pname, recs in people.items():
            lines.append(f"── {pname} ──")
            for i, rec in enumerate(recs):
                steps = rec["steps"]
                if i == 0:
                    diff_text = "（首筆）"
                else:
                    diff = steps - recs[i - 1]["steps"]
                    diff_text = f"（+{diff:,} 步）" if diff > 0 else f"（{diff:,} 步）"
                lines.append(f"  {rec['time']}　{steps:,} 步 {diff_text}")
            if len(recs) >= 2:
                total_diff = recs[-1]["steps"] - recs[0]["steps"]
                lines.append(f"  📈 共走了 {total_diff:,} 步\n")
        return "\n".join(lines)

    # 指定了 name
    lines = [f"📊 {name}步數紀錄（{query_date}）\n"]
    for i, rec in enumerate(records):
        steps = rec["steps"]
        if i == 0:
            diff_text = "（首筆）"
        else:
            diff = steps - records[i - 1]["steps"]
            diff_text = f"（+{diff:,} 步）" if diff > 0 else f"（{diff:,} 步）"
        lines.append(f"  {rec['time']}　{steps:,} 步 {diff_text}")

    if len(records) >= 2:
        total_diff = records[-1]["steps"] - records[0]["steps"]
        lines.append(f"\n📈 {records[0]['time']}～{records[-1]['time']} 共走了 {total_diff:,} 步")

    return "\n".join(lines)


def _build_daily_summary(records, title, name=None):
    """通用的每日摘要產生器，按人分組顯示"""
    if not records:
        return None

    # 按 (名字, 日期) 分組取最大步數
    daily = {}
    for rec in records:
        key = (rec["name"], rec["date"])
        if key not in daily or rec["steps"] > daily[key]["steps"]:
            daily[key] = rec

    # 按人分組
    people = {}
    for (pname, d), rec in daily.items():
        people.setdefault(pname, []).append((d, rec))

    lines = [title]
    grand_total = 0

    for pname in sorted(people.keys()):
        days_data = sorted(people[pname], key=lambda x: x[0])

        if not name and len(people) > 1:
            lines.append(f"── {pname} ──")

        person_total = 0
        for d, rec in days_data:
            steps = rec["steps"]
            person_total += steps
            mark = _step_emoji(steps)
            lines.append(f"  {d}　{steps:,} 步 {mark}")

        avg = person_total // len(days_data) if days_data else 0
        lines.append(f"  📈 平均：{avg:,} 步/天　合計：{person_total:,} 步\n")
        grand_total += person_total

    return "\n".join(lines).rstrip()


def _build_summary_days(days, name=None):
    """最近 N 天摘要"""
    now = datetime.now(TW)
    end_date = now.strftime("%Y-%m-%d")
    start_date = (now - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    records = db_get_date_range(start_date, end_date, name)

    label = name if name else "全部"
    title = f"📊 {label}步數摘要（最近 {days} 天）\n"
    result = _build_daily_summary(records, title)
    return result if result else f"📊 最近 {days} 天沒有步數紀錄"


def _build_summary_range(start_date, end_date, name=None):
    """指定日期範圍摘要"""
    records = db_get_date_range(start_date, end_date, name)

    label = name if name else "全部"
    title = f"📊 {label}步數摘要（{start_date} ～ {end_date}）\n"
    result = _build_daily_summary(records, title)
    return result if result else f"📊 {start_date} ～ {end_date} 沒有步數紀錄"






# ════════════════════════════════════════════════
#  工具函式
# ════════════════════════════════════════════════
def do_reply(reply_token, content):
    try:
        if isinstance(content, str):
            line_bot_api.reply_message(reply_token, TextSendMessage(text=content))
        elif content is not None:
            line_bot_api.reply_message(reply_token, content)
    except Exception as e:
        print("[do_reply] error:", repr(e))
        raise


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"[Bot] 啟動中，port {port}")
    app.run(host="0.0.0.0", port=port)