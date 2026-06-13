import time
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import get_settings
from app.rag.retriever import RetrievedDoc, relevant_only, retrieve
from app.rag.vectorstore import get_vectorstore

SYSTEM_PROMPT = """You are a Python programming tutor for data science learners. \
You answer questions using ONLY the Stack Overflow Q&A context provided below.

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

Answer the question using only the context above."""

OUT_OF_SCOPE_ANSWER = (
    "I couldn't find anything relevant to that in my knowledge base, which covers "
    "Python programming questions from Stack Overflow. I can only answer questions "
    "grounded in that data, so rather than guess I'll pass on this one. "
    "Try rephrasing it as a Python programming question!"
)


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
    """Retrieval-augmented answer pipeline. Built once at app startup."""

    def __init__(self) -> None:
        settings = get_settings()
        self.vectorstore = get_vectorstore()
        llm = ChatGoogleGenerativeAI(
            model=settings.generation_model,
            google_api_key=settings.google_api_key,
            temperature=0.2,
        )
        prompt = ChatPromptTemplate.from_messages(
            [("system", SYSTEM_PROMPT), ("human", USER_PROMPT)]
        )
        self.chain = prompt | llm | StrOutputParser()
        self.model_name = settings.generation_model

    async def astream(self, question: str):
        """Yield SSE event dicts: thinking → token* → metadata → done."""
        started = time.perf_counter()

        yield {"type": "thinking", "status": "retrieving"}
        hits = retrieve(self.vectorstore, question)
        docs = relevant_only(hits)

        if not docs:
            yield {"type": "thinking", "status": "generating"}
            for char in OUT_OF_SCOPE_ANSWER:
                yield {"type": "token", "content": char}
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
        async for chunk in self.chain.astream({"context": context, "question": question}):
            yield {"type": "token", "content": chunk}

        yield {
            "type": "metadata",
            "sources": sources,
            "grounded": True,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "model": self.model_name,
        }
        yield {"type": "done"}

    async def ask(self, question: str) -> dict[str, Any]:
        started = time.perf_counter()
        hits = retrieve(self.vectorstore, question)
        docs = relevant_only(hits)

        if not docs:
            return {
                "answer": OUT_OF_SCOPE_ANSWER,
                "sources": [],
                "grounded": False,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "model": self.model_name,
            }

        answer = await self.chain.ainvoke(
            {"context": format_context(docs), "question": question}
        )
        return {
            "answer": answer,
            "sources": make_sources(docs),
            "grounded": True,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "model": self.model_name,
        }
