"""AI-assisted OD document intelligence (deterministic core; LLM assistance added in Phase 5)."""
from . import od_service as svc


def explain_eligibility(result: dict) -> str:
    return svc.explain(result)


def analyse_document(document_id: int) -> None:
    """Placeholder until document analysis is implemented."""
    return None
