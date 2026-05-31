# zoffline 本地使用说明

## 当前已完成能力

1. Intervals.icu
- 可在启动 Zwift 前自动拉取当天 workout
- 骑完保存后可自动上传活动回 Intervals.icu
- 若活动匹配当天同步的 workout，会自动带 paired_event_id 并 mark-done

2. Strava
- 已支持 OAuth 授权
- 骑完保存后可自动上传 FIT 到 Strava

3. TrainingPeaks
- 已支持手工桥接模式
- 将 TrainingPeaks 导出的 `.zwo` 文件放入本地目录后，可一键导入 Zwift custom workouts
- 当前不支持官方 API 自动拉取/自动上传，因为需要 TrainingPeaks partner access

4. Provider 互斥模式
- Intervals.icu 和 TrainingPeaks 不会再同时出现在 customworkouts
- 谁最后同步，谁就是当前 active provider

## 启动方式

推荐使用非特权端口本地运行：

```bash
cd /Users/sumulige/Documents/Antigravity/zwift-offline
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
env \
  ZOFFLINE_CDN_PORT=18080 \
  ZOFFLINE_TCP_PORT=13025 \
  ZOFFLINE_UDP_PORT=13024 \
  ZOFFLINE_API_PORT=18443 \
  ZOFFLINE_API_USE_CERT=false \
  ./.venv/bin/python standalone.py
```

打开页面：
- 主页: `http://127.0.0.1:18443/user/zoffline/`
- Settings: `http://127.0.0.1:18443/settings/zoffline/`
- Intervals: `http://127.0.0.1:18443/intervals/zoffline/`
- Strava: `http://127.0.0.1:18443/strava/zoffline/`
- TrainingPeaks: `http://127.0.0.1:18443/trainingpeaks/zoffline/`

## Intervals.icu 设置

在 `Settings -> Intervals` 中填写：
- Athlete ID
- API key

然后你可以：
- 点击 `Sync today's workout` 手动同步
- 或点击 `Start Zwift` 时自动同步

同步成功后：
- workout 会写入 `storage/<player_id>/customworkouts/`
- metadata 会写入 provider state 文件

## Strava 设置

在 `Settings -> Strava` 中填写：
- Client ID
- Client Secret

然后点击 `Authorize` 完成 OAuth。

授权成功后，`storage/<player_id>/strava_token.txt` 会存在。

之后每次活动保存时会自动上传到 Strava。

## TrainingPeaks 手工桥接

1. 在 TrainingPeaks 中导出 workout 为 `.zwo`
2. 把 `.zwo` 文件放到本地某个目录，例如：
   - `/Users/yourname/TrainingPeaksExports`
3. 打开 `TrainingPeaks` 页面
4. 在 `Bridge folder` 输入该目录
5. 点击 `Save bridge folder`
6. 点击 `Import workouts`

导入后的文件会写到：
- `storage/<player_id>/customworkouts/trainingpeaks-*.zwo`

## Provider 切换规则

- 点击 `Intervals -> Sync today's workout`
  - active provider 切到 `intervals-icu`
  - TrainingPeaks workouts 会被清掉

- 点击 `TrainingPeaks -> Import workouts`
  - active provider 切到 `trainingpeaks`
  - Intervals workouts 会被清掉

- 点击 `Start Zwift` 时，只会同步当前 active provider

## 关键文件

- Intervals provider: `intervals_workouts.py`
- TrainingPeaks bridge/provider scaffold: `trainingpeaks_workouts.py`
- Provider state: `workout_state.py`
- 主服务: `zwift_offline.py`

## Git 提交

本次功能提交：
- commit: `f0418ee`
- message: `feat: add workout provider sync integrations`
