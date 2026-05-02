"""
CLARIQ Billing Routes
Handles Stripe subscriptions, trial management, Connect onboarding, and webhooks
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
import stripe
import os
from typing import Optional

router = APIRouter(prefix="/api", tags=["billing"])

stripe.api_key = os.getenv("STRIPE_API_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    plan: str
    billing_cycle: str

class SignupResponse(BaseModel):
    user_id: str
    email: str
    plan: str
    trial_ends_at: datetime
    subscription_id: str

@router.post("/signup", response_model=SignupResponse)
async def signup(data: SignupRequest):
    try:
        plans = {
            "starter_monthly": {"price_id": "price_starter_monthly", "amount": 3900},
            "starter_yearly": {"price_id": "price_starter_yearly", "amount": 39000},
            "pro_monthly": {"price_id": "price_pro_monthly", "amount": 9900},
            "pro_yearly": {"price_id": "price_pro_yearly", "amount": 99000},
        }
        
        plan_key = f"{data.plan}_{data.billing_cycle}"
        if plan_key not in plans:
            raise HTTPException(status_code=400, detail="Invalid plan or billing cycle")
        
        plan_config = plans[plan_key]
        
        customer = stripe.Customer.create(
            email=data.email,
            name=data.name,
            metadata={"signup_date": datetime.utcnow().isoformat()}
        )
        customer_id = customer.id
        
        trial_end = datetime.utcnow() + timedelta(days=7)
        
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": plan_config["price_id"]}],
            trial_end=int(trial_end.timestamp()),
            metadata={
                "user_email": data.email,
                "plan": data.plan,
                "billing_cycle": data.billing_cycle
            }
        )
        
        subscription_id = subscription.id
        
        return SignupResponse(
            user_id=customer_id,
            email=data.email,
            plan=data.plan,
            trial_ends_at=trial_end,
            subscription_id=subscription_id
        )
        
    except stripe.error.CardError as e:
        raise HTTPException(status_code=400, detail=f"Card error: {e.user_message}")
    except stripe.error.StripeException as e:
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signup failed: {str(e)}")

class ConnectLinkRequest(BaseModel):
    user_id: str

@router.post("/stripe-connect-link")
async def create_connect_link(data: ConnectLinkRequest):
    try:
        connect_account = stripe.Account.create(
            type="express",
            country="US",
            email="seller@clariq.com",
            metadata={
                "clariq_user_id": data.user_id,
                "created_at": datetime.utcnow().isoformat()
            }
        )
        
        connect_account_id = connect_account.id
        
        account_link = stripe.AccountLink.create(
            account=connect_account_id,
            type="account_onboarding",
            refresh_url="https://tryclariq.com/billing?reconnect=true",
            return_url="https://tryclariq.com/billing?success=true"
        )
        
        return {
            "connect_account_id": connect_account_id,
            "onboarding_url": account_link.url,
            "status": "pending"
        }
        
    except stripe.error.StripeException as e:
        raise HTTPException(status_code=500, detail=f"Connect link failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    event_type = event["type"]
    
    if event_type == "customer.subscription.trial_will_end":
        subscription = event["data"]["object"]
        customer_id = subscription["customer"]
        print(f"✓ Trial ending soon for customer {customer_id}")
    
    elif event_type == "invoice.payment_succeeded":
        invoice = event["data"]["object"]
        customer_id = invoice["customer"]
        amount_paid = invoice["amount_paid"]
        
        stripe_fee_percent = 0.029
        stripe_fee_fixed = 30
        
        amount_usd = amount_paid / 100
        stripe_fees = (amount_usd * stripe_fee_percent) + (stripe_fee_fixed / 100)
        clariq_revenue = (amount_usd - stripe_fees) * 0.70
        
        print(f"✓ Payment received from {customer_id}: ${amount_usd:.2f}")
        print(f"  Stripe fees: ${stripe_fees:.2f}")
        print(f"  CLARIQ payout: ${clariq_revenue:.2f}")
    
    elif event_type == "invoice.payment_failed":
        invoice = event["data"]["object"]
        customer_id = invoice["customer"]
        print(f"✗ Payment failed for customer {customer_id}")
    
    elif event_type == "account.updated":
        account = event["data"]["object"]
        account_id = account["id"]
        charges_enabled = account.get("charges_enabled", False)
        status = "verified" if charges_enabled else "pending"
        print(f"✓ Connect account {account_id} updated: {status}")
    
    return {"status": "received"}

@router.get("/account/billing")
async def get_billing_info(user_id: str):
    try:
        customer_id = user_id
        customer = stripe.Customer.retrieve(customer_id)
        
        subscriptions = stripe.Subscription.list(customer=customer_id, limit=1)
        if not subscriptions.data:
            raise HTTPException(status_code=404, detail="No active subscription")
        
        subscription = subscriptions.data[0]
        
        payment_method = None
        if subscription.default_payment_method:
            pm = stripe.PaymentMethod.retrieve(subscription.default_payment_method)
            if pm.card:
                payment_method = f"•••• {pm.card.last4}"
        
        plan_info = {
            "starter_monthly": {"name": "Starter", "cycle": "Monthly", "amount": 39},
            "starter_yearly": {"name": "Starter", "cycle": "Yearly", "amount": 390},
            "pro_monthly": {"name": "Pro", "cycle": "Monthly", "amount": 99},
            "pro_yearly": {"name": "Pro", "cycle": "Yearly", "amount": 990},
        }
        
        plan_name = subscription.items.data[0].price.metadata.get("plan", "starter")
        plan_cycle = subscription.items.data[0].price.recurring.interval
        plan_key = f"{plan_name}_{plan_cycle}"
        plan_config = plan_info.get(plan_key, {"name": "Pro", "cycle": "Monthly", "amount": 99})
        
        return {
            "current_plan": plan_config["name"],
            "billing_cycle": plan_config["cycle"],
            "next_charge_date": datetime.fromtimestamp(subscription.current_period_end),
            "amount_usd": plan_config["amount"],
            "payment_method": payment_method,
            "stripe_connect_status": "not_connected",
            "subscription_id": subscription.id,
            "status": subscription.status
        }
        
    except stripe.error.StripeException as e:
        raise HTTPException(status_code=500, detail=f"Billing lookup failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def calculate_payout(amount_usd: float) -> dict:
    stripe_fee_percent = 0.029
    stripe_fee_fixed = 0.30
    
    stripe_fees = (amount_usd * stripe_fee_percent) + stripe_fee_fixed
    net_revenue = amount_usd - stripe_fees
    clariq_payout = net_revenue * 0.70
    
    return {
        "amount_charged": amount_usd,
        "stripe_fees": round(stripe_fees, 2),
        "net_revenue": round(net_revenue, 2),
        "clariq_payout": round(clariq_payout, 2)
    }
