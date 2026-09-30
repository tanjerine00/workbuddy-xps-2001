---
name: workbuddy-bash-path-fix
description: 修复 WorkBuddy / CodeBuddy 的 Bash 工具在 Windows 本机报 `dirname: command not found` / `ls: command not found`（连带 shell-runtime-bash-env.sh line 3 报错、`cd: null directory`、管道全废）的问题。2026-09-14 复核后推翻旧结论：真正的根因是**子 bash 拿到的是 WorkBuddy 启动时刻的 PATH 旧快照**，改注册表在会话内无效；正确修法是在 BASH_ENV 指向的 shim 顶部插一段纯 bash 的自愈补丁（无需重启）。含决定性诊断手法、附带发现（删除守卫被静默关闭）、以及"别再走"的弯路清单。
agent_created: true
---

# WorkBuddy Bash 工具 PATH 修复（Windows）

## 一句话结论

**不要在注册表 PATH 上努力。** 在 `BASH_ENV` 指向的 shim 顶部插一段纯 bash 的 PATH 自愈补丁。

原因：WorkBuddy 用 **PortableGit 的 `bash.exe`** 起 shell，但它传给子进程的是
**启动时刻的 PATH 快照**，注册表里新增的 PATH 项在当前会话里读不到（已实测证明）。
而 PATH 里一旦缺 msys 的 `usr/bin`，shim 第 3 行的 `dirname` 就找不到，
于是**后面两个 bootstrap 被 `||` 短路静默跳过**——注意：`|` 短路造成的失败
**不会有任何报错**，你只会看到 unix 命令全没了。

## 症状

```
...\cli\vendor\shim\shell-runtime-bash-env.sh: line 3: dirname: command not found
...\cli\vendor\shim\shell-runtime-bash-env.sh: line 3: cd: null directory
...\PortableGit\versions\<ver>\bin\bash.exe: line 1: ls: command not found
...\PortableGit\versions\<ver>\bin\bash.exe: line 1: grep: command not found
```

`ls` / `dirname` / `grep` / `sed` / `head` / `cat` / `wc` / `tr` / `sort` 全 `command not found`，
管道与重定向随之失效。`bash.exe` 本身能起（不是"bash 坏了"）。

## 决定性诊断（先做这个，别猜）

**测试 A：注册表改动能不能到达子进程？**

```powershell
# 往用户 PATH 尾巴上塞一个不存在的探针
$cur = [Environment]::GetEnvironmentVariable("Path","User")
[Environment]::SetEnvironmentVariable("Path", $cur + ";C:\__pathtest__", "User")
```

然后在 Bash 工具里看：

```bash
echo "SEEN=$(case ":$PATH:" in *"__pathtest__"*) echo YES;; *) echo NO;; esac)"
```

**结果 `NO` = 子进程用的是旧快照，改注册表在当前会话里永远无效。**
（2026-09-14 实测就是 `NO`。测完记得把探针删掉。）

**测试 B：工具到底缺不缺**

```bash
for t in dirname ls cat head grep sed awk sort tr wc; do
  printf '%-9s %s\n' "$t" "$(command -v $t || echo MISSING)"; done
```

## 修法（已实测生效，不需要重启）

在 `<安装目录>\resources\app.asar.unpacked\cli\vendor\shim\shell-runtime-bash-env.sh`
**顶部**（必须在第 3 行的 `dirname` 调用**之前**）插入：

```sh
# --- [local patch] ---
for __cb_msys in /c/Users/<用户名>/.workbuddy/binaries/PortableGit/versions/*/usr/bin \
                 /c/Users/<用户名>/AppData/Local/Programs/MinGit/usr/bin; do
	[ -x "$__cb_msys/dirname.exe" ] || continue
	case ":$PATH:" in
		*":$__cb_msys:"*) ;;
		*) PATH="$__cb_msys:$PATH" ;;
	esac
	break
done
unset __cb_msys
export PATH
# --- [/local patch] ---
```

为什么这么写：

- **插在顶部**才能救第 3 行；追加在末尾没用（`dirname` 已经失败过了）。
- **只用 bash 内建**（`for` / `[ -x ]` / `case`），不调任何外部命令——所以它自己不会
  因为 PATH 坏掉而失效。这是这段补丁能自举的关键。
- **用 glob 匹配 `versions/*/usr/bin`**：PortableGit 换版本目录后依然有效，不用改脚本。
- 补丁必须写成 **LF、无 BOM**。用 PowerShell 的 `Set-Content -Encoding UTF8`
  会写入 BOM，bash 会把 `\ufeff#` 当命令报错。要这样写：
  ```powershell
  [System.IO.File]::WriteAllText($p, $s, (New-Object System.Text.UTF8Encoding($false)))
  ```

**生效时机**：下一次 Bash 工具调用即生效（`BASH_ENV` 每次启动子 bash 都会 source），
**不需要重启 WorkBuddy**。

## 已验证的结果（2026-09-14）

- 20 个工具（dirname/basename/ls/cat/head/tail/grep/sed/awk/sort/uniq/wc/tr/find/xargs/cut/
  touch/mkdir/cp/rm）全部解析到 `PortableGit\versions\<ver>\usr\bin`；
- `dirname /a/b/c` → `/a/b`；管道 `printf|sort|tr` 正常；
- stderr 里那条 `line 3` 报错消失。

## 附带发现：这个 bug 会静默关掉"删除守卫"

`shell-runtime-bash-env.sh` 的前两行 source 顺序是：

```sh
__codebuddy_shell_runtime_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # ← dirname 失败 → 变量为空
[ ! -f "${...}/safe-bin/safe-delete-bash-env.sh" ] || . "..."                    # ← 判成"文件不存在"→ 不 source
```

结果：`rm` / `rmdir` / `unlink` 的**回收站包装没了，变成真删**，而且没有任何提示。

**判据**（修好后应为 function）：

```bash
command -v rm          # 正常输出 "rm"（= function）；坏掉时会输出真实路径
type rm | head -3      # 期望看到 "rm is a function"
```

⚠️ 注意 `safe_delete_main` / `try_trash` 这些函数**在顶层 shell 里本来就查不到**——
它们定义在 `safe-bin/safe-delete-common.sh`，由 `safe-bin/rm` 等包装脚本在被调用时自己 source。
所以**别用 `declare -f try_trash` 判断守卫是否加载**，要看 `command -v rm`。

## 升级兜底：双击即可重新打补丁

WorkBuddy 升级可能覆盖 `app.asar.unpacked` 下的 shim。已在本机放好一套守护脚本：

- `C:\Users\zyx32\bin\fix-bash-path.cmd` —— 双击运行（`.cmd` 纯 ASCII，中文交互不放批处理里）
- 同目录 `fix-bash-path.ps1`（纯 ASCII）+ `bash-path-hook.txt`（UTF-8，补丁正文母本）

`.ps1` 的行为：检测到 `__cb_msys` 已存在就报 `[ OK ] patch already present` 并退出；
否则先 `.bak` 备份再写入。**把补丁正文单独放进一个 UTF-8 的 `.txt`，
是为了绕开 PowerShell 5.1 按 ANSI 读 `.ps1` 导致中文字符串写坏的问题。**

## 这三个方案试过，无效（别再走）

| 方案 | 为什么不行 |
|---|---|
| **改注册表 + 重启**（旧结论） | 子进程拿的是启动时的 PATH 快照；2026-09-14 用探针实测 `NO`。之前"重启后修好了"是**误判**——那段时间实际是沙箱的 `brokered-bin` 在顶班 |
| **把 PATH 项追加到用户 PATH 末尾** | 同上，到不了子进程；而且就算到了，末尾顺序最容易被后续拼接挤掉 |
| 往里目录拷 `dirname.exe` | msys 程序要 `msys-2.0.dll`，不放同目录会**静默失败**（执行后无输出、不报错） |
| 用 `versions\current` 做稳定路径 | 本机 `current` 是个标记文件（`Mode=-a----`），不是目录/链接 |

## 顺手记住三条环境事实

- **PowerShell 工具不回显 stdout**：`Exit Code: 0` 但一行输出都没有。一律写文件再 Read。
  （注意 `*>` / `>` 重定向在 PS 5.1 里写的是 **UTF-16**，Read 工具会判为二进制并拒读 →
  要么 `-Encoding UTF8` 写，要么用 Python 转码后再读。）
- **Bash 工具和 PowerShell 工具都拒绝调用外部 shell**：
  `& $bash -c "..."` 会报 `cmd.exe cannot be used from the PowerShell tool`。
- **本机 `resources\app.asar.unpacked\` 下的 shim 是可写的**（不是只读 asar），
  所以补丁能落盘；但也意味着**升级会覆盖它**，需要守护脚本。
