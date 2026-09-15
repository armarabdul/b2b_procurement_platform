# ProcureHub UAE | Enterprise B2B Procurement & RFQ Platform

> **Smarter Procurement. Better Quotations. Stronger Supplier Decisions.**  
> Next-generation B2B Request-for-Quotation (RFQ) and procurement platform designed for the United Arab Emirates (Dubai) corporate market.

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![Django 5.1](https://img.shields.io/badge/Django-5.1-green.svg)](https://www.djangoproject.com/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-Play%20CDN-38B2AC.svg)](https://tailwindcss.com/)
[![PostgreSQL Ready](https://img.shields.io/badge/PostgreSQL-Ready-336791.svg)](https://www.postgresql.org/)
[![VAT Compliance](https://img.shields.io/badge/UAE%20VAT-5%25%20Compliant-gold.svg)]()
[![Tests Passing](https://img.shields.io/badge/Tests-Passing-brightgreen.svg)]()

---

## 1. Executive Summary

**ProcureHub** connects enterprise buyers (corporate procurement departments, construction firms, logistics hubs) with vetted UAE commercial suppliers. It replaces inefficient email-based tender inquiries with an end-to-end digital procurement workflow:

1. **Enterprise Buyer** specifies multi-line procurement requirements with UAE delivery dates, locations across the 7 emirates, and technical tolerances.
2. **Approved Suppliers** discover open RFQ opportunities, submit competitive line-item bids with automated 5% UAE VAT calculations, and declare delivery lead times and payment terms.
3. **Multi-Factor Evaluation Engine** evaluates proposals across four key dimensions (Price 40%, Delivery Speed 25%, Supplier Reliability 20%, Commercial Terms 15%) and generates weighted composite scores and AI recommendations.
4. **Single-Winner Award & PO Generation** atomically issues an official Purchase Order (`PO-2026-XXXX`), transitions the winning proposal to `ACCEPTED`, and auto-rejects competing bids with automated notifications.
5. **Commercial Settlement / Mock Escrow** simulates advance payments (e.g. 40% Mobilization), delivery balance (60%), or structured 3-stage installments via an abstracted payment service layer.

---

## 2. Technology Stack

- **Backend**: Python 3.12+, Django 5.1, Django REST Framework, Django ORM
- **Database**: SQLite (local development & zero-setup demo) / PostgreSQL-ready (`DATABASE_URL` via `dj-database-url`)
- **Frontend**: Django Templates, Tailwind CSS (enterprise dark & emerald palette), Alpine.js for micro-interactions & dynamic calculations, Lucide Icons
- **Precision Financials**: Python `Decimal` and Django `DecimalField` (strictly zero floating-point arithmetic)
- **Static Assets**: Whitenoise with compressed storage
- **Containerization & WSGI**: Docker, Docker Compose, Gunicorn

---

## 3. System Architecture & Modular Structure

```
procurehub/
│
├── manage.py                          # Django management utility
├── requirements.txt                   # Core & production dependencies
├── .env.example                       # Environment template
├── Dockerfile                         # Production Docker image
├── docker-compose.yml                 # PostgreSQL + Web container definition
│
├── config/                            # Project configuration package
│   ├── settings/
│   │   ├── base.py                    # Shared apps, middleware, auth model
│   │   ├── development.py             # SQLite, debug mode, hot reload
│   │   └── production.py              # PostgreSQL, SSL headers, Whitenoise
│   ├── urls.py                        # Master routing table & error handlers
│   ├── wsgi.py                        # WSGI entrypoint for Gunicorn
│   └── asgi.py                        # ASGI entrypoint
│
├── apps/                              # Modular domain applications
│   ├── accounts/                      # Custom User (AbstractUser), RBAC, UAE Auth
│   ├── customers/                     # CustomerProfile, Buyer Portal views & forms
│   ├── suppliers/                     # SupplierProfile, Trade Licenses, Vendor Portal
│   ├── rfqs/                          # Categories, RFQs, RFQItems, Status Workflow
│   ├── quotations/                    # Quotation, QuotationItems, Decimal VAT engine
│   ├── procurement/                   # QuotationEvaluation, RFQAward, Purchase Orders
│   ├── payments/                      # Abstracted BasePaymentService, Mock Gateway
│   ├── notifications/                 # In-app notifications & context processor
│   ├── audit/                         # Immutable ActivityLog compliance stream
│   ├── api/                           # DRF REST API Serializers & Viewsets
│   └── core/                          # Landing page, custom admin portal, seed commands
│
├── templates/                         # High-finish Tailwind HTML templates
│   ├── base.html                      # Layout, demo persona bar, toasts, Alpine.js
│   ├── portal_base.html               # Enterprise sidebar, topbar, notifications
│   ├── landing.html                   # UAE corporate SaaS landing page
│   ├── accounts/                      # Login, buyer register, supplier register
│   ├── customer/                      # Dashboard, RFQ create, matrix comparison, PO
│   ├── supplier/                      # Dashboard, RFQ discovery, submit bid, PO
│   ├── admin/                         # Executive dashboard, user approvals, audit log
│   ├── notifications/                 # Notification list & mark-read
│   └── errors/                        # 400, 403, 404, 500 error templates
│
├── static/                            # CSS stylesheets, fonts, icons
├── media/                             # Trade license & attachment uploads
├── scripts/                           # Acceptance test runner & verification scripts
└── tests/                             # End-to-end automated test suite
```

---

## 4. Default Demo Accounts

All pre-seeded accounts share the password: **`Demo123456!`**

| Persona | Email | Role | Company / Entity |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@procurehub.demo` | `ADMIN` | ProcureHub UAE Governance Committee |
| **Corporate Buyer** | `customer@procurehub.demo` | `CUSTOMER` | Al-Futtaim Enterprises UAE LLC |
| **Supplier 1** | `supplier1@procurehub.demo` | `SUPPLIER` | Emirates Office Solutions LLC (Rating: 4.90) |
| **Supplier 2** | `supplier2@procurehub.demo` | `SUPPLIER` | Gulf Commercial Supplies FZCO (Rating: 4.65) |
| **Supplier 3** | `supplier3@procurehub.demo` | `SUPPLIER` | Dubai Furnishings & Tech Ltd (Rating: 4.40) |
| **Pending Buyer** | `pending_buyer@procurehub.demo`| `CUSTOMER` | Emaar Hospitality Group PJSC (Verification Pending) |

> **Interactive Demo Switcher:** At the very top of the interface, click any of the persona buttons (`Admin`, `Buyer`, `Supplier 1`, `Supplier 2`, `Supplier 3`) to instantly switch authentication sessions without typing passwords.

---

## 5. Local Setup Instructions

### Prerequisites
- Python 3.12+ (tested on Python 3.12 and 3.13)
- `pip`

### Step-by-Step Installation

```bash
# 1. Clone repository & enter workspace
git clone <repository_url>
cd b2b_procurement_platform

# 2. Create & activate virtual environment (optional but recommended)
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux / macOS:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment variables
cp .env.example .env

# 5. Apply database migrations
python manage.py migrate

# 6. Seed realistic UAE demo data
python manage.py seed_demo

# 7. Start local development server
python manage.py runserver 127.0.0.1:8000
```

Open your browser at **`http://127.0.0.1:8000/`**.

---

## 6. Running Automated Tests

Run the complete end-to-end procurement test suite:

```bash
python manage.py test tests
```

To run the automated 25-step acceptance scenario:

```bash
python scripts/verify_acceptance_scenario.py
```

---

## 7. Core Business Rules Implemented

1. **Strict Verification Gates**: New buyers and suppliers cannot publish RFQs or submit bids until reviewed and approved by an administrator (`approval_status == 'APPROVED'`).
2. **Strict Financial Calculations**: All line items, taxes (5% UAE VAT), discounts, and totals are computed using Python `Decimal` with `ROUND_HALF_UP` quantization. No floating point errors.
3. **Multi-Factor Scoring Matrix**: Proposals are evaluated on Price (40%), Delivery Lead Time (25%), Supplier Reliability (20%), and Credit Terms (15%). The buyer makes the final informed award decision.
4. **Atomic Quotation Award**: Awarding a quotation atomically marks the winner as `ACCEPTED`, marks all competing quotes as `REJECTED`, updates RFQ status to `AWARDED`, generates the official `PurchaseOrder` with line items, and fires in-app notifications and immutable audit logs.
5. **Service Layer Payment Abstraction**: Payment plans (Full, 40/60 Advance & Balance, 3 Installments) are handled via `BasePaymentGatewayService` and `MockPaymentGatewayService`, ready for Telr/Stripe swap-in.

---

## 8. REST API Endpoints

ProcureHub includes complete Django REST Framework endpoints:

- `GET /api/categories/` - Business capability categories
- `GET /api/rfqs/` - List published requirements (filterable)
- `POST /api/rfqs/` - Create requirement (authenticated buyers)
- `GET /api/quotations/` - List quotations for RFQs
- `GET /api/orders/` - List purchase orders
- `GET /api/payments/` - Settlement transactions and installments
- `GET /api/notifications/` - User notifications feed

---

## 9. Production & Docker Deployment

### Docker Compose (PostgreSQL + Gunicorn)
```bash
docker-compose up --build -d
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py seed_demo
```

### Free-Tier Cloud Deployment (Render, Railway, Fly.io)
1. Add environment variable `DJANGO_SETTINGS_MODULE=config.settings.production`
2. Configure `DATABASE_URL` with your PostgreSQL instance.
3. Set `SECRET_KEY` and `ALLOWED_HOSTS=<your-app>.onrender.com`.
4. Build command:
   ```bash
   pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate && python manage.py seed_demo
   ```
5. Start command:
   ```bash
   gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
   ```

---

## 10. Phase 2 Recommended Enhancements

- **Real UAE Payment Gateways**: Integrate Telr or Network International via the existing `BasePaymentGatewayService`.
- **SMS & WhatsApp Dispatch**: Twilio / WhatsApp Business API notifications for RFQ deadlines and award letters.
- **S3 / Azure Blob Storage**: S3 presigned URLs for large engineering CAD drawings and spec sheets.
- **Multi-Currency Converter**: Support USD, EUR, and SAR alongside AED with live Central Bank exchange rates.
