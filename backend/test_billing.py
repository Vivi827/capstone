from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import main
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
