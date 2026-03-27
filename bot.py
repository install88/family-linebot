"""
家庭 LINE Bot — 主程式
醫院：雙和醫院（新北市中和區）
語言：繁體中文
"""

import os
from datetime import datetime
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    FlexSendMessage, BubbleContainer, BoxComponent,
    TextComponent, SeparatorComponent
)

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET       = os.environ.get("LINE_CHANNEL_SECRET", "")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler      = WebhookHandler(LINE_CHANNEL_SECRET)

# 暫存資料（重啟後清空，未來可換成 SQLite）
step_data = {}
GROUP_ID  = os.environ.get("LINE_GROUP_ID", "")


# ════════════════════════════════════════════════
#  Webhook 入口
# ════════════════════════════════════════════════

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global GROUP_ID
    text        = event.message.text.strip()
    reply_token = event.reply_token

    # 自動記錄群組 ID（Bot 加入群組後第一次有人說話時）
    if hasattr(event.source, "group_id") and not GROUP_ID:
        GROUP_ID = event.source.group_id
        print(f"[Bot] 記錄群組 ID: {GROUP_ID}")

    # ── 指令路由 ──────────────────────────────────
    if text in ["/幫助", "/help", "幫助", "help"]:
        do_reply(reply_token, build_help())

    elif text in ["/步數", "步數", "媽媽步數"]:
        do_reply(reply_token, build_steps_message())

    elif text in ["雙和", "雙和醫院"]:
        do_reply(reply_token, build_hospital_info())

    elif text.startswith("/掛號查詢") or text.startswith("掛號查詢"):
        # 格式：/掛號查詢 心臟內科
        keyword = text.replace("/掛號查詢", "").replace("掛號查詢", "").strip()
        if keyword:
            do_reply(reply_token, build_appointment_card(keyword))
        else:
            do_reply(reply_token, build_dept_menu())

    elif text.startswith("/提醒"):
        # 格式：/提醒 08:30 記得吃藥
        parts = text.split(" ", 2)
        if len(parts) == 3:
            do_reply(reply_token, f"✅ 提醒已設定\n⏰ {parts[1]}：{parts[2]}\n\n（推播功能即將上線）")
        else:
            do_reply(reply_token, "格式：/提醒 時間 內容\n例：/提醒 08:30 記得吃藥")

    elif text == "/看診進度":
        do_reply(reply_token,
            "📋 看診進度查詢\n\n"
            "請前往雙和醫院官網或 App 查詢即時進度：\n"
            "🔗 https://shh.tmu.edu.tw\n"
            "📱 搜尋「雙和掛號」下載 App"
        )


# ════════════════════════════════════════════════
#  接收 Android App 步數
# ════════════════════════════════════════════════

@app.route("/steps", methods=["POST"])
def receive_steps():
    data  = request.get_json(silent=True) or {}
    steps = int(data.get("steps", 0))
    now   = datetime.now()

    step_data.update({
        "steps": steps,
        "date":  now.strftime("%Y-%m-%d"),
        "time":  now.strftime("%H:%M"),
    })
    print(f"[步數] {steps} 步 @ {now.strftime('%H:%M')}")

    # 傍晚 18:00 整點（前 30 分內）自動推播到群組
    if now.hour == 18 and now.minute < 31 and GROUP_ID:
        line_bot_api.push_message(
            GROUP_ID,
            TextSendMessage(text=build_steps_message())
        )

    return {"status": "ok", "steps": steps}


@app.route("/push-steps", methods=["GET"])
def manual_push():
    """手動觸發步數推播（測試用）"""
    if GROUP_ID:
        line_bot_api.push_message(
            GROUP_ID,
            TextSendMessage(text=build_steps_message())
        )
        return "推播成功"
    return "尚未設定 GROUP_ID", 400


# ════════════════════════════════════════════════
#  訊息內容建構
# ════════════════════════════════════════════════

def build_help():
    return (
        "🤖 家庭助理指令表\n\n"
        "🏥 掛號\n"
        "  雙和醫院 — 查看醫院資訊\n"
        "  /掛號查詢 心臟內科 — 查詢掛號方式\n"
        "  /掛號查詢 — 顯示全部科別\n"
        "  /看診進度 — 即時看診進度連結\n\n"
        "👟 步數\n"
        "  /步數 — 查看媽媽今日步數\n\n"
        "⏰ 提醒\n"
        "  /提醒 08:30 記得吃藥\n\n"
        "輸入 /幫助 隨時查看此列表"
    )


def build_steps_message():
    if not step_data:
        return (
            "📱 尚未收到步數資料\n\n"
            "請確認媽媽手機的步數 App 是否正在執行。\n"
            "App 每 30 分鐘自動更新一次。"
        )
    steps = step_data["steps"]
    if   steps >= 8000: emoji, note = "🎉", "太棒了！今日目標達成！"
    elif steps >= 5000: emoji, note = "👍", "走得不錯，再加把勁！"
    elif steps >= 2000: emoji, note = "🚶", "走了一些，晚飯後再散散步吧"
    else:               emoji, note = "💕", "今天步數少，記得多走動喔"

    return (
        f"👟 媽媽今日步數報告\n"
        f"📅 {step_data['date']}　最後更新：{step_data['time']}\n\n"
        f"{emoji} {steps:,} 步\n\n"
        f"{note}\n"
        f"每日建議目標：8,000 步"
    )


# ── 雙和醫院資訊 ──────────────────────────────────

HOSPITAL = {
    "name":     "衛生福利部雙和醫院",
    "short":    "雙和醫院",
    "address":  "新北市中和區中正路291號",
    "phone":    "02-2249-0088",
    "reg_web":  "https://shh.tmu.edu.tw",
    "reg_voice":"02-2248-0098（語音）",
    "reg_human":"02-2248-0607（人工）",
    "color":    "#1565C0",
    "hours": {
        "上午診": "08:30 – 11:30",
        "下午診": "13:30 – 16:30",
        "夜間診": "18:00 – 21:00",
    },
    "note": "週六僅上午診；週日及國定假日請至急診",
    "depts": [
        "心臟內科", "家醫科", "骨科", "神經內科",
        "腸胃內科", "眼科",  "復健科", "腎臟科",
        "胸腔內科", "皮膚科", "精神科", "婦產科",
    ],
    "report_times": "上午診報到截止 11:00\n下午診報到截止 16:00\n夜間診報到截止 20:30",
}


def build_hospital_info():
    h = HOSPITAL
    hours_text = "\n".join(f"  {k}：{v}" for k, v in h["hours"].items())
    depts_text = "、".join(h["depts"])

    contents = [
        TextComponent(text=f"🏥 {h['short']}", weight="bold", size="xl", color=h["color"]),
        TextComponent(text="（委託臺北醫學大學興建經營）", size="xs", color="#888888", margin="xs"),
        SeparatorComponent(margin="md"),
        TextComponent(text=f"📍 {h['address']}", size="sm", margin="md", wrap=True),
        TextComponent(text=f"☎  代表號：{h['phone']}",  size="sm", margin="sm"),
        SeparatorComponent(margin="md"),
        TextComponent(text="🕐 門診時段", weight="bold", size="sm", margin="md", color="#444444"),
        TextComponent(text=hours_text, size="sm", margin="xs", wrap=True),
        TextComponent(text=f"⚠️ {h['note']}", size="xs", margin="sm", color="#E65100", wrap=True),
        SeparatorComponent(margin="md"),
        TextComponent(text="📞 掛號方式", weight="bold", size="sm", margin="md", color="#444444"),
        TextComponent(text=f"網路：{h['reg_web']}", size="xs", margin="sm", wrap=True, color="#1565C0"),
        TextComponent(text=f"電話：{h['reg_voice']}", size="xs", margin="xs"),
        TextComponent(text=f"電話：{h['reg_human']}", size="xs", margin="xs"),
        TextComponent(text="📱 App：搜尋「雙和掛號」", size="xs", margin="xs"),
        SeparatorComponent(margin="md"),
        TextComponent(text="常見科別", weight="bold", size="sm", margin="md", color="#444444"),
        TextComponent(text=depts_text, size="xs", wrap=True, margin="sm", color="#333333"),
        SeparatorComponent(margin="md"),
        TextComponent(
            text="輸入「/掛號查詢 科別」查詢該科掛號資訊",
            size="xs", wrap=True, margin="sm", color="#555555"
        ),
    ]

    return FlexSendMessage(
        alt_text="雙和醫院資訊",
        contents=BubbleContainer(
            body=BoxComponent(layout="vertical", contents=contents, paddingAll="lg")
        )
    )


def build_appointment_card(dept):
    h = HOSPITAL
    today = datetime.now().strftime("%Y/%m/%d")

    # 判斷是否為支援的科別
    matched = next((d for d in h["depts"] if dept in d or d in dept), None)
    dept_display = matched or dept
    is_known = matched is not None
    unknown_note = "" if is_known else f"\n⚠️ 「{dept}」不在常見科別清單，請至網站確認是否有此科別。"

    contents = [
        TextComponent(text="🏥 掛號資訊", weight="bold", size="lg", color=h["color"]),
        SeparatorComponent(margin="md"),
        TextComponent(text=f"醫院：{h['short']}", size="sm", margin="md"),
        TextComponent(text=f"科別：{dept_display}", size="sm", margin="xs", weight="bold"),
        TextComponent(text=f"查詢日期：{today}", size="sm", margin="xs", color="#888888"),
        SeparatorComponent(margin="md"),
        TextComponent(text="📋 掛號步驟", weight="bold", size="sm", margin="md", color="#444444"),
        TextComponent(
            text=(
                "1️⃣ 前往官網或 App 選擇科別\n"
                "2️⃣ 選擇醫師與可掛時段\n"
                "3️⃣ 輸入健保卡號完成預約\n"
                "4️⃣ 看診當日帶健保卡插卡報到"
            ),
            size="xs", wrap=True, margin="sm", color="#333333"
        ),
        SeparatorComponent(margin="md"),
        TextComponent(text="📞 掛號方式", weight="bold", size="sm", margin="md", color="#444444"),
        TextComponent(text=f"🌐 {h['reg_web']}", size="xs", wrap=True, color="#1565C0", margin="sm"),
        TextComponent(text=f"📱 App：搜尋「雙和掛號」", size="xs", margin="xs"),
        TextComponent(text=f"☎ 語音：{h['reg_voice']}", size="xs", margin="xs"),
        TextComponent(text=f"☎ 人工：{h['reg_human']}", size="xs", margin="xs"),
        SeparatorComponent(margin="md"),
        TextComponent(text="⏰ 報到截止時間", weight="bold", size="xs", margin="md", color="#444444"),
        TextComponent(text=h["report_times"], size="xs", wrap=True, margin="sm", color="#555555"),
    ]

    if not is_known:
        contents.append(TextComponent(
            text=f"⚠️「{dept}」不在常見科別清單，請至網站確認是否有此科",
            size="xs", wrap=True, margin="md", color="#E65100"
        ))

    return FlexSendMessage(
        alt_text=f"雙和醫院 {dept_display} 掛號資訊",
        contents=BubbleContainer(
            body=BoxComponent(layout="vertical", contents=contents, paddingAll="lg")
        )
    )


def build_dept_menu():
    depts = HOSPITAL["depts"]
    dept_list = "\n".join(f"  /掛號查詢 {d}" for d in depts)
    return f"🏥 雙和醫院常見科別\n\n請輸入以下指令查詢：\n\n{dept_list}"


# ════════════════════════════════════════════════
#  工具函式
# ════════════════════════════════════════════════

def do_reply(reply_token, content):
    if isinstance(content, str):
        line_bot_api.reply_message(reply_token, TextSendMessage(text=content))
    elif content is not None:
        line_bot_api.reply_message(reply_token, content)


# ════════════════════════════════════════════════
#  健康檢查
# ════════════════════════════════════════════════

@app.route("/", methods=["GET"])
def health():
    return {
        "status":   "running",
        "steps":    step_data,
        "group_id": GROUP_ID,
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"[Bot] 啟動中，port {port}")
    app.run(host="0.0.0.0", port=port)
