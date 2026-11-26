import io
import logging
import re
import uuid
import os
import mimetypes
import base64
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)
from django.db import transaction
from django.utils.text import slugify
from django.utils import timezone
from django.core.files.base import ContentFile
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from products.models import Product, Category, Subcategory, ProductSize, ProductVariant, ProductImage

try:
    from Homepage.signals import purge_homepage_cache
except Exception:
    def purge_homepage_cache():
        pass


SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


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
    "unittype": "unit_type",

    # Type & Status
    "type": "product_type",
    "producttype": "product_type",
    "status": "status",
    "productstatus": "is_active",
    "isactive": "is_active",
    "active": "is_active",
    "isfeatured": "is_featured",
    "featured": "is_featured",
    "displayorder": "display_order",
    "order": "display_order",

    # Description & Images
    "description": "description",
    "shortdescription": "short_description",
    "desc": "description",
    "image": "image_url",
    "imageurl": "image_url",
    "mainimage": "image_url",
    "photo": "image_url",
    "galleryimages": "gallery_images",
    "gallery": "gallery_images",
    "additionalimages": "gallery_images",
    "moreimages": "gallery_images",

    # Variant Fields
    "variantname": "variant_name",
    "size": "variant_name",
    "option": "variant_name",
    "variant": "variant_name",
    "weightoption": "variant_name",
    "packsize": "variant_name",
    "variantprice": "variant_price",
    "variantsellingprice": "variant_price",
    "optionsellingprice": "variant_price",
    "variantmrp": "variant_mrp",
    "variantoriginalprice": "variant_mrp",
    "optionmrp": "variant_mrp",
    "variantstock": "variant_stock",
    "optionstock": "variant_stock",
    "variantsku": "variant_sku",
    "optionsku": "variant_sku",
    "variantimage": "variant_image",
    "optionimage": "variant_image",
}


def _normalize_header(header_val):
    if not header_val:
        return ""
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", str(header_val)).lower()
    if cleaned in HEADER_MAP:
        return HEADER_MAP[cleaned]
    if "gallery" in cleaned:
        return "gallery_images"
    if "variantprice" in cleaned:
        return "variant_price"
    if "variantmrp" in cleaned:
        return "variant_mrp"
    if "variantstock" in cleaned:
        return "variant_stock"
    if "variantsku" in cleaned:
        return "variant_sku"
    if "variantimage" in cleaned or "optionimage" in cleaned:
        return "variant_image"
    if "variant" in cleaned or "option" in cleaned or "packsize" in cleaned:
        return "variant_name"
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
    if "unittype" in cleaned:
        return "unit_type"
    if "unitval" in cleaned or "weight" in cleaned:
        return "unit_value"
    if "unit" in cleaned or "uom" in cleaned:
        return "unit"
    if "status" in cleaned or "active" in cleaned:
        return "is_active"
    if "feature" in cleaned:
        return "is_featured"
    if "type" in cleaned:
        return "product_type"
    if "desc" in cleaned:
        return "description"
    if "image" in cleaned or "photo" in cleaned or "picture" in cleaned:
        return "image_url"
    return cleaned


def parse_and_validate_excel(file_obj, image_files_map=None):
    """
    Parses an uploaded Excel (.xlsx) file, maps headers intelligently,
    validates data rules, detects existing vs new products, groups variants,
    verifies image files if image_files_map is provided (from ZIP),
    and returns a structured validation preview dictionary.
    """
    image_files_map = image_files_map or {}
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

    # Pre-load existing categories and subcategories
    existing_categories = {c.name.strip().lower(): c for c in Category.objects.all()}
    existing_subcategories = {s.name.strip().lower(): s for s in Subcategory.objects.select_related("category").all()}

    # Pre-load existing products by SKU and Name
    existing_products_by_sku = {}
    for p in Product.objects.all():
        if p.product_number:
            existing_products_by_sku[p.product_number.strip().lower()] = p
    existing_products_by_name = {p.name.strip().lower(): p for p in Product.objects.all()}

    valid_rows = []
    invalid_rows = []
    missing_categories = set()
    missing_subcategories = set()

    data_rows = rows[header_row_idx + 1:]

    # Group rows by product identifier (SKU or Name) to support multi-row variants
    grouped_products = {}  # key -> product_dict
    group_order = []

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

        name = row_data.get("name", "").strip()
        sku = row_data.get("sku", "").strip()
        variant_name = row_data.get("variant_name", "").strip()
        raw_price = row_data.get("price", "").strip()
        raw_vprice = row_data.get("variant_price", "").strip()

        # Grouping key: either explicit SKU, or product name
        group_key = (sku.lower() if sku else name.lower())
        if not group_key:
            errors.append("Product Name or SKU is required.")
            invalid_rows.append({
                "row_num": excel_row_num,
                "name": name or "(Empty)",
                "sku": sku,
                "errors": errors,
            })
            continue

        # Selling price validation
        price_to_eval = raw_vprice if (variant_name and raw_vprice) else raw_price
        clean_price = re.sub(r"[^\d.]", "", price_to_eval)
        price_val = None
        if not clean_price:
            errors.append("Selling Price is required.")
        else:
            try:
                price_val = Decimal(clean_price)
                if price_val <= 0:
                    errors.append("Selling Price must be greater than 0.")
            except (InvalidOperation, ValueError):
                errors.append(f"Invalid Selling Price format: '{price_to_eval}'.")

        # MRP validation
        raw_mrp = row_data.get("variant_mrp", "").strip() or row_data.get("mrp", "").strip()
        clean_mrp = re.sub(r"[^\d.]", "", raw_mrp)
        mrp_val = price_val
        if clean_mrp:
            try:
                mrp_val = Decimal(clean_mrp)
                if price_val and mrp_val < price_val:
                    mrp_val = price_val
            except (InvalidOperation, ValueError):
                mrp_val = price_val

        # Stock validation
        raw_stock = row_data.get("variant_stock", "").strip() or row_data.get("stock", "").strip()
        clean_stock = re.sub(r"[^\d]", "", raw_stock)
        stock_val = 0
        if clean_stock:
            try:
                stock_val = int(clean_stock)
            except ValueError:
                stock_val = 0

        # Category check
        raw_cat = row_data.get("category", "").strip()
        if raw_cat and raw_cat.lower() not in existing_categories:
            missing_categories.add(raw_cat)

        raw_subcat = row_data.get("subcategory", "").strip()
        if raw_subcat and raw_subcat.lower() not in existing_subcategories:
            missing_subcategories.add(raw_subcat)

        # Image validation / Thumbnail generation
        img_raw = row_data.get("image_url", "").strip()
        matched_image_filename = ""
        thumbnail_b64 = None

        if img_raw:
            clean_base = os.path.basename(img_raw).strip().lower()
            if clean_base in image_files_map:
                matched_image_filename = clean_base
                img_bytes = image_files_map[clean_base]
                mime, _ = mimetypes.guess_type(clean_base)
                mime = mime or "image/jpeg"
                preview_bytes = img_bytes[:256 * 1024]
                thumbnail_b64 = f"data:{mime};base64,{base64.b64encode(preview_bytes).decode('ascii')}"
            elif img_raw.startswith("http://") or img_raw.startswith("https://"):
                matched_image_filename = img_raw
                thumbnail_b64 = img_raw

        # Variant Image check
        v_img_raw = row_data.get("variant_image", "").strip()
        v_matched_img = ""
        if v_img_raw:
            v_clean_base = os.path.basename(v_img_raw).strip().lower()
            if v_clean_base in image_files_map:
                v_matched_img = v_clean_base
            elif v_img_raw.startswith("http://") or v_img_raw.startswith("https://"):
                v_matched_img = v_img_raw

        # Gallery images list
        gallery_raw = row_data.get("gallery_images", "").strip()
        gallery_list = [g.strip() for g in gallery_raw.split(",") if g.strip()] if gallery_raw else []

        if errors:
            invalid_rows.append({
                "row_num": excel_row_num,
                "name": name,
                "sku": sku,
                "category": raw_cat,
                "subcategory": raw_subcat,
                "price": str(price_val or raw_price),
                "stock": stock_val,
                "errors": errors,
            })
            continue

        # Check existing product match in DB
        existing_obj = None
        action_type = "create"
        if sku and sku.lower() in existing_products_by_sku:
            existing_obj = existing_products_by_sku[sku.lower()]
            action_type = "update"
        elif name and name.lower() in existing_products_by_name:
            existing_obj = existing_products_by_name[name.lower()]
            action_type = "update"

        # Check Active Status
        status_val = row_data.get("is_active", "").strip().lower()
        is_active_val = status_val not in ("inactive", "false", "0", "no", "n")

        # Check Featured
        feat_val = row_data.get("is_featured", "").strip().lower()
        is_featured_val = feat_val in ("yes", "true", "1", "y")

        # Determine Product Type
        raw_type = row_data.get("product_type", "").strip().lower()
        is_var = bool(variant_name or raw_type == "variable")

        # Build Variant Dict if variant info is present
        variant_dict = None
        if variant_name or is_var:
            variant_dict = {
                "name": variant_name or "Standard",
                "price": float(price_val) if price_val else 0.0,
                "mrp": float(mrp_val) if mrp_val else (float(price_val) if price_val else 0.0),
                "stock": stock_val,
                "sku": row_data.get("variant_sku", "").strip() or (f"{sku}-{variant_name[:4].upper()}" if sku and variant_name else ""),
                "image": v_matched_img or v_img_raw,
            }

        if group_key not in grouped_products:
            grouped_products[group_key] = {
                "row_num": excel_row_num,
                "name": name,
                "sku": sku,
                "brand": row_data.get("brand", "").strip() or "TipsyCart",
                "category": raw_cat,
                "subcategory": raw_subcat,
                "product_type": "variable" if is_var else "simple",
                "unit_type": row_data.get("unit_type", "").strip().lower() or ("weight" if any(u in (row_data.get("unit", "")).lower() for u in ["kg", "g", "gm"]) else "count"),
                "unit": row_data.get("unit", "").strip() or "Piece",
                "unit_value": row_data.get("unit_value", "").strip() or None,
                "price": float(price_val) if price_val else 0.0,
                "mrp": float(mrp_val) if mrp_val else 0.0,
                "stock": stock_val,
                "is_active": is_active_val,
                "is_featured": is_featured_val,
                "description": row_data.get("description", "").strip(),
                "image_url": matched_image_filename or img_raw,
                "gallery_images": gallery_list,
                "thumbnail_b64": thumbnail_b64,
                "variants": [variant_dict] if variant_dict else [],
                "action": action_type,
                "existing_id": existing_obj.id if existing_obj else None,
                "existing_name": existing_obj.name if existing_obj else "",
            }
            group_order.append(group_key)
        else:
            # Append additional variant to existing parent product group
            parent = grouped_products[group_key]
            parent["product_type"] = "variable"
            if variant_dict:
                parent["variants"].append(variant_dict)
                # Recalculate parent stock as sum of variants
                parent["stock"] += stock_val
                # Base price is minimum variant price
                if price_val and float(price_val) < parent["price"]:
                    parent["price"] = float(price_val)

    # Compile valid rows
    for key in group_order:
        item = grouped_products[key]
        # Clean up unit value decimal if possible
        if item.get("unit_value"):
            try:
                item["unit_value"] = float(re.sub(r"[^\d.]", "", str(item["unit_value"])))
            except Exception:
                item["unit_value"] = None
        valid_rows.append(item)

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
        "preview_valid": valid_rows[:35],
        "preview_invalid": invalid_rows[:35],
    }


def commit_excel_import(valid_rows, auto_create_missing_categories=True, image_files_map=None):
    """
    Executes the validated rows into the database atomically.
    Supports:
    - Main image upload to Cloudinary (from in-memory image_files_map or URL)
    - Multiple gallery images creation (ProductImage)
    - Variable products with automatic ProductSize and ProductVariant rows
    - Independent pricing, MRP, stock, and variant images
    - Auto-purges homepage cache after import so changes reflect immediately!
    """
    image_files_map = image_files_map or {}
    stats = {
        "created": 0,
        "updated": 0,
        "variants_created": 0,
        "gallery_images_added": 0,
        "skipped": 0,
        "errors": [],
    }

    category_cache = {c.name.strip().lower(): c for c in Category.objects.all()}
    subcategory_cache = {s.name.strip().lower(): s for s in Subcategory.objects.all()}

    for item in valid_rows:
        try:
            with transaction.atomic():
                # 1. Resolve Category
                cat_obj = None
                raw_cat = item.get("category", "").strip()
                if raw_cat:
                    cat_lower = raw_cat.lower()
                    if cat_lower in category_cache:
                        cat_obj = category_cache[cat_lower]
                    elif auto_create_missing_categories:
                        cat_slug = slugify(raw_cat) or "category"
                        base_slug = cat_slug
                        cnt = 1
                        while Category.objects.filter(slug=cat_slug).exists():
                            cat_slug = f"{base_slug}-{cnt}"
                            cnt += 1
                        cat_obj = Category.objects.create(name=raw_cat, slug=cat_slug, is_active=True)
                        category_cache[cat_lower] = cat_obj

                # 2. Resolve Subcategory
                subcat_obj = None
                raw_subcat = item.get("subcategory", "").strip()
                if raw_subcat:
                    subcat_lower = raw_subcat.lower()
                    if subcat_lower in subcategory_cache:
                        subcat_obj = subcategory_cache[subcat_lower]
                    elif auto_create_missing_categories and cat_obj:
                        subcat_slug = slugify(raw_subcat) or "subcategory"
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

                # 3. Find or Initialize Product
                existing_id = item.get("existing_id")
                prod = None
                if existing_id:
                    prod = Product.objects.filter(id=existing_id).first()
                if not prod and item.get("sku"):
                    prod = Product.objects.filter(product_number__iexact=item["sku"]).first()
                if not prod and item.get("name"):
                    prod = Product.objects.filter(name__iexact=item["name"]).first()

                is_new = prod is None
                if is_new:
                    sku_val = item.get("sku", "").strip()
                    if not sku_val:
                        sku_val = f"TC-PRD-{int(timezone.now().timestamp() * 1000) % 1000000}"
                    prod = Product(product_number=sku_val)

                # Set product attributes
                prod.name = item["name"]
                prod.brand = item.get("brand") or "TipsyCart"
                prod.product_type = item.get("product_type") or "simple"
                prod.unit_type = item.get("unit_type") or "weight"
                prod.unit = item.get("unit") or "Piece"
                if item.get("unit_value") is not None:
                    prod.unit_value = Decimal(str(item["unit_value"]))
                prod.price = Decimal(str(item["price"]))
                prod.original_price = Decimal(str(item.get("mrp") or item["price"]))
                prod.stock = int(item["stock"])
                prod.is_active = bool(item.get("is_active", True))
                if item.get("is_featured") is not None:
                    prod.is_featured = bool(item.get("is_featured"))
                if item.get("description"):
                    prod.description = item["description"]

                if cat_obj:
                    prod.category_ref = cat_obj
                    prod.category = cat_obj.name
                if subcat_obj:
                    prod.subcategory_ref = subcat_obj
                    prod.subcategory = subcat_obj.name

                # 4. Attach Main Image if provided
                img_ref = item.get("image_url", "").strip()
                if img_ref:
                    clean_img_base = os.path.basename(img_ref).strip().lower()
                    if clean_img_base in image_files_map:
                        try:
                            img_bytes = image_files_map[clean_img_base]
                            prod.image.save(clean_img_base, ContentFile(img_bytes), save=False)
                        except Exception as img_err:
                            logger.warning(f"Could not upload main image {clean_img_base} to Cloudinary: {img_err}")
                    elif img_ref.startswith("http://") or img_ref.startswith("https://"):
                        prod.image_url = img_ref

                prod.save()

                if is_new:
                    stats["created"] += 1
                else:
                    stats["updated"] += 1

                # 5. Attach Gallery Images
                gallery_refs = item.get("gallery_images", [])
                for g_ref in gallery_refs:
                    g_clean = os.path.basename(g_ref).strip().lower()
                    if g_clean in image_files_map:
                        try:
                            g_bytes = image_files_map[g_clean]
                            ProductImage.objects.create(
                                product=prod,
                                image=ContentFile(g_bytes, name=g_clean)
                            )
                            stats["gallery_images_added"] += 1
                        except Exception as g_err:
                            logger.warning(f"Could not upload gallery image {g_clean} to Cloudinary: {g_err}")
                    elif g_ref.startswith("http://") or g_ref.startswith("https://"):
                        ProductImage.objects.create(
                            product=prod,
                            image_url=g_ref
                        )
                        stats["gallery_images_added"] += 1

                # 6. Create / Update Variants if Variable Product
                variants = item.get("variants", [])
                if variants and prod.product_type == "variable":
                    for idx, v_data in enumerate(variants, start=1):
                        v_name = v_data.get("name", "").strip() or f"Option {idx}"
                        v_price = Decimal(str(v_data.get("price") or prod.price))
                        v_mrp = Decimal(str(v_data.get("mrp") or prod.original_price or v_price))
                        v_stock = int(v_data.get("stock") or 0)
                        v_sku = v_data.get("sku", "").strip() or f"{prod.product_number}-{slugify(v_name)[:5].upper() or idx}"

                        # Create or get Size Option
                        size_obj, _ = ProductSize.objects.get_or_create(
                            product=prod,
                            name=v_name,
                            defaults={"display_order": idx, "is_active": True}
                        )

                        # Create or update Variant
                        variant_obj, _ = ProductVariant.objects.get_or_create(
                            product=prod,
                            size=size_obj,
                            defaults={
                                "variant_name": v_name,
                                "price": v_price,
                                "original_price": v_mrp,
                                "stock": v_stock,
                                "sku": v_sku,
                                "is_active": True,
                            }
                        )
                        variant_obj.price = v_price
                        variant_obj.original_price = v_mrp
                        variant_obj.stock = v_stock
                        variant_obj.sku = v_sku
                        variant_obj.is_active = True

                        # Variant custom image
                        v_img_ref = v_data.get("image", "").strip()
                        if v_img_ref:
                            v_clean = os.path.basename(v_img_ref).strip().lower()
                            if v_clean in image_files_map:
                                try:
                                    v_bytes = image_files_map[v_clean]
                                    variant_obj.image.save(v_clean, ContentFile(v_bytes), save=False)
                                except Exception as v_img_err:
                                    logger.warning(f"Could not upload variant image {v_clean} to Cloudinary: {v_img_err}")
                            elif v_img_ref.startswith("http://") or v_img_ref.startswith("https://"):
                                variant_obj.image_url = v_img_ref

                        variant_obj.save()
                        stats["variants_created"] += 1

        except Exception as e:
            stats["errors"].append(f"Row {item.get('row_num', '?')} ({item.get('name', 'Product')}): {str(e)}")

    # Auto-purge homepage cache so imported products appear immediately
    purge_homepage_cache()

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
    header_fill = PatternFill(start_color="991B1B", end_color="991B1B", fill_type="solid")
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
    Generates a comprehensive 2-sheet sample .xlsx template:
    - Sheet 1: 'Products & Variants' with realistic Simple and Variable product examples.
    - Sheet 2: 'Instructions & Guide' with clear step-by-step Hindi & English rules for the team.
    """
    wb = openpyxl.Workbook()

    # ----------------------------------------------------
    # SHEET 1: PRODUCTS & VARIANTS
    # ----------------------------------------------------
    ws1 = wb.active
    ws1.title = "Products & Variants"
    ws1.views.sheetView[0].showGridLines = True

    header_font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="A51655", end_color="A51655", fill_type="solid")
    simple_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
    variable_fill = PatternFill(start_color="FDF2F8", end_color="FDF2F8", fill_type="solid")
    data_font = Font(name="Calibri", size=9)
    border = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0"),
    )

    headers = [
        "Product Name *",
        "SKU / Code *",
        "Brand",
        "Category *",
        "Subcategory",
        "Product Type (simple/variable)",
        "Unit Type (weight/volume/count/size)",
        "Unit (e.g. Kg, g, ml, L, Piece)",
        "Unit Value (e.g. 1, 250, 500)",
        "Selling Price (₹) *",
        "MRP (₹)",
        "Stock Quantity *",
        "Product Status (Active/Inactive)",
        "Is Featured (Yes/No)",
        "Description",
        "Main Image (File Name or URL)",
        "Gallery Images (Comma-separated)",
        "Variant Name / Size (for Variable Products)",
        "Variant Selling Price (₹)",
        "Variant MRP (₹)",
        "Variant Stock",
        "Variant SKU",
        "Variant Image (File Name or URL)",
    ]

    for col_idx, h in enumerate(headers, start=1):
        cell = ws1.cell(row=1, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border
    ws1.row_dimensions[1].height = 32

    # Realistic sample rows
    sample_rows = [
        # 1. Simple Product - Groceries
        [
            "Fresh Apples (Kinnaur Crisp)", "TC-APL-01", "Tipsy Fresh Cuts", "Groceries", "Fresh Fruits",
            "simple", "weight", "Kg", 1, 149.00, 175.00, 50, "Active", "Yes",
            "Fresh sweet and juicy crisp Kinnaur apples delivered doorstep.", "apples_main.jpg", "apples_cut.jpg, apples_box.jpg",
            "", "", "", "", "", ""
        ],
        # 2. Simple Product - Daily Essentials
        [
            "Vim Dishwash Liquid Gel", "TC-VIM-500", "Vim", "Daily Essentials", "Cleaning Essentials",
            "simple", "volume", "ml", 500, 115.00, 145.00, 40, "Active", "No",
            "Power of 100 lemons for instant grease removal.", "vim_500ml.jpg", "",
            "", "", "", "", "", ""
        ],
        # 3. Variable Product - Fish / Non-Veg (Row 1: 250g)
        [
            "Fresh River Basa Fish Fillets", "TC-BASA-01", "Tipsy Fresh Cuts", "Tipsy Fresh Cuts", "Fish",
            "variable", "weight", "Kg", 1, 120.00, 150.00, 115, "Active", "Yes",
            "Fresh boneless river Basa fish fillets, cleaned and hygienically packed.", "basa_cover.jpg", "basa_dish.jpg",
            "250g", 120.00, 150.00, 50, "TC-BASA-250G", "basa_250g.jpg"
        ],
        # 4. Variable Product - Fish (Row 2: 500g)
        [
            "Fresh River Basa Fish Fillets", "TC-BASA-01", "Tipsy Fresh Cuts", "Tipsy Fresh Cuts", "Fish",
            "variable", "weight", "Kg", 1, 120.00, 150.00, 115, "Active", "Yes",
            "Fresh boneless river Basa fish fillets, cleaned and hygienically packed.", "basa_cover.jpg", "basa_dish.jpg",
            "500g", 220.00, 280.00, 40, "TC-BASA-500G", "basa_500g.jpg"
        ],
        # 5. Variable Product - Fish (Row 3: 1 kg)
        [
            "Fresh River Basa Fish Fillets", "TC-BASA-01", "Tipsy Fresh Cuts", "Tipsy Fresh Cuts", "Fish",
            "variable", "weight", "Kg", 1, 120.00, 150.00, 115, "Active", "Yes",
            "Fresh boneless river Basa fish fillets, cleaned and hygienically packed.", "basa_cover.jpg", "basa_dish.jpg",
            "1 kg", 400.00, 500.00, 25, "TC-BASA-1KG", "basa_1kg.jpg"
        ],
        # 6. Variable Product - Fashion / Jewellery (Row 1: Pink)
        [
            "Dainty Butterfly Pendant Necklace", "TC-JWL-09", "TipsyCart", "Fashion & Jewellery", "Necklace",
            "variable", "count", "Piece", 1, 145.00, 155.00, 18, "Active", "Yes",
            "Elegant silver link chain with lustrous pearls and crystal butterfly pendant.", "necklace_main.jpg", "necklace_box.jpg",
            "Pink Butterfly", 145.00, 155.00, 10, "TC-JWL-PNK", "necklace_pink.jpg"
        ],
        # 7. Variable Product - Fashion / Jewellery (Row 2: Silver)
        [
            "Dainty Butterfly Pendant Necklace", "TC-JWL-09", "TipsyCart", "Fashion & Jewellery", "Necklace",
            "variable", "count", "Piece", 1, 145.00, 155.00, 18, "Active", "Yes",
            "Elegant silver link chain with lustrous pearls and crystal butterfly pendant.", "necklace_main.jpg", "necklace_box.jpg",
            "Silver Butterfly", 145.00, 155.00, 8, "TC-JWL-SLV", "necklace_silver.jpg"
        ],
    ]

    for row_idx, r_data in enumerate(sample_rows, start=2):
        is_var_row = bool(r_data[17])  # has variant
        fill_to_use = variable_fill if is_var_row else simple_fill
        for col_idx, val in enumerate(r_data, start=1):
            cell = ws1.cell(row=row_idx, column=col_idx, value=val)
            cell.font = data_font
            cell.fill = fill_to_use
            cell.border = border
            if col_idx in [10, 11, 19, 20] and val != "":
                cell.number_format = "₹#,##0.00"
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif col_idx in [9, 12, 21] and val != "":
                cell.alignment = Alignment(horizontal="right", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    for col in ws1.columns:
        col_letter = get_column_letter(col[0].column)
        ws1.column_dimensions[col_letter].width = 22
    ws1.column_dimensions["A"].width = 30
    ws1.column_dimensions["O"].width = 34
    ws1.column_dimensions["P"].width = 24
    ws1.column_dimensions["Q"].width = 28
    ws1.column_dimensions["W"].width = 24

    # ----------------------------------------------------
    # SHEET 2: INSTRUCTIONS & GUIDE (टीम के लिए गाइड)
    # ----------------------------------------------------
    ws2 = wb.create_sheet(title="Guide & Instructions (गाइड)")
    ws2.views.sheetView[0].showGridLines = True

    guide_title_font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    guide_header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    section_font = Font(name="Calibri", size=11, bold=True, color="1E3A8A")
    body_font = Font(name="Calibri", size=10)
    bold_body = Font(name="Calibri", size=10, bold=True)

    ws2.merge_cells("A1:D1")
    title_cell = ws2.cell(row=1, column=1, value="TipsyCart Bulk Product Upload Guide for Store Team (एक्सेल अपलोड गाइड)")
    title_cell.font = guide_title_font
    title_cell.fill = guide_header_fill
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws2.row_dimensions[1].height = 36

    instructions = [
        ("1. SIMPLE PRODUCT कैसे भरें?", "अगर किसी प्रोडक्ट का सिर्फ 1 ही साइज़, 1 ही प्राइस है (जैसे Maggi 70g, Dettol साबुन):", [
            ("Row Count:", "सिर्फ 1 रो भरें।"),
            ("Product Type:", "simple लिखें।"),
            ("Columns 1 to 17:", "नाम, SKU, केटेगरी, सब-केटेगरी, सेलिंग प्राइस, MRP, स्टॉक और मेन इमेज भरें।"),
            ("Columns 18 to 23:", "वेरियंट के कॉलम्स को खाली (Blank) छोड़ दें।"),
        ]),
        ("2. VARIABLE PRODUCT (मल्टीपल वजन/साइज़) कैसे भरें?", "अगर प्रोडक्ट में 250g, 500g, 1 kg जैसे अलग-अलग वजन हैं (जैसे Fish, Atta):", [
            ("Row Count:", "जितने वजन/ऑप्शन्स हैं, उतनी रो भरें (जैसे 250g के लिए 1 रो, 500g के लिए 2nd रो, 1 kg के लिए 3rd रो)।"),
            ("Same SKU / Name:", "तीनों रो में Product Name और SKU / Code बिल्कुल सेम रखें ताकि सिस्टम समझ सके कि ये एक ही प्रोडक्ट के वजन हैं।"),
            ("Product Type:", "variable लिखें।"),
            ("Variant Columns (18 to 23):", "हर रो में Variant Name (जैसे 250g), Variant Selling Price, Variant MRP, Variant Stock और Variant Image भरें।"),
            ("Different Prices & Images:", "250g का प्राइस 120 और फोटो basa_250g.jpg, 500g का प्राइस 220 और फोटो basa_500g.jpg डाल सकते हैं।"),
        ]),
        ("3. IMAGES (फोटो) और ZIP फ़ोल्डर कैसे बनाएं?", "अगर आपके पास सभी प्रोडक्ट्स और वेरियंट्स की फ़ोटो हैं:", [
            ("Step 1:", "अपने कंप्यूटर में एक नया फ़ोल्डर बनाएं।"),
            ("Step 2:", "इस एक्सेल फ़ाइल (.xlsx) को उस फ़ोल्डर में रखें।"),
            ("Step 3:", "एक्सेल में जिन-जिन फोटो का नाम लिखा है (जैसे basa_cover.jpg, vim_500ml.jpg), उन सभी फ़ोटो को उसी फ़ोल्डर में डाल दें।"),
            ("Step 4:", "उस फ़ोल्डर पर राइट क्लिक करके 'Compress to ZIP' (या Send to -> Compressed folder) बनाएं।"),
            ("Step 5:", "एडमिन पैनल में 'Import from Excel (.xlsx)' या 'Import Products (ZIP + Images)' में जाकर यह ZIP अपलोड कर दें!"),
            ("Cloudinary Auto-Upload:", "सिस्टम सभी फ़ोटो को अपने आप Cloudinary पर सुरक्षित अपलोड कर देगा और डेटाबेस से लिंक कर देगा।"),
        ]),
        ("4. केटेगरी और सब-केटेगरी ऑटो-लिंक", "अगर आपकी एक्सेल शीट में लिखी केटेगरी डेटाबेस में मौजूद नहीं है:", [
            ("Auto-Creation:", "सिस्टम अपने आप नई केटेगरी और सब-केटेगरी बना देगा और प्रोडक्ट को उसमें शिफ्ट कर देगा।"),
            ("Exact Match:", "अगर केटेगरी पहले से मौजूद है (जैसे Groceries, Tipsy Fresh Cuts), तो प्रोडक्ट उसी में चला जाएगा।"),
        ]),
    ]

    curr_row = 3
    for sec_title, sec_desc, rules in instructions:
        ws2.cell(row=curr_row, column=1, value=sec_title).font = section_font
        curr_row += 1
        ws2.cell(row=curr_row, column=1, value=sec_desc).font = body_font
        curr_row += 1
        for rule_name, rule_val in rules:
            c1 = ws2.cell(row=curr_row, column=1, value=f"• {rule_name}")
            c1.font = bold_body
            c2 = ws2.cell(row=curr_row, column=2, value=rule_val)
            c2.font = body_font
            curr_row += 1
        curr_row += 1

    ws2.column_dimensions["A"].width = 30
    ws2.column_dimensions["B"].width = 85

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
