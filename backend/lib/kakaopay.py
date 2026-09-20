"""KakaoPay sandbox gateway. This module cannot submit live payments."""

import logging
import os
from datetime import datetime
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator


TEST_CID = "TCSUBSCRIP"
API_ORIGIN = "https://open-api.kakaopay.com"


class KakaoPayError(Exception):
    """Safe gateway error; response bodies and credentials are never exposed."""


class ReadyResponse(BaseModel):
    tid: str = Field(min_length=1, max_length=100)
    next_redirect_pc_url: str
    next_redirect_mobile_url: str
    created_at: datetime

    @field_validator("next_redirect_pc_url", "next_redirect_mobile_url")
    @classmethod
    def sandbox_url(cls, value: str) -> str:
        url = urlsplit(value)
        if (url.scheme != "https" or url.hostname != "online-payment.kakaopay.com"
                or url.port not in (None, 443) or url.username or url.password
                or not url.path.startswith("/mockup/")):
            raise ValueError("Unexpected sandbox checkout URL")
        return value


class Amount(BaseModel):
    total: int = Field(strict=True, ge=0)


class ApprovedResponse(BaseModel):
    tid: str
    cid: str
    partner_order_id: str
    partner_user_id: str
    sid: str = Field(min_length=1)
    # SID-only (0 KRW) registration omits amount in the actual sandbox response.
    amount: Amount | None = None
    approved_at: datetime


class OrderResponse(BaseModel):
    tid: str
    cid: str
    partner_order_id: str
    partner_user_id: str
    status: str
    amount: Amount
    approved_at: datetime | None = None


class SubscriptionState(BaseModel):
    cid: str
    sid: str
    status: str


def _request(endpoint: str, payload: dict, schema: type[BaseModel]):
    key = os.getenv("KAKAOPAY_SECRET_KEY_DEV", "")
    if not key:
        raise KakaoPayError("카카오페이 테스트 결제 설정이 필요해요.")
    try:
        # Never retry payment mutations. Order lookup cannot restore a lost SID;
        # results without a durable receipt may require manual reconciliation.
        response = httpx.post(
            f"{API_ORIGIN}/online/v1/payment/{endpoint}",
            headers={"Authorization": f"SECRET_KEY {key}"},
            json={**payload, "cid": TEST_CID},
            timeout=20,
        )
        response.raise_for_status()
        return schema.model_validate(response.json())
    except (httpx.HTTPError, ValidationError, ValueError) as exc:
        logging.error("KakaoPay sandbox %s failed (%s)", endpoint, type(exc).__name__)
        raise KakaoPayError("결제 상태를 확인하지 못했어요. 잠시 후 다시 확인해 주세요.") from exc


def ready(payload: dict) -> ReadyResponse:
    return _request("ready", payload, ReadyResponse)


def approve(payload: dict) -> ApprovedResponse:
    return _request("approve", payload, ApprovedResponse)


def order(tid: str) -> OrderResponse:
    return _request("order", {"tid": tid}, OrderResponse)


def renew(payload: dict) -> ApprovedResponse:
    return _request("subscription", payload, ApprovedResponse)


def deactivate(sid: str) -> SubscriptionState:
    result = _request("manage/subscription/status", {"sid": sid}, SubscriptionState)
    if result.status != "INACTIVE":
        result = _request("manage/subscription/inactive", {"sid": sid}, SubscriptionState)
    if result.cid != TEST_CID or result.sid != sid or result.status != "INACTIVE":
        raise KakaoPayError("정기결제 해지를 확인하지 못했어요.")
    return result


def verify_payment(result: ApprovedResponse | OrderResponse, saved: dict) -> None:
    if (result.cid != TEST_CID or result.tid != saved["tid"]
            or result.partner_order_id != saved["id"]
            or result.partner_user_id != saved["partner_user_id"]
            or result.amount is None or result.amount.total != saved["amount"]):
        logging.error("KakaoPay sandbox receipt does not match the stored order")
        raise KakaoPayError("결제 정보가 일치하지 않아 처리하지 못했어요.")
