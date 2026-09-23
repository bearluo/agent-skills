# 自成长协议(SELF-GROWTH)

`android-driver` agent / `android-playtest` skill 在真机驱动中学到新经验时,按此把它「长」进知识库。目标:让 `engines/*.md`(尤其 cocos.md 的 TODO)随实跑逐步充实,而不是学完就丢。

## 谁执行(子 agent 只读,主会话落库)

- **子 agent `android-driver` 只读**(工具仅 Bash/Read/Glob,**无 Write**),故**不自己落库**;它在回传里单列「候选经验」块,每条标疑似 **public / local**。
- **主会话**(有 Write + 记忆 + 能问你)负责:分类 → **批量问用户** → 写进对应桶。
- `android-playtest` skill 的**收尾步**同样收集候选并走这套。

## 两个桶

| 桶 | 装什么 | 落点 |
|---|---|---|
| **public**(开发者角度) | 引擎**通用**经验:某引擎 swiftshader 黑屏报错、观察通道、so/资源识别特征、日志 tag 规律 | 引擎专属 → `<skill目录>/android/engines/<engine>.md`;**不属于任何引擎**的环境层经验(选镜像、建 AVD、本机路径规矩、原生 App 观察通道)→ `<skill目录>/android/emulator.md`。**本 skills 仓库是 git 仓库,落公共 = 一次提交**(可 diff / 回滚 / 日后推团队) |
| **local**(个人角度) | **游戏/本机专属**:包名、按钮像素坐标、某游戏的 log 里程碑行、APK 路径、个人偏好 | **个人 auto-memory** `~/.claude/projects/<项目>/memory/*.md`(+ MEMORY.md 索引行);**不进版本库** |

判据:**能脱离具体游戏复用 = public;只对某游戏/某台机成立 = local**。拿不准时归 local(更保守,不污染共享层)。

## 门槛(定版:两桶都问,批量一次确认)

1. 跑完把本次所有候选攒成一小段,每条列:**内容 / 疑似桶 / 建议落点文件 / 是否已存在**(落库前先 Read 目标去重)。
2. **一次性**交用户勾选(可整批同意 / 逐条改桶 / 丢弃)——不逐条打断。
3. 用户确认后:
   - **public** → Edit/Write 对应 `engines/<engine>.md`,随后 `git -C "<skills 仓库根>" add -A && git commit -m "learn(<engine>): …"`。
   - **local** → 写/更新 auto-memory 的 `.md` + 补 `MEMORY.md` 一行索引。
4. **已存在的经验只更新、不重复追加**(去重是自成长不膨胀的关键)。

## 触发点(提醒随文本自带,无需 runtime)

- agent「回传纪律」末尾的**候选经验块** → 主会话看到即走本协议。
- skill「收尾·自成长」步。
- 二者都指向本文件(`<skill目录>/android/SELF-GROWTH.md`)。

## 典型:填 cocos.md 的 TODO

第一次真机驱 Cocos 跑通后:swiftshader 具体报错 / 日志 tag / 观察通道 = **public**,落 `cocos.md` 并 commit;那个 Cocos 游戏的包名/Activity/分辨率 = **local**,落个人记忆。新引擎同理:先加 `engines/<engine>.md` 骨架,再由本协议逐步喂实测。
