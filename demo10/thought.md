# Question

- **Q：RAG 是什么？什么时候用 RAG，什么时候用微调？**
  A：Retrieval-Augmented Generation——先检索再生成，把外部知识实时塞进 prompt。知识频繁更新、需要溯源、有私有数据时用 RAG；要改变模型的风格或固有能力时才用微调。本质区别：RAG 改的是"模型这一轮能看到什么"，微调改的是"模型本身"。两者可叠加。

- **Q：RAG 的完整链路是什么？demo10 对应哪几步？**
  A：加载 → 切分 → 向量化 → 入库 → 检索 → 生成。对应 `load_knowledge_base` → `split_text` → `embed_texts` → `rebuild_index`（写 pgvector）→ `retrieve`（问题转向量 + cosine Top-K）→ `answer_with_rag`（资料 + 问题进 prompt）。链路上**每一环都可能成为失败点**——实测中网络、Key、数据库各挂过一次。

- **Q：为什么必须切 chunk？CHUNK_SIZE=700 / OVERLAP=120 怎么权衡？**
  A：检索粒度由 chunk 决定。太大：一个 chunk 混多个主题，检索不精准、还浪费生成时的上下文窗口；太小：语义断裂，答案缺少上下文。overlap 让相邻 chunk 保留衔接，代价是存储和召回重复。700/120 只是经验起点，真实项目按文档结构（标题、段落边界）切分会更好——字符数切分可能把一句话拦腰斩断。

- **Q：为什么查询文本和文档必须用同一个 embedding 模型？**
  A：相似度比的是向量空间里的距离，而不同模型的向量空间是不同的坐标系，跨模型的向量不可比较。demo10 里 `embed_texts` 和 `embed_query` 都固定走 embedding-3，就是保证查询和文档在同一空间。

- **Q：pgvector 的 `<=>` 是什么？distance 越小意味着什么？**
  A：cosine distance 运算符（1 − 余弦相似度）。`ORDER BY embedding <=> 查询向量 LIMIT K` 就是最近邻检索。demo 把 distance 随资料一起展示，人可以据此判断召回质量——这是低成本的可解释性。

- **Q：RAG 怎么防幻觉？系统提示词够吗？**
  A：三层。系统提示词约束（"必须优先依据资料、资料不足要明说"）是**软约束**；检索质量是**硬基础**——召回的资料不对，prompt 写得再严也没用；给资料附上 source 和 distance，让模型（和人）能判断这份资料靠不靠谱。实测：问"法国的首都"，模型明确回答资料不包含、不编造。

- **Q：Top-K 怎么选？调大调小各有什么代价？**
  A：demo 取 4。太小：召回不足，答案缺依据；太大：无关 chunk 挤进上下文，既费 token 又可能稀释关键资料（还放大检索噪声）。调参方法：固定一组测试问题，对比不同 K 值下的回答质量，而不是拍脑袋。

- **Q：`chunk_id` 为什么用 md5(文件名:序号:内容)？**
  A：内容寻址——内容一变 id 就变，配合 `ON CONFLICT DO UPDATE` 得到幂等写入，这是增量索引的基础（只重嵌变化的 chunk）。demo10 为了流程简单，每次启动 TRUNCATE 全量重建；真实系统的演进方向就是利用这个 id 做增量。

- **Q：hnsw 索引创建失败了，demo 为什么还能跑？**
  A：hnsw 是近似最近邻索引，属于**性能优化**而不是 RAG 功能的前提。实测报错原因：embedding-3 是 2048 维，超过 pgvector hnsw 的 2000 维上限；代码捕获异常后降级为顺序扫描。4 个 chunk 顺序扫描毫无压力，百万级向量没索引才不可接受。把可选优化和必要功能分开、失败时优雅降级，是工程上很值得抄的设计。

- **Q：RAG 和 Agent 是什么关系？**
  A：RAG 给 Agent 装"外部记忆"（知道什么），工具调用给 Agent 装"外部动作"（能做什么）。demo10 的 `retrieve` 本质是一个工具，`answer_with_rag` 是"检索工具 + 生成"的最小组合；进阶形态是把 retrieve 注册成 Agent 工具之一，由模型在对话中自主决定何时查库。

# 实测记录（2026-09-20 跑通全过程）

## 环境搭建

- 数据库：Docker 起的 `pgvector/pgvector:pg16` 容器（user=zxt / password 走环境变量 / 库=agent_demo），`config.py` 的 `PGVECTOR_USER` 已从原作者的 `ljx` 改掉
- 网络：本机**直连 open.bigmodel.cn 会被重置**（Docker Hub 反而通），必须走 Clash 代理；为此做了本地启动脚本 `run_demo10.bat`（自动设变量 + 确保容器在跑，已 gitignore，防止 `git add .` 把 Key 带上 GitHub）

## Key 端点矩阵（逐个实测的结论）

| Key | embedding-3（标准端点） | 标准 chat | coding 端点 chat |
|---|---|---|---|
| Coding Plan Key（32 位 hex） | ✗ 401 | ✗ 401 | ✗ 401（已失效） |
| 标准平台 Key（id.secret 格式） | ✓ 200 | ✓ 200 | ✓ 200 |

- **关键发现：Coding Plan 订阅不覆盖标准端点的 embedding API**——demo10 的 embedding 走 `/api/paas/v4/embeddings`，必须用标准平台按量 Key；标准 Key 反而三个端点全通，demo10 两个变量都填它即可
- 排查方法论：先用无鉴权请求确认网络通（返回"未收到 Authorization"说明头能到达），再用带 Bearer 的原始 HTTP 逐端点测，最后才怪 SDK——把"网络、Key、SDK"三个变量拆开测

## 端到端行为

- 4 篇文档 → 4 个 chunk 入库，每次启动全量重建索引（教学设计）
- 知识库内问题（ReAct 区别、HITL 审批作用）：回答引用资料、结构对得上检索内容
- 知识库外问题（法国的首都）：明确回答"资料不包含、无法回答"，不编造——README 建议练习③ 顺带验证 ✓
- hnsw 降级实测发生：2048 维 > 2000 上限 → 顺序扫描，功能不受影响

# Practice 完成记录

## 练习一：新增知识库文档（rag.md），观察检索与回答变化

- 对照问题选了"embedding-3 的向量维度是多少？"——这个事实只存在于新增文档里
- **新增前**：top-4 命中的全是无关文档（distance 0.71~0.81），回答明确说"资料没有涉及 embedding 模型的技术参数，无法回答"
- **新增后**（4 篇 → 5 篇，chunks 4 → 6）：rag.md 的两个 chunk 包揽前两名（distance 0.6265 / 0.6671），回答准确引用资料给出"2048 维"
- 结论：知识库内容直接划定 RAG 系统的知识边界——文档没写的事实，系统宁可说资料不足也不编造；文档写了的，立刻能检索到并引用

## 练习二：chunk / overlap / Top-K 参数扫描

- 写了可重复运行的 `practice_experiments.py`：独立实验表 `rag_chunks_exp`（不碰 demo 主表），4 组参数 × 5 个标注来源的问题，Top-K 从同一次 top-8 结果上切出来评估
- 结果：4 组参数 top1 全部 **5/5**——小而主题分明的小知识库里，"找对文档"对 chunk 参数并不敏感
- 真正的差别在最优 distance 均值（越小 = 命中片段与问题语义越贴合）：

  | 参数 | chunks | 最优 distance 均值 |
  |---|---|---|
  | chunk=200 / overlap=40 | 12 | **0.4574**（最贴） |
  | chunk=200 / overlap=0 | 11 | 0.4615 |
  | chunk=700 / overlap=120 | 6 | 0.4951 |
  | chunk=2000 / overlap=0 | 5 | 0.5006（最散） |

- 解读：chunk 越小命中片段越聚焦（distance 越小）；chunk 越大一个 chunk 混多个主题，相似度被稀释。overlap=40 比 0 略好——边界处保留的衔接起作用了
- 但 distance 不是全部：小 chunk 检索准、生成时可能缺上下文；大 chunk 上下文全、却稀释检索信号还费 token。"chunk 太大不精准、太小断裂"这句话的量化版本就在这张表里
- Top-K：本题集所有期望命中都是 rank1，K=1 就够；K 的价值要在答案需要跨多个片段拼装时才体现
- 意外发现：原 4 篇文档都短于 700 字符，默认参数下每篇就是 1 个 chunk——**chunk 参数只在文档超过 chunk_size 时才真正生效**；把 rag.md 写到 1000+ 字后才切出 2 个 chunk，参数差异这才显现

# idea

- 这一课最大的体会：RAG 难的不是任何单环节的代码（每一步都很短），而是**链路的完整性**——六步任何一步断掉，系统就退化为"看起来在跑、实际全靠模型裸编"。最危险的失败模式不是报错，而是**静默退化**
- 检索质量是 RAG 的天花板：prompt 约束是软的，召回是硬的。优化优先级应该是：切分策略 → embedding 模型选型 → Top-K / rerank → prompt 措辞
- `[资料 N] source=... distance=...` 这种展示是好的可解释性实践：用户一眼能看出"这个回答基于什么、召回靠不靠谱"，也方便调试检索
- 练习①②③已全部完成（见上方 Practice 完成记录）：加文档看边界变化、参数扫描看检索质量、知识库外问题不编造——三个练习合起来恰好是"知识边界、检索质量、诚实性"三个维度
- 放在教程全局看：demo10 = Agent 的外部记忆，demo11（MCP）= Agent 的外部动作，两者合起来是 Agent 能力向外延伸的两条主线
