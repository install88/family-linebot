# 家庭步數 1.0.2 修正與發布

## 行為
- 計步由 StepService 單一負責，畫面只讀取狀態。優先使用手機提供的 wake-up step counter，沒有時回退到原本來源。
- 以感測事件的發生時間換算台灣日期，不以回呼抵達時間分日。
- 上傳使用不可變的日期／步數快照；拿不到今日有效資料時等待更新，不上傳昨日數值。
- 保存上一筆硬體值，保留正常跨日的第一批差額；重開機／來源切換／無法觀測完整日期時，保留可確認的步數並標示「部分累計」。升級前的今日計數保留為部分累計，不重建小米內建數字。
- 新格式含 step_date、sensor_at、partial、device_id、app_version、observation_id。後端驗證日期，依來源時間拒絕較舊的回傳，完整快照與品質先一起存入既有 config 表，再寫 steps 歷史。重試具有去重與完成標記恢復處理。
- 新後端以 protocol_version=2 回覆。App 只有確認後端支援後才上傳 waiting 狀態，舊後端期間等待狀態不會被誤寫成 0 步。
- LINE 明確顯示部分累計與等待更新，舊手機格式繼續接受。

## 發布順序
1. 先發布這個分支的後端，再依賴跨日日期驗證的完整保證。App 在午夜前送出的請求可能午夜後才抵達，舊後端只看接收日，不能提供這個保證。
2. 目前方案以單一 Python worker 為部署前提，現代上傳以程序內鎖序列化；增加多個 worker／副本前需將排序與去重改成 DB transaction/RPC。
3. 無需 DB schema migration。新增的 config key 為 step_status:<暱稱>，保存最新完整觀測與品質；保留既有 rows。
4. 安裝桌面「家庭步數-1.0.2-跨日修正版.apk」。同一簽章、versionCode 3，直接覆蓋可保留設定。
5. 開啟 App，確認服務與計步持續運作。鎖屏走路、重新開啟、實際上傳後再查 DB。

## 驗證
- Android 純計步測試 15 個：午夜、延遲事件、順序、跨日重開機、硬體重設、缺日、來源切換、舊版狀態。
- Python unittest 16 個：日期驗證、等待／部分狀態、DB 錯誤、去重、倒序上傳、metadata 失敗與恢復、舊手機相容。
- Android instrumentation：migration／rebase／activity。
- Emulator：精確鬧鐘允許與拒絕兩種情境。
- assembleDebug、assembleDebugAndroidTest、lintDebug：通過，lint 無 Error；簽章與 1.0.1 相同。
- 實機升級與新資料上傳：已確認；新版鎖屏走路測試 49 → 81 步（增加 32），未重開 App、服務 PID 不變。
- 真實整夜跨日執行尚待發生，不將程式測試當作實際跨夜的證明。

## 歷史資料與還原
不刪除、不回填 11/18 已寫入的舊 4,117。舊錯誤紀錄仍可能影響既有歷史最大值摘要，需在有可靠依據與明確授權後另行處理。
Android 原始碼及升級前手機偏好設定備份：C:/Users/insta/step-counter-app/backups/day-rollover-20261118-221113。
後端可回復本次 commit；由於新版 App 在舊後端會跳過 waiting 請求，回復相容，但會失去伺服器日期檢查。APK 降版需 Android 的明確降版流程，勿為降版先解除安裝而遺失資料。
