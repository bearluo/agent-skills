---
name: rebase-merge
description: Use when merging/finishing/integrating a feature branch into main (or any base branch), or whenever the user asks to merge branches, land a PR/MR, or keep history linear / avoid merge commits. Covers the rebase-before-merge workflow, fast-forward merge, GitLab (glab) MR settings, conflict handling, and the "only rebase private branches" safety rule.
---

# Rebase-Merge:保持 main 线性历史(不留 merge commit)

目标:把特性分支合进基线分支(通常 `main`)时**不产生 merge commit**,历史保持一条直线,`git log` / `bisect` 清爽。

## ⚠️ 唯一铁律:只 rebase「私有分支」

- ✅ **可以 rebase**:只有你自己在用、**没有别人基于它开发 / pull 过**的特性分支。
- ❌ **绝不 rebase**:`main`、或任何**已共享、别人正基于它工作**的分支。rebase 会改写 commit hash,别人本地会对不上、被迫强推恢复,一团乱。
- 一句话:**rebase 私有分支,共享分支别碰。**
- 已经把特性分支推到远程、且有人 pull 了它 → 不要再 rebase(或先协调)。

## 怎么选:rebase 还是 merge?

| 场景 | 用 |
|---|---|
| 你一个人的特性分支 / worktree 分支,准备合进 main | **rebase**(本节) |
| 分支已被多人共享、别人基于它提交 | 普通 **merge**(别 rebase) |
| 想把一堆 WIP 提交压成一个干净提交 | **squash**(见下) |

## 工作流 A:本地 fast-forward 合并(无 merge commit)

```bash
# 1. 把私有特性分支 rebase 到最新 main 之上(注意:在特性分支上执行)
git checkout <feature>
git fetch origin
git rebase origin/main
#   冲突:改文件 → git add <file> → git rebase --continue
#   想放弃整个 rebase:git rebase --abort

# 2. fast-forward 合入 main —— 因为已线性,不产生 merge commit
git checkout main
git pull --ff-only origin main        # 确保本地 main 最新
git merge --ff-only <feature>
git push origin main

# 3. 清理分支
git branch -d <feature>
git push origin --delete <feature>    # 若推过远程
```

> 关键点:**永远是把 feature rebase 到 main,不是反过来**。
> `git merge --ff-only` 若报错(non-fast-forward),说明 feature 没基于最新 main,回到第 1 步重新 rebase。

## 工作流 B:GitLab MR(本机用 glab)

```bash
git push -u origin <feature>
glab mr create --fill --remove-source-branch

# 合并时让 GitLab 走 rebase / fast-forward,而不是 merge commit:
glab mr merge <iid> --rebase          # 线性,无 merge commit
# 或把整支压成一个提交:
glab mr merge <iid> --squash
```

**项目级一劳永逸**:GitLab → 项目 **Settings → Merge requests → Merge method → 选「Fast-forward merge」**。从此该仓库的 MR 必须先 rebase 才能合,强制线性,杜绝 merge commit。(本仓库历史目前是默认的 merge-commit 风格,想统一就切这个。)

### ff 仓库上常卡的两处

**`422 Branch cannot be merged`** —— 不是冲突。是**刚才另一条 MR 合进去了、目标分支动了**,你这条不再线性。ff 仓库不替你自动 rebase:

```bash
glab mr rebase <iid>          # ✓ Rebase successful!
glab mr merge <iid> --rebase
```

**连着合两条 MR 时,第二条必然撞上这个** —— 是规则在生效,不是故障。别去改 merge method 绕开它。

**合完删本地分支,git 说 `not fully merged`** —— GitLab 是在**服务端** rebase 之后合的,落到 `main` 上的提交 **SHA 跟你本地那几个不一样**,git 因此认不出这是同一份东西。别看见提示就 `-D`,先确认内容真的都在:

```bash
# 只比这条分支自己改过的文件,空 = 一字不差都在 main 上
git diff --stat <feature> main -- <它改过的路径…>
git branch -D <feature>
```

**不要**直接 `git diff <feature> main` 就下结论 —— 那会把 `main` 上**别人**的新提交也算成差异,看着像"没合进去",其实是你的分支落后了。两者的区别就是有没有限定路径。

## 把 WIP 提交压干净(可选)

合并前在特性分支上整理提交:
```bash
git rebase -i origin/main             # 把多个 WIP 标成 squash/fixup,合成有意义的提交
```
或者直接用 MR 的 `--squash`,让 GitLab 压成一个。

## worktree 场景

worktree 里的特性分支天然是**私有的**(独立目录、独立 checkout),rebase 它完全安全。常见组合:在 worktree 里开发完 → `git fetch && git rebase origin/main` → 回主仓库 fast-forward 合 main。

## 红旗(别犯)

- 在 `main` 上执行 `git rebase <feature>` —— 反了,这是在改写 main。永远 checkout 到 feature 再 rebase main。
- 对共享分支 `git push --force` —— 把别人的提交冲掉。私有分支 rebase 后用 `git push --force-with-lease`(更安全)。
- rebase 到一半放弃却忘了 `git rebase --abort`,留下半截状态。
- `git pull` 不带 `--ff-only` 导致本地 main 莫名其妙多出 merge commit —— 拉 main 一律 `git pull --ff-only`。
