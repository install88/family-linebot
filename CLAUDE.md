# 家庭 LINE Bot 專案說明

## 架構
- **bot.py** — Flask LINE Bot，部署在 Railway，GitHub push 自動部署
- **Android App** — 步數計數器，源碼在 `../step-counter-app/`，build 在 `C:/Users/insta/step-counter-app/`
- **Supabase** — 免費 PostgreSQL，存步數/行程/GROUP_ID

## 部署
- Railway 自動部署：push 到 GitHub main branch 即可
- Server URL: `https://web-production-67a7.up.railway.app`
- APK 輸出：`C:/Users/insta/Desktop/家庭步數.apk`
- Build APK：`cd C:/Users/insta/step-counter-app && JAVA_HOME="C:/Program Files/Android/Android Studio/jbr" ./gradlew assembleDebug`

## 憑證（全部 hardcode 在 bot.py，Railway env var 不管用）
- LINE token/secret：bot.py 第 30-31 行
- Supabase URL: `https://oqydathbpfnigrhxgplb.supabase.co`
- Supabase Key: `sb_publishable_Hw2ErHE0YQD3S14JB5pXiQ_pHQFNmWc`

## Supabase Tables
```sql
steps    -- name, steps, date(YYYY-MM-DD), time(HH:MM)
events   -- title, date, time, end_time, recurring, weekday, remind_hours, last_notified
config   -- key(PK), value  ← 存 GROUP_ID
```

## LINE 群組
- 家人群組 GROUP_ID: `Ce946ad66c42c253b276872cd75efd56a` （提醒推播目標）
- 測試群組：另一個群組，只有自己
- GROUP_ID 只在為空時才會設定，不會被覆蓋

## 行程提醒
- cron-job.org 每 30 分鐘打 `/check-reminders`
- 每天只提醒一次（last_notified 機制）
- 預設提前 8 小時提醒，可用「提前N小時」覆蓋
- 單次行程：過了事件時間自動刪除

## Android App 邏輯
- TYPE_STEP_COUNTER 感測器（累計步數，需計算差值）
- 每天以第一筆感測器值為基準（initialSteps）
- AlarmManager.setExactAndAllowWhileIdle 每 30 分鐘上傳
- 啟動後 5 秒立即上傳第一次
- 需設定電池「無限制」才能穩定背景執行
- SharedPreferences 存: server_url, nickname, is_running, today_steps, initial_steps, saved_date, last_upload

## 指令
- `/步數` — 今日所有人最新步數
- `/步數紀錄 [name] [日期/N天/日期範圍]`
- `/行程` — 查詢行程列表
- `/行程 MMDD HH:MM [endtime] 標題 [提前N小時]`
- `/行程 每週X HH:MM [endtime] 標題 [提前N小時]`
- `/行程 刪除 ID`
- 不認識的訊息不回覆
