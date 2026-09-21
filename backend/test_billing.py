import asyncio
from datetime import datetime
from threading import Event
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import main
from lib import billing
from lib.kakaopay import ApprovedResponse, KakaoPayError, ReadyResponse, verify_payment
from lib.billing import BillingError, entitled, return_url


def test_unsigned_mock_webhook_cannot_grant_pro(monkeypatch):
    def forbidden():
        pytest.fail("Unsigned webhook must not reach the database")

    monkeypatch.setattr(main, "get_supabase", forbidden)
    response = TestClient(main.app).post("/api/webhooks/billing/mock", json={
        "event_id": "forged", "user_id": "victim", "action": "activate",
    })
    assert response.status_code == 404


@pytest.mark.parametrize("url", [
    "https://online-payment.kakaopay.com/production/payment/abc",
    "https://online-payment.kakaopay.com.attacker.example/mockup/abc",
    "http://online-payment.kakaopay.com/mockup/abc",
    "https://attacker@online-payment.kakaopay.com/mockup/abc",
])
def test_gateway_only_accepts_sandbox_checkout_urls(url):
    with pytest.raises(ValidationError):
        ReadyResponse(tid="test", next_redirect_pc_url=url,
                      next_redirect_mobile_url=url, created_at=datetime.now())


@pytest.mark.parametrize("field,value", [
    ("cid", "LIVE_CID"), ("tid", "other-tid"),
    ("partner_order_id", "other-order"), ("partner_user_id", "other-user"),
    ("amount", {"total": 1}),
])
def test_gateway_rejects_mismatched_receipts(field, value):
    receipt = dict(tid="tid", cid="TCSUBSCRIP", sid="sid", partner_order_id="order",
                   partner_user_id="user", amount={"total": 9900}, approved_at=datetime.now())
    saved = dict(tid="tid", id="order", partner_user_id="user", amount=9900)
    verify_payment(ApprovedResponse(**receipt), saved)
    receipt[field] = value
    with pytest.raises(KakaoPayError):
        verify_payment(ApprovedResponse(**receipt), saved)


def test_trial_registration_without_amount_requires_order_verification():
    receipt = ApprovedResponse(tid="tid", cid="TCSUBSCRIP", sid="sid",
                               partner_order_id="order", partner_user_id="user", approved_at=datetime.now())
    assert receipt.amount is None
    with pytest.raises(KakaoPayError):
        verify_payment(receipt, dict(tid="tid", id="order", partner_user_id="user", amount=0))


@pytest.mark.parametrize("row", [None, {"entitled": True, "status": "active"},
    {"entitled": True, "status": "active", "current_period_end": "2020-01-01T00:00:00Z"},
    {"entitled": True, "status": "revoked", "current_period_end": "2100-01-01T00:00:00Z"}])
def test_expired_or_unverified_subscription_does_not_grant_pro(row):
    assert not entitled(row)


@pytest.mark.parametrize("url", ["https://attacker.example/settings/plans?checkout=success",
    "https://yourpally.app@attacker.example/settings/plans?checkout=success",
    "https://yourpally.app/settings/plans?checkout=success&next=https://attacker.example",
    "https://yourpally.app/other?checkout=success"])
def test_checkout_return_url_is_allowlisted(url):
    with pytest.raises(BillingError):
        return_url(url, "success")


def test_active_trial_grants_pro():
    assert entitled({"entitled": True, "status": "trialing", "current_period_end": "2100-01-01T00:00:00Z"})


def _worker_receipt(order_id="order"):
    return ApprovedResponse(tid="tid", cid="TCSUBSCRIP", sid="sid",
                            partner_order_id=order_id, partner_user_id="user",
                            amount={"total": 9900}, approved_at=datetime.now())


def test_stopped_tick_does_not_start_database_or_provider_work(monkeypatch):
    stop = Event()
    stop.set()
    db = Mock()
    execute = Mock(side_effect=AssertionError("Stopped worker must not query the database"))
    monkeypatch.setattr(billing, "execute", execute)
    billing.tick(db, should_stop=stop.is_set)
    db.table.assert_not_called()
    db.rpc.assert_not_called()
    execute.assert_not_called()


@pytest.mark.parametrize("fails", [False, True])
def test_shutdown_finishes_current_recovery_without_starting_next(monkeypatch, fails):
    stop = Event()
    db = Mock()
    rows = [{"id": order_id, "receipt": _worker_receipt(order_id).model_dump(mode="json")}
            for order_id in ("first", "second")]
    execute = Mock(return_value=rows)
    monkeypatch.setattr(billing, "execute", execute)

    def finish(_db, saved, _receipt):
        assert saved["id"] == "first"
        stop.set()
        if fails:
            raise BillingError("Simulated recovery failure")

    finish_call = Mock(side_effect=finish)
    monkeypatch.setattr(billing, "finish", finish_call)
    billing.tick(db, should_stop=stop.is_set)
    finish_call.assert_called_once()
    db.table.assert_called_once_with("billing_orders")
    db.rpc.assert_not_called()
    execute.assert_called_once()


def test_shutdown_during_recovery_query_does_not_start_recovery(monkeypatch):
    stop = Event()
    db = Mock()

    def execute(_query):
        stop.set()
        return [{"id": "order", "receipt": _worker_receipt().model_dump(mode="json")}]

    monkeypatch.setattr(billing, "execute", execute)
    finish_call = Mock()
    monkeypatch.setattr(billing, "finish", finish_call)
    billing.tick(db, should_stop=stop.is_set)
    finish_call.assert_not_called()
    db.table.assert_called_once_with("billing_orders")
    db.rpc.assert_not_called()


@pytest.mark.parametrize("stop_when", ["query", "deactivate", "deactivate_failure"])
def test_shutdown_does_not_start_next_deactivation_or_renewal(monkeypatch, stop_when):
    stop = Event()
    db = Mock()
    monkeypatch.setattr(billing, "recover_receipts", Mock())
    accounts = [{"user_id": "first", "sid": "first-sid"},
                {"user_id": "second", "sid": "second-sid"}]
    database_calls = []

    def execute(_query):
        database_calls.append(_query)
        if len(database_calls) == 1:
            if stop_when == "query":
                stop.set()
            return accounts
        return []

    def deactivate(sid):
        assert sid == "first-sid"
        stop.set()
        if stop_when == "deactivate_failure":
            raise KakaoPayError("Simulated deactivation failure")

    monkeypatch.setattr(billing, "execute", execute)
    deactivate_call = Mock(side_effect=deactivate)
    monkeypatch.setattr(billing.kakaopay, "deactivate", deactivate_call)
    billing.tick(db, should_stop=stop.is_set)
    assert deactivate_call.call_count == (0 if stop_when == "query" else 1)
    assert len(database_calls) == (2 if stop_when == "deactivate" else 1)
    db.rpc.assert_not_called()


@pytest.mark.parametrize("stop_when", ["claim", "charge", "receipt", "finish"])
def test_shutdown_drains_claimed_renewal_before_stopping(monkeypatch, stop_when):
    stop = Event()
    db = Mock()
    monkeypatch.setattr(billing, "recover_receipts", Mock())
    saved = {"id": "order", "sid": "sid", "partner_user_id": "user", "amount": 9900}
    events = []

    def execute(query):
        if query is db.rpc.return_value:
            events.append("claim")
            if stop_when == "claim":
                stop.set()
            return saved
        if "charge" in events:
            events.append("receipt")
            if stop_when == "receipt":
                stop.set()
        return []

    def renew(_payload):
        events.append("charge")
        if stop_when == "charge":
            stop.set()
        return _worker_receipt()

    def finish(_db, _saved, _receipt):
        events.append("finish")
        if stop_when == "finish":
            stop.set()

    monkeypatch.setattr(billing, "execute", execute)
    monkeypatch.setattr(billing.kakaopay, "renew", renew)
    monkeypatch.setattr(billing, "finish", finish)
    billing.tick(db, should_stop=stop.is_set)
    assert events == ["claim", "charge", "receipt", "finish"]
    db.rpc.assert_called_once_with("billing_claim_renewal", {})
    db.table.return_value.update.assert_called_once()


def test_shutdown_records_claimed_renewal_failure_without_starting_next(monkeypatch):
    stop = Event()
    db = Mock()
    monkeypatch.setattr(billing, "recover_receipts", Mock())
    saved = {"id": "order", "sid": "sid", "partner_user_id": "user", "amount": 9900}

    def execute(query):
        return saved if query is db.rpc.return_value else []

    def renew(_payload):
        stop.set()
        raise KakaoPayError("Simulated charge failure")

    monkeypatch.setattr(billing, "execute", execute)
    monkeypatch.setattr(billing.kakaopay, "renew", renew)
    billing.tick(db, should_stop=stop.is_set)
    db.rpc.assert_called_once_with("billing_claim_renewal", {})
    db.table.return_value.update.assert_called_once_with({"status": "uncertain"})


def test_tick_without_stop_callback_keeps_existing_direct_call_contract(monkeypatch):
    db = Mock()
    monkeypatch.setattr(billing, "recover_receipts", Mock())
    monkeypatch.setattr(billing, "execute", Mock(side_effect=[[], None]))
    billing.tick(db)
    db.rpc.assert_called_once_with("billing_claim_renewal", {})


def test_worker_passes_stop_predicate_to_threaded_tick(monkeypatch):
    async def scenario():
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        db = object()

        def tick(received_db, should_stop):
            assert received_db is db
            assert not should_stop()
            loop.call_soon_threadsafe(stop.set)

        tick_call = Mock(side_effect=tick)
        monkeypatch.setattr(billing, "tick", tick_call)
        await asyncio.wait_for(billing.worker(lambda: db, stop), timeout=2)
        tick_call.assert_called_once()
        assert stop.is_set()

    asyncio.run(scenario())
