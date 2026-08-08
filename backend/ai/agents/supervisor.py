"""
LangGraph supervisor — orchestrates Security + Code Review agents.

Graph:
  START → supervisor → [security_node | code_review_node] → supervisor → END

The supervisor inspects finding categories and routes accordingly.
"""
from __future__ import annotations
import json
import logging
from typing import Any, List, Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from ai.agents.context import build_context
from ai.agents.security_agent import run_security_agent
from ai.agents.code_review_agent import run_code_review_agent
from analysis.rules.base import Finding

logger = logging.getLogger(__name__)


# ── State ─────────────────────────────────────────────────────────────────────

class ReviewState(TypedDict):
    modified_files: List[str]        # files directly modified in PR
    file_contents: dict              # {file_path: source}
    security_results: List[dict] | None  # enriched by SecurityAgent, None means not run
    code_review_results: List[dict] | None  # enriched by CodeReviewAgent, None means not run
    routed_security: bool
    routed_code_review: bool
    done: bool
    loop_count: int                  # guard against infinite loops
    repo_name: Optional[str]         # repository full name for isolated Chroma RAG querying
    has_ci_failure: bool             # flag indicating CI failed
    ci_logs: str                     # raw CI traceback/execution logs
    ci_results: List[dict] | None    # parsed findings from CI Agent
    routed_ci: bool                  # routing flag for CI node


# ── Nodes ─────────────────────────────────────────────────────────────────────

def supervisor_node(state: ReviewState) -> ReviewState:
    """Decide which agents to invoke and track iterations."""
    state = dict(state)
    state["routed_security"] = True
    state["routed_code_review"] = True
    state["loop_count"] = state.get("loop_count", 0) + 1
    return state  # type: ignore[return-value]


def format_code_with_line_numbers(file_contents: dict[str, str]) -> dict[str, str]:
    """Prefix each line of code with its 1-based line number for LLM context."""
    formatted = {}
    for path, code in file_contents.items():
        lines = code.splitlines()
        formatted[path] = "\n".join(f"{i+1}: {line}" for i, line in enumerate(lines))
    return formatted


def security_node(state: ReviewState) -> ReviewState:
    """Run the Security agent on modified files."""
    numbered_context = format_code_with_line_numbers(state.get("file_contents", {}))
    context_payload = json.dumps({
        "modified_files": state.get("modified_files", []),
        "code_context": numbered_context,
    })
    results = run_security_agent(context_payload)
    state = dict(state)
    state["security_results"] = results
    return state  # type: ignore[return-value]


def code_review_node(state: ReviewState) -> ReviewState:
    """Run the Code Review agent on modified files with Chroma RAG architectural context."""
    numbered_context = format_code_with_line_numbers(state.get("file_contents", {}))
    
    # Query Chroma DB vector collections for architectural signatures
    repo_name = state.get("repo_name")
    architecture_context = ""
    if repo_name:
        try:
            from analysis.parser.architecture_sync import query_architecture_context, _chroma_manager
            contexts = []
            file_contents = state.get("file_contents", {})
            for fpath in state.get("modified_files", []):
                snippet = file_contents.get(fpath, fpath)
                # Pass first 600 chars of actual file code to compute vector embedding similarity
                ctx = query_architecture_context(repo_name, snippet[:600], n_results=3)
                if ctx and "No matching architecture context" not in ctx:
                    contexts.append(f"Architectural Signatures for {fpath}:\n{ctx}")
            if contexts:
                architecture_context = "\n\n---\n\n".join(contexts)
            else:
                # Fallback: Retrieve overall repository collection documents if available
                try:
                    coll = _chroma_manager.get_collection(repo_name)
                    docs = coll.get()["documents"]
                    if docs:
                        architecture_context = "Repository Architectural Baseline Signatures:\n" + "\n\n".join(docs[:5])
                except Exception:
                    pass
        except Exception as e:
            logger.warning("Failed querying architecture context during review: %s", e)

    context_payload = json.dumps({
        "modified_files": state.get("modified_files", []),
        "code_context": numbered_context,
        "architecture_context": architecture_context,
    })
    results = run_code_review_agent(context_payload)
    state = dict(state)
    state["code_review_results"] = results
    return state  # type: ignore[return-value]


def finish_node(state: ReviewState) -> ReviewState:
    state = dict(state)
    state["done"] = True
    return state  # type: ignore[return-value]


def ci_node(state: ReviewState) -> ReviewState:
    """Run the CI/CD Log Analysis agent on build failure logs."""
    from ai.agents.ci_agent import run_ci_agent
    results = run_ci_agent(state.get("ci_logs", ""))
    
    # Map raw finding models to JSON dicts for LangGraph state serialization compatibility
    dict_results = [
        {
            "rule_id": f.rule_id,
            "rule_name": f.rule_name,
            "category": f.category,
            "severity": f.severity,
            "confidence": f.confidence,
            "file_path": f.file_path,
            "line_number": f.line_number,
            "code_snippet": f.code_snippet,
            "message": f.message,
            "suggestion": f.suggestion,
            "source": f.source,
        }
        for f in results
    ]
    state = dict(state)
    state["ci_results"] = dict_results
    state["routed_ci"] = True
    return state  # type: ignore[return-value]


# ── Routing ───────────────────────────────────────────────────────────────────

def route_after_supervisor(
    state: ReviewState,
) -> Literal["ci_node", "security_node", "code_review_node", "finish"]:
    loop_count = state.get("loop_count", 0)
    if loop_count > 10:
        logger.warning("   ⚠️ [Supervisor] Infinite loop guard triggered! Exceeded 10 iterations. Forcing termination...")
        return "finish"

    if state.get("has_ci_failure"):
        if state.get("ci_results") is None:
            return "ci_node"
        return "finish"

    if state.get("routed_security") and state.get("security_results") is None:
        return "security_node"
    if state.get("routed_code_review") and state.get("code_review_results") is None:
        return "code_review_node"
    return "finish"


# ── Build graph ───────────────────────────────────────────────────────────────

def build_graph() -> Any:
    g = StateGraph(ReviewState)

    g.add_node("supervisor", supervisor_node)
    g.add_node("ci_node", ci_node)
    g.add_node("security_node", security_node)
    g.add_node("code_review_node", code_review_node)
    g.add_node("finish", finish_node)

    g.add_edge(START, "supervisor")
    g.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "ci_node": "ci_node",
            "security_node": "security_node",
            "code_review_node": "code_review_node",
            "finish": "finish",
        },
    )
    # After each specialist agent, go back to supervisor to check if more routing needed
    g.add_edge("ci_node", "supervisor")
    g.add_edge("security_node", "supervisor")
    g.add_edge("code_review_node", "supervisor")
    g.add_edge("finish", END)

    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


# ── Public API ────────────────────────────────────────────────────────────────

def run_supervisor(
    modified_files: List[str],
    file_contents: dict[str, str],
    repo_name: Optional[str] = None,
    has_ci_failure: bool = False,
    ci_logs: str = "",
) -> dict[str, List[dict]]:
    """
    Run the full LangGraph supervisor pipeline for direct code review.

    Returns:
        {
          "ci_results": [...],
          "security_results": [...],
          "code_review_results": [...],
        }
    """
    if not modified_files:
        return {"ci_results": [], "security_results": [], "code_review_results": []}

    initial_state: ReviewState = {
        "modified_files": modified_files,
        "file_contents": file_contents,
        "security_results": None,
        "code_review_results": None,
        "routed_security": False,
        "routed_code_review": False,
        "done": False,
        "loop_count": 0,
        "repo_name": repo_name,
        "has_ci_failure": has_ci_failure,
        "ci_logs": ci_logs,
        "ci_results": None,
        "routed_ci": False,
    }

    graph = get_graph()
    try:
        final_state = graph.invoke(initial_state)
        return {
            "ci_results": final_state.get("ci_results") or [],
            "security_results": final_state.get("security_results") or [],
            "code_review_results": final_state.get("code_review_results") or [],
        }
    except Exception as exc:
        logger.error("Supervisor graph failed: %s", exc)
        raise exc
