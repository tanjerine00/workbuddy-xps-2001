---
name: capswriter-local-asr
description: 在 Windows 上部署并验证 CapsWriter-Offline（本地离线语音转写 / 语音输入）——软件本体与模型分离下载、引擎选型、config 改动、命令行无 GUI 跑通转写、以及用 WebSocket 协议做无头批量基准测试。当用户要"本地语音转写 / 离线字幕 / 不要联网的录音转文字"，或要复刻/迁移/扩展这套工具时使用。
agent_created: true
---

# CapsWriter-Offline 本地转写部署与验证

## 这是什么 / 为什么选它

`HaujetZhao/CapsWriter-Offline`（GitHub，6.8k+ Star，持续更新）：
Windows 完全离线的语音输入 + 文件转写工具。**C/S 架构**，两个 exe 双击即用。

- 优点：完全离线、双击即用、能把音视频拖到 exe 上直接出 `.srt/.txt/.json`、带热词替换、
  可用 LLM 角色文件做润色（接 DeepSeek API = 本地转写 + 云端总结）。
- 缺点：**没有说话人分离**（SenseVoice/Paraformer/Qwen3-ASR 都不带）。要 `SPEAKER_01/02`
  得另搭 `funasr` + `cam++` 说话人模型。
- 仅保证 Windows 10/11 64 位。MacOS 因 `keyboard` 库不支持的缘故放弃了。

## 一、下载（关键：本体与模型分两个 Release）

**这一步和 Vosk 一样是"API 与模型分离"的坑**，别只下本体就以为完事。

```bash
GH="https://gh-proxy.com/https://github.com/HaujetZhao/CapsWriter-Offline/releases/download"

# ① 软件本体（~99MB），在 releases/latest
#    v2.6 资产：CapsWriter-Offline-20260531.zip（完整）/ CapsWriter-Offline-Client-*.zip（仅客户端）
get "$GH/v2.6/CapsWriter-Offline-20260531.zip" "CapsWriter-Offline.zip"

# ② 模型，在 releases/tag/models（不是 latest！）
get "$GH/models/Sensevoice-Small-ONNX.zip" "Sensevoice-Small-ONNX.zip"
```

先取精确字节数用于校验（比哈希更省事，且足够）：
```bash
curl -s "https://api.github.com/repos/HaujetZhao/CapsWriter-Offline/releases/latest" | \
  python -c "import sys,json;[print(a['name'],a['size']) for a in json.load(sys.stdin)['assets']]"
```
实测参考值：本体 104,162,430 B；`Sensevoice-Small-ONNX.zip` 433,798,984 B。
下载方法（镜像测速、低速熔断循环）见技能 `github-release-download-cn`。

### 该下哪个模型

| 引擎 | 精度 | 速度 | 格式 | 显卡加速 | 该下吗 |
|---|---|---|---|---|---|
| SenseVoice-Small | ★★★☆☆ | ★★★★★ | ONNX | ✅ | **轻量机首选**（约 414MB） |
| Paraformer | ★★★☆☆ | ★★★★★ | ONNX | ❌ | 不建议，**还要额外挂标点模型** |
| Fun-ASR-Nano | ★★★★☆ | ★★★★☆ | ONNX+GGUF | ✅ | 精度更好，约 796MB |
| Qwen3-ASR-1.7B | ★★★★★ | ★★★☆☆ | ONNX+GGUF | ✅ | 独显才值得，q5_k 约 1.8GB |

- **只要 SenseVoice 就不用下 `Punct-CT-Transformer`（259MB）**——它自带标点。
  只有 Paraformer 需要外挂标点，所以 Paraformer 不划算，作者自己说"仅作纪念性保留"。
- Qwen3-ASR 不带时间戳，要出准确 srt 还得再挂 `Qwen3-ForcedAligner`（597MB）。轻量机别碰。
- 国内还有个百度网盘备用源（README 里有），GitHub 慢时可以试。

## 二、解压与目录结构

```bash
python -c "
import zipfile
zipfile.ZipFile('CapsWriter-Offline.zip').extractall('.')
# 注意：模型要解到  models/<引擎名>/  下面，压缩包内已带 Sensevoice-Small-ONNX/ 这一层
zipfile.ZipFile('Sensevoice-Small-ONNX.zip').extractall('CapsWriter-Offline/models/SenseVoice-Small')
"
```

正确结构（对不上就是"模型文件检查不通过"）：
```
CapsWriter-Offline/
├── start_server.exe / start_client.exe
├── config_server.py / config_client.py     ← 改这里
├── models/SenseVoice-Small/Sensevoice-Small-ONNX/
│      ├── SenseVoice-Encoder.fp16.onnx   (447MB)
│      ├── SenseVoice-CTC.fp16.onnx       (25MB)
│      └── tokenizer.bpe.model
└── logs/server_latest.log、client_latest.log
```

## 三、必改的两处配置

**`config_server.py`** —— 默认引擎是跑不动大模型就会崩的 `qwen_asr`：
```python
model_type = 'sensevoice'   # 可选 'qwen_asr' / 'fun_asr_nano' / 'sensevoice' / 'paraformer'
```
轻量机建议顺手把 `SenseVoiceArgs.onnx_provider = 'DML'` 试一下（Intel/AMD 集显走 DirectML 加速），
不划算再改回 `'CPU'`。

**`config_client.py`**：
```python
file_save_merge = True      # 默认 False。打开会多出一份 *.merge.txt（整段不切行长文）
                            # 「录音纪要」式的阅读体验靠它，*.txt 是按标点逐行切开的
file_seg_duration = 60      # 内存紧张（8GB）就调到 30
llm_enabled = True          # 润色功能，需在 LLM/ 配角色文件和 API key
```

依赖检查（不用装）：VC++ 运行库（`msvcp140.dll` 在 `C:\Windows\System32`）+ `ffmpeg` 在 **PATH** 上。
程序用 `shutil.which('ffmpeg')` 找，不在 PATH 就在根目录放一份 `ffmpeg.exe`。

## 四、跑起来

**GUI 路径（用户实际用法）**：
```
1. 双击 start_server.exe   → 加载模型约 7~10 秒，缩到托盘
2. 双击 start_client.exe   → 监听 CapsLock / 鼠标侧键 X2，按住说话松开上屏
   或：把音频/视频拖到 start_client.exe 图标上 → 同目录生成 .srt/.txt/.merge.txt/.json
```

**命令行路径（关键发现，无 GUI 也能跑官方流程）**：
`core/client/app.py` 里有 `files = [Path(f) for f in sys.argv[1:] if os.path.exists(f)]`
—— **客户端 exe 直接支持命令行传文件**：
```bash
./start_client.exe "D:\某录音.mp3"
```
跑完会停在 `input('\n按回车退出\n')`；如果 stdin 被重定向会抛 `EOFError`，**无害**，结果文件已写好。

> **不要用脚本/后台任务去替用户起 `start_server.exe`。** 两个原因：
> 1. 它在端口冲突等错误路径上会调 `input("\n按回车键退出...")`，非交互环境下直接
>    `EOFError` → `Failed to execute script` 崩掉，还会在控制台留下难看的完整 traceback。
> 2. 它是 console 子系统程序，从脚本启动会**在用户桌面上弹出一个控制台窗口**，
>    用户会以为是自己开的。
>
> 正确分工：**脚本只负责诊断和清理（`netstat` / `tasklist` / `taskkill`），
> 让用户自己双击** `start_server.exe`。这样托盘图标、窗口归属、stdin 都是对的。
>
> **例外（实测可行）**：用户自己双击的 `.cmd` 里，用
> `subprocess.Popen([server_exe], cwd=APP_DIR, creationflags=CREATE_NEW_CONSOLE)`
> 起服务端是安全的 —— 它有独立的真实控制台，stdin 不会是重定向的管道，所以不会 EOFError。
> 之后用 `netstat` 轮询直到端口 LISTENING（本机 CPU 冷启动约 17s）再发任务。
> 真正要避免的只有"后台任务 / stdin 被重定向"这一种启动方式。
> 代价：桌面上会多出一个服务端控制台窗口，脚本结束它也不关（留着给下一次用），
> 要在结尾打印一句"服务端已保留，关掉那个黑窗口即退出"。
>
> ⚠️ **但"脚本起"有个真实边界（实测）**：从**智能体自己的 shell** 里拉起的实例，
> 会在会话 / 进程树回收时被 `TerminateProcess` 干掉 —— 日志里**没有任何退出记录**，只留 `TIME_WAIT`，
> 极易误判成"程序崩了"。加 `CREATE_NEW_PROCESS_GROUP` 也没用。
> 用户自己双击（父进程是 Explorer）不受影响。
> → 所以脚本里"顺手起服务端"只能当作**当次任务能用**，不要向用户承诺它会长期存活。

## 五、无头基准测试（不走 GUI）

要批量测、算准确率、做对比时，直接对接它的 WebSocket 协议。

**协议**（`core/protocol.py`）：服务端 `websockets.serve(handler, addr, port, subprotocols=["binary"], max_size=None)`，
地址 `ws://127.0.0.1:6016`，文本帧 JSON。

客户端 → 服务端 `AudioMessage`：
```python
{"task_id": str, "source": "file", "data": base64(音频),
 "is_final": bool, "time_start": float,
 "seg_duration": 60.0, "seg_overlap": 4.0, "context": "", "language": "auto"}
```
- **`data` 是 `base64` 的 float32 / 16kHz / 单声道 裸流**（不是 int16！每样本 4 字节）。
  用 `ffmpeg -v error -i IN -f f32le -ac 1 -ar 16000 -` 流式产出。
- 分块大小 = `16000 * 4 * 60`（一分钟）。
- 最后必须再发一条 `is_final=True` 的空 `data` 消息。

服务端 → 客户端 `RecognitionMessage`：
```python
{"task_id", "is_final", "duration", "time_start", "time_submit", "time_complete",
 "text", "text_accu", "tokens": [...], "timestamps": [...]}
```
- **`text_accu` 是去重后的精确拼接（用于字幕），`text` 是简单拼接。做评测用 `text_accu`。**
- `tokens` + `timestamps` 是字级时间戳，直接能生成 srt。
- 初始 `deps`：`pip install websockets`（任意 3.13 解释器都行，服务端不依赖客户端的环境）。

参考实现：`_test/test_client.py`（本项目里已写好，含 ffmpeg 流式发送 + 收结果 + 实时倍率统计）。
配套 `_test/eval_cer.py` 算字错误率（编辑距离）并由时间戳生成 SRT。

## 六、造测试音频（沙箱里 TTS 只能用这条路）

**PowerShell 的 SAPI 走不通**（`New-Object -ComObject` 和 `Add-Type` 都被沙箱拒绝），改用：
```bash
pip install edge-tts
python -c "
import asyncio, edge_tts
async def go():
    c = edge_tts.Communicate('要读的中文文本', 'zh-CN-XiaoxiaoNeural')
    await c.save('test.mp3')
asyncio.run(go())
"
ffmpeg -y -v error -i test.mp3 -ar 16000 -ac 1 -c:a pcm_s16le test.wav   # 需要的话转 16k wav
```
真人语音测试素材（国内直连快，不用翻墙）：
```
https://isv-data.oss-cn-hangzhou.aliyuncs.com/ics/MaaS/ASR/test_audio/asr_example_zh.wav
```
内容是"欢迎大家来体验达摩院推出的语音识别模型"，5.55s，16k/mono/16bit，适合当 ground truth 基准。

## 七、实测性能参考（供预期管理）

机器：i7-8550U（2017 低压 U，4C8T）/ 8GB / Intel UHD 620，**纯 CPU**，SenseVoice-Small：

| 音频 | 处理耗时 | 实时倍率 |
|---|---|---|
| 5.55s 真人 | 3.51s（含连接开销） | 1.58x |
| 8.11s | 1.85s | 4.38x |
| 57.29s | 5.66s（官方客户端） | **10.1x** |
| 57.29s，20s 分段 | 6.48s | 8.84x |

- 模型加载 6.83s（一次性），能力清单 `ASR / PUNC / HOTWORDS / TIMESTAMPS`。
- 字错误率 **0.40%**（247 字长段落，唯一错误是漏了一个"是"）。
- 经验公式：这类机器上 **1 小时录音 ≈ 6 分钟出稿**。分段（20~30s）比单段略快，标点完整度也更好。

## 七·B、语言切换（中文 / 英文，不用换模型）

> ⚠️ **2026-09-30 用户决定：本机只保留中文单功能。** 语言切换器（`切换语言.cmd`/`switch_lang.py`）
> 和按语言的独立入口（`转中文/英文文件.cmd`/`transcribe_file.py`）**已全部删除**，
> `config_client.py` 的 `language` 定死 `'chinese'`。本节知识保留，恢复英文只需把 language 改回
> `'auto'` 或 `'english'`（并重启客户端）。**教训：改完 language 配置必须回读确认**——
> 当时英语验证完忘了恢复，配置在 `'english'` 上挂了十天，期间中文听写会出乱码。

SenseVoice **本身就是多语言模型**，英文开箱即用，不需要另下模型。

- **开关在客户端**：`config_client.py` 的 `language = 'auto'`（服务端 `config_server.py` 没有这项）。
  支持范围见 `core/server/engines/language.py` 的 LANGUAGE_MAP，SenseVoice 实际只支持
  `auto / chinese / english / japanese / cantonese / korean`（对应 lid `auto zh en ja ko yue`）；
  其余 20+ 语言只有 Qwen3-ASR 引擎支持。
- 语言由客户端随每次请求经 `core/protocol.py` 的 `language` 字段发出（服务端 `ws_recv.py` 取用）。
  → **改完只需重启 `start_client.exe`，服务端不用重启。**
- ★ **显式指定语言比 `auto` 快约 2 倍**（重复跑排除冷启动后仍成立）：
  英文长段 50.69s → `auto` 15.34s / `english` **7.02s**；中文长段 57.29s → `auto` 18.93s /
  `chinese` **10.70s**。输出文本完全一致。→ 纯语种素材一律显式指定。
- 英文实测（TTS 合成）：短句 19 词 **WER 0%**；长段 128 词 **WER 1.56%**（只漏 2 个词）。
  ITN 有效：`twenty twenty five`→`2025`、`eighteen percent`→`18%`、`eight hundred`→`800`。
- ⚠️ **中英混说不可用**：SenseVoice 一次只处理一种语言，混说会把中文整段丢掉
  （实测"这个 feature 我们下个 sprint 再做" → `Feature Sprint priority bug`）。

**给 Windows 用户做切换入口**：`切换语言.cmd`（纯 ASCII + CRLF）+ `switch_lang.py`（中文 UI）。
Python 侧用正则幂等替换 `^\s*language\s*=\s*'[^']*'` 并**回读校验**，拒绝 LANGUAGE_MAP 之外的值。

**★ 更好的办法：按语言做「独立入口」，别去切配置。**（2026-09-30 已按用户要求删除，思路保留）
语言是**每条请求**的一个字段，不是全局状态 —— 所以自己写一个客户端，在消息里直接写死
`"language": "english"`，就得到一个"拖上去就按英文转"的入口，**中文听写的配置完全不受影响**，
省掉"切过去 → 重启客户端 → 用完再切回来"这一整套动作。参考实现 `transcribe_file.py`：

- 输出 `<原名>.<语言短码>.txt`（英文 = `.en.txt`），落在原文件同目录；
  官方客户端出的是 `<原名>.txt/.srt/.json/.merge.txt`，两者**不互相覆盖**。
- 独立入口只出纯文本，没有字幕时间轴；要 srt 还是得走官方 `start_client.exe`。
- 一次拖多个文件就循环处理，每个各出一份。

## 八、横向对比时别踩的坑

- **精度高 ≠ 体验追平**。本地拿 99.6%，第三方实测讯飞听见 96.8%、夸克听记 91.5%，
  但云端多了**说话人分离 / 一键摘要 / 导出 Word·PDF**。差距在整合度，不在识别率。
- **干净 TTS 音频的高分不能外推到真实会议录音**（回声、串音、方言会明显掉点）。
  评测时至少要有 1 段真人素材，别只用 TTS。
- 输出目录：结果生成在**原文件同目录**、同名不同后缀，不会单独建文件夹。
- **★ 算 WER 前必须把标点从词边界剥离**（`token.strip('.')` 之类，保留词内小数点与百分号）。
  否则 `meeting.` 与 `meeting` 会被判成两个词：实测同一份结果，未剥离时 WER 虚高到 6.25%，
  剥离后是真实的 1.56% —— 8 处"错误"里 6 处其实只是标点位置。
- **★ 别把 AI 摘要当事实依据**：云端工具的摘要会把 ASR 误识别**固化成结论**
  （实测夸克把误识别的"玻璃"写成了一整条"玻璃包装材料需防破碎"的风险论述，
  把乱码"共同研究汽车的"写成"汽车级应用规范"）。摘要越通顺，错误越难发现。
  留档/写报告必须回逐字稿核对。

## 九、常见问题速查

### 两个报错含义相反，最容易看反（实测踩过）

| 窗口显示 | 真实含义 | 该做什么 |
|---|---|---|
| 服务端：`端口冲突：0.0.0.0:6016 已被占用` | **已经有一个服务端在正常跑了** | **直接去拖文件**，把报错窗口关掉 |
| 客户端：`无法连接 / Connection refused` | 确实一个都没开 | 双击 `start_server.exe` |

**服务端只需要开一个。** 重复双击不会更快，只会攒下一堆绑不上端口、白吃内存的空壳进程
（实测重复 3 次攒了 9 个进程、几百 MB）。

**进程结构**：`1 个健康实例 = 3 个同名 start_server.exe 进程`
（主进程 + pyinstaller 引导 + 识别子进程）。
所以 `tasklist | grep -c start_server` 得到 **3 是正常的**，得到 9 就是开了 3 个实例。

### `opening handshake failed` 那段红色 traceback —— 无害，别慌

```
websockets.exceptions.InvalidMessage: did not receive a valid HTTP request
EOFError: line without CRLF
EOFError: connection closed while reading HTTP request line
```

含义：有东西连上了 6016 但没发合法的 HTTP/WebSocket 握手（典型是**只发了一个裸换行符**就断开），
websockets 拒绝**这一次连接**，服务端继续正常工作、不影响任何转写。

**判断无害的方法**：看 `logs/server_latest.log` 末尾，如果紧接着有正常任务记录即可：
```
10:58:58 INFO [pipeline.py:162] 任务完成: 25f25d77, 时长=8.11s, 耗时=1.446s, RTF=0.178
```
只有当它**大量反复刷屏**时才要管（说明有程序在持续扫端口）。

> **给自动化脚本的教训**：不要用裸 TCP 写入来探测服务是否就绪，例如
> `(echo > /dev/tcp/127.0.0.1/6016)` —— 这会往端口写一个裸 `\n`，**正好触发上面这段 traceback**，
> 在用户屏幕上显示出一屏吓人的红字，让人误判成服务崩了（真实发生过）。
> **正确做法**：`netstat -ano | grep "0.0.0.0:6016.*LISTENING"` 判断监听，不发起连接、零副作用。

### 其他

| 现象 | 原因 |
|---|---|
| 拖文件没反应 | `start_server.exe` 没开，或**文件拖进了窗口而不是拖到 exe 图标上** |
| 双击 `start_client.exe` 后按 CapsLock 有用、拖文件没用 | 模式弄反了。不带文件参数启动进的是**麦克风听写模式**（`app.py:127`，`sys.argv[1:]` 里没有存在的文件就走 `MicRunner`）。文件模式**只能拖到图标上** |
| 传了个不存在的路径，却"没报错" | 同上：路径不存在 → 过滤后为空 → **静默退化成麦克风模式** |
| 日志无 `ffmpeg found` | ffmpeg 不在 PATH |
| 大文件转录卡 / 内存顶不住 | `file_seg_duration` 从 60 调到 30 |
| "模型文件检查通过" 没出现 | 模型解压层级错了，看第二节的目录结构 |
| 客户端 EOFError | stdin 被重定向，正常现象，结果已写好 |

### 彻底重来

```bash
taskkill /F /IM start_server.exe    # 两个命令要分开跑
taskkill /F /IM start_client.exe    # 报"没有找到进程"是正常的
netstat -ano | grep 6016            # 无输出 = 端口已释放
```

日志：`logs/server_latest.log`、`logs/client_latest.log`（`log_level = 'DEBUG'` 时很详细）。
**注意这两个文件是跨次追加的，不是每次清空** —— 排查时要看文件**末尾**的时间戳，
否则会被前面的历史 `端口冲突` 记录误导。另外 **websockets 的 traceback 只打到控制台**，
不写进日志文件，所以在日志里搜不到它。
