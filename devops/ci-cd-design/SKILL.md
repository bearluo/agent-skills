---
name: ci-cd-design
description: Use when designing, reviewing, debugging, or speeding up a CI/CD pipeline — GitLab CI, GitHub Actions, self-hosted runners, container builds, image tagging, deploy jobs. Covers how to measure where pipeline minutes actually go before changing anything, why before_script package installs dominate cost, content-fingerprint image tags vs commit SHA, when rules:changes silently lies, when cache: is a net loss, and the guard patterns that keep a pipeline from failing silently.
---

# CI/CD 设计与提速

**先量再改。** 流水线的直觉几乎总是错的 —— 慢的那一段通常不是在跑测试，是在装工具。

## 一、量：机时到底花在哪

GitLab 的作业日志**每行带 UTC 时间戳**，另有 `section_start/end:<unixtime>:<段名>` 标记。所以不用猜：

```bash
# 一条流水线里每个作业的时长
glab api "projects/<组>%2F<仓库>/pipelines/<id>/jobs" > /tmp/j.json

# 某个作业内部：哪一行开始、哪一行结束
glab api "projects/<组>%2F<仓库>/jobs/<作业id>/trace" \
  | sed 's/\x1b\[[0-9;]*[A-Za-z]//g; s/\r/\n/g' | grep -n '^\S* \S*O \$ '
```

按**作业类型**把最近十几条流水线的时长加起来，做成一张表。真正想跑的那件事（test / lint）
往往只占 10%，其余是基础设施在自我供养。

**实测过的一次（hr-interview，2026-08-25）：**

| 作业 | 机时占比 | 内部拆解 |
|---|---:|---|
| plan | 52% | apt update 114s + apt install 378s = 492s，**真正干活 2s** |
| guard | 14% | apt 273s，`git fetch` + `merge-base` **1s** |
| deploy | 14% | 同一笔 apt + 真正的 ssh 部署 |
| test | 10% | 47s，**直接用基础镜像不装东西 —— 这是对照组** |

同一条流水线里有一个不装东西的作业，就等于自带对照组，一眼能看出装包的开销。

## 二、最常见的那笔浪费：`before_script` 里的 apt

```yaml
# 反面
.ci-tools:
  image: node:24-slim
  before_script:
    - apt-get update -qq
    - apt-get install -y -qq --no-install-recommends ca-certificates git curl openssh-client
```

三个作业 extends 它，就装三遍；每条流水线都装。**烤进镜像，推自己的 registry：**

```yaml
variables:
  CI_TOOLS_IMAGE: <registry>/<项目>/xxx-ci:node24-20260825   # 钉日期 tag
.ci-tools:
  image: $CI_TOOLS_IMAGE
```

实测这一改让 `plan` 从 **498s → 10.4s**。

几条配套的硬约束：

- **tag 钉死日期，不用 `latest`。** CI 的基础镜像悄悄换掉是「昨天还好好的」那类故障里最难查的
  一种；出问题要能一行改回上一个 tag。旧 tag 别覆盖。
- **重建走 CI 里一个 `manual` + `allow_failure: true` 的 kaniko 作业，不在本机 `docker build` 再 push。**
  本机 buildx 默认出 OCI manifest list + attestation manifest，跟 runner 平时拉镜像验过的不是同一种
  东西。真要本机推，加 `--platform linux/amd64 --provenance=false --sbom=false`。
- **那个作业挂在 build stage、不挡任何东西** —— 它的产物是给**下一条**流水线用的，没有理由排在前面。
- **不要把 CI 镜像的 Dockerfile 算进业务镜像的指纹**，否则改一行 CI 工具链就四个业务镜像全重出。
- **`ca-certificates` 这类包不是可选项。** `-slim` 系镜像普遍没有 CA 包，表现是 git 报
  「server certificate verification failed. CAfile: none」、curl 报 `(77)` —— 看着像网络问题。

## 三、镜像 tag：内容指纹 > commit sha

commit sha 每个提交都变，于是「这次要不要重出这个镜像」根本问不出口。换成
「这个镜像构建时真正读到的那些路径的 git 对象 id 拼起来哈希」之后，答案是确定的 ——
去 registry 问一句「这个 tag 在不在」，在就整个作业跳过。

```bash
fp() { { echo "$REF:.gitlab-ci.yml"; echo "$REF:.dockerignore"
         for p in "$@"; do echo "$REF:$p"; done
       } | xargs git rev-parse | sha256sum | cut -c1-12; }
```

- **路径清单宁可宽不可窄**：多列一个，代价是偶尔白重出一次（有层缓存）；少列一个，代价是拿旧镜像
  当新的发出去，**且不报错**。`.gitlab-ci.yml` 和 `.dockerignore` 一定要算进去 —— 它们不在 build
  context 里，但都改得动产物。
- **指纹的定义只能有一份**（一个脚本），CI 和手工部署脚本都从它取。两处各抄一份的后果是 tag 对不上，
  而报出来的是「镜像不存在」，离原因很远。
- 代价照实说：**「现在跑的是哪个提交」不能再从 tag 读出来。** 补偿是部署时在目标机上落一份
  `DEPLOYED` 文件记下提交和各个 tag。
- **别再往 destination 里加浮动 tag**（`:latest` / `:$CI_COMMIT_SHORT_SHA`）—— 作业会被跳过，
  那个浮动 tag 就只在「恰好重出了」的几次才更新，**比没有更坏：它看着是最新的**。

## 四、几个静默失效的坑

- **`rules:changes` 在 tag / scheduled / manual 流水线上恒为 true**（GitLab 文档明写）。写上去 YAML
  看着配好了、作业照旧全跑 —— **假开关比没有开关更坏**。要跳过就自己算指纹。
- **`cache:` 在没配分布式缓存的 shared runner 上是净亏。** 日志里出现
  `No URL provided, cache will not be uploaded` / `Cache file does not exist` 就说明没配 S3，
  而 docker executor 下"本地"那份也不跨作业。归档几万个文件白花十几秒，`reused 0` 一次没变过。
  **先确认 `[runners.cache]` 配了再加。**
- **runner tag 写错 = 无限 pending，而 pending 不是失败**：流水线不红、不发通知、列表里显示
  「运行中」。放进 `default:` 一次给全部作业，别逐个写。
- **把「请求失败」当「不存在」的探测函数必须先单独探一次路。** 否则任何让请求起不来的原因
  （CA 缺了、403、出网不通）都被翻译成「不存在 → 全部重建」，而作业**照样是绿的**：跳过功能
  静默关掉，只表现为流水线突然变慢，没人会去查。
- **依赖不在自己手里时加 `command -v` 守卫。** runner 的默认镜像归运维管，可以随时被换掉
  （实测踩过：`ubuntu2204_ansible` → `redis:7-alpine`，三个作业当场全挂）。守卫让它当场报出来，
  而不是在后面某一行以莫名其妙的 `not found` 冒出来。
- **dotenv 传变量的作业别加 `needs:` / `dependencies:`** —— 加了链就断，而断了的表现是变量变成空串
  （`仓库:` 这种拼串），不是报错。每个下游作业第一件事断言它非空。

## 五、并发与排队

- **runner 并发是 1 时，机时 = 墙上时间。** 省下的每一秒都是人真的在等的时间；并发高时同样的浪费
  会被并行掩盖，优先级不同。先查 `concurrent` 配置再判断值不值得优化。
- **一个 MR 常有两条流水线**（推分支一条 + 建 MR 一条；服务端 rebase 再来一条）。
  `workflow:rules` 里那条 `$CI_COMMIT_BRANCH && $CI_OPEN_MERGE_REQUESTS → never` 只能去掉
  「MR 已存在时的分支推送」那一种，**先推后建 MR 的那次去不掉**。把单条流水线做便宜比去重要紧。

## 六、部署作业

- **只送运行期真正要的文件**（compose 文件、迁移 SQL），源码不再参与运行就别送。
- **`.env` 一个字都不碰。** 目标机上的密钥（尤其是加密用的 secret key）往往跟别处不是同一把，
  覆盖了就是库里所有密文全解不开。
- **远端动作写成脚本 scp 过去再执行**，不要在 ssh 命令行上拼引号 —— 每加一层就多一次
  「本地看着对、到那头少了一对引号」。
- **compose 重建一个服务会连带重建它的依赖**，而那次连带重建吃的是命令行上给的那套文件。
  少给 override、或只挑几个服务 up，被连带的那个就会掉回 `build:` 那一路 —— **而且六个容器照样
  全 healthy，不报错**。要么全给，要么别动。
- 清旧镜像**逐个仓库清、各留最近几个**，不要 `docker image prune`（机器上可能还有别人的东西），
  也不要一个通配符把几个仓库一起排序（等于每个仓库只留一个）。
