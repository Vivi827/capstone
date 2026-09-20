"""Persisted sandbox subscription orchestration and renewal worker."""

import asyncio
import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from lib import kakaopay


class BillingError(Exception):
    def __init__(self, message: str, status: int = 503):
        self.status = status
        super().__init__(message)


def execute(query):
    try:
        return query.execute().data
    except Exception as exc:
        logging.error("Billing persistence failed (%s, code=%s)", type(exc).__name__, getattr(exc, "code", "unknown"))
        message = str(getattr(exc, "message", ""))
        conflicts = {
            "subscription_active": "이미 이용 중인 구독이 있어요.",
            "checkout_pending": "진행 중인 결제가 있어요. 기존 결제창에서 완료하거나 취소해 주세요.",
            "payment_processing": "결제 처리 중이에요. 잠시 후 다시 시도해 주세요.",
            "idempotency_conflict": "같은 요청으로 다른 상품을 결제할 수 없어요.",
        }
        if message in conflicts:
            raise BillingError(conflicts[message], 409) from exc
        raise BillingError("결제 정보를 저장하지 못했어요. 잠시 후 다시 확인해 주세요.") from exc


def read_order(sb, order_id: str) -> dict:
    rows = execute(sb.table("billing_orders").select("*").eq("id", order_id))
    if not rows:
        raise BillingError("결제 내역을 찾지 못했어요.", 404)
    return rows[0]


def timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone(timedelta(hours=9)))
    return result.astimezone(timezone.utc)


def entitled(row: dict | None) -> bool:
    return bool(row and row.get("entitled") and row.get("status") in ("active", "trialing")
                and row.get("current_period_end")
                and timestamp(row["current_period_end"]) > datetime.now(timezone.utc))


def return_url(value: str, outcome: str) -> str:
    origins = os.getenv("BILLING_FRONTEND_ORIGINS", "https://yourpally.app,http://localhost:3000").split(",")
    allowed = {f"{origin.strip().rstrip('/')}/settings/plans?checkout={outcome}" for origin in origins}
    if value not in allowed:
        raise BillingError("허용되지 않은 결제 복귀 주소예요.", 422)
    return value


def checkout(sb, user_id: str, product_id: str, success: str, cancel: str, idem: str, mobile: bool) -> dict:
    success, cancel = return_url(success, "success"), return_url(cancel, "cancel")
    if not os.getenv("KAKAOPAY_SECRET_KEY_DEV"):
        raise BillingError("카카오페이 테스트 결제 설정이 필요해요.")
    if os.getenv("BILLING_WORKER_ENABLED") != "true":
        raise BillingError("정기결제 갱신 작업 설정이 필요해요.")
    callback_origin = os.getenv("BILLING_CALLBACK_ORIGIN", "").rstrip("/")
    if callback_origin not in ("http://localhost:8001", "https://web-production-8dee5.up.railway.app"):
        raise BillingError("결제 복귀 주소 설정이 필요해요.")
    state = secrets.token_urlsafe(32)
    saved = execute(sb.rpc("billing_begin_checkout", {
        "p_user_id": user_id, "p_product_id": product_id, "p_idempotency_key": idem,
        "p_callback_state": state, "p_success_url": success, "p_cancel_url": cancel,
    }))
    if saved["status"] == "preparing" and saved["callback_state"] == state:
        callback = f"{callback_origin}/api/billing/kakaopay/callback?" + urlencode({"order_id": saved["id"], "state": state})
        try:
            result = kakaopay.ready({
                "partner_order_id": saved["id"], "partner_user_id": saved["partner_user_id"],
                "item_name": "Pally Pro 연간 구독" if product_id == "pro_yearly" else "Pally Pro 월간 구독",
                "quantity": 1, "total_amount": saved["amount"], "tax_free_amount": 0,
                "approval_url": callback + "&result=approve",
                "cancel_url": callback + "&result=cancel", "fail_url": callback + "&result=fail",
            })
            execute(sb.table("billing_orders").update({
                "tid": result.tid, "checkout_url": result.next_redirect_pc_url,
                "mobile_url": result.next_redirect_mobile_url, "status": "ready",
            }).eq("id", saved["id"]))
            saved = read_order(sb, saved["id"])
        except kakaopay.KakaoPayError:
            execute(sb.table("billing_orders").update({"status": "failed"}).eq("id", saved["id"]))
            raise
    if saved["status"] != "ready" or timestamp(saved["expires_at"]) <= datetime.now(timezone.utc):
        raise BillingError("결제가 처리 중이거나 만료됐어요. 상태를 다시 확인해 주세요.", 409)
    return {"product_id": product_id, "checkout_url": saved["mobile_url"] if mobile else saved["checkout_url"],
            "expires_at": saved["expires_at"]}


def finish(sb, saved: dict, receipt: kakaopay.ApprovedResponse) -> None:
    verified = kakaopay.order(receipt.tid)
    kakaopay.verify_payment(verified, {**saved, "tid": saved["tid"] if saved["tid"] else receipt.tid})
    if verified.status != "SUCCESS_PAYMENT" or verified.approved_at is None:
        raise BillingError("결제 승인이 확인되지 않았어요.")
    if (receipt.cid != kakaopay.TEST_CID or receipt.partner_order_id != saved["id"]
            or receipt.partner_user_id != saved["partner_user_id"]):
        raise BillingError("결제 정보가 일치하지 않아요.")
    execute(sb.rpc("billing_finish_order", {
        "p_order_id": saved["id"], "p_tid": receipt.tid, "p_sid": receipt.sid,
        "p_approved_at": timestamp(verified.approved_at.isoformat()).isoformat(),
    }))


def callback(sb, order_id: str, state: str, result: str, pg_token: str | None) -> str:
    saved = read_order(sb, order_id)
    if not saved["callback_state"] or not hmac.compare_digest(saved["callback_state"], state):
        raise BillingError("유효하지 않은 결제 요청이에요.", 403)
    if saved["status"] == "approved":
        return saved["success_url"]
    if result != "approve":
        execute(sb.table("billing_orders").update({"status": "canceled"}).eq("id", order_id).eq("status", "ready"))
        return saved["cancel_url"]
    if not pg_token:
        raise BillingError("결제 승인 정보가 없어요.", 422)
    if saved["receipt"]:
        finish(sb, saved, kakaopay.ApprovedResponse.model_validate(saved["receipt"]))
        return saved["success_url"]
    claimed = execute(sb.rpc("billing_claim_approval", {"p_order_id": order_id}))
    if not claimed:
        return saved["success_url"].replace("checkout=success", "checkout=pending")
    try:
        receipt = kakaopay.approve({
            "tid": saved["tid"], "partner_order_id": order_id,
            "partner_user_id": saved["partner_user_id"], "pg_token": pg_token,
            "total_amount": saved["amount"],
        })
        execute(sb.table("billing_orders").update({"receipt": receipt.model_dump(mode="json")}).eq("id", order_id))
        finish(sb, saved, receipt)
        return saved["success_url"]
    except (kakaopay.KakaoPayError, BillingError):
        execute(sb.table("billing_orders").update({"status": "uncertain"}).eq("id", order_id).neq("status", "approved"))
        return saved["success_url"].replace("checkout=success", "checkout=pending")


def cancel_subscription(sb, user_id: str) -> None:
    sid = execute(sb.rpc("billing_stop_renewal", {"p_user_id": user_id}))
    if sid:
        kakaopay.deactivate(sid)
        execute(sb.table("billing_accounts").update({"deactivation_pending": False}).eq("user_id", user_id).eq("sid", sid))


def recover_receipts(sb, user_id: str | None = None) -> None:
    # Complete durable receipts after a process restart without sending the charge again.
    query = sb.table("billing_orders").select("*").in_("status", ["processing", "uncertain"]).not_.is_("receipt", "null")
    if user_id:
        query = query.eq("user_id", user_id)
    recovery = execute(query.limit(20))
    for saved in recovery:
        try:
            finish(sb, saved, kakaopay.ApprovedResponse.model_validate(saved["receipt"]))
        except Exception as exc:
            logging.error("Billing receipt recovery failed; order=%s (%s)", saved["id"], type(exc).__name__)


def tick(sb) -> None:
    recover_receipts(sb)
    pending = execute(sb.table("billing_accounts").select("user_id,sid").eq("deactivation_pending", True).limit(20))
    for account in pending:
        try:
            kakaopay.deactivate(account["sid"])
            execute(sb.table("billing_accounts").update({"deactivation_pending": False}).eq("user_id", account["user_id"]).eq("sid", account["sid"]))
        except Exception as exc:
            logging.error("Billing deactivation retry failed (%s)", type(exc).__name__)
    for _ in range(20):
        saved = execute(sb.rpc("billing_claim_renewal", {}))
        if saved is None:
            break
        try:
            receipt = kakaopay.renew({
                "sid": saved["sid"], "partner_user_id": saved["partner_user_id"],
                "partner_order_id": saved["id"], "item_name": "Pally Pro 자동 갱신",
                "quantity": 1, "total_amount": saved["amount"], "tax_free_amount": 0,
            })
            if receipt.sid != saved["sid"]:
                raise BillingError("정기결제 정보가 일치하지 않아요.")
            execute(sb.table("billing_orders").update({"receipt": receipt.model_dump(mode="json"), "tid": receipt.tid}).eq("id", saved["id"]))
            finish(sb, saved, receipt)
        except (kakaopay.KakaoPayError, BillingError):
            # Ambiguous results require reconciliation, never blind retries with another order.
            execute(sb.table("billing_orders").update({"status": "uncertain"}).eq("id", saved["id"]).neq("status", "approved"))
            logging.error("Sandbox renewal requires reconciliation; order=%s", saved["id"])


async def worker(get_db, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.to_thread(tick, get_db())
        except Exception as exc:
            logging.error("Billing worker failed (%s)", type(exc).__name__)
        try:
            await asyncio.wait_for(stop.wait(), timeout=60)
        except asyncio.TimeoutError:
            continue
