import io
import re
import uuid
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.utils.text import slugify
from django.utils import timezone
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from products.models import Product, Category, Subcategory


# Canonical header normalization mappings
HEADER_MAP = {
    # Product Name
    "productname": "name",
    "product": "name",
    "name": "name",
    "title": "name",
    "producttitle": "name",
    "itemname": "name",

    # SKU / Product Number
    "sku": "sku",
    "productnumber": "sku",
    "productid": "sku",
    "itemcode": "sku",
    "code": "sku",

    # Brand
    "brand": "brand",
    "brandname": "brand",
    "manufacturer": "brand",

    # Category
    "category": "category",
    "categoryname": "category",
    "department": "category",

    # Subcategory
    "subcategory": "subcategory",
    "subcat": "subcategory",
    "subcategoryname": "subcategory",

    # Pricing
    "price": "price",
    "sellingprice": "price",
    "saleprice": "price",
    "offerprice": "price",
    "unitprice": "price",
    "mrp": "mrp",
    "originalprice": "mrp",
    "regularprice": "mrp",
    "listprice": "mrp",
    "cost": "mrp",

    # Stock
    "stock": "stock",
    "availablestock": "stock",
    "quantity": "stock",
    "qty": "stock",
    "inventory": "stock",

    # Unit & Measurement
    "unit": "unit",
    "uom": "unit",
    "unitvalue": "unit_value",
    "weight": "unit_value",
    "size": "unit_value",

    # Type & Status
    "type": "product_type",
    "producttype": "product_type",
    "status": "status",
    "isactive": "is_active",
    "active": "is_active",

    # Description & Image
    "description": "description",
    "shortdescription": "short_description",
    "image": "image_url",
    "imageurl": "image_url",
}


def _normalize_header(header_val):
    if not header_val:
        return ""
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", str(header_val)).lower()
    if cleaned in HEADER_MAP:
        return HEADER_MAP[cleaned]
    if "sku" in cleaned or "itemcode" in cleaned or "productcode" in cleaned:
        return "sku"
    if "productname" in cleaned or "itemname" in cleaned:
        return "name"
    if "sellingprice" in cleaned or "saleprice" in cleaned or "unitprice" in cleaned or (cleaned.startswith("price") and "mrp" not in cleaned):
        return "price"
    if "mrp" in cleaned or "originalprice" in cleaned or "regularprice" in cleaned:
        return "mrp"
    if "stock" in cleaned or "qty" in cleaned or "quantity" in cleaned:
        return "stock"
    if "subcat" in cleaned:
        return "subcategory"
    if "cat" in cleaned or "department" in cleaned:
        return "category"
    if "brand" in cleaned:
        return "brand"
    if "unitval" in cleaned or "weight" in cleaned:
        return "unit_value"
    if "unit" in cleaned or "uom" in cleaned:
        return "unit"
    if "status" in cleaned or "active" in cleaned:
        return "is_active"
    if "type" in cleaned:
        return "product_type"
    if "desc" in cleaned:
        return "description"
    return cleaned


def parse_and_validate_excel(file_obj):
    """
    Parses an uploaded Excel (.xlsx) file, maps headers intelligently,
    validates data rules, detects existing vs new products, flags conflicts,
    and returns a structured validation preview dictionary.
    """
    try:
        wb = openpyxl.load_workbook(file_obj, data_only=True)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to read Excel file. Please ensure it is a valid .xlsx file. Details: {str(e)}"
        }

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    if not rows or len(rows) < 2:
        return {
            "success": False,
            "error": "The uploaded Excel sheet is empty or only contains headers."
        }

    # Find the header row (scan first 5 rows to handle possible title banners)
    header_row_idx = None
    column_mapping = {}  # {col_idx: canonical_key}

    for idx, row in enumerate(rows[:5]):
        mapped_keys = set()
        for col_idx, cell in enumerate(row):
            norm = _normalize_header(cell)
            if norm in ("name", "sku", "price", "stock", "category"):
                mapped_keys.add(norm)
        if "name" in mapped_keys or "sku" in mapped_keys:
            header_row_idx = idx
            for col_idx, cell in enumerate(row):
                norm = _normalize_header(cell)
                if norm:
                    column_mapping[col_idx] = norm
            break

    if header_row_idx is None:
        return {
            "success": False,
            "error": "Could not identify table headers. Please include columns like 'Product Name', 'SKU', 'Price', 'Stock', 'Category'."
        }

    # Pre-load existing categories and subcategories for fast in-memory validation
    existing_categories = {c.name.strip().lower(): c for c in Category.objects.all()}
    existing_subcategories = {s.name.strip().lower(): s for s in Subcategory.objects.select_related("category").all()}

    # Pre-load existing products by SKU (product_number) and Name
    existing_products_by_sku = {}
    for p in Product.objects.all():
        if p.product_number:
            existing_products_by_sku[p.product_number.strip().lower()] = p
    existing_products_by_name = {p.name.strip().lower(): p for p in Product.objects.all()}

    valid_rows = []
    invalid_rows = []
    seen_skus_in_file = set()
    missing_categories = set()
    missing_subcategories = set()

    data_rows = rows[header_row_idx + 1:]

    for line_offset, row in enumerate(data_rows):
        excel_row_num = header_row_idx + 2 + line_offset
        if not any(cell is not None and str(cell).strip() != "" for cell in row):
            continue  # skip completely blank rows

        row_data = {}
        for col_idx, key in column_mapping.items():
            if col_idx < len(row):
                val = row[col_idx]
                row_data[key] = str(val).strip() if val is not None else ""
            else:
                row_data[key] = ""

        errors = []

        # Validate Product Name
        name = row_data.get("name", "").strip()
        if not name:
            errors.append("Product Name is required.")

        # Validate SKU
        sku = row_data.get("sku", "").strip()
        if sku:
            sku_lower = sku.lower()
            if sku_lower in seen_skus_in_file:
                errors.append(f"Duplicate SKU '{sku}' found within this Excel file.")
            else:
                seen_skus_in_file.add(sku_lower)

        # Validate Selling Price
        raw_price = row_data.get("price", "").strip()
        clean_price = re.sub(r"[^\d.]", "", raw_price)
        price_val = None
        if not clean_price:
            errors.append("Selling Price is required.")
        else:
            try:
                price_val = Decimal(clean_price)
                if price_val <= 0:
                    errors.append("Selling Price must be greater than 0.")
            except (InvalidOperation, ValueError):
                errors.append(f"Invalid Selling Price format: '{raw_price}'.")

        # Validate MRP / Original Price
        raw_mrp = row_data.get("mrp", "").strip()
        clean_mrp = re.sub(r"[^\d.]", "", raw_mrp)
        mrp_val = None
        if clean_mrp:
            try:
                mrp_val = Decimal(clean_mrp)
                if price_val and mrp_val < price_val:
                    # MRP is lower than price; default MRP to price
                    mrp_val = price_val
            except (InvalidOperation, ValueError):
                mrp_val = price_val
        else:
            mrp_val = price_val

        # Validate Stock
        raw_stock = row_data.get("stock", "").strip()
        clean_stock = re.sub(r"[^\d]", "", raw_stock)
        stock_val = 0
        if raw_stock:
            try:
                stock_val = int(clean_stock) if clean_stock else 0
                if stock_val < 0:
                    errors.append("Stock quantity cannot be negative.")
            except ValueError:
                errors.append(f"Invalid Stock value: '{raw_stock}'.")

        # Check Category
        raw_cat = row_data.get("category", "").strip()
        cat_match = None
        if raw_cat:
            cat_match = existing_categories.get(raw_cat.lower())
            if not cat_match:
                missing_categories.add(raw_cat)

        # Check Subcategory
        raw_subcat = row_data.get("subcategory", "").strip()
        subcat_match = None
        if raw_subcat:
            subcat_match = existing_subcategories.get(raw_subcat.lower())
            if not subcat_match:
                missing_subcategories.add(raw_subcat)

        # Check Unit Value
        raw_unit_val = row_data.get("unit_value", "").strip()
        clean_unit_val = re.sub(r"[^\d.]", "", raw_unit_val)
        unit_value_num = None
        if clean_unit_val:
            try:
                unit_value_num = Decimal(clean_unit_val)
            except (InvalidOperation, ValueError):
                unit_value_num = None

        # Check Active Status
        status_val = row_data.get("is_active", "").strip().lower()
        if status_val in ("active", "true", "1", "yes", "y", ""):
            is_active_val = True
        elif status_val in ("inactive", "false", "0", "no", "n"):
            is_active_val = False
        else:
            is_active_val = True

        # Check whether this product exists in DB (Matching by SKU or Name)
        existing_obj = None
        action_type = "create"
        if sku and sku.lower() in existing_products_by_sku:
            existing_obj = existing_products_by_sku[sku.lower()]
            action_type = "update"
        elif name and name.lower() in existing_products_by_name:
            existing_obj = existing_products_by_name[name.lower()]
            action_type = "update"

        processed_row = {
            "row_num": excel_row_num,
            "name": name,
            "sku": sku or (existing_obj.product_number if existing_obj else ""),
            "brand": row_data.get("brand", "").strip() or "TipsyCart",
            "category": raw_cat,
            "category_id": cat_match.id if cat_match else None,
            "category_exists": bool(cat_match),
            "subcategory": raw_subcat,
            "subcategory_id": subcat_match.id if subcat_match else None,
            "subcategory_exists": bool(subcat_match),
            "price": float(price_val) if price_val is not None else 0.0,
            "mrp": float(mrp_val) if mrp_val is not None else 0.0,
            "stock": stock_val,
            "unit": row_data.get("unit", "").strip(),
            "unit_value": float(unit_value_num) if unit_value_num is not None else None,
            "is_active": is_active_val,
            "action": action_type,
            "existing_id": existing_obj.id if existing_obj else None,
            "existing_name": existing_obj.name if existing_obj else "",
            "image_url": row_data.get("image_url", "").strip(),
            "description": row_data.get("description", "").strip(),
            "errors": errors,
        }

        if errors:
            invalid_rows.append(processed_row)
        else:
            valid_rows.append(processed_row)

    token = str(uuid.uuid4())

    create_count = sum(1 for r in valid_rows if r["action"] == "create")
    update_count = sum(1 for r in valid_rows if r["action"] == "update")

    return {
        "success": True,
        "token": token,
        "total_rows": len(valid_rows) + len(invalid_rows),
        "valid_rows_count": len(valid_rows),
        "invalid_rows_count": len(invalid_rows),
        "create_count": create_count,
        "update_count": update_count,
        "missing_categories": sorted(list(missing_categories)),
        "missing_subcategories": sorted(list(missing_subcategories)),
        "valid_rows": valid_rows,
        "invalid_rows": invalid_rows,
        # Preview rows: top 30 valid rows + top 20 invalid rows
        "preview_valid": valid_rows[:30],
        "preview_invalid": invalid_rows[:30],
    }


def commit_excel_import(valid_rows, auto_create_missing_categories=True):
    """
    Executes the validated rows into the database atomically.
    Safety guarantees:
    - Never deletes any product.
    - Never modifies orders, order items, carts, or payments.
    - Preserves existing images unless new non-empty image_url is provided.
    - Wrapped in an atomic transaction; rolls back on unhandled error.
    """
    stats = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "errors": [],
    }

    category_cache = {c.name.strip().lower(): c for c in Category.objects.all()}
    subcategory_cache = {s.name.strip().lower(): s for s in Subcategory.objects.all()}

    with transaction.atomic():
        for item in valid_rows:
            try:
                cat_obj = None
                raw_cat = item.get("category", "").strip()
                if raw_cat:
                    cat_lower = raw_cat.lower()
                    if cat_lower in category_cache:
                        cat_obj = category_cache[cat_lower]
                    elif auto_create_missing_categories:
                        cat_slug = slugify(raw_cat)
                        # Ensure unique slug
                        base_slug = cat_slug
                        cnt = 1
                        while Category.objects.filter(slug=cat_slug).exists():
                            cat_slug = f"{base_slug}-{cnt}"
                            cnt += 1
                        cat_obj = Category.objects.create(name=raw_cat, slug=cat_slug, is_active=True)
                        category_cache[cat_lower] = cat_obj

                subcat_obj = None
                raw_subcat = item.get("subcategory", "").strip()
                if raw_subcat:
                    subcat_lower = raw_subcat.lower()
                    if subcat_lower in subcategory_cache:
                        subcat_obj = subcategory_cache[subcat_lower]
                    elif auto_create_missing_categories and cat_obj:
                        subcat_slug = slugify(raw_subcat)
                        base_slug = subcat_slug
                        cnt = 1
                        while Subcategory.objects.filter(slug=subcat_slug).exists():
                            subcat_slug = f"{base_slug}-{cnt}"
                            cnt += 1
                        subcat_obj = Subcategory.objects.create(
                            category=cat_obj,
                            name=raw_subcat,
                            slug=subcat_slug,
                            is_active=True
                        )
                        subcategory_cache[subcat_lower] = subcat_obj

                # Find product to update or create
                existing_id = item.get("existing_id")
                prod = None
                if existing_id:
                    try:
                        prod = Product.objects.get(id=existing_id)
                    except Product.DoesNotExist:
                        prod = None

                if not prod and item.get("sku"):
                    prod = Product.objects.filter(product_number__iexact=item["sku"]).first()

                if prod:
                    # UPDATE EXISTING PRODUCT
                    # Safe update: never delete, preserve image if none provided
                    prod.name = item["name"]
                    prod.price = Decimal(str(item["price"]))
                    if item.get("mrp"):
                        prod.original_price = Decimal(str(item["mrp"]))
                    prod.stock = item["stock"]
                    if item.get("brand"):
                        prod.brand = item["brand"]
                    if item.get("unit"):
                        prod.unit = item["unit"]
                    if item.get("unit_value"):
                        prod.unit_value = Decimal(str(item["unit_value"]))
                    prod.is_active = item["is_active"]
                    if cat_obj:
                        prod.category_ref = cat_obj
                        prod.category = cat_obj.name
                    if subcat_obj:
                        prod.subcategory_ref = subcat_obj
                        prod.subcategory = subcat_obj.name
                    if item.get("description"):
                        prod.description = item["description"]
                    
                    prod.save()
                    stats["updated"] += 1

                else:
                    # CREATE NEW PRODUCT
                    sku_val = item.get("sku", "").strip()
                    if not sku_val:
                        sku_val = f"TC-PRD-{int(timezone.now().timestamp() * 1000) % 1000000}"

                    prod = Product.objects.create(
                        name=item["name"],
                        product_number=sku_val,
                        brand=item.get("brand") or "TipsyCart",
                        category_ref=cat_obj,
                        category=cat_obj.name if cat_obj else "",
                        subcategory_ref=subcat_obj,
                        subcategory=subcat_obj.name if subcat_obj else "",
                        price=Decimal(str(item["price"])),
                        original_price=Decimal(str(item.get("mrp") or item["price"])),
                        stock=item["stock"],
                        unit=item.get("unit") or "Piece",
                        unit_value=Decimal(str(item["unit_value"])) if item.get("unit_value") else None,
                        is_active=item["is_active"],
                        description=item.get("description") or "",
                    )
                    stats["created"] += 1

            except Exception as e:
                stats["errors"].append(f"Row {item.get('row_num', '?')}: {str(e)}")

    return stats


def generate_import_error_excel(invalid_rows):
    """
    Generates an Excel spreadsheet containing rejected/invalid rows
    with their exact error explanations, allowing easy review and correction.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Rejected Rows - Errors"
    ws.views.sheetView[0].showGridLines = True

    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="991B1B", end_color="991B1B", fill_type="solid")  # Crimson Red
    border = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0"),
    )

    headers = [
        "Row #",
        "Product Name",
        "SKU",
        "Brand",
        "Category",
        "Subcategory",
        "Selling Price",
        "MRP",
        "Stock",
        "Unit",
        "Status",
        "Rejection Reasons / Errors",
    ]

    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border
    ws.row_dimensions[1].height = 26

    error_font = Font(name="Calibri", size=10, color="991B1B", bold=True)
    data_font = Font(name="Calibri", size=10)

    for row_idx, r in enumerate(invalid_rows, start=2):
        row_vals = [
            r.get("row_num"),
            r.get("name"),
            r.get("sku"),
            r.get("brand"),
            r.get("category"),
            r.get("subcategory"),
            r.get("price"),
            r.get("mrp"),
            r.get("stock"),
            r.get("unit"),
            "Active" if r.get("is_active") else "Inactive",
            " | ".join(r.get("errors", [])),
        ]
        for col_idx, val in enumerate(row_vals, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.border = border
            if col_idx == 12:
                cell.font = error_font
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            else:
                cell.font = data_font
                cell.alignment = Alignment(horizontal="center" if col_idx in [1, 3, 7, 8, 9, 10, 11] else "left", vertical="center")

    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = 20
    ws.column_dimensions["L"].width = 50

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def generate_sample_excel_template():
    """
    Generates a professionally styled sample .xlsx template that the admin
    can download and fill out to import products.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "TipsyCart Import Template"
    ws.views.sheetView[0].showGridLines = True

    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="A51655", end_color="A51655", fill_type="solid")
    example_fill = PatternFill(start_color="FDF2F8", end_color="FDF2F8", fill_type="solid")
    data_font = Font(name="Calibri", size=10)
    border = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0"),
    )

    headers = [
        "Product Name *",
        "SKU / Product Code",
        "Brand",
        "Category *",
        "Subcategory",
        "Selling Price (₹) *",
        "MRP (₹)",
        "Stock Quantity *",
        "Unit (e.g. Kg, Piece, Gram)",
        "Unit Value (e.g. 1, 500)",
        "Product Status (Active/Inactive)",
        "Description",
    ]

    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border
    ws.row_dimensions[1].height = 26

    sample_rows = [
        ["Fresh Apples (Kinnaur)", "TC-APL-01", "Tipsy Fresh Cuts", "Groceries", "Fruits", 149.00, 175.00, 50, "Kg", 1, "Active", "Crisp juicy fresh Kinnaur apples."],
        ["Aashirvaad Shudh Chakki Atta", "TC-ATA-05", "Aashirvaad", "Daily Essentials", "Atta & Flours", 265.00, 295.00, 35, "Kg", 5, "Active", "100% whole wheat chakki atta."],
        ["Vim Dishwash Liquid Gel", "TC-VIM-500", "Vim", "Personal Care", "Cleaning", 115.00, 145.00, 40, "ml", 500, "Active", "Power of 100 lemons for grease cleaning."],
        ["Bhatinda Chikki Crunchy Peanut", "TC-CHK-450", "TipsyCart", "Gajak & Chikki", "Chikki", 210.00, 220.00, 25, "Gram", 450, "Active", "Traditional peanut jaggery brittle."],
        ["Bluetooth Wireless Earbuds", "TC-AUD-99", "Boat", "Mobile Accessories", "Headphones", 899.00, 1499.00, 15, "Piece", 1, "Active", "High bass fast charging earbuds."],
    ]

    for row_idx, r_data in enumerate(sample_rows, start=2):
        for col_idx, val in enumerate(r_data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = data_font
            cell.fill = example_fill
            cell.border = border
            if col_idx in [6, 7]:
                cell.number_format = "₹#,##0.00"
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif col_idx in [8, 10]:
                cell.alignment = Alignment(horizontal="right", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = 22
    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["L"].width = 36

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
