# CLARIQ Backend Billing Integration Guide

## Files to Add/Update

### 1. Add Billing Routes
**File:** `backend/routes/billing.py` (NEW)
- Copy the content from `clariq_billing_routes.py`
- Contains all 4 API endpoints + webhook handlers

### 2. Update Main FastAPI App
**File:** `backend/main.py`

Add these imports at the top:
```python
from routes import billing
```

Add this in the FastAPI setup (after other routers):
```python
app.include_router(billing.router)
```

### 3. Update Requirements
**File:** `backend/requirements.txt`

Add/ensure these are present:
```
stripe==5.4.0
python-dotenv==1.0.0
pydantic[email]==2.0.0
```

### 4. Add Environment Variables
**File:** `backend/.env` (local) and Railway Variables (production)

```
STRIPE_API_KEY=sk_live_xxxxxxxxxxxx (or sk_test_xxxx for dev)
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxx (from Stripe Dashboard)
```

Get these from:
1. Stripe Dashboard → API Keys → Secret Key
2. Stripe Dashboard → Webhooks → Signing secret (for endpoint listening at /api/webhooks/stripe)

### 5. Set Up Stripe Webhook in Stripe Dashboard
1. Go to Stripe Dashboard → Developers → Webhooks
2. Add endpoint: `https://clariq-production-1ddf.up.railway.app/api/webhooks/stripe`
3. Select events:
   - `customer.subscription.trial_will_end`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
   - `account.updated`
4. Copy signing secret → Add to `.env` as `STRIPE_WEBHOOK_SECRET`

### 6. Create Stripe Price IDs
Go to Stripe Dashboard → Products → Create prices for each plan:

```
Starter Monthly: price_starter_monthly → $39/month
Starter Yearly:  price_starter_yearly  → $390/year (25% off)
Pro Monthly:     price_pro_monthly     → $99/month
Pro Yearly:      price_pro_yearly      → $990/year (25% off)
```

Update these in `billing.py` line ~65:
```python
plans = {
    "starter_monthly": {"price_id": "price_xxxxx", "amount": 3900},
    ...
}
```

---

## API Endpoints

### POST /api/signup
**Request:**
```json
{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "password": "SecurePass123",
  "plan": "starter",
  "billing_cycle": "monthly"
}
```

**Response:**
```json
{
  "user_id": "cus_xxxxx",
  "email": "jane@example.com",
  "plan": "starter",
  "trial_ends_at": "2026-05-09T12:00:00",
  "subscription_id": "sub_xxxxx"
}
```

### POST /api/stripe-connect-link
**Request:**
```json
{
  "user_id": "cus_xxxxx"
}
```

**Response:**
```json
{
  "connect_account_id": "acct_xxxxx",
  "onboarding_url": "https://connect.stripe.com/...",
  "status": "pending"
}
```

### POST /api/webhooks/stripe
Stripe sends events automatically. No manual call needed.

**Handles:**
- `customer.subscription.trial_will_end` (day 7)
- `invoice.payment_succeeded` (day 8+)
- `invoice.payment_failed` (retry)
- `account.updated` (Connect bank linked)

### GET /api/account/billing?user_id=cus_xxxxx
**Response:**
```json
{
  "current_plan": "Starter",
  "billing_cycle": "Monthly",
  "next_charge_date": "2026-05-09T12:00:00",
  "amount_usd": 39,
  "payment_method": "•••• 4242",
  "bank_account": "Chase Bank •••• 1234",
  "stripe_connect_status": "verified",
  "subscription_id": "sub_xxxxx",
  "status": "active"
}
```

---

## Database Integration (TODO)

The billing routes have TODO markers for database calls. You need to implement:

### Create Tables

```sql
-- Users table
CREATE TABLE users (
  id UUID PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  name VARCHAR(255),
  password_hash VARCHAR(255),
  stripe_customer_id VARCHAR(255) UNIQUE,
  stripe_subscription_id VARCHAR(255),
  stripe_connect_id VARCHAR(255),
  stripe_connect_status VARCHAR(50), -- 'pending', 'verified'
  plan VARCHAR(50), -- 'starter', 'pro'
  billing_cycle VARCHAR(50), -- 'monthly', 'yearly'
  trial_ends_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Transactions table (for payout tracking)
CREATE TABLE transactions (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  stripe_customer_id VARCHAR(255),
  invoice_id VARCHAR(255),
  amount_paid_usd DECIMAL(10, 2),
  stripe_fees_usd DECIMAL(10, 2),
  clariq_payout_usd DECIMAL(10, 2),
  status VARCHAR(50), -- 'pending', 'paid', 'failed'
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Replace TODO Comments

In `billing.py`, replace all `await db.create_user()`, `await db.get_user()`, etc. with actual calls to your database (Snowflake, PostgreSQL, etc.).

Example:
```python
# Before (placeholder)
# TODO: Create local user record in database
# user = await db.create_user(...)

# After (actual DB call)
user = await db.create_user(
    email=data.email,
    name=data.name,
    password_hash=hash_password(data.password),
    stripe_customer_id=customer_id,
    stripe_subscription_id=subscription_id,
    plan=data.plan,
    billing_cycle=data.billing_cycle,
    trial_ends_at=trial_end
)
```

---

## Testing

### Local Development
```bash
# Start Flask with webhook testing
stripe listen --forward-to localhost:8000/api/webhooks/stripe

# In another terminal, run tests
pytest tests/billing_test.py
```

### Test Cards (Stripe Sandbox)
```
Success: 4242 4242 4242 4242
Failure: 4000 0000 0000 0002
3D Secure: 4000 0025 0000 3155
```

### Create Test Subscription
```bash
curl -X POST http://localhost:8000/api/signup \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "password": "Test123!",
    "plan": "starter",
    "billing_cycle": "monthly"
  }'
```

---

## Deployment

### 1. Push to GitHub
```bash
cd ~/Downloads/clariq/backend
git add routes/billing.py
git commit -m "Add billing endpoints: signup, stripe-connect, webhooks, account"
git push origin main
```

### 2. Railway Auto-Deploy
Railway watches your GitHub repo. Once pushed, it auto-deploys.

### 3. Verify on Railway
```bash
curl https://clariq-production-1ddf.up.railway.app/api/health
```

### 4. Test Webhook in Stripe Dashboard
1. Go to Stripe Dashboard → Webhooks
2. Click endpoint → "Send test event"
3. Select `invoice.payment_succeeded`
4. Railway logs should show webhook received

---

## Payout Calculation Example

**Customer pays: $39 (Starter Monthly)**

```
Stripe fee (2.9% + $0.30): $1.43
Net to platform: $37.57
CLARIQ takes (70%): $26.30
```

**Customer pays: $990 (Pro Yearly)**

```
Stripe fee (2.9% + $0.30): $28.91
Net to platform: $961.09
CLARIQ takes (70%): $672.76
```

---

## Next Steps

1. Copy `clariq_billing_routes.py` → `backend/routes/billing.py`
2. Update `backend/main.py` with imports
3. Add environment variables to Railway
4. Create Stripe Price IDs
5. Set up webhook endpoint in Stripe Dashboard
6. Implement database tables + TODO calls
7. Push to GitHub → Railway auto-deploys
8. Test signup flow end-to-end

**Ready?**
