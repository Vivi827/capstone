"""Caller-scoped, read-only billing overview contract tests."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import main
from lib import billing


CALLER = "e34fc812-176e-4b19-b600-18c9c077b8ec"
OTHER = "d167bce7-c262-40cf-b9b2-d33994855803"
NOW = datetime.now(timezone.utc)


def order(number=1, **changes):
    value = {
        "id": str(UUID(int=number)), "user_id": CALLER,
        "product_id": "pro_monthly", "amount": 9900,
        "kind": "initial", "trial_days": 0, "status": "approved",
        "created_at": NOW.isoformat(), "approved_at": NOW.isoformat(),
        "expires_at": (NOW + timedelta(minutes=15)).isoformat(),
        "sid": "private-sid", "tid": "private-tid",
        "receipt": {"private": "receipt"}, "callback_state": "private-state",
        "checkout_url": "https://private-checkout.example",
    }
    value.update(changes)
    return value


def subscription(**changes):
    value = {
        "user_id": CALLER, "status": "active", "entitled": True,
        "product_id": "pro_monthly", "will_renew": False,
        "current_period_end": (NOW + timedelta(days=10)).isoformat(),
        "updated_at": NOW.isoformat(),
    }
    value.update(changes)
    return value


class Query:
    def __init__(self, db, table):
        self.db = db
        self.table = table
        self.fields = "*"
        self.filters = []
        self.sorts = []
        self.row_limit = None
        self.pending_filter = None

    def select(self, fields):
        self.fields = fields
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def order(self, field, desc=False):
        self.sorts.append((field, desc))
        return self

    def limit(self, value):
        self.row_limit = value
        return self

    def or_(self, expression):
        prefix = "status.in.(processing,uncertain),and(status.in.(preparing,ready),expires_at.gt."
        assert expression.startswith(prefix)
        assert expression.endswith(")")
        self.pending_filter = billing.timestamp(expression[len(prefix):-1])
        return self

    def execute(self):
        self.db.executed.append(self)
        assert ("user_id", CALLER) in self.filters
        rows = list(self.db.rows[self.table])
        for field, value in self.filters:
            rows = [row for row in rows if row[field] == value]
        if self.pending_filter is not None:
            rows = [row for row in rows if row["status"] in ("processing", "uncertain")
                    or (row["status"] in ("preparing", "ready")
                        and billing.timestamp(row["expires_at"]) > self.pending_filter)]
        for field, reverse in reversed(self.sorts):
            rows.sort(key=lambda row: row[field], reverse=reverse)
        if self.row_limit is not None:
            rows = rows[:self.row_limit]
        if self.fields != "*":
            rows = [{field: row[field] for field in self.fields.split(",")} for row in rows]
        return SimpleNamespace(data=rows)


class Database:
    def __init__(self, orders=(), subscriptions=(), accounts=()):
        self.rows = {
            "billing_orders": list(orders), "subscriptions": list(subscriptions),
            "billing_accounts": list(accounts),
        }
        self.executed = []

    def table(self, name):
        return Query(self, name)


@pytest.fixture
def caller_client(monkeypatch):
    db = Database()
    monkeypatch.setattr(main, "get_supabase", lambda: db)
    main.app.dependency_overrides[main.get_current_user_id] = lambda: CALLER
    forbidden = Mock(side_effect=AssertionError("Overview must not mutate payments"))
    monkeypatch.setattr(billing, "recover_receipts", forbidden)
    monkeypatch.setattr(billing, "checkout", forbidden)
    monkeypatch.setattr(billing, "cancel_subscription", forbidden)
    try:
        yield TestClient(main.app), db
    finally:
        del main.app.dependency_overrides[main.get_current_user_id]


def test_overview_requires_authentication_before_database_access(monkeypatch):
    forbidden = Mock(side_effect=AssertionError("Unauthenticated database access"))
    monkeypatch.setattr(main, "get_supabase", forbidden)
    response = TestClient(main.app).get("/api/billing/overview")
    assert response.status_code == 401
    forbidden.assert_not_called()


def test_empty_overview_is_explicit_and_not_cached(caller_client):
    client, db = caller_client
    response = client.get("/api/billing/overview")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "subscription": main._subscription_to_response(None),
        "history": [], "history_has_more": False, "pending_order": None,
        "checkout_blocked_reason": None,
    }
    assert len(db.executed) == 4


@pytest.mark.parametrize("total,has_more", [(0, False), (50, False), (51, True), (60, True)])
def test_history_is_approved_owned_bounded_and_stably_ordered(caller_client, total, has_more):
    client, db = caller_client
    db.rows["billing_orders"] = [order(number) for number in range(1, total + 1)] + [
        order(100, user_id=OTHER), order(101, status="failed"), order(102, status="canceled"),
    ]
    db.rows["subscriptions"] = [subscription(user_id=OTHER)]
    db.rows["billing_accounts"] = [{
        "user_id": OTHER, "renewal_enabled": True, "deactivation_pending": True,
    }]
    payload = client.get("/api/billing/overview?user_id=" + OTHER).json()
    assert payload["history_has_more"] is has_more
    assert len(payload["history"]) == min(50, total)
    assert [row["id"] for row in payload["history"]] == [
        str(UUID(int=number)) for number in range(total, max(0, total - 50), -1)
    ]
    assert payload["checkout_blocked_reason"] is None
    assert payload["subscription"]["entitled"] is False
    history_query = next(query for query in db.executed if ("status", "approved") in query.filters)
    assert history_query.row_limit == 51
    assert history_query.sorts == [("created_at", True), ("id", True)]
    for query in db.executed:
        assert ("user_id", CALLER) in query.filters
        if query.table != "subscriptions":
            assert query.fields != "*"


def test_history_exposes_only_safe_fields_and_zero_won_trial(caller_client):
    client, db = caller_client
    db.rows["billing_orders"] = [order(product_id="pro_yearly", amount=0, trial_days=7)]
    payload = client.get("/api/billing/overview").json()
    assert set(payload["history"][0]) == {
        "id", "product_id", "amount", "currency", "kind", "trial_days", "status",
        "created_at", "approved_at",
    }
    assert payload["history"][0]["amount"] == 0
    assert payload["history"][0]["trial_days"] == 7
    assert payload["history"][0]["currency"] == "KRW"
    for secret in ("private-sid", "private-tid", "private-state", "private-checkout", CALLER):
        assert secret not in str(payload)


@pytest.mark.parametrize("status,expired,expected", [
    ("preparing", False, True), ("ready", False, True),
    ("preparing", True, False), ("ready", True, False),
    ("processing", False, True), ("processing", True, True),
    ("uncertain", False, True), ("uncertain", True, True),
    ("approved", False, False), ("failed", False, False), ("canceled", False, False),
])
def test_pending_order_uses_checkout_expiration_rules(caller_client, status, expired, expected):
    client, db = caller_client
    expiry = NOW + timedelta(days=-1 if expired else 1)
    db.rows["billing_orders"] = [order(status=status, expires_at=expiry.isoformat())]
    payload = client.get("/api/billing/overview").json()
    assert (payload["pending_order"] is not None) is expected
    assert payload["checkout_blocked_reason"] == ("payment_pending" if expected else None)
    if expected:
        assert set(payload["pending_order"]) == {
            "id", "product_id", "amount", "currency", "kind", "trial_days", "status",
            "created_at", "expires_at",
        }


def test_latest_blocking_order_is_found_without_limiting_before_filter(caller_client):
    client, db = caller_client
    db.rows["billing_orders"] = [
        order(1, status="uncertain", created_at=(NOW - timedelta(days=2)).isoformat()),
        order(2, status="ready", expires_at=(NOW - timedelta(minutes=1)).isoformat()),
        order(3, status="processing", user_id=OTHER),
    ]
    assert client.get("/api/billing/overview").json()["pending_order"]["id"] == str(UUID(int=1))


@pytest.mark.parametrize("entitled,pending,deactivation,renewal,expected", [
    (True, True, True, True, "payment_pending"),
    (True, False, True, True, "subscription_active"),
    (True, False, False, False, "subscription_active"),
    (False, False, True, True, "deactivation_pending"),
    (False, False, True, False, "deactivation_pending"),
    (False, False, False, True, "renewal_active"),
    (False, False, False, False, None),
])
def test_checkout_guard_prioritizes_pending_entitlement_and_account_flags(
    caller_client, entitled, pending, deactivation, renewal, expected,
):
    client, db = caller_client
    db.rows["subscriptions"] = [subscription(current_period_end=(
        NOW + timedelta(days=1 if entitled else -1)
    ).isoformat())]
    db.rows["billing_accounts"] = [{
        "user_id": CALLER, "renewal_enabled": renewal, "deactivation_pending": deactivation,
    }]
    if pending:
        db.rows["billing_orders"] = [order(status="processing")]
    payload = client.get("/api/billing/overview").json()
    assert payload["subscription"]["entitled"] is entitled
    assert payload["checkout_blocked_reason"] == expected


@pytest.mark.parametrize("changes", [
    {"id": "not-a-uuid"}, {"amount": -1}, {"amount": "9900"},
    {"product_id": "unknown"}, {"kind": "refund"}, {"trial_days": 30},
    {"approved_at": None}, {"created_at": "not-a-date"},
])
def test_invalid_stored_history_does_not_become_a_successful_response(caller_client, changes):
    client, db = caller_client
    db.rows["billing_orders"] = [order(**changes)]
    with pytest.raises(ValidationError):
        client.get("/api/billing/overview")


def test_invalid_account_flags_do_not_enable_checkout(caller_client):
    client, db = caller_client
    db.rows["billing_accounts"] = [{
        "user_id": CALLER, "renewal_enabled": "false", "deactivation_pending": False,
    }]
    with pytest.raises(ValidationError):
        client.get("/api/billing/overview")


def test_database_failure_does_not_return_empty_billing_success(caller_client, monkeypatch):
    client, _ = caller_client
    monkeypatch.setattr(billing, "execute", Mock(side_effect=billing.BillingError("조회 실패", 503)))
    response = client.get("/api/billing/overview")
    assert response.status_code == 503
    assert "history" not in response.json()
