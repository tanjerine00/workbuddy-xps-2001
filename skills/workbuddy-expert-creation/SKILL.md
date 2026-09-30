---
name: workbuddy-expert-creation
description: 在 Windows / WorkBuddy 本机按 expert-manager 规范创建或修改专家包（Agent 型 / Team 型）时必须知道的机器相关坑：Pillow 只在默认 venv、ImageGen 出图超 500KB 上限与遗留原图、PowerShell 工具不回显 stdout。当用户要求"创建专家 / 转成专家 / 修改专家包 / 打包专家"时使用。
agent_created: true
---

# WorkBuddy 专家包创建（Windows 本机实操）

`expert-manager` 是内置 skill，它给出的流程（init → 填内容 → 头像 → validate → register →
package）**是对的，照着走**。本 skill 只记录它没写、但在这台机器上一定会撞到的环境问题。

## 一、脚本与环境（先确认这三条）

| 项 | 值 |
|---|---|
| 专家根目录 | `%WORKBUDDY_CONFIG_DIR%\plugins\marketplaces\my-experts\plugins`（本机 = `C:\Users\zyx32\.workbuddy\...`） |
| 跑脚本的 Python | `C:\Users\zyx32\.workbuddy\binaries\python\versions\3.13.12\python.exe`（纯标准库，够用） |
| 处理图片的 Python | `C:\Users\zyx32\.workbuddy\binaries\python\envs\default\Scripts\python.exe`（**只有这里有 Pillow**） |

`init_expert.py --path` 硬校验必须等于专家根目录，传错直接报错退出，别试图改路径。
`register_expert.py` 从环境变量 `CODEBUDDY_SESSION_ID` 取会话 ID 写 `.created-by-session`；
在 Bash 工具里它是有的（`echo $CODEBUDDY_SESSION_ID` 可验），不用手动传 `--session-id`。

`marketplace.json` 是**多专家共存**的，注册脚本会 merge。本机已存在
`foresight-industry-investor`，注册新专家后要回读该文件确认老条目还在。

## 二、Bash 工具 PATH —— 已永久修复（2026-09-14）

曾经这台机器 Bash 工具的 `ls` / `dirname` / `find` 全部 `command not found`
（`find` 还会命中 Windows 自带的 `find.exe`，报"参数格式不正确"）。
根因：WorkBuddy 用 PortableGit 的 `bash.exe` 起 shell，却漏把它的 **`usr/bin`** 放进 PATH。
**已改用户级 PATH 修好**，细节见技能 `workbuddy-bash-path-fix`。

所以现在**可以直接用 unix 工具**，不必再在命令前 `export PATH=...`。
若哪天又见到 `dirname: command not found`，多半是 PortableGit 换了版本目录，
照 `workbuddy-bash-path-fix` 补一条即可（改完要重启 WorkBuddy）。

## 三、头像流程（最容易翻车的一步）

1. **ImageGen 规格**：`size="1024x1024"`，`output_dir` 指向专家包的 `avatars/`。
2. **产物超标**：1024×1024 PNG 约 **1.5 MB**，而规范要求 **≤500 KB**。必须缩。
   用默认 venv 的 Python：

   ```python
   from PIL import Image
   img = Image.open(src).convert("RGB").resize((512, 512), Image.LANCZOS)
   img.save(tmp, format="PNG", optimize=True)   # → 约 430 KB
   ```

   ⚠️ 系统 python（3.13.12）**没有 Pillow**，用它跑上面这段会 `ModuleNotFoundError`。
3. **重命名**为 plugin.json 里声明的 `avatars/expert.png`。
4. **清理遗留文件**：ImageGen 会在 `output_dir` 里留下一张带时间戳的原图
   （`Professional_cartoon_style_ill_<时间>.png`），**必须在 package 前删掉**，
   否则 zip 体积直接翻倍（本次实测 433 KB → 不删会到 1.6 MB+）。
   `package_expert.py` 只跳过 `.gitkeep`，不会自动忽略这类文件。
5. prompt 必须**从 Agent MD 的正文提取**（角色/能力/背景符号），不要用通用模板；
   `categoryId` 决定背景色调，见 `references/avatar-spec.md` 的对照表。

## 四、收尾自检清单

- [ ] `validate_expert.py <dir>` 输出 `✅ Expert package is valid!`
- [ ] `register_expert.py <dir>` 输出 `now registered and visible`
- [ ] 回读 `marketplace.json`，确认新条目存在**且旧专家条目未被覆盖**
- [ ] `avatars/` 里只有声明的那一张图，无时间戳残留
- [ ] `package_expert.py <dir> <output-dir>` 打包成功，zip 体积合理（单头像应在 450 KB 上下）

## 五、字段速查（易错项）

- `agentName` = `agents/` 下 MD 文件名（不含 `.md`），**必须带业务语义**，不能叫 `team-lead`。
- `tags` 恰好 3 个、`quickPrompts` 恰好 3 个，且 `defaultInitPrompt` 必须等于 `quickPrompts[0]`。
- `displayDescription.zh` 要 **40–50 字**（超出只是 warning，但注册门槛之外最好守规范）。
- Agent MD 的 frontmatter **不能出现 `tools:` 字段**（会被校验直接判错）。
- `name` / `agentName` / 目录名 / MD 文件名是唯一标识，**创建后不可改**，改名只能重建。
- `author` 字段规范里是可选的；不写不会导致校验或注册失败（不要为了填它编造邮箱）。
- `categoryId` 分类表里**没有教育/数学类目**，教学类专家归 `12-IndustryConsultant`。
