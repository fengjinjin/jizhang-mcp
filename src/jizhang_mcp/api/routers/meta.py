from fastapi import APIRouter

from jizhang_mcp.constants import DEFAULT_EXPENSE_PRIMARIES, DEFAULT_INCOME_PRIMARIES

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/categories")
async def meta_categories():
    return {
        "expense": [{"name": n, "sort_order": i} for i, n in enumerate(DEFAULT_EXPENSE_PRIMARIES)],
        "income": [{"name": n, "sort_order": i} for i, n in enumerate(DEFAULT_INCOME_PRIMARIES)],
    }
