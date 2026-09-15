from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.accounts.models import UserRole, ApprovalStatus
from apps.customers.models import CustomerProfile, UAEEmirate
from apps.suppliers.models import SupplierProfile
from apps.rfqs.models import Category, RFQ, RFQItem, RFQStatus
from apps.quotations.models import Quotation, QuotationItem, QuotationStatus
from apps.procurement.services import evaluate_rfq_quotations
from apps.notifications.models import Notification, NotificationType
from apps.audit.models import ActivityLog

User = get_user_model()


class Command(BaseCommand):
    help = "Seed realistic UAE/Dubai enterprise procurement demo data."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding ProcureHub UAE Demo Database..."))

        # 1. Categories
        categories_data = [
            ("Office Furniture", "box", "Executive desks, ergonomic seating, conference setups, storage"),
            ("Electrical Equipment", "zap", "Cables, distribution boards, lighting, industrial switches"),
            ("IT Equipment", "server", "Laptops, network switches, enterprise servers, monitors"),
            ("Stationery & Supplies", "file-text", "Corporate stationery, paper products, desktop materials"),
            ("Safety Equipment", "shield", "PPE, fire alarms, safety harnesses, hazardous material gear"),
            ("Cleaning Supplies", "sparkles", "Commercial sanitization chemicals, cleaning equipment"),
        ]
        created_categories = {}
        for name, icon, desc in categories_data:
            cat, _ = Category.objects.get_or_create(
                name=name,
                defaults={'icon': icon, 'description': desc}
            )
            created_categories[name] = cat
        self.stdout.write(self.style.SUCCESS(f"Loaded {len(created_categories)} business categories."))

        # 2. Users (Admin, Customer, 3 Suppliers, 1 Pending Buyer, 1 Pending Supplier)
        DEMO_PASSWORD = "Demo123456!"

        # Admin
        admin_user, _ = User.objects.get_or_create(
            email="admin@procurehub.demo",
            defaults={
                'username': "admin@procurehub.demo",
                'first_name': "Hamdan",
                'last_name': "Al-Maktoum",
                'company_name': "ProcureHub UAE Governance Committee",
                'phone': "+971 4 330 0000",
                'role': UserRole.ADMIN,
                'approval_status': ApprovalStatus.APPROVED,
                'is_staff': True,
                'is_superuser': True,
            }
        )
        admin_user.set_password(DEMO_PASSWORD)
        admin_user.save()

        # Customer / Buyer (Al-Futtaim Logistics Buyer)
        customer_user, _ = User.objects.get_or_create(
            email="customer@procurehub.demo",
            defaults={
                'username': "customer@procurehub.demo",
                'first_name': "Tariq",
                'last_name': "Al-Mansoor",
                'company_name': "Al-Futtaim Enterprises UAE LLC",
                'phone': "+971 4 213 1111",
                'role': UserRole.CUSTOMER,
                'approval_status': ApprovalStatus.APPROVED,
            }
        )
        customer_user.set_password(DEMO_PASSWORD)
        customer_user.save()

        CustomerProfile.objects.get_or_create(
            user=customer_user,
            defaults={
                'trade_license_number': "CN-DED-884920",
                'tax_registration_number': "100293847500003",
                'industry': "Conglomerate Logistics & Commercial Retail",
                'contact_person_designation': "VP of Group Procurement",
                'emirate': UAEEmirate.DUBAI,
                'office_address': "Floor 22, Festival Tower, Dubai Festival City, Dubai, UAE"
            }
        )

        # Pending Customer
        pending_buyer, _ = User.objects.get_or_create(
            email="pending_buyer@procurehub.demo",
            defaults={
                'username': "pending_buyer@procurehub.demo",
                'first_name': "Fatima",
                'last_name': "Al-Zahra",
                'company_name': "Emaar Hospitality Group PJSC",
                'phone': "+971 4 367 3333",
                'role': UserRole.CUSTOMER,
                'approval_status': ApprovalStatus.PENDING,
            }
        )
        pending_buyer.set_password(DEMO_PASSWORD)
        pending_buyer.save()

        CustomerProfile.objects.get_or_create(
            user=pending_buyer,
            defaults={
                'trade_license_number': "CN-DED-910283",
                'tax_registration_number': "100987654300003",
                'industry': "Hospitality & Leisure",
                'contact_person_designation': "Procurement Director",
                'emirate': UAEEmirate.DUBAI,
                'office_address': "Downtown Dubai, Emaar Square Bldg 4, Dubai, UAE"
            }
        )

        # Suppliers 1, 2, 3
        suppliers_info = [
            (
                "supplier1@procurehub.demo", "Rashid", "Khan",
                "Emirates Office Solutions LLC", "+971 4 347 5555",
                "DED-774921", UAEEmirate.DUBAI, "Warehouse 14, Al Quoz Industrial 3, Dubai",
                Decimal('4.90'), 8, "Office Furniture, Commercial Workspace Equipment"
            ),
            (
                "supplier2@procurehub.demo", "Bilal", "Ahmed",
                "Gulf Commercial Supplies FZCO", "+971 4 883 2222",
                "DAFZA-COMM-3921", UAEEmirate.DUBAI, "Plot 5B, Dubai Airport Freezone (DAFZA), Dubai",
                Decimal('4.65'), 5, "Office Furniture, Electrical Equipment, IT Hardware"
            ),
            (
                "supplier3@procurehub.demo", "Zaid", "Al-Qasimi",
                "Dubai Furnishings & Tech Ltd", "+971 6 542 9999",
                "SHJ-IND-48210", UAEEmirate.SHARJAH, "Industrial Area 13, Sharjah / Showroom Sheikh Zayed Rd",
                Decimal('4.40'), 12, "Office Furniture, Industrial Machinery"
            ),
        ]

        created_suppliers = []
        for email, fn, ln, cname, phone, tlic, em, addr, rating, yrs, cats in suppliers_info:
            suser, _ = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': email,
                    'first_name': fn,
                    'last_name': ln,
                    'company_name': cname,
                    'phone': phone,
                    'role': UserRole.SUPPLIER,
                    'approval_status': ApprovalStatus.APPROVED,
                }
            )
            suser.set_password(DEMO_PASSWORD)
            suser.save()

            SupplierProfile.objects.get_or_create(
                user=suser,
                defaults={
                    'trade_license_number': tlic,
                    'tax_registration_number': f"100{tlic[-6:]}00003",
                    'emirate': em,
                    'office_address': addr,
                    'supplier_rating': rating,
                    'years_in_business': yrs,
                    'business_categories': cats,
                    'is_verified': True,
                }
            )
            created_suppliers.append(suser)

        self.stdout.write(self.style.SUCCESS("Demo users and verified UAE profiles created."))

        # 3. Create Realistic Published RFQ: "Office Furniture Requirement - Dubai"
        rfq, _ = RFQ.objects.get_or_create(
            customer=customer_user,
            title="Office Furniture Requirement - Dubai Marina HQ",
            defaults={
                'category': created_categories["Office Furniture"],
                'description': (
                    "Complete supply, delivery, and ergonomic workstation fit-out for our newly leased corporate "
                    "offices at Marina Plaza. High durability, ESMA compliance certificates, and 3+ year warranty required."
                ),
                'delivery_location': "Level 18, Marina Plaza Tower, Dubai Marina, Dubai, UAE",
                'emirate': UAEEmirate.DUBAI,
                'delivery_deadline': timezone.now().date() + timezone.timedelta(days=35),
                'submission_deadline': timezone.now() + timezone.timedelta(days=12),
                'status': RFQStatus.QUOTATIONS_RECEIVED,
                'preferred_terms': "Net 30 Days from Inspection",
                'estimated_budget': Decimal('55000.00'),
                'additional_notes': "Delivery must be scheduled during non-peak freight hours (after 7 PM) per building management rules."
            }
        )

        item1, _ = RFQItem.objects.get_or_create(
            rfq=rfq,
            item_name="Executive Ergonomic High-Back Chair",
            defaults={
                'quantity': Decimal('50.00'),
                'unit': "Pcs",
                'specifications': "Breathable high-tensile mesh, synchronized tilt-mechanism, adjustable 3D armrests, ESMA certified",
                'preferred_brand': "Herman Miller / Steelcase or equivalent"
            }
        )
        item2, _ = RFQItem.objects.get_or_create(
            rfq=rfq,
            item_name="Energy-Efficient Ceiling Ventilation Fan",
            defaults={
                'quantity': Decimal('30.00'),
                'unit': "Pcs",
                'specifications': "1200mm sweep, BLDC low-noise motor, remote control, 5-star ESMA rating",
                'preferred_brand': "Panasonic / Havells or equivalent"
            }
        )
        item3, _ = RFQItem.objects.get_or_create(
            rfq=rfq,
            item_name="Heavy-Duty Modular Workstation Desk",
            defaults={
                'quantity': Decimal('25.00'),
                'unit': "Sets",
                'specifications': "1500mm x 750mm x 750mm, powder-coated steel leg frame, cable management conduit, privacy acoustic screen",
                'preferred_brand': "Commercial grade melamine"
            }
        )

        self.stdout.write(self.style.SUCCESS(f"Loaded procurement RFQ {rfq.rfq_number} with 3 line items."))

        # 4. Create Quotations from All 3 Suppliers
        # Supplier 1: Emirates Office Solutions (Best Balanced, Recommended)
        # 50 chairs @ 420 = 21,000 | 30 fans @ 180 = 5,400 | 25 desks @ 790 = 19,750 | Sub: 46,150 | VAT 5%: 2,307.50 | Disc: 0 | Grand: 48,457.50
        q1, _ = Quotation.objects.get_or_create(
            rfq=rfq,
            supplier=created_suppliers[0],
            defaults={
                'validity_date': timezone.now().date() + timezone.timedelta(days=30),
                'delivery_days': 7,
                'payment_terms': "Net 30 Days from Delivery",
                'notes': "Includes complete delivery, on-site assembly, and 3-year warranty across Dubai.",
                'status': QuotationStatus.SUBMITTED
            }
        )
        QuotationItem.objects.get_or_create(
            quotation=q1,
            rfq_item=item1,
            defaults={'quantity': Decimal('50.00'), 'unit_price': Decimal('420.00'), 'discount': Decimal('0.00'), 'tax_rate': Decimal('5.00'), 'remarks': "Model: Ergofit Pro Mesh (Grade A)"}
        )
        QuotationItem.objects.get_or_create(
            quotation=q1,
            rfq_item=item2,
            defaults={'quantity': Decimal('30.00'), 'unit_price': Decimal('180.00'), 'discount': Decimal('0.00'), 'tax_rate': Decimal('5.00'), 'remarks': "Model: Panasonic WhisperBLDC 1200mm"}
        )
        QuotationItem.objects.get_or_create(
            quotation=q1,
            rfq_item=item3,
            defaults={'quantity': Decimal('25.00'), 'unit_price': Decimal('790.00'), 'discount': Decimal('0.00'), 'tax_rate': Decimal('5.00'), 'remarks': "Model: ModularSteel 150 Desk Set"}
        )
        q1.calculate_totals()

        # Supplier 2: Gulf Commercial Supplies (Lowest Raw Price, Longer Lead Time)
        # 50 chairs @ 390 = 19,500 | 30 fans @ 170 = 5,100 | 25 desks @ 760 = 19,000 | Sub: 43,600 | Disc: 500 = 43,100 | VAT 5%: 2,155 | Grand: 45,255.00
        q2, _ = Quotation.objects.get_or_create(
            rfq=rfq,
            supplier=created_suppliers[1],
            defaults={
                'validity_date': timezone.now().date() + timezone.timedelta(days=20),
                'delivery_days': 16,
                'payment_terms': "50% Advance / 50% on Delivery",
                'notes': "Direct factory imports from JAFZA warehouse. Assembly available at additional AED 500.",
                'status': QuotationStatus.SUBMITTED
            }
        )
        QuotationItem.objects.get_or_create(
            quotation=q2,
            rfq_item=item1,
            defaults={'quantity': Decimal('50.00'), 'unit_price': Decimal('390.00'), 'discount': Decimal('200.00'), 'tax_rate': Decimal('5.00'), 'remarks': "Direct factory import equivalent"}
        )
        QuotationItem.objects.get_or_create(
            quotation=q2,
            rfq_item=item2,
            defaults={'quantity': Decimal('30.00'), 'unit_price': Decimal('170.00'), 'discount': Decimal('100.00'), 'tax_rate': Decimal('5.00'), 'remarks': "Standard ESMA certified BLDC"}
        )
        QuotationItem.objects.get_or_create(
            quotation=q2,
            rfq_item=item3,
            defaults={'quantity': Decimal('25.00'), 'unit_price': Decimal('760.00'), 'discount': Decimal('200.00'), 'tax_rate': Decimal('5.00'), 'remarks': "JAFZA stock modular workstations"}
        )
        q2.calculate_totals()

        # Supplier 3: Dubai Furnishings Ltd (Fastest Delivery, Slightly Higher Price)
        # 50 chairs @ 450 = 22,500 | 30 fans @ 200 = 6,000 | 25 desks @ 820 = 20,500 | Sub: 49,000 | VAT: 2,450 | Grand: 51,450.00
        q3, _ = Quotation.objects.get_or_create(
            rfq=rfq,
            supplier=created_suppliers[2],
            defaults={
                'validity_date': timezone.now().date() + timezone.timedelta(days=45),
                'delivery_days': 4,
                'payment_terms': "Net 60 Days",
                'notes': "Immediate stock available in Sharjah central logistics hub. Guaranteed 4-day delivery.",
                'status': QuotationStatus.SUBMITTED
            }
        )
        QuotationItem.objects.get_or_create(
            quotation=q3,
            rfq_item=item1,
            defaults={'quantity': Decimal('50.00'), 'unit_price': Decimal('450.00'), 'discount': Decimal('0.00'), 'tax_rate': Decimal('5.00'), 'remarks': "Express ready stock Herman Miller licensed"}
        )
        QuotationItem.objects.get_or_create(
            quotation=q3,
            rfq_item=item2,
            defaults={'quantity': Decimal('30.00'), 'unit_price': Decimal('200.00'), 'discount': Decimal('0.00'), 'tax_rate': Decimal('5.00'), 'remarks': "ESMA 5-star ventilation"}
        )
        QuotationItem.objects.get_or_create(
            quotation=q3,
            rfq_item=item3,
            defaults={'quantity': Decimal('25.00'), 'unit_price': Decimal('820.00'), 'discount': Decimal('0.00'), 'tax_rate': Decimal('5.00'), 'remarks': "Heavy duty steel frames"}
        )
        q3.calculate_totals()

        # 5. Run Evaluation Engine for this RFQ
        evaluate_rfq_quotations(rfq)
        self.stdout.write(self.style.SUCCESS("Evaluated 3 competitive quotations with weighted scores."))

        # 6. Pre-seed notifications (idempotent lookup by recipient and link)
        Notification.objects.get_or_create(
            recipient=customer_user,
            link=f"/portal/customer/rfqs/{rfq.id}/compare/",
            defaults={
                'title': f"3 Quotations Received for {rfq.rfq_number}",
                'message': "Emirates Office Solutions, Gulf Commercial Supplies, and Dubai Furnishings have submitted bids.",
                'notification_type': NotificationType.INFO,
            }
        )

        # 7. Pre-seed activity logs (idempotent: avoid duplicate log entries)
        if not ActivityLog.objects.filter(action="SEED_DATABASE").exists():
            ActivityLog.log(
                user=customer_user,
                action="SEED_DATABASE",
                description="Initialized realistic Dubai enterprise demo procurement scenario with 3 suppliers."
            )

        self.stdout.write(self.style.SUCCESS("""
================================================================
ProcureHub UAE Demo Seed Completed Successfully!
================================================================
Demo Credentials (Password for all: Demo123456!):

1. Admin:
   Email: admin@procurehub.demo
   Role:  ADMIN

2. Buyer / Customer:
   Email: customer@procurehub.demo
   Role:  CUSTOMER (Al-Futtaim Enterprises UAE LLC)

3. Suppliers:
   - supplier1@procurehub.demo (Emirates Office Solutions LLC)
   - supplier2@procurehub.demo (Gulf Commercial Supplies FZCO)
   - supplier3@procurehub.demo (Dubai Furnishings & Tech Ltd)

4. Pre-populated RFQ:
   RFQ-2026-0001: "Office Furniture Requirement - Dubai Marina HQ"
   - 3 Submitted Quotations with 4-Way Weighted Scores Ready for Comparison!
================================================================
"""))
