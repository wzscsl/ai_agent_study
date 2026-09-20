from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from psycopg import sql

from demo6.framework import ask_llm_text
from demo10.config import EMBEDDING_DIMENSION, KNOWLEDGE_BASE_DIR
from demo10.document_loader import split_text
from demo10.embeddings import embed_query, embed_texts
from demo10.rag_demo import build_context_text
from demo10.rag_store import connect, vector_literal

# 实验用独立表，不碰 demo10 主流程的 rag_chunks 表。
EXP_TABLE = "rag_chunks_exp"

# 练习②的评估问题集：每题标注期望命中的来源文档。
EVAL_QUESTIONS = [
    ("人工审批适合哪些高风险场景？", "hitl.md"),
    ("ReAct 循环中工具结果如何回传给模型？", "react.md"),
    ("workflow 节点如何决定下一跳？", "workflow.md"),
    ("一个最小 Agent 由哪几部分组成？", "agent_basics.md"),
    ("RAG 相比微调有什么优势？", "rag.md"),
]

# 练习①的对比问题：答案只在新增的 rag.md 里。
P1_QUESTION = "embedding-3 的向量维度是多少？"


def build_exp_index(chunk_size: int, overlap: int) -> int:
    """按指定参数重建实验索引，返回 chunk 数。"""
    rows: list[tuple[str, int, str]] = []
    for path in sorted(KNOWLEDGE_BASE_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for index, content in enumerate(split_text(text, chunk_size=chunk_size, overlap=overlap)):
            rows.append((path.name, index, content))
    if not rows:
        raise RuntimeError("knowledge_base 目录下没有 Markdown 文档。")

    embeddings = embed_texts([content for _, _, content in rows])

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(
                sql.SQL(
                    """
                    CREATE TABLE IF NOT EXISTS {t} (
                        id TEXT PRIMARY KEY,
                        source TEXT NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        embedding vector({d}) NOT NULL
                    )
                    """
                ).format(t=sql.Identifier(EXP_TABLE), d=sql.SQL(str(EMBEDDING_DIMENSION)))
            )
            cur.execute(sql.SQL("TRUNCATE TABLE {t}").format(t=sql.Identifier(EXP_TABLE)))
            for (source, index, content), embedding in zip(rows, embeddings):
                cur.execute(
                    sql.SQL(
                        """
                        INSERT INTO {t} (id, source, chunk_index, content, embedding)
                        VALUES (%s, %s, %s, %s, %s::vector)
                        ON CONFLICT (id) DO UPDATE SET
                            content = EXCLUDED.content, embedding = EXCLUDED.embedding
                        """
                    ).format(t=sql.Identifier(EXP_TABLE)),
                    [
                        f"exp:{source}:{index}:{chunk_size}:{overlap}",
                        source,
                        index,
                        content,
                        vector_literal(embedding),
                    ],
                )
    return len(rows)


def query_exp(question: str, top_k: int = 8) -> list[tuple[str, int, str, float]]:
    """在实验表上做与 rag_store.retrieve 等价的相似度检索。"""
    query_vector = vector_literal(embed_query(question))
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL(
                    """
                    SELECT source, chunk_index, content, embedding <=> %s::vector AS distance
                    FROM {t}
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """
                ).format(t=sql.Identifier(EXP_TABLE)),
                [query_vector, query_vector, top_k],
            )
            rows = cur.fetchall()
    return [(row[0], row[1], row[2], float(row[3])) for row in rows]


def answer_from_hits(question: str, hits: list[tuple[str, int, str, float]]) -> str:
    """复刻 answer_with_rag 的生成方式，但基于实验表的检索结果。"""
    chunks = [
        SimpleNamespace(source=s, chunk_index=i, distance=d, content=c)
        for s, i, c, d in hits[:4]
    ]
    system_prompt = (
        "你是一个 RAG 教程助手。"
        "回答问题时必须优先依据提供的资料。"
        "如果资料里没有答案，要明确说资料不足，不要编造。"
        "回答使用简洁清晰的中文。"
    )
    user_content = f"用户问题：{question}\n\n可参考资料：\n{build_context_text(chunks)}"
    return ask_llm_text(system_prompt, user_content)


def show_hits(question: str, hits: list[tuple[str, int, str, float]], limit: int = 4) -> None:
    print(f"问题：{question}")
    for source, index, content, distance in hits[:limit]:
        print(f"  {source}#{index}  distance={distance:.4f}  {content[:36]}...")


def phase_before() -> None:
    """练习①第一阶段：rag.md 尚不存在时的检索与回答。"""
    chunks = build_exp_index(700, 120)
    docs = len({p.name for p in KNOWLEDGE_BASE_DIR.glob('*.md')})
    print(f"[before] documents={docs}, chunks={chunks}（chunk=700/overlap=120）\n")
    hits = query_exp(P1_QUESTION)
    show_hits(P1_QUESTION, hits)
    print("\n回答：", answer_from_hits(P1_QUESTION, hits))


def phase_after() -> None:
    """练习①第二阶段（A/B）+ 练习②参数扫描。"""
    # --- A/B：同样的问题，rag.md 加入之后 ---
    chunks = build_exp_index(700, 120)
    docs = len({p.name for p in KNOWLEDGE_BASE_DIR.glob('*.md')})
    print(f"[after] documents={docs}, chunks={chunks}（chunk=700/overlap=120）\n")
    hits = query_exp(P1_QUESTION)
    show_hits(P1_QUESTION, hits)
    print("\n回答：", answer_from_hits(P1_QUESTION, hits))

    # --- 练习②：chunk / overlap 扫描，Top-K 在同一次 top-8 结果上切出来评估 ---
    print("\n" + "=" * 70)
    print("练习②：参数扫描（评估 5 题，统计期望文档的命中排名）")
    print("=" * 70)
    for chunk_size, overlap in [(200, 0), (200, 40), (700, 120), (2000, 0)]:
        chunk_count = build_exp_index(chunk_size, overlap)
        top1 = top4 = top8 = 0
        best_distances: list[float] = []
        details: list[str] = []
        for question, expected in EVAL_QUESTIONS:
            hits = query_exp(question, top_k=8)
            sources = [h[0] for h in hits]
            rank = sources.index(expected) + 1 if expected in sources else None
            best_distances.append(hits[0][3])
            if rank == 1:
                top1 += 1
            if rank and rank <= 4:
                top4 += 1
            if rank:
                top8 += 1
            details.append(f"{expected.split('.')[0]}:rank{rank if rank else '-'}")
        print(
            f"chunk={chunk_size:>4}/overlap={overlap:>3} -> chunks={chunk_count:>2} | "
            f"top1 {top1}/5  top4 {top4}/5  top8 {top8}/5 | "
            f"最优distance均值 {sum(best_distances) / len(best_distances):.4f} | {' '.join(details)}"
        )


def main() -> None:
    phase = sys.argv[1] if len(sys.argv) > 1 else "after"
    if phase == "before":
        phase_before()
    elif phase == "after":
        phase_after()
    else:
        raise SystemExit(f"未知阶段：{phase}（可用：before / after）")


if __name__ == "__main__":
    main()
