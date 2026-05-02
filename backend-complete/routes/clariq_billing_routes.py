"""
CLARIQ Billing Routes
Handles Stripe subscriptions, trial management, Connect onboarding, and webhooks
Add to backend/routes/billing.py
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
import stripe
import os
from typing import Optional

router = APIRouter(prefix="/api", tags=["billing"])

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_API_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Database models (replace with your actual DB)
class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    plan: str  # "starter" or "pro"
    billing_cycle: str  # "monthly" or "yearly"

class SignupResponse(BaseModel):
    user_id: str
    email: str
    plan: str
    trial_ends_at: datetime
    subscription_id: str

class BillingInfo(BaseModel):
    current_plan: str
    next_charge_date: datetime
    amount_usd: float
    payment_method: Optional[str]
    bank_account: Optional[str]
    stripe_connect_status: str  # "pending", "connected", "verified"

# ============================================================================
# POST /api/signup
# ============================================================================
@router.post("/signup", response_model=SignupResponse)
async def signup(data: SignupRequest):
    """
    Create user account + subscription with 7-day trial
    
    Flow:
    1. Create Stripe customer
    2. Attach payment method
    3. Create subscription with 7-day trial
    4. Create local user record
    5. Return subscription details
    """
    try:
        # Plan pricing (in cents)
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
        
        # Step 1: Create Stripe customer
        customer = stripe.Customer.create(
            email=data.email,
            name=data.name,
            metadata={"signup_date": datetime.utcnow().isoformat()}
        )
        customer_id = customer.id
        
        # Step 2: Calculate trial end date (7 days from now)
        trial_end = datetime.utcnow() + timedelta(days=7)
        
        # Step 3: Create subscription with trial
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
        
        # Step 4: Create local user record in database
        # TODO: Replace with actual DB call
        # user = await db.create_user(
        #     email=data.email,
        #     name=data.name,
        #     password_hash=hash_password(data.password),
        #     stripe_customer_id=customer_id,
        #     stripe_subscription_id=subscription_id,
        #     plan=data.plan,
        #     billing_cycle=data.billing_cycle,
        #     trial_ends_at=trial_end
        # )
        
        return SignupResponse(
            user_id=customer_id,  # Use Stripe customer ID as user ID
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


# ============================================================================
# POST /api/stripe-connect-link
# ============================================================================
class ConnectLinkRequest(BaseModel):
    user_id: str

@router.post("/stripe-connect-link")
async def create_connect_link(data: ConnectLinkRequest):
    """
    Generate Stripe Connect onboarding link for bank account linking
    
    Flow:
    1. Get Stripe customer ID from user_id
    2. Create Connect account for seller
    3. Generate onboarding link
    4. Return redirect URL
    """
    try:
        # TODO: Fetch user from DB using user_id
        # user = await db.get_user(data.user_id)
        # if not user:
        #     raise HTTPException(status_code=404, detail="User not found")
        
        # Create a Connect account for the seller
        connect_account = stripe.Account.create(
            type="express",
            country="US",
            email="seller@clariq.com",  # TODO: Use actual user email
            metadata={
                "clariq_user_id": data.user_id,
                "created_at": datetime.utcnow().isoformat()
            }
        )
        
        connect_account_id = connect_account.id
        
        # Generate onboarding link
        account_link = stripe.AccountLink.create(
            account=connect_account_id,
            type="account_onboarding",
            refresh_url="https://tryclariq.com/billing?reconnect=true",
            return_url="https://tryclariq.com/billing?success=true"
        )
        
        # TODO: Store connect_account_id in user record
        # await db.update_user(
        #     user_id=data.user_id,
        #     stripe_connect_id=connect_account_id,
        #     stripe_connect_status="pending"
        # )
        
        return {
            "connect_account_id": connect_account_id,
            "onboarding_url": account_link.url,
            "status": "pending"
        }
        
    except stripe.error.StripeException as e:
        raise HTTPException(status_code=500, detail=f"Connect link failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# POST /api/webhooks/stripe
# ============================================================================
@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events:
    - customer.subscription.trial_will_end (day 7) → Send email reminder
    - invoice.payment_succeeded (day 8+) → Auto-charge customer
    - invoice.payment_failed → Retry or cancel
    - account.updated (Connect) → Update bank status
    
    Payout calculation:
    - Customer pays: $39 (Starter) or $99 (Pro)
    - Stripe takes: 2.9% + $0.30
    - CLARIQ receives: 70% of revenue
    - Payout = (Customer Price - Stripe Fees) × 0.70
    """
    
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
    
    # Trial ending soon (day 7)
    if event_type == "customer.subscription.trial_will_end":
        subscription = event["data"]["object"]
        customer_id = subscription["customer"]
        
        # TODO: Send email reminder to customer
        # customer = stripe.Customer.retrieve(customer_id)
        # await send_email(
        #     to=customer.email,
        #     subject="Your clariq trial ends tomorrow",
        #     template="trial_ending_soon"
        # )
        
        print(f"✓ Trial ending soon for customer {customer_id}")
    
    # Payment succeeded (day 8 and onwards)
    elif event_type == "invoice.payment_succeeded":
        invoice = event["data"]["object"]
        customer_id = invoice["customer"]
        amount_paid = invoice["amount_paid"]  # In cents
        
        # Calculate payout (70% of revenue after Stripe fees)
        stripe_fee_percent = 0.029  # 2.9%
        stripe_fee_fixed = 30  # $0.30 in cents
        
        amount_usd = amount_paid / 100
        stripe_fees = (amount_usd * stripe_fee_percent) + (stripe_fee_fixed / 100)
        clariq_revenue = (amount_usd - stripe_fees) * 0.70
        
        # TODO: Log transaction in DB
        # await db.create_transaction(
        #     stripe_customer_id=customer_id,
        #     amount_paid_usd=amount_usd,
        #     stripe_fees_usd=stripe_fees,
        #     clariq_payout_usd=clariq_revenue,
        #     invoice_id=invoice["id"],
        #     status="paid"
        # )
        
        print(f"✓ Payment received from {customer_id}: ${amount_usd:.2f}")
        print(f"  Stripe fees: ${stripe_fees:.2f}")
        print(f"  CLARIQ payout: ${clariq_revenue:.2f}")
    
    # Payment failed
    elif event_type == "invoice.payment_failed":
        invoice = event["data"]["object"]
        customer_id = invoice["customer"]
        
        # TODO: Send payment retry email
        # await send_email(
        #     to=invoice.customer_email,
        #     subject="Payment failed — please update your card",
        #     template="payment_failed"
        # )
        
        print(f"✗ Payment failed for customer {customer_id}")
    
    # Connect account updated (bank linked/verified)
    elif event_type == "account.updated":
        account = event["data"]["object"]
        account_id = account["id"]
        charges_enabled = account.get("charges_enabled", False)
        
        # TODO: Update user's Connect status
        # await db.update_user(
        #     stripe_connect_id=account_id,
        #     stripe_connect_status="verified" if charges_enabled else "pending"
        # )
        
        status = "verified" if charges_enabled else "pending"
        print(f"✓ Connect account {account_id} updated: {status}")
    
    return {"status": "received"}


# ============================================================================
# GET /api/account/billing
# ============================================================================
class BillingRequest(BaseModel):
    user_id: str

@router.get("/account/billing")
async def get_billing_info(user_id: str):
    """
    Get current billing info for authenticated user
    
    Returns:
    - Current plan (Starter/Pro, Monthly/Yearly)
    - Next charge date
    - Amount to be charged
    - Payment method (last 4 digits)
    - Bank account status (connected/verified/pending)
    """
    try:
        # TODO: Fetch user from DB
        # user = await db.get_user(user_id)
        # if not user:
        #     raise HTTPException(status_code=404, detail="User not found")
        
        # Retrieve Stripe subscription
        customer_id = user_id  # Assume user_id is Stripe customer ID
        customer = stripe.Customer.retrieve(customer_id)
        
        # Get active subscription
        subscriptions = stripe.Subscription.list(customer=customer_id, limit=1)
        if not subscriptions.data:
            raise HTTPException(status_code=404, detail="No active subscription")
        
        subscription = subscriptions.data[0]
        
        # Get payment method details
        payment_method = None
        if subscription.default_payment_method:
            pm = stripe.PaymentMethod.retrieve(subscription.default_payment_method)
            if pm.card:
                payment_method = f"•••• {pm.card.last4}"
        
        # Get Connect account status
        stripe_connect_status = "not_connected"
        bank_account = None
        
        # TODO: Fetch from user record
        # if user.stripe_connect_id:
        #     account = stripe.Account.retrieve(user.stripe_connect_id)
        #     stripe_connect_status = "verified" if account.charges_enabled else "pending"
        #     if account.external_accounts.total_count > 0:
        #         bank = account.external_accounts.data[0]
        #         bank_account = f"{bank.bank_name} •••• {bank.last4}"
        
        plan_info = {
            "starter_monthly": {"name": "Starter", "cycle": "Monthly", "amount": 39},
            "starter_yearly": {"name": "Starter", "cycle": "Yearly", "amount": 390},
            "pro_monthly": {"name": "Pro", "cycle": "Monthly", "amount": 99},
            "pro_yearly": {"name": "Pro", "cycle": "Yearly", "amount": 990},
        }
        
        # Parse plan from subscription items
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
            "bank_account": bank_account,
            "stripe_connect_status": stripe_connect_status,
            "subscription_id": subscription.id,
            "status": subscription.status
        }
        
    except stripe.error.StripeException as e:
        raise HTTPException(status_code=500, detail=f"Billing lookup failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Helper: Calculate payout (used in webhook + GET /api/account/billing)
# ============================================================================
def calculate_payout(amount_usd: float) -> dict:
    """
    Calculate payouts from customer charge
    
    Stripe fees: 2.9% + $0.30
    CLARIQ takes: 70% of (revenue - Stripe fees)
    
    Example:
    Customer pays: $39
    Stripe fee: $1.43 (2.9% × $39 + $0.30)
    Net to CLARIQ: $37.57
    CLARIQ payout (70%): $26.30
    """
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
