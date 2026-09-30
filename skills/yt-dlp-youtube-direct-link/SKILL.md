---
name: yt-dlp-youtube-direct-link
description: 用 yt-dlp 提取 YouTube 视频的真实直链并交给 IDM / 外部下载器使用，含 UA 绑定、IP 绑定、6 小时过期、音视频分离等已知坑与验证方法，以及「分开的视频和音频如何合并」的编码/容器决策规则与一键脚本。当用户问「yt-dlp 能不能给出下载链接 / 直链 / 给 IDM 用 / -g 怎么用 / 下载下来没声音 / 音视频怎么合并」时使用。
agent_created: true
---

# yt-dlp 取 YouTube 直链给 IDM 用

## 一句话结论

**能取到，IDM 也确实能下**（实测 HTTP 206 + 真实 MP4 数据），但必须同时满足
「UA 一致 + 代理一致 + 立刻下载」，且高清流必然是**两条链接**、需要事后合并。

## 命令

```bash
# 只打印链接，不下载
yt-dlp --proxy socks5://127.0.0.1:7890 \
       --user-agent "<固定UA>" --no-playlist \
       -f "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b" \
       -g "https://www.youtube.com/watch?v=XXXX"
```

- `-g` / `--get-url` 仍然有效（**新版 `--help` 里不列出，但能用**，实测过）。
  `--print urls` 是等价新写法；`-j` 输出 JSON，直链在 `formats[].url`。
- 必须显式 `--user-agent`，这样才知道要往 IDM 里填什么 UA。
- 有 `--no-playlist` 才不会连带整个列表。

## 四个必踩的坑（都实测确认过）

| 坑 | 机制 | 对策 |
| --- | --- | --- |
| **403 Forbidden** | 直链绑定取链时的 User-Agent | IDM 里把 UA 改成**完全相同**的字符串 |
| **下完没有声音** | 现代 YouTube **没有** muxed 单文件格式（itag 18/22 已消失），视频流、音频流是两条独立 URL | 两条都下，再 `ffmpeg -i video.mp4 -i audio.m4a -c copy out.mp4` |
| **链接很快失效** | URL 带 `expire=<unix秒>`，约 **6 小时** | 取到就立刻开始下载 |
| **换网络即失效** | URL 带 `ip=<取链时的出口IP>` | 下载器必须走同一个代理，中途别换节点 |

用 `echo "$URL" | grep -o 'expire=[0-9]*'` 可以核对失效时刻。

## 快速自检（判断某条直链给普通 HTTP 客户端能不能用）

```bash
curl -s --max-time 60 -x socks5h://127.0.0.1:7890 -r 0-2000000 \
  -H "User-Agent: <同一个UA>" -o t.bin \
  -w "HTTP %{http_code}  %{content_type}  %{size_download} bytes\n" "$VURL"
# 期望 HTTP 206 + video/mp4 + 真实字节数；文件头应为 `....ftypdash`
```

## IDM 侧设置（一次性）

`选项 → 连接`：

| 项目 | 值 |
| --- | --- |
| 代理/Socks | 地址 `127.0.0.1`、端口按实测（常见 7890）、类型 **SOCKS5** |
| 用户代理 | 粘贴与 `--user-agent` 完全一致的那串 |

注意：**IDM 的 UA 设置在「选项 → 连接」里，GUI 是有的**；改完要重启 IDM。
另外 IDM 只有 HTTP 代理才常见，SOCKS5 需要在新版里显式选类型。

## 更好的替代方案（多数情况其实不该绕 IDM）

IDM 的核心价值是多线程，而 yt-dlp 自己就能多线程，还自动带对 UA/Range 并合并：

```bash
yt-dlp --proxy socks5://127.0.0.1:7890 -N 16 \
       -f "bv*[height<=1080]+ba/b" --merge-output-format mp4 "URL"
```

**只有用户明确想用 IDM 的队列 / 断点续传界面时才走直链方案。**

## 合并分开的音视频（已验证的决策规则）

**先判断要不要合**——别凭扩展名猜，用 ffprobe 看流：

```bash
ffprobe -v error -show_entries stream=codec_type,codec_name -of csv=p=0 "文件"
# 同时有 video / audio 两行 → 已经合好了，什么都不用做
# 只有 video 一行 → 才需要合
```

**决策按「编码」而不是「扩展名」**，容器能否装下取决于流编码：

| 视频编码 | 音频编码 | 落地方案 |
| --- | --- | --- |
| h264 / hevc / av1 / mpeg4 | aac / mp3 / ac3 / eac3 | 直接 `-c copy` 封进 **MP4**（无损、秒级） |
| 上面这些 | opus / vorbis / flac 等 | `-c:v copy -c:a aac` 进 MP4（只重编音频） |
| vp8 / vp9 / 其他 MP4 不收的 | 任意 | `-c copy` 封进 **MKV**（最省事，VLC/PotPlayer/现代浏览器都能放） |
| 一定要在手机/电视/微信上放 | — | `-c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -c:a aac -b:a 192k` 输出 MP4 |

必备要点：

- `-c copy` 只是换封装，**不重编码、不损画质、几秒完成**；能 copy 就别重编码。
- 加 `-map 0:v:0 -map 1:a:0`，避免源文件自带静音轨时选错流。
- **输出文件绝不能和任一输入同名**，否则 ffmpeg 报
  `FFmpeg cannot edit existing files in-place`。
- 合完必须回头验一遍产物里有没有 `audio` 流——这是「没声音」的唯一可靠判据。

本机已装好一键脚本（在 `~` 的 `bin` 目录，与 ffmpeg 同级）：

```cmd
yt-merge.cmd <video> <audio> [output] [-h264]
```

自动读编码、选容器、纠正参数顺序、验证音轨。四条路径均已实测通过：
h264+aac→MP4 无损；参数反传→自动交换；vp9+opus→自动改存 MKV；`-h264`→重编码 MP4。

## 排查清单

1. YouTube 直连不通 → 必须有代理，先确认本地代理端口与协议
   （`/dev/tcp` 扫端口 + 分别用 `http://` 与 `socks5h://` 试通）。
2. `Requested format is not available` → 说明该视频没有 muxed 单文件格式，属正常；
   用 `-F` 看实际列表，改用 `bv*+ba` 组合。
3. 链接能取但 IDM 报 403 → 99% 是 UA 不一致或代理出口 IP 变了。
4. 下完只有画面 → 忘下音频那条，或忘了合并；用 `yt-merge.cmd` 或
   `ffmpeg -i v -i a -c copy -map 0:v:0 -map 1:a:0 out.mp4`。

## 写 Windows 批处理工具时的两个坑（本机实测）

1. **参数解析**：想跳过前两个必填参数再遍历剩余参数时，要**先连续 `shift` 两次**再进循环。
   若写成「先进循环再 shift」，循环第一轮取到的其实还是旧的 `%2`，
   典型症状是输出文件名被错误地设成第二个输入参数，报
   `FFmpeg cannot edit existing files in-place`。
2. **变量展开时机**：`for %%I in ("%VIN%") do set "VBASE=%%~nI"` 与随后的
   `set "OUT=%VBASE%.merged.mp4"` 若处在**同一个括号块内**，`%VBASE%` 会在解析期展开成空，
   输出文件名变成 `.merged.mp4`。同块内必须用 `!VBASE!`（配合 `enabledelayedexpansion`）。

另外：本机 PowerShell 工具在调用 `.cmd` 时**捕获不到 stdout**（返回空），
用 Bash 直接执行 `./xxx.cmd args` 可以正常看到输出；测试批处理优先走 Bash。
Git Bash 给 `.cmd` 传参时会把 `=` 当分隔符拆开（URL 里的 `?v=` 会被拆成两个参数），
测试含 `=` 的参数要用包装脚本或换 PowerShell 调用。

