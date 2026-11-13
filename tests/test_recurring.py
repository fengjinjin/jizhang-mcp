import pytest

from jizhang_mcp.services.recurring_service import next_occurrence, today_in_rule_tz_temp


@pytest.mark.asyncio
async def test_recurring_monthly_add(api_client, user_with_key):
    token = user_with_key["token"]
    resp = await api_client.post(
        "/api/v1/recurring/rules",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "房租",
            "direction": "expense",
            "amount": 2500,
            "category": "住房-房租",
            "frequency": "monthly",
            "day_of_month": 1,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["frequency"] == "monthly"


@pytest.mark.parametrize(
    "month_of_year,day_of_month",
    [(2, 31), (4, 31)],
)
@pytest.mark.asyncio
async def test_yearly_invalid_calendar_days_return_400(
    api_client, user_with_key, month_of_year, day_of_month
):
    token = user_with_key["token"]
    resp = await api_client.post(
        "/api/v1/recurring/rules",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "无效日",
            "direction": "expense",
            "amount": 1,
            "category": "餐饮",
            "frequency": "yearly",
            "month_of_year": month_of_year,
            "day_of_month": day_of_month,
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_monthly_today_catch_up_creates_ledger_and_advances_next(api_client, user_with_key):
    token = user_with_key["token"]
    today = today_in_rule_tz_temp("Asia/Shanghai")
    resp = await api_client.post(
        "/api/v1/recurring/rules",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "每月今日",
            "direction": "expense",
            "amount": 50,
            "category": "餐饮",
            "frequency": "monthly",
            "catch_up_today": True,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["day_of_month"] == today.day
    assert body["last_run_date"] == today.isoformat()
    expected_next = next_occurrence(
        type(
            "R",
            (),
            {
                "frequency": "monthly",
                "day_of_week": None,
                "day_of_month": today.day,
                "month_of_year": None,
            },
        )(),
        today,
    )
    assert body["next_run_date"] == expected_next.isoformat()

    entries = await api_client.get(
        "/api/v1/ledger/entries",
        headers={"Authorization": f"Bearer {token}"},
        params={"recurring_rule_id": body["id"], "limit": 5},
    )
    assert entries.status_code == 200
    items = entries.json()["items"]
    assert len(items) == 1
    assert items[0]["scheduled_for_date"] == today.isoformat()
