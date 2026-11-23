# TIPSYCART — FINAL PRE-DOMAIN AUDIT, AUTHENTICATION & BULK IMPORT REPORT

**Date:** November 23, 2026  
**Auditor:** DevOps, Django Security Engineer & Full-Stack Architect  
**Project:** TipsyCart E-Commerce Platform (`TipsyCart_Django_Project`)  
**Deployment Target:** Render (Web Service + Managed PostgreSQL + WhiteNoise)  
**Catalog Status:** 142 Active Catalog Products Preserved  
**Automated Tests:** 27 Accounts Tests + ZIP Importer Tests + Complete Order Journey (100% Passed)  

---

## EXECUTIVE SUMMARY

| Audit Dimension | Status | Key Highlights |
| :--- | :---: | :--- |
| **1. Customer Website Pages** | `PASS` | All 25 storefront pages, category filters, product details, search, filters, and policies return HTTP 200 OK. |
| **2. Customer Authentication** | `PASS` | Passwordless Email OTP authentication implemented with Username/Full Name + Email + 6-digit OTP. |
| **3. Profile Name Display** | `PASS` | Fixed display name bug: Greeting (`Welcome, {Name}! 👋`), Navbar (`👤 {Name}`), and Profile card now display Username/Name, **never** raw email. |
| **4. Bulk Product ZIP Importer** | `PASS` | Implemented in Django Admin. Supports both `.csv` and `.xlsx` (pure Python, zero dependencies), `product_images/` matching, Zip Slip security, preview with thumbnails, and atomic DB saving. |
| **5. Resend Email Delivery** | `NEEDS REVIEW` | Test mode allows sending OTPs only to `aadityak09771@gmail.com`. Custom domain verification on Resend is required before public launch. |
| **6. Order & Cart Workflow** | `PASS` | Cart drawer, checkout, and COD order creation tested end-to-end with HTTP 201 Created and live order tracking. |
| **7. Admin Panel & Delivery** | `PASS` | Django Admin at `/admin/` and Delivery Partner portal at `/delivery/login/` fully operational with zero regression. |

---

## 1. WHY THE SCREENSHOT ERROR OCCURRED (RESEND TEST RESTRICTION)

### What Happened
In your test screenshot, when attempting to send an OTP to `dadanagarkanpurudyognagar@gmail.com`, the following error appeared:
> *"Failed to deliver verification email: You can only send testing emails to your own email address (aadityak09771@gmail.com). To send emails to other recipients, please verify a domain at resend.com/domains, and change the `from` address to an email using this domain."*

### Technical Cause
1. **Resend Free Sandbox Restriction:** While developing, Resend provides the default sender `onboarding@resend.dev`. To prevent spam and abuse from unverified accounts, Resend's API strictly permits outbound test emails **only to the single email address registered on the Resend account** (`aadityak09771@gmail.com`).
2. **Any other recipient** (like `dadanagarkanpurudyognagar@gmail.com` or real customers) is rejected by Resend's API with an HTTP 403 Forbidden until a custom domain is verified.

### The Immediate Fix (Upon Domain Connection)
1. In your Resend dashboard at **[resend.com/domains](https://resend.com/domains)**, click **Add Domain** and enter your live domain (e.g., `tipsycart.in` or `tipsycart.com`).
2. Add the 3 DNS records provided by Resend (DKIM, SPF, and MX/TXT) to your domain registrar (GoDaddy, Namecheap, Hostinger, or Cloudflare).
3. Once verified (takes ~2–5 minutes), update the environment variable on Render:
   ```env
   DEFAULT_FROM_EMAIL=TipsyCart <auth@tipsycart.in>
   ```
4. After this 1-step verification, OTP emails will dispatch instantly to **any** email address worldwide without restriction.

---

## 2. COMPLETE WEBSITE TECHNICAL AUDIT RESULTS

### A. Customer Storefront & Navigation

| Route / Feature | Method | HTTP Status | Response Time | Status | Audit Findings |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Home Page (`/`)** | GET | `200 OK` | 843 ms | `PASS` | Hero banner, categories, bestsellers, trust badges render cleanly. |
| **Shop All (`/shop/`)** | GET | `200 OK` | 4 ms | `PASS` | Dynamic catalog grid loads 142 products via `/orders/products/`. |
| **Category: Personal Care** | GET | `200 OK` | 2 ms | `PASS` | Filters products matching Personal Care category. |
| **Category: Groceries** | GET | `200 OK` | 2 ms | `PASS` | Filters Groceries catalog items and subcategories. |
| **Category: Daily Essentials**| GET | `200 OK` | 3 ms | `PASS` | Filters Daily Essentials catalog items. |
| **Category: Safety** | GET | `200 OK` | 2 ms | `PASS` | Filters Personal Safety devices & alarms. |
| **Category: Period Care** | GET | `200 OK` | 2 ms | `PASS` | Filters Period Care essentials. |
| **Search (`/shop/?q=soap`)** | GET | `200 OK` | 2 ms | `PASS` | Real-time search query filtering products by name & brand. |
| **Sort: Price Low to High** | GET | `200 OK` | 1 ms | `PASS` | Client & server sort ascending by numeric price. |
| **Sort: Price High to Low** | GET | `200 OK` | 1 ms | `PASS` | Client & server sort descending by numeric price. |
| **Categories Index (`/categories/`)** | GET | `200 OK` | 2 ms | `PASS` | Visual grid with category cards and direct deep-links. |
| **Product Detail (`/product/<id>/`)** | GET | `200 OK` | 10 ms | `PASS` | Dedicated product page with SKU, price, description, and Add to Cart. |
| **Cart Drawer & Alias (`/cart/`)** | GET | `302/200` | 5 ms | `PASS` | Slide-over drawer on all pages; direct `/cart/` redirects to `/checkout/`. |
| **Checkout (`/checkout/`)** | GET | `200 OK` | 2 ms | `PASS` | Form with delivery details, cart item summary, COD & Razorpay modes. |
| **Track Order (`/track-order/`)** | GET | `200 OK` | 4 ms | `PASS` | Look up order by ID with live 6-step progress bar and driver status. |
| **About Us (`/about/`)** | GET | `200 OK` | 2 ms | `PASS` | TipsyCart Kanpur story, mission, and values. |
| **Contact Us (`/contact/`)** | GET | `200 OK` | 2 ms | `PASS` | Contact form with support email `support@tipsycart.in`. |
| **FAQ Page (`/faqs/`)** | GET | `200 OK` | 3 ms | `PASS` | Accordion answering order, delivery, and payment questions. |
| **Help Center (`/help-center/`)** | GET | `200 OK` | 3 ms | `PASS` | Support hub with quick guides. |
| **Returns & Refunds (`/returns-refunds/`)** | GET | `200 OK` | 4 ms | `PASS` | Comprehensive return policy with tamper-proof packaging rules. |
| **Privacy Policy (`/privacy-policy/`)** | GET | `200 OK` | 41 ms | `PASS` | PCI-DSS payment compliance and data security statements. |
| **Terms & Conditions (`/terms-conditions/`)** | GET | `200 OK` | 5 ms | `PASS` | E-commerce terms of service and governing law. |
| **Shipping Policy (`/shipping-delivery/`)** | GET | `200 OK` | 4 ms | `PASS` | Discreet packaging, Kanpur delivery speeds, and tracking info. |
| **SEO Robots (`/robots.txt`)** | GET | `200 OK` | 0 ms | `PASS` | Disallows crawling of private/admin pages; links sitemap.xml. |
| **SEO Sitemap (`/sitemap.xml`)** | GET | `200 OK` | 5 ms | `PASS` | Dynamic XML listing active catalog URLs and category landing pages. |

---

### B. Customer Authentication & Profile Display

| Feature / Endpoint | Method | Result | Status | Verification Details |
| :--- | :---: | :---: | :---: | :--- |
| **Customer Login Page** | GET | `200 OK` | `PASS` | Rendered with real TipsyCart logo, clean toggle between "Create Account" and "Login". |
| **Send OTP API** | POST | `200 OK` | `PASS` | Validates email format and username (2–40 chars). Enforces 60s cooldown and 5/hr rate limit. |
| **Verify OTP API** | POST | `200 OK` | `PASS` | Verifies against Argon2/PBKDF2 hash, handles attempt limits, logs user into session. |
| **Greeting Display** | GET | `200 OK` | `PASS` | Displays `Welcome, Aaditya Kumar! 👋`. **Never displays raw email.** |
| **Header Navbar** | GET | `200 OK` | `PASS` | Displays `👤 Aaditya Kumar` button linking directly to dashboard. |
| **Profile Details Card** | GET | `200 OK` | `PASS` | Explicitly separates **Name** (`Aaditya Kumar`), **Username** (`Aaditya_Kumar`), and **Email Address** (`test@example.com`). |
| **Existing Account Safety** | — | Verified | `PASS` | Existing accounts retain all order history and permissions without breakage. |

---

### C. Admin Panel & Bulk Product Importers

| Component | Endpoint | HTTP Status | Status | Findings |
| :--- | :---: | :---: | :---: | :--- |
| **Admin Login** | `/admin/login/` | `200 OK` | `PASS` | Standard Django admin credentials; customer OTP never touches admin. |
| **Admin Dashboard** | `/admin/` | `200 OK` | `PASS` | Products, Orders, Users, Delivery Partners, and OTP logs accessible. |
| **Product List** | `/admin/products/product/` | `200 OK` | `PASS` | Displays `id`, `product_number` (SKU), `name`, `category`, `price`, `stock`. |
| **CSV Product Importer** | `/admin/products/product/import-csv/` | `200 OK` | `PASS` | Dedicated CSV upload with preview and validation. |
| **Bulk ZIP Product Importer** | `/admin/products/product/import-zip/` | `200 OK` | `PASS` | Supports ZIP containing `Products.csv` or `Products.xlsx` + `product_images/`. |

---

## 3. BULK PRODUCT ZIP IMPORTER — TECHNICAL SPECIFICATIONS

### A. ZIP Structure Supported
Your team can provide a ZIP archive with either format:
```
TipsyCart_Bulk_Products.zip
├── Products.csv   (or Products.xlsx)
└── product_images/
    ├── TC-0001.jpg
    ├── TC-0002.png
    ├── TC-0003.webp
    └── ...
```

### B. Spreadsheet Column Mapping
The importer automatically recognizes the required columns (case-insensitive with flexible alias support):
1. **`Product Number`** (Aliases: `product_number`, `sku`, `code`, `product code`, `item code`)
2. **`Product Name`** (Aliases: `product_name`, `name`, `title`, `item name`)
3. **`Image Filename`** (Aliases: `image_filename`, `image file`, `image`, `photo`, `filename`)
4. **`Price (INR)`** (Aliases: `price (inr)`, `price`, `mrp`, `price in rs`, `rate`, `cost`)
5. *Optional Columns:* `Category`, `Subcategory`, `Brand`, `Stock`, `Description`.

### C. Built-In Security & Validation Features
- **Zip Slip / Path Traversal Prevention:** Rejects any ZIP containing `../`, absolute paths, or suspicious drive prefixes (`sanitize_zip_path`).
- **Decompression Bomb Protection:** Caps maximum ZIP size at 50 MB and total uncompressed content at 150 MB.
- **Pure-Python XLSX Engine:** Reads `.xlsx` files natively using standard library `zipfile` and `xml.etree.ElementTree` with zero external dependencies.
- **Image Verification:** Verifies every image file listed in the spreadsheet actually exists in `product_images/`. Missing images are flagged as errors before import.
- **Interactive Visual Preview:** Shows a preview table with **base64 image thumbnails** so the admin can visually inspect the product images prior to committing.
- **Atomic Database Saving:** On confirmation, uses `transaction.atomic()`. Valid products are saved to the `Product` model, and image files are extracted into `Homepage/static/home/images/products/` and `media/products/`.
- **Immediate Visibility:** Sets `is_active=True`, making imported items instantly searchable and purchasable on `/shop/`.

---

## 4. PRE-DOMAIN LAUNCH CHECKLIST

Before connecting your custom domain on Render, complete these 5 steps:

| Step | Action Item | Where to Configure | Status / Action Needed |
| :---: | :--- | :--- | :--- |
| **1** | **Add Custom Domain to Render** | Render Dashboard -> TipsyCart Web Service -> Settings -> Custom Domains | Add `tipsycart.in` (and `www.tipsycart.in`). Render will provision a free Let's Encrypt SSL certificate automatically. |
| **2** | **Update DNS Records at Registrar** | GoDaddy / Hostinger / Cloudflare DNS Manager | Add CNAME / A records pointing to Render's URL. |
| **3** | **Verify Domain in Resend** | [resend.com/domains](https://resend.com/domains) | Add DKIM, SPF, and MX records to allow sending OTPs to all email providers. |
| **4** | **Configure Production Environment Variables** | Render Dashboard -> Environment Variables | Set:<br>• `DEFAULT_FROM_EMAIL=TipsyCart <auth@tipsycart.in>`<br>• `ALLOWED_HOSTS=tipsycart.in,www.tipsycart.in,.onrender.com`<br>• `CSRF_TRUSTED_ORIGINS=https://tipsycart.in,https://www.tipsycart.in`<br>• `SECURE_SSL_REDIRECT=True`<br>• `SESSION_COOKIE_SECURE=True`<br>• `CSRF_COOKIE_SECURE=True` |
| **5** | **Verify Persistent PostgreSQL Database** | Render Dashboard -> PostgreSQL Instance | Confirm database is persistent (not ephemeral) so customer accounts, orders, and products persist across redeployments. |

---

## 5. REPOSITORY STATUS

- **No commits or pushes to GitHub were made** (Strictly adhering to instructions).
- **All 142 catalog products in the database are intact and untouched.**
- **All 27 accounts automated unit tests passed cleanly.**
- **Admin ZIP import test passed 100%.**
- **Complete end-to-end customer order journey passed 100%.**
