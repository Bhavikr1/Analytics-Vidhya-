import time
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import get_settings
from app.rag.retriever import RetrievedDoc, relevant_only, retrieve
from app.rag.vectorstore import get_vectorstore

# ── Grounded prompt (context found) ──────────────────────────────────────────

SYSTEM_PROMPT = """You are a Python programming tutor for data science learners. \
You answer questions using the Stack Overflow Q&A context provided below.

You also have access to the recent conversation history. Use it to understand \
follow-up questions, resolve pronouns ("it", "that", "the previous example"), and \
maintain continuity across a session — but always ground your answer in the context.

RULES:
1. Ground every claim in the provided context. Never invent APIs, functions, or behavior.
2. Include code examples from the context when they help, formatted as fenced code blocks.
3. Cite the sources you used inline as [1], [2], etc., matching the numbered context entries.
4. If the context only partially answers the question, answer what you can and say what \
is not covered.
5. If the context does not answer the question at all, say so honestly — do not guess.
6. Be clear and beginner-friendly: short explanation first, then code, then caveats.
7. Note when a context answer is old and the modern Python 3 idiom differs, but only if \
the context itself shows the newer approach."""

USER_PROMPT = """CONTEXT (Stack Overflow Q&A):
{context}

QUESTION: {question}

Answer the question using the context above."""

# ── Fallback prompt (no context found — answer from general knowledge) ────────

FALLBACK_SYSTEM_PROMPT = """You are an expert Python programming tutor. \
A search of the curated Stack Overflow knowledge base returned no relevant results \
for this question, so you will answer from your own Python expertise.

Be accurate, practical, and include a code example if it helps. \
Do not fabricate Stack Overflow links or cite sources you do not have. \
Answer naturally and helpfully — do not start by saying "I don't know" or \
apologising for lack of context."""

FALLBACK_USER_PROMPT = """QUESTION: {question}

Answer this Python programming question from your general expertise."""


def format_context(docs: list[RetrievedDoc]) -> str:
    blocks = []
    for i, rd in enumerate(docs, start=1):
        meta = rd.document.metadata
        blocks.append(
            f"[{i}] \"{meta.get('title', 'Untitled')}\" "
            f"(question score: {meta.get('question_score', '?')}, "
            f"answer score: {meta.get('answer_score', '?')})\n"
            f"{rd.document.page_content}"
        )
    return "\n\n---\n\n".join(blocks)


def make_sources(docs: list[RetrievedDoc]) -> list[dict[str, Any]]:
    sources = []
    for rd in docs:
        meta = rd.document.metadata
        sources.append(
            {
                "title": meta.get("title", "Untitled"),
                "link": meta.get("link", ""),
                "question_score": int(meta.get("question_score", 0)),
                "answer_score": int(meta.get("answer_score", 0)),
                "snippet": rd.document.page_content[:300],
            }
        )
    return sources


class RAGPipeline:
    """Hybrid RAG pipeline (dense MMR + sparse text + RRF). Built once at startup."""

    def __init__(self) -> None:
        settings = get_settings()
        self.vectorstore = get_vectorstore()

        llm = ChatGoogleGenerativeAI(
            model=settings.generation_model,
            google_api_key=settings.google_api_key,
            temperature=0.2,
        )

        # Grounded chain — uses retrieved Stack Overflow context
        grounded_prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="history", optional=True),
            ("human", USER_PROMPT),
        ])
        self.chain = grounded_prompt | llm | StrOutputParser()

        # Fallback chain — answers from general LLM knowledge when no context found
        fallback_prompt = ChatPromptTemplate.from_messages([
            ("system", FALLBACK_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="history", optional=True),
            ("human", FALLBACK_USER_PROMPT),
        ])
        self.fallback_chain = fallback_prompt | llm | StrOutputParser()

        self.model_name = settings.generation_model

    @staticmethod
    def _build_history(history: list[dict]) -> list[HumanMessage | AIMessage]:
        msgs = []
        for msg in history:
            if msg["role"] == "user":
                msgs.append(HumanMessage(content=msg["content"]))
            else:
                msgs.append(AIMessage(content=msg["content"]))
        return msgs

    async def astream(self, question: str, history: list[dict] | None = None):
        """Yield SSE event dicts: thinking → token* → metadata → done."""
        started = time.perf_counter()
        history_msgs = self._build_history(history or [])

        yield {"type": "thinking", "status": "retrieving"}
        hits = await retrieve(self.vectorstore, question)
        docs = relevant_only(hits)

        if not docs:
            # No Stack Overflow context — answer from general LLM knowledge
            yield {"type": "thinking", "status": "generating"}
            async for chunk in self.fallback_chain.astream({
                "question": question,
                "history": history_msgs,
            }):
                yield {"type": "token", "content": chunk}
            yield {
                "type": "metadata",
                "sources": [],
                "grounded": False,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "model": self.model_name,
            }
            yield {"type": "done"}
            return

        sources = make_sources(docs)
        context = format_context(docs)

        yield {"type": "thinking", "status": "generating"}
        async for chunk in self.chain.astream({
            "context": context,
            "question": question,
            "history": history_msgs,
        }):
            yield {"type": "token", "content": chunk}

        yield {
            "type": "metadata",
            "sources": sources,
            "grounded": True,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "model": self.model_name,
        }
        yield {"type": "done"}

    async def ask(self, question: str, history: list[dict] | None = None) -> dict[str, Any]:
        started = time.perf_counter()
        history_msgs = self._build_history(history or [])
        hits = await retrieve(self.vectorstore, question)
        docs = relevant_only(hits)

        if not docs:
            answer = await self.fallback_chain.ainvoke({
                "question": question,
                "history": history_msgs,
            })
            return {
                "answer": answer,
                "sources": [],
                "grounded": False,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "model": self.model_name,
            }

        answer = await self.chain.ainvoke({
            "context": format_context(docs),
            "question": question,
            "history": history_msgs,
        })
        return {
            "answer": answer,
            "sources": make_sources(docs),
            "grounded": True,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "model": self.model_name,
        }
