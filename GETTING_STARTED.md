# 快速上手指南

这份文档面向第一次打开本仓库的你，目标是：**从零环境开始，一步步跑通所有 Demo**。

完整的课程介绍和学习路线请看 [README.md](README.md)，每个 Demo 的详细讲解在各自的 `demoN/README.md` 里。

## 1. 这个仓库是什么

一个循序渐进的 Agent 教程仓库，从 `demo1` 到 `demo11`，用纯 Python 手写（不依赖 LangChain 等框架），一步步搭出越来越完整的 Agent：

> 最小 LLM 调用 → 多轮对话记忆 → Tool Calling → Planning → ReAct 循环 → Agent 框架抽象 → Coding Agent → Workflow 编排 → HITL 人工审批 → RAG → MCP

## 2. 前置条件

- Windows 系统，使用 PowerShell（仓库内示例均按 PowerShell 语法编写）
- 已安装 [Miniconda](https://docs.conda.io/en/latest/miniconda.html)（其他 Python 管理方式也可以，本文以 Miniconda 为例）
- 一个可用的 LLM API Key（DeepSeek；`demo1` 当前版本使用智谱 BigModel 平台的 Key，见第 8 节 FAQ）

## 3. 创建 Python 环境（Miniconda）

在 PowerShell 中执行：

```powershell
# 创建名为 agent 的虚拟环境（推荐 Python 3.11）
conda create -n agent python=3.11 -y

# 激活环境
conda activate agent
```

> 如果报错 `CondaToSNonInteractiveError: Terms of Service have not been accepted...`，先执行以下三条命令接受官方源的服务条款，再重新创建：
>
> ```powershell
> conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
> conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
> conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/msys2
> ```

常用环境管理命令：

```powershell
conda env list              # 查看所有环境
conda deactivate            # 退出当前环境
conda remove -n agent --all # 删除环境
```

## 4. 安装依赖

激活 `agent` 环境后，在项目根目录执行：

```powershell
cd "d:\AI agent\agent-tutorial"
pip install -r requirements.txt
```

依赖只有 4 个，各自服务于哪些 Demo：

| 依赖 | 用途 | 主要使用 |
| --- | --- | --- |
| `requests` | HTTP 请求，直调 Chat API | demo1 ~ demo5 |
| `psycopg[binary]` | PostgreSQL 驱动 | demo10（RAG 向量库） |
| `zai-sdk` | 智谱 Embedding SDK | demo10（文档向量化） |
| `mcp` | MCP 官方 SDK（FastMCP） | demo11（外部工具接入） |

## 5. 配置 API Key

所有 Demo 通过**环境变量**读取密钥，不会写入代码。每次新开一个 PowerShell 终端，都需要先设置：

```powershell
$env:DEEPSEEK_API_KEY="你的 API Key"
```

`demo10` 额外需要（跑 demo10 之前再配即可，不影响其他 Demo）：

```powershell
$env:ZHIPU_API_KEY="你的智谱 API Key"
$env:PGVECTOR_HOST="你的 PostgreSQL 访问地址"
$env:PGVECTOR_PASSWORD="你的数据库密码"
```

> 注意：`$env:XXX` 设置的环境变量只在当前终端会话有效，重开终端需要重新设置。

## 6. 跑通第一个示例

```powershell
python demo1/hello_world.py
```

预期输出：先打印发送给模型的消息，然后是模型的一句话回复（介绍什么是 Agent），最后是 token 用量统计。

看到这三段输出，说明环境和 API 都已经通了。

## 7. 按顺序跑完所有 Demo

建议在**项目根目录**下运行（demo7 之后的代码依赖 `sys.path` 从根目录导入 `demo6.framework` 等包）：

| Demo | 主题 | 运行命令 | 额外准备 |
| --- | --- | --- | --- |
| demo1 | 最小 LLM 调用 | `python demo1/hello_world.py` | 无 |
| demo2 | 多轮对话与短期记忆 | `python demo2/memory_demo.py` | 无（交互式） |
| demo3 | Tool Calling 文件工具 | `python demo3/tool_demo.py` | 无 |
| demo4 | 显式规划状态机 | `python demo4/planning_demo.py` | 无 |
| demo5 | ReAct 循环 Agent | `python demo5/react_demo.py` | 无 |
| demo6 | 最小 Agent 框架抽象 | `python demo6/framework_demo.py` | 无 |
| demo7 | 简化版 Coding Agent | `python demo7/coding_agent_demo.py` | 无 |
| demo8 | 固定节点 Workflow | `python demo8/workflow_demo.py` | 无 |
| demo9 | HITL 人工审批 | `python demo9/hitl_demo.py` | 无（审批时需输入 yes） |
| demo10 | pgvector RAG | `python demo10/rag_demo.py` | 智谱 Key + pgvector 数据库 |
| demo11 | MCP 工具接入 | `python demo11/mcp_agent_demo.py` | 无 |

**demo10 的额外准备**：

1. 需要一个启用了 `pgvector` 扩展的 PostgreSQL 数据库
2. 除第 5 节的三个环境变量外，数据库名和用户名写在 [demo10/config.py](demo10/config.py) 中（`PGVECTOR_DATABASE`、`PGVECTOR_USER`），与你的实际环境不一致时需要手动修改
3. 每次启动会清空并重建 `rag_chunks` 表，属于教程预期行为

如果暂时没有 pgvector 数据库，可以先跳过 demo10，不影响其他章节。

## 8. 常见问题（FAQ）

**Q1：`CondaToSNonInteractiveError` 报错怎么办？**

见第 3 节的说明，执行三条 `conda tos accept` 命令即可。

**Q2：报错 `缺少环境变量 DEEPSEEK_API_KEY`？**

当前终端没有设置环境变量，重新执行第 5 节的 `$env:DEEPSEEK_API_KEY="..."`。

**Q3：demo1 和其他 Demo 用的是同一个 API 吗？**

不是。当前代码中：

- `demo1` 指向智谱 BigModel 平台（`open.bigmodel.cn`，模型 `glm-5.3`），需要智谱平台的 API Key
- `demo2` 及之后指向 DeepSeek 平台（`api.deepseek.com`，模型 `deepseek-v4-flash`），需要 DeepSeek 的 API Key

两个平台的 Key 不同。如果只有其中一个平台的 Key，运行对应 Demo 时需要把对应文件里的 `API_URL` / `MODEL_NAME` 改成你实际可用的平台。

**Q4：VS Code 里运行报 `ModuleNotFoundError`？**

1. 确认右下角 Python 解释器已切换到 `agent` 环境（`conda activate agent` 后 VS Code 一般会自动提示）
2. 确认是在**项目根目录**下运行，demo7 之后的代码依赖从根目录导入框架包

**Q5：pip 安装依赖很慢？**

可以使用国内镜像：

```powershell
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**Q6：demo10 连接数据库失败？**

- 检查 `PGVECTOR_HOST` / `PGVECTOR_PASSWORD` 是否已设置
- 检查数据库是否启用了 `pgvector` 扩展
- 检查 [demo10/config.py](demo10/config.py) 中的数据库名、用户名、端口是否与实际环境一致

## 9. 下一步

环境跑通后，回到 [README.md](README.md) 查看完整的学习路线（完全新手 / 已会调 API / 想写框架三条路线），然后从 [demo1/README.md](demo1/README.md) 开始按顺序学习。

每个 Demo 的推荐学习节奏：

1. 先运行，感受它能做什么
2. 读这一节的 `README.md`
3. 看入口文件和关键模块
4. 自己改一个小功能，验证是否真的理解
