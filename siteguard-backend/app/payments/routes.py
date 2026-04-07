"""
Payment integration routes.
Supports YooKassa (primary) with webhook handling for automatic
license creation upon successful payment.
"""
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime
from typing import Optional

import aiohttp
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt_handler import get_current_user
from app.config import settings
from app.database import get_db
from app.licensing.key_generator import LicenseKeyGenerator
from app.licensing.models import License, LicensePlan, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


# ===== Pydantic schemas =====

class CreatePaymentRequest(BaseModel):
    plan: str  # starter, professional, business
    period: str = "yearly"  # monthly, yearly
    promo_code: Optional[str] = None
    return_url: Optional[str] = None


class CreatePaymentResponse(BaseModel):
    payment_id: str
    payment_url: str
    amount: float
    currency: str = "RUB"
    description: str


class PaymentWebhookData(BaseModel):
    event: str
    object: dict


# ===== Price configuration =====

PRICES = {
    "starter": {
        "monthly": 299,
        "yearly": 2990,
    },
    "professional": {
        "monthly": 999,
        "yearly": 9990,
    },
    "business": {
        "monthly": 2999,
        "yearly": 29990,
    },
    "enterprise": {
        "monthly": 9999,
        "yearly": 99990,
    },
}

PROMO_CODES = {
    "LAUNCH20": {"discount_percent": 20, "valid_until": "2025-12-31"},
    "PARTNER30": {"discount_percent": 30, "valid_until": "2025-06-30"},
    "FRIEND50": {
        "discount_percent": 50,
        "valid_until": "2025-03-31",
        "max_uses": 100,
        "used": 0,
    },
}


# ===== YooKassa client =====

class YooKassaClient:
    """Client for the YooKassa payment API."""

    def __init__(self):
        self.shop_id = settings.YOOKASSA_SHOP_ID
        self.secret_key = settings.YOOKASSA_SECRET_KEY
        self.base_url = "https://api.yookassa.ru/v3"

    async def create_payment(
        self,
        amount: float,
        currency: str,
        description: str,
        return_url: str,
        metadata: dict = None,
    ) -> dict:
        """Create a payment via YooKassa API."""
        idempotency_key = str(uuid.uuid4())

        payload = {
            "amount": {
                "value": f"{amount:.2f}",
                "currency": currency,
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url,
            },
            "capture": True,
            "description": description,
            "metadata": metadata or {},
        }

        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
        }

        auth = aiohttp.BasicAuth(self.shop_id, self.secret_key)

        async with aiohttp.ClientSession(auth=auth) as session:
            async with session.post(
                f"{self.base_url}/payments",
                json=payload,
                headers=headers,
            ) as resp:
                data = await resp.json()
                if resp.status not in (200, 201):
                    raise Exception(f"YooKassa error: {data}")
                return data

    async def get_payment(self, payment_id: str) -> dict:
        """Get payment status from YooKassa."""
        auth = aiohttp.BasicAuth(self.shop_id, self.secret_key)

        async with aiohttp.ClientSession(auth=auth) as session:
            async with session.get(
                f"{self.base_url}/payments/{payment_id}"
            ) as resp:
                return await resp.json()

    def verify_webhook(self, body: bytes, signature: str) -> bool:
        """Verify webhook signature from YooKassa."""
        expected = hmac.new(
            self.secret_key.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


yookassa = YooKassaClient()


# ===== Endpoints =====

@router.post("/create", response_model=CreatePaymentResponse)
async def create_payment(
    request: CreatePaymentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a payment for purchasing or renewing a license."""
    # Validate plan
    if request.plan not in PRICES:
        raise HTTPException(400, f"Unknown plan: {request.plan}")

    if request.period not in ("monthly", "yearly"):
        raise HTTPException(400, "Period must be 'monthly' or 'yearly'")

    # Base price
    amount = PRICES[request.plan][request.period]

    # Promo code
    discount_text = ""
    if request.promo_code:
        promo = PROMO_CODES.get(request.promo_code.upper())
        if promo:
            valid_until = datetime.strptime(
                promo["valid_until"], "%Y-%m-%d"
            )
            if datetime.now() <= valid_until:
                discount = promo["discount_percent"]
                amount = amount * (1 - discount / 100)
                discount_text = f" (discount {discount}%)"
            else:
                raise HTTPException(400, "Promo code expired")
        else:
            raise HTTPException(400, "Invalid promo code")

    # Description
    plan_names = {
        "starter": "Starter",
        "professional": "Professional",
        "business": "Business",
        "enterprise": "Enterprise",
    }
    period_names = {
        "monthly": "1 month",
        "yearly": "1 year",
    }

    description = (
        f"SiteGuard Monitor -- {plan_names[request.plan]} "
        f"({period_names[request.period]}){discount_text}"
    )

    return_url = request.return_url or (
        f"{settings.FRONTEND_URL}/payment/success"
    )

    # Create payment via YooKassa
    try:
        payment_data = await yookassa.create_payment(
            amount=amount,
            currency="RUB",
            description=description,
            return_url=return_url,
            metadata={
                "user_id": str(current_user.id),
                "plan": request.plan,
                "period": request.period,
                "promo_code": request.promo_code or "",
                "email": current_user.email,
            },
        )
    except Exception as e:
        logger.error(f"Payment creation error: {e}")
        raise HTTPException(500, "Payment creation failed")

    payment_id = payment_data["id"]
    confirmation_url = payment_data["confirmation"]["confirmation_url"]

    logger.info(
        f"Payment created: {payment_id} for user {current_user.id}, "
        f"plan={request.plan}, amount={amount}"
    )

    return CreatePaymentResponse(
        payment_id=payment_id,
        payment_url=confirmation_url,
        amount=amount,
        currency="RUB",
        description=description,
    )


@router.post("/webhook/yookassa")
async def yookassa_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Webhook from YooKassa -- handles successful payments.
    Automatically creates a license on payment success.
    """
    body = await request.body()

    data = json.loads(body)
    event = data.get("event")
    payment_obj = data.get("object", {})

    logger.info(
        f"YooKassa webhook: {event}, payment={payment_obj.get('id')}"
    )

    if event == "payment.succeeded":
        payment_id = payment_obj["id"]
        metadata = payment_obj.get("metadata", {})
        user_id = int(metadata.get("user_id", 0))
        plan_str = metadata.get("plan", "starter")
        period = metadata.get("period", "yearly")
        amount = float(
            payment_obj.get("amount", {}).get("value", 0)
        )

        if not user_id:
            logger.error(
                f"No user_id in payment {payment_id} metadata"
            )
            return {"status": "error", "message": "no user_id"}

        # Map plan string to enum
        plan_map = {
            "starter": LicensePlan.STARTER,
            "professional": LicensePlan.PROFESSIONAL,
            "business": LicensePlan.BUSINESS,
            "enterprise": LicensePlan.ENTERPRISE,
        }
        plan = plan_map.get(plan_str, LicensePlan.STARTER)

        # Duration
        duration = 365 if period == "yearly" else 30

        # Create license
        try:
            license = await LicenseKeyGenerator.create_license(
                db=db,
                user_id=user_id,
                plan=plan,
                payment_amount=amount,
                payment_method="yookassa",
                payment_id=payment_id,
                custom_duration_days=duration,
            )

            logger.info(
                f"License created: {license.license_key} "
                f"for user {user_id}, plan={plan_str}"
            )

            # Send license key to user via email
            try:
                from app.notifications.email import send_license_email

                result = await db.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                if user:
                    await send_license_email(
                        to_email=user.email,
                        license_key=license.license_key,
                        plan_name=plan_str.upper(),
                        expires_at=license.expires_at,
                        payment_amount=amount,
                    )
            except Exception as email_err:
                logger.warning(f"Failed to send license email: {email_err}")

            return {
                "status": "ok",
                "license_key": license.license_key,
            }

        except Exception as e:
            logger.error(
                f"License creation error for payment "
                f"{payment_id}: {e}"
            )
            return {"status": "error", "message": str(e)}

    elif event == "payment.canceled":
        logger.info(f"Payment cancelled: {payment_obj.get('id')}")
        return {"status": "ok"}

    elif event == "refund.succeeded":
        # Handle refund -- revoke license
        payment_id = payment_obj.get(
            "payment_id", payment_obj.get("id")
        )
        logger.warning(f"Refund for payment {payment_id}")

        await db.execute(
            update(License)
            .where(License.payment_id == payment_id)
            .values(status="revoked")
        )
        await db.commit()

        return {"status": "ok", "action": "license_revoked"}

    return {"status": "ok"}


@router.get("/status/{payment_id}")
async def get_payment_status(
    payment_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get the current status of a payment from YooKassa."""
    try:
        payment_data = await yookassa.get_payment(payment_id)
        return {
            "payment_id": payment_data.get("id"),
            "status": payment_data.get("status"),
            "amount": payment_data.get("amount", {}).get("value"),
            "currency": payment_data.get("amount", {}).get("currency"),
            "description": payment_data.get("description"),
            "created_at": payment_data.get("created_at"),
            "paid": payment_data.get("paid", False),
        }
    except Exception as e:
        logger.error(f"Payment status check error: {e}")
        raise HTTPException(500, "Failed to check payment status")


@router.get("/history")
async def get_payment_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get payment history for the current user."""
    result = await db.execute(
        select(License)
        .where(License.user_id == current_user.id)
        .where(License.payment_amount > 0)
        .order_by(License.created_at.desc())
    )
    licenses = result.scalars().all()

    return [
        {
            "date": lic.created_at.isoformat(),
            "plan": lic.plan.value,
            "amount": lic.payment_amount,
            "currency": lic.payment_currency,
            "payment_method": lic.payment_method,
            "license_key": (
                lic.license_key[:8] + "****" + lic.license_key[-5:]
            ),
            "status": lic.status.value,
            "expires_at": lic.expires_at.isoformat(),
        }
        for lic in licenses
    ]
