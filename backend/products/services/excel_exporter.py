import io
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, F, Q, Value, DecimalField
from django.db.models.functions import Coalesce

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from orders.models import OrderItem
from products.models import optimize_image_url


# Valid order statuses that count towards completed/valid sales
VALID_ORDER_STATUSES = [
    "Pending", "Confirmed", "Processing", "Packed",
    "Assigned", "Accepted", "Picked Up", "Out for Delivery", "Delivered"
]


def generate_products_excel(queryset, filter_description="All Filtered Products"):
    """
    Generates a professionally styled Excel spreadsheet (.xlsx) of products and their variants,
    including real-time stock levels and order-driven sales/revenue analytics.
    Returns an in-memory BytesIO buffer ready to stream as an HttpResponse.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Products & Inventory"
    ws.views.sheetView[0].showGridLines = True

    # ----------------------------------------------------
    # COLOR PALETTE & STYLES (TipsyCart Brand Palette)
    # ----------------------------------------------------
    PRIMARY_ROSE = "9F1239"   # Dark Rose / Brand Header
    ACCENT_PINK = "FCE7F3"    # Light Pink / Metadata
    ZEBRA_TINT = "FDF2F8"     # Alternate Row Tint
    WHITE = "FFFFFF"
    DARK_TEXT = "1E293B"
    MUTED_TEXT = "64748B"
    BORDER_COLOR = "E2E8F0"

    title_font = Font(name="Calibri", size=14, bold=True, color=WHITE)
    meta_font = Font(name="Calibri", size=10, italic=True, color=DARK_TEXT)
    header_font = Font(name="Calibri", size=11, bold=True, color=WHITE)
    data_font = Font(name="Calibri", size=10, color=DARK_TEXT)
    bold_data_font = Font(name="Calibri", size=10, bold=True, color=DARK_TEXT)
    muted_data_font = Font(name="Calibri", size=9, color=MUTED_TEXT)

    title_fill = PatternFill(start_color=PRIMARY_ROSE, end_color=PRIMARY_ROSE, fill_type="solid")
    meta_fill = PatternFill(start_color=ACCENT_PINK, end_color=ACCENT_PINK, fill_type="solid")
    header_fill = PatternFill(start_color="A51655", end_color="A51655", fill_type="solid")
    zebra_fill = PatternFill(start_color=ZEBRA_TINT, end_color=ZEBRA_TINT, fill_type="solid")
    white_fill = PatternFill(start_color=WHITE, end_color=WHITE, fill_type="solid")

    thin_border = Border(
        left=Side(style="thin", color=BORDER_COLOR),
        right=Side(style="thin", color=BORDER_COLOR),
        top=Side(style="thin", color=BORDER_COLOR),
        bottom=Side(style="thin", color=BORDER_COLOR),
    )

    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")

    # ----------------------------------------------------
    # ROW 1 & 2: REPORT TITLE & METADATA
    # ----------------------------------------------------
    ws.merge_cells("A1:U1")
    title_cell = ws["A1"]
    title_cell.value = "TIPSYCART — ADVANCED PRODUCT MANAGEMENT, INVENTORY & SALES REPORT"
    title_cell.font = title_font
    title_cell.fill = title_fill
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 36

    now_str = timezone.localtime(timezone.now()).strftime("%Y-%m-%d %I:%M:%S %p")
    total_count = queryset.count()
    ws.merge_cells("A2:U2")
    meta_cell = ws["A2"]
    meta_cell.value = f"Generated On: {now_str} (IST)  |  Scope / Filter: {filter_description}  |  Total Products: {total_count}  |  Database Source: Live Django Database"
    meta_cell.font = meta_font
    meta_cell.fill = meta_fill
    meta_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[2].height = 22

    # Row 3 is a blank spacing row
    ws.row_dimensions[3].height = 8

    # ----------------------------------------------------
    # ROW 4: TABLE HEADERS
    # ----------------------------------------------------
    headers = [
        "Product ID",
        "Product Number",
        "Product Name",
        "Brand",
        "Category",
        "Subcategory",
        "Product Type",
        "Variant Name",
        "Size / Unit",
        "Colour",
        "SKU",
        "MRP (₹)",
        "Selling Price (₹)",
        "Discount (%)",
        "Available Stock",
        "Units Sold",
        "Total Revenue (₹)",
        "Product Status",
        "Stock Status",
        "Created Date",
        "Last Updated",
    ]

    for col_num, header_title in enumerate(headers, start=1):
        cell = ws.cell(row=4, column=col_num, value=header_title)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border

    ws.row_dimensions[4].height = 28

    # ----------------------------------------------------
    # PRE-FETCH SALES METRICS BY PRODUCT & VARIANT
    # ----------------------------------------------------
    # Calculate order sales metrics directly from OrderItem
    p_ids = list(queryset.values_list("id", flat=True))
    
    order_items_qs = OrderItem.objects.filter(
        product_id__in=p_ids,
        order__status__in=VALID_ORDER_STATUSES
    )

    # Product-level sales
    prod_sales_map = {}
    for row in order_items_qs.values("product_id").annotate(
        qty=Sum("quantity"),
        rev=Sum(F("price") * F("quantity"))
    ):
        prod_sales_map[row["product_id"]] = {
            "qty": row["qty"] or 0,
            "rev": Decimal(str(row["rev"] or "0.00"))
        }

    # Variant-level sales
    var_sales_map = {}
    for row in order_items_qs.exclude(variant_id=None).values("variant_id").annotate(
        qty=Sum("quantity"),
        rev=Sum(F("price") * F("quantity"))
    ):
        var_sales_map[row["variant_id"]] = {
            "qty": row["qty"] or 0,
            "rev": Decimal(str(row["rev"] or "0.00"))
        }

    # ----------------------------------------------------
    # ROW GENERATION (PRODUCT & VARIANT LEVEL)
    # ----------------------------------------------------
    current_row = 5

    products_list = queryset.select_related("category_ref", "subcategory_ref").prefetch_related(
        "variants", "variants__colour", "variants__size"
    ).order_by("-created_at")

    for prod_idx, p in enumerate(products_list):
        cat_name = p.category_ref.name if p.category_ref else (p.category or "")
        subcat_name = p.subcategory_ref.name if p.subcategory_ref else (p.subcategory or "")
        p_type = "Variable" if p.is_variable else "Simple"
        created_str = timezone.localtime(p.created_at).strftime("%Y-%m-%d") if p.created_at else ""
        prod_sales = prod_sales_map.get(p.id, {"qty": 0, "rev": Decimal("0.00")})

        active_variants = list(p.variants.all()) if p.is_variable else []

        # If variable product has configured variants, export each variant as its own row
        if p.is_variable and active_variants:
            for v_idx, v in enumerate(active_variants):
                row_fill = zebra_fill if prod_idx % 2 == 1 else white_fill
                v_sales = var_sales_map.get(v.id, {"qty": 0, "rev": Decimal("0.00")})
                
                v_name = v.variant_name or v.get_title()
                v_size = v.size.name if v.size else (f"{v.unit_value} {v.unit}".strip() if v.unit_value else (v.unit or ""))
                v_colour = v.colour.name if v.colour else ""
                v_sku = v.sku or p.product_number or ""
                v_mrp = float(v.original_price or p.original_price or v.price)
                v_price = float(v.price)
                v_disc = float(v.discount_percentage or 0)
                v_stock = v.stock
                v_sold = v_sales["qty"]
                v_rev = float(v_sales["rev"])
                v_status = "Active" if (p.is_active and v.is_active) else "Inactive"
                
                if v_stock == 0:
                    stock_status = "Out of Stock"
                elif v_stock <= 10:
                    stock_status = "Low Stock"
                else:
                    stock_status = "In Stock"

                row_values = [
                    p.id,
                    p.product_number or f"TC-PRD-{p.id}",
                    p.name,
                    p.brand or "TipsyCart",
                    cat_name,
                    subcat_name,
                    "Variable",
                    v_name,
                    v_size,
                    v_colour,
                    v_sku,
                    v_mrp,
                    v_price,
                    v_disc / 100.0,
                    v_stock,
                    v_sold,
                    v_rev,
                    v_status,
                    stock_status,
                    created_str,
                    now_str,
                ]

                for col_idx, val in enumerate(row_values, start=1):
                    cell = ws.cell(row=current_row, column=col_idx, value=val)
                    cell.font = data_font
                    cell.fill = row_fill
                    cell.border = thin_border

                    # Alignments & Formats
                    if col_idx in [1, 2, 7, 10, 11, 18, 19, 20]:
                        cell.alignment = center_align
                    elif col_idx in [12, 13, 17]:
                        cell.alignment = right_align
                        cell.number_format = "₹#,##0.00"
                    elif col_idx == 14:
                        cell.alignment = right_align
                        cell.number_format = "0.0%"
                    elif col_idx in [15, 16]:
                        cell.alignment = right_align
                        cell.number_format = "#,##0"
                    else:
                        cell.alignment = left_align

                current_row += 1

        else:
            # Simple Product or Variable product without variants yet
            row_fill = zebra_fill if prod_idx % 2 == 1 else white_fill
            mrp = float(p.original_price or p.price)
            price = float(p.price)
            disc = float(p.discount_percentage or 0)
            stock = p.stock
            sold = prod_sales["qty"]
            rev = float(prod_sales["rev"])
            status_str = "Active" if p.is_active else "Inactive"

            if stock == 0:
                stock_status = "Out of Stock"
            elif stock <= 10:
                stock_status = "Low Stock"
            else:
                stock_status = "In Stock"

            unit_str = f"{p.unit_value:g} {p.unit}".strip() if p.unit_value else (p.unit or "")

            row_values = [
                p.id,
                p.product_number or f"TC-PRD-{p.id}",
                p.name,
                p.brand or "TipsyCart",
                cat_name,
                subcat_name,
                p_type,
                "Base Product",
                unit_str,
                "-",
                p.product_number or f"TC-PRD-{p.id}",
                mrp,
                price,
                disc / 100.0,
                stock,
                sold,
                rev,
                status_str,
                stock_status,
                created_str,
                now_str,
            ]

            for col_idx, val in enumerate(row_values, start=1):
                cell = ws.cell(row=current_row, column=col_idx, value=val)
                cell.font = data_font
                cell.fill = row_fill
                cell.border = thin_border

                if col_idx in [1, 2, 7, 10, 11, 18, 19, 20]:
                    cell.alignment = center_align
                elif col_idx in [12, 13, 17]:
                    cell.alignment = right_align
                    cell.number_format = "₹#,##0.00"
                elif col_idx == 14:
                    cell.alignment = right_align
                    cell.number_format = "0.0%"
                elif col_idx in [15, 16]:
                    cell.alignment = right_align
                    cell.number_format = "#,##0"
                else:
                    cell.alignment = left_align

            current_row += 1

    # ----------------------------------------------------
    # FREEZE PANES & AUTO-FIT COLUMN WIDTHS
    # ----------------------------------------------------
    # Freeze rows 1 to 4 so headers always stay visible
    ws.freeze_panes = "A5"

    # Enable Excel Auto-Filter on Table Headers (Row 4)
    last_col_letter = get_column_letter(len(headers))
    ws.auto_filter.ref = f"A4:{last_col_letter}{current_row - 1}"

    # Auto-adjust column widths based on maximum text length
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            # Skip merged banner in rows 1 and 2 for width calculation
            if cell.row in [1, 2, 3]:
                continue
            if cell.value:
                val_str = str(cell.value)
                if len(val_str) > max_len:
                    max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    # Specific comfortable minimums
    ws.column_dimensions["A"].width = 12  # Product ID
    ws.column_dimensions["B"].width = 16  # Product Number
    ws.column_dimensions["C"].width = 30  # Product Name
    ws.column_dimensions["D"].width = 16  # Brand
    ws.column_dimensions["E"].width = 20  # Category
    ws.column_dimensions["F"].width = 22  # Subcategory
    ws.column_dimensions["G"].width = 14  # Type
    ws.column_dimensions["H"].width = 22  # Variant Name
    ws.column_dimensions["I"].width = 14  # Size / Unit
    ws.column_dimensions["K"].width = 18  # SKU

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def generate_category_subcategory_excel(
    queryset,
    filter_description="All Filtered Products",
    category_name=None,
    subcategory_name=None,
    product_type=None,
):
    """
    Generates a professional 3-worksheet Excel workbook (.xlsx) tailored for
    Category-wise, Subcategory-wise, and Product Type exports:
    - Sheet 1: 'Products' – Full product details, pricing, stock, sales, and image URLs.
    - Sheet 2: 'Variants' – Complete variable product variant attributes, SKUs, prices, stock.
    - Sheet 3: 'Images' – All media assets (Cover, Gallery, Colour & Variant photos) linked by Product ID.

    Features:
    - TipsyCart Brand Rose styling
    - Auto-filter enabled on row 4 across all sheets
    - Rows 1-4 frozen across all sheets
    - Auto-adjusted column widths with comfortable minimums
    - Currency (₹#,##0.00), percentage (0.0%), integer (#,##0), and date formatting
    - Direct, valid Cloudinary / web image URLs via optimize_image_url
    """
    wb = openpyxl.Workbook()

    # ----------------------------------------------------
    # COLOR PALETTE & STYLES (TipsyCart Brand Palette)
    # ----------------------------------------------------
    PRIMARY_ROSE = "9F1239"   # Dark Rose / Brand Header
    ACCENT_PINK = "FCE7F3"    # Light Pink / Metadata
    ZEBRA_TINT = "FDF2F8"     # Alternate Row Tint
    WHITE = "FFFFFF"
    DARK_TEXT = "1E293B"
    MUTED_TEXT = "64748B"
    BORDER_COLOR = "E2E8F0"

    title_font = Font(name="Calibri", size=13, bold=True, color=WHITE)
    meta_font = Font(name="Calibri", size=9.5, italic=True, color=DARK_TEXT)
    header_font = Font(name="Calibri", size=10.5, bold=True, color=WHITE)
    data_font = Font(name="Calibri", size=9.5, color=DARK_TEXT)
    muted_data_font = Font(name="Calibri", size=9, color=MUTED_TEXT)

    title_fill = PatternFill(start_color=PRIMARY_ROSE, end_color=PRIMARY_ROSE, fill_type="solid")
    meta_fill = PatternFill(start_color=ACCENT_PINK, end_color=ACCENT_PINK, fill_type="solid")
    header_fill = PatternFill(start_color="A51655", end_color="A51655", fill_type="solid")
    zebra_fill = PatternFill(start_color=ZEBRA_TINT, end_color=ZEBRA_TINT, fill_type="solid")
    white_fill = PatternFill(start_color=WHITE, end_color=WHITE, fill_type="solid")

    thin_border = Border(
        left=Side(style="thin", color=BORDER_COLOR),
        right=Side(style="thin", color=BORDER_COLOR),
        top=Side(style="thin", color=BORDER_COLOR),
        bottom=Side(style="thin", color=BORDER_COLOR),
    )

    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")

    now_dt = timezone.localtime(timezone.now())
    now_str = now_dt.strftime("%Y-%m-%d %I:%M:%S %p")
    date_only_str = now_dt.strftime("%Y-%m-%d")

    # ----------------------------------------------------
    # PRE-FETCH PRODUCTS & SALES ANALYTICS
    # ----------------------------------------------------
    products_list = list(
        queryset.select_related("category_ref", "subcategory_ref")
        .prefetch_related(
            "gallery_images",
            "colours",
            "colours__images",
            "variants",
            "variants__colour",
            "variants__size",
        )
        .order_by("-created_at")
    )
    total_products = len(products_list)
    p_ids = [p.id for p in products_list]

    order_items_qs = OrderItem.objects.filter(
        product_id__in=p_ids,
        order__status__in=VALID_ORDER_STATUSES
    )

    prod_sales_map = {}
    for row in order_items_qs.values("product_id").annotate(
        qty=Sum("quantity"),
        rev=Sum(F("price") * F("quantity"))
    ):
        prod_sales_map[row["product_id"]] = {
            "qty": row["qty"] or 0,
            "rev": Decimal(str(row["rev"] or "0.00"))
        }

    var_sales_map = {}
    for row in order_items_qs.exclude(variant_id=None).values("variant_id").annotate(
        qty=Sum("quantity"),
        rev=Sum(F("price") * F("quantity"))
    ):
        var_sales_map[row["variant_id"]] = {
            "qty": row["qty"] or 0,
            "rev": Decimal(str(row["rev"] or "0.00"))
        }

    def _setup_sheet_headers(ws, title_text, meta_text, headers):
        ws.views.sheetView[0].showGridLines = True
        num_cols = len(headers)
        end_col_letter = get_column_letter(num_cols)

        # Row 1: Title
        ws.merge_cells(f"A1:{end_col_letter}1")
        t_cell = ws["A1"]
        t_cell.value = title_text
        t_cell.font = title_font
        t_cell.fill = title_fill
        t_cell.alignment = center_align
        ws.row_dimensions[1].height = 34

        # Row 2: Metadata
        ws.merge_cells(f"A2:{end_col_letter}2")
        m_cell = ws["A2"]
        m_cell.value = meta_text
        m_cell.font = meta_font
        m_cell.fill = meta_fill
        m_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws.row_dimensions[2].height = 20

        # Row 3: Blank separator
        ws.row_dimensions[3].height = 8

        # Row 4: Headers
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=4, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align
            cell.border = thin_border
        ws.row_dimensions[4].height = 26

    def _finalize_sheet_formatting(ws, headers, current_row, min_widths=None):
        min_widths = min_widths or {}
        num_cols = len(headers)
        end_col_letter = get_column_letter(num_cols)

        # Freeze rows 1-4
        ws.freeze_panes = "A5"

        # Auto-filter
        last_row = max(current_row - 1, 4)
        ws.auto_filter.ref = f"A4:{end_col_letter}{last_row}"

        # Adjust column widths
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                if cell.row in [1, 2, 3]:
                    continue
                if cell.value is not None:
                    s_len = len(str(cell.value))
                    if s_len > max_len:
                        max_len = s_len
            min_w = min_widths.get(col_letter, 12)
            ws.column_dimensions[col_letter].width = max(max_len + 3, min_w)

    # ====================================================
    # SHEET 1: PRODUCTS
    # ====================================================
    ws_products = wb.active
    ws_products.title = "Products"

    prod_headers = [
        "Product ID",
        "SKU / Code",
        "Product Name",
        "Brand",
        "Category",
        "Subcategory",
        "Product Type",
        "Description",
        "Unit Type",
        "Default Size / Unit",
        "MRP (₹)",
        "Selling Price (₹)",
        "Discount (%)",
        "Stock Quantity",
        "Units Sold",
        "Total Revenue (₹)",
        "Stock Status",
        "Product Status",
        "Is Featured",
        "Today's Deal",
        "Variant Count",
        "Primary Image URL",
        "Additional Gallery Images",
        "Created Date",
        "Export Date",
    ]

    prod_meta = (
        f"Generated On: {now_str} (IST)  |  Scope / Filter: {filter_description}  |  "
        f"Total Products: {total_products}  |  Database Source: Live Django Database"
    )
    _setup_sheet_headers(ws_products, "TIPSYCART — PRODUCTS & INVENTORY CATALOG", prod_meta, prod_headers)

    row_p = 5
    for idx, p in enumerate(products_list):
        cat_name = p.category_ref.name if p.category_ref else (p.category or "")
        subcat_name = p.subcategory_ref.name if p.subcategory_ref else (p.subcategory or "")
        p_type = "Variable" if p.is_variable else "Simple"
        created_str = timezone.localtime(p.created_at).strftime("%Y-%m-%d") if p.created_at else ""
        prod_sales = prod_sales_map.get(p.id, {"qty": 0, "rev": Decimal("0.00")})

        mrp = float(p.original_price or p.price)
        price = float(p.price)
        disc = float(p.discount_percentage or 0)
        stock = p.total_stock if p.is_variable else p.stock
        sold = prod_sales["qty"]
        rev = float(prod_sales["rev"])
        status_str = "Active" if p.is_active else "Inactive"

        if stock == 0:
            stock_status = "Out of Stock"
        elif stock <= 10:
            stock_status = "Low Stock"
        else:
            stock_status = "In Stock"

        unit_str = f"{p.unit_value:g} {p.unit}".strip() if p.unit_value else (p.unit or "")
        unit_type_display = p.get_unit_type_display() if hasattr(p, "get_unit_type_display") else p.unit_type

        # Primary and gallery images
        primary_img_url = optimize_image_url(p.get_image_url()) if p.get_image_url() else ""
        gallery_urls = [
            optimize_image_url(g.get_image_url())
            for g in p.gallery_images.all()
            if g.get_image_url()
        ]
        gallery_urls_str = " ; ".join(gallery_urls) if gallery_urls else ""

        var_count = p.variants.count() if p.is_variable else 0
        is_feat_str = "Yes" if p.is_featured else "No"
        is_deal_str = "Yes" if p.is_deal_of_the_day else "No"

        row_fill = zebra_fill if idx % 2 == 1 else white_fill

        values = [
            p.id,
            p.product_number or f"TC-PRD-{p.id}",
            p.name,
            p.brand or "TipsyCart",
            cat_name,
            subcat_name,
            p_type,
            p.description or "",
            unit_type_display,
            unit_str,
            mrp,
            price,
            disc / 100.0,
            stock,
            sold,
            rev,
            stock_status,
            status_str,
            is_feat_str,
            is_deal_str,
            var_count,
            primary_img_url,
            gallery_urls_str,
            created_str,
            date_only_str,
        ]

        for col_idx, val in enumerate(values, start=1):
            cell = ws_products.cell(row=row_p, column=col_idx, value=val)
            cell.font = data_font
            cell.fill = row_fill
            cell.border = thin_border

            # Column specific alignment & format
            if col_idx in [1, 2, 7, 9, 10, 17, 18, 19, 20, 21, 24, 25]:
                cell.alignment = center_align
            elif col_idx in [11, 12, 16]:
                cell.alignment = right_align
                cell.number_format = "₹#,##0.00"
            elif col_idx == 13:
                cell.alignment = right_align
                cell.number_format = "0.0%"
            elif col_idx in [14, 15]:
                cell.alignment = right_align
                cell.number_format = "#,##0"
            else:
                cell.alignment = left_align

        ws_products.row_dimensions[row_p].height = 20
        row_p += 1

    prod_min_widths = {
        "A": 12, "B": 16, "C": 32, "D": 16, "E": 20, "F": 22,
        "G": 14, "H": 30, "I": 16, "J": 18, "K": 14, "L": 14,
        "M": 12, "N": 14, "O": 12, "P": 16, "Q": 14, "R": 14,
        "S": 12, "T": 12, "U": 14, "V": 40, "W": 40, "X": 14, "Y": 14
    }
    _finalize_sheet_formatting(ws_products, prod_headers, row_p, prod_min_widths)

    # ====================================================
    # SHEET 2: VARIANTS
    # ====================================================
    ws_variants = wb.create_sheet(title="Variants")

    var_headers = [
        "Product ID",
        "Product SKU",
        "Product Name",
        "Category",
        "Subcategory",
        "Variant ID",
        "Variant SKU",
        "Variant Title / Name",
        "Size / Option",
        "Colour / Shade",
        "Colour Hex Code",
        "Unit / Measurement",
        "Barcode / EAN",
        "Variant MRP (₹)",
        "Variant Selling Price (₹)",
        "Discount (%)",
        "Variant Stock",
        "Units Sold",
        "Total Revenue (₹)",
        "Stock Status",
        "Variant Status",
        "Variant Image URL",
        "Created Date",
    ]

    # Pre-count total variants
    all_variants_count = sum(len(list(p.variants.all())) for p in products_list if p.is_variable)
    var_meta = (
        f"Linked to Products via 'Product ID'  |  Total Variable Products: {sum(1 for p in products_list if p.is_variable)}  |  "
        f"Total Variants: {all_variants_count}  |  Single Source of Truth: TipsyCart Database"
    )
    _setup_sheet_headers(ws_variants, "TIPSYCART — PRODUCT VARIANTS & ATTRIBUTES", var_meta, var_headers)

    row_v = 5
    var_row_idx = 0
    for p in products_list:
        if not p.is_variable:
            continue

        cat_name = p.category_ref.name if p.category_ref else (p.category or "")
        subcat_name = p.subcategory_ref.name if p.subcategory_ref else (p.subcategory or "")
        parent_sku = p.product_number or f"TC-PRD-{p.id}"

        for v in p.variants.all():
            v_sales = var_sales_map.get(v.id, {"qty": 0, "rev": Decimal("0.00")})
            v_name = v.variant_name or v.get_title()
            v_size = v.size.name if v.size else (f"{v.unit_value} {v.unit}".strip() if v.unit_value else (v.unit or ""))
            v_colour = v.colour.name if v.colour else ""
            v_hex = v.colour.color_code if v.colour else ""
            v_unit = f"{v.unit_value:g} {v.unit}".strip() if v.unit_value else (v.unit or "")
            v_sku = v.sku or f"{parent_sku}-V{v.id}"
            v_mrp = float(v.original_price or p.original_price or v.price)
            v_price = float(v.price)
            v_disc = float(v.discount_percentage or 0)
            v_stock = v.stock
            v_sold = v_sales["qty"]
            v_rev = float(v_sales["rev"])
            v_status = "Active" if (p.is_active and v.is_active) else "Inactive"

            if v_stock == 0:
                v_stock_status = "Out of Stock"
            elif v_stock <= 10:
                v_stock_status = "Low Stock"
            else:
                v_stock_status = "In Stock"

            v_img_url = optimize_image_url(v.get_image_url()) if v.get_image_url() else ""
            v_created = timezone.localtime(v.created_at).strftime("%Y-%m-%d") if v.created_at else date_only_str

            row_fill = zebra_fill if var_row_idx % 2 == 1 else white_fill

            v_values = [
                p.id,
                parent_sku,
                p.name,
                cat_name,
                subcat_name,
                v.id,
                v_sku,
                v_name,
                v_size,
                v_colour,
                v_hex,
                v_unit,
                v.barcode or "",
                v_mrp,
                v_price,
                v_disc / 100.0,
                v_stock,
                v_sold,
                v_rev,
                v_stock_status,
                v_status,
                v_img_url,
                v_created,
            ]

            for col_idx, val in enumerate(v_values, start=1):
                cell = ws_variants.cell(row=row_v, column=col_idx, value=val)
                cell.font = data_font
                cell.fill = row_fill
                cell.border = thin_border

                if col_idx in [1, 2, 6, 7, 11, 13, 20, 21, 23]:
                    cell.alignment = center_align
                elif col_idx in [14, 15, 19]:
                    cell.alignment = right_align
                    cell.number_format = "₹#,##0.00"
                elif col_idx == 16:
                    cell.alignment = right_align
                    cell.number_format = "0.0%"
                elif col_idx in [17, 18]:
                    cell.alignment = right_align
                    cell.number_format = "#,##0"
                else:
                    cell.alignment = left_align

            ws_variants.row_dimensions[row_v].height = 20
            row_v += 1
            var_row_idx += 1

    var_min_widths = {
        "A": 12, "B": 16, "C": 30, "D": 20, "E": 22, "F": 12,
        "G": 18, "H": 24, "I": 16, "J": 16, "K": 16, "L": 18,
        "M": 16, "N": 14, "O": 14, "P": 12, "Q": 14, "R": 12,
        "S": 16, "T": 14, "U": 14, "V": 40, "W": 14
    }
    _finalize_sheet_formatting(ws_variants, var_headers, row_v, var_min_widths)

    # ====================================================
    # SHEET 3: IMAGES
    # ====================================================
    ws_images = wb.create_sheet(title="Images")

    img_headers = [
        "Product ID",
        "Product SKU",
        "Product Name",
        "Category",
        "Image Record ID",
        "Image Type",
        "Display Order",
        "Is Primary",
        "Alt Text / Label",
        "Image URL",
    ]

    img_meta = (
        f"Linked to Products via 'Product ID'  |  Complete Media Catalog  |  "
        f"Valid Cloudinary & Web URLs  |  Single Source of Truth: TipsyCart Database"
    )
    _setup_sheet_headers(ws_images, "TIPSYCART — PRODUCT IMAGES & MEDIA ASSETS", img_meta, img_headers)

    row_img = 5
    img_row_idx = 0
    for p in products_list:
        cat_name = p.category_ref.name if p.category_ref else (p.category or "")
        parent_sku = p.product_number or f"TC-PRD-{p.id}"
        seen_urls = set()

        # 1. Main cover image
        cover_url = optimize_image_url(p.get_image_url()) if p.get_image_url() else ""
        if cover_url:
            seen_urls.add(cover_url)
            row_fill = zebra_fill if img_row_idx % 2 == 1 else white_fill
            img_values = [
                p.id,
                parent_sku,
                p.name,
                cat_name,
                0,
                "Cover Image (Primary)",
                1,
                "Yes",
                p.name,
                cover_url,
            ]
            for col_idx, val in enumerate(img_values, start=1):
                cell = ws_images.cell(row=row_img, column=col_idx, value=val)
                cell.font = data_font
                cell.fill = row_fill
                cell.border = thin_border
                if col_idx in [1, 2, 5, 7, 8]:
                    cell.alignment = center_align
                else:
                    cell.alignment = left_align
            ws_images.row_dimensions[row_img].height = 20
            row_img += 1
            img_row_idx += 1

        # 2. Gallery images
        for gimg in p.gallery_images.all().order_by("display_order", "id"):
            raw_url = gimg.get_image_url()
            url = optimize_image_url(raw_url) if raw_url else ""
            if url and url not in seen_urls:
                seen_urls.add(url)
                row_fill = zebra_fill if img_row_idx % 2 == 1 else white_fill
                is_p_str = "Yes" if gimg.is_primary else "No"
                img_values = [
                    p.id,
                    parent_sku,
                    p.name,
                    cat_name,
                    gimg.id,
                    "Gallery Image",
                    gimg.display_order,
                    is_p_str,
                    gimg.alt_text or p.name,
                    url,
                ]
                for col_idx, val in enumerate(img_values, start=1):
                    cell = ws_images.cell(row=row_img, column=col_idx, value=val)
                    cell.font = data_font
                    cell.fill = row_fill
                    cell.border = thin_border
                    if col_idx in [1, 2, 5, 7, 8]:
                        cell.alignment = center_align
                    else:
                        cell.alignment = left_align
                ws_images.row_dimensions[row_img].height = 20
                row_img += 1
                img_row_idx += 1

        # 3. Colour images (for variable fashion / cosmetics products)
        for c in p.colours.all():
            for cimg in c.images.all().order_by("display_order", "id"):
                raw_url = cimg.get_image_url()
                url = optimize_image_url(raw_url) if raw_url else ""
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    row_fill = zebra_fill if img_row_idx % 2 == 1 else white_fill
                    is_p_str = "Yes" if cimg.is_primary else "No"
                    img_values = [
                        p.id,
                        parent_sku,
                        p.name,
                        cat_name,
                        cimg.id,
                        f"Colour Variant Image ({c.name})",
                        cimg.display_order,
                        is_p_str,
                        f"{p.name} - {c.name}",
                        url,
                    ]
                    for col_idx, val in enumerate(img_values, start=1):
                        cell = ws_images.cell(row=row_img, column=col_idx, value=val)
                        cell.font = data_font
                        cell.fill = row_fill
                        cell.border = thin_border
                        if col_idx in [1, 2, 5, 7, 8]:
                            cell.alignment = center_align
                        else:
                            cell.alignment = left_align
                    ws_images.row_dimensions[row_img].height = 20
                    row_img += 1
                    img_row_idx += 1

        # 4. Variant-specific custom photos
        for v in p.variants.all():
            if v.image or v.image_url:
                raw_url = v.get_image_url()
                url = optimize_image_url(raw_url) if raw_url else ""
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    row_fill = zebra_fill if img_row_idx % 2 == 1 else white_fill
                    img_values = [
                        p.id,
                        parent_sku,
                        p.name,
                        cat_name,
                        v.id,
                        f"Variant Photo ({v.get_title()})",
                        1,
                        "No",
                        v.get_full_name(),
                        url,
                    ]
                    for col_idx, val in enumerate(img_values, start=1):
                        cell = ws_images.cell(row=row_img, column=col_idx, value=val)
                        cell.font = data_font
                        cell.fill = row_fill
                        cell.border = thin_border
                        if col_idx in [1, 2, 5, 7, 8]:
                            cell.alignment = center_align
                        else:
                            cell.alignment = left_align
                    ws_images.row_dimensions[row_img].height = 20
                    row_img += 1
                    img_row_idx += 1

    img_min_widths = {
        "A": 12, "B": 16, "C": 30, "D": 20, "E": 14,
        "F": 24, "G": 14, "H": 12, "I": 28, "J": 50
    }
    _finalize_sheet_formatting(ws_images, img_headers, row_img, img_min_widths)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def generate_analytics_excel(summary_data, top_products, low_stock_items, category_performance, filter_desc=""):
    """
    Generates a multi-sheet, beautifully styled executive analytics workbook (.xlsx)
    containing:
    - Sheet 1: Executive KPI Summary & Category Performance
    - Sheet 2: Top Selling Products
    - Sheet 3: Low Stock & Reorder Alerts
    """
    wb = openpyxl.Workbook()
    
    # ----------------------------------------------------
    # COLOR PALETTE
    # ----------------------------------------------------
    PRIMARY_ROSE = "9F1239"
    ACCENT_PINK = "FCE7F3"
    WHITE = "FFFFFF"
    DARK_TEXT = "1E293B"
    BORDER_COLOR = "E2E8F0"
    GREEN_FILL = "DCFCE7"
    AMBER_FILL = "FEF3C7"
    RED_FILL = "FEE2E2"

    title_font = Font(name="Calibri", size=14, bold=True, color=WHITE)
    section_font = Font(name="Calibri", size=11, bold=True, color=WHITE)
    header_font = Font(name="Calibri", size=10, bold=True, color=WHITE)
    kpi_val_font = Font(name="Calibri", size=13, bold=True, color="9F1239")
    kpi_lbl_font = Font(name="Calibri", size=9, bold=True, color="64748B")
    data_font = Font(name="Calibri", size=10, color=DARK_TEXT)
    bold_data_font = Font(name="Calibri", size=10, bold=True, color=DARK_TEXT)

    thin_border = Border(
        left=Side(style="thin", color=BORDER_COLOR),
        right=Side(style="thin", color=BORDER_COLOR),
        top=Side(style="thin", color=BORDER_COLOR),
        bottom=Side(style="thin", color=BORDER_COLOR),
    )
    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")

    title_fill = PatternFill(start_color=PRIMARY_ROSE, end_color=PRIMARY_ROSE, fill_type="solid")
    meta_fill = PatternFill(start_color=ACCENT_PINK, end_color=ACCENT_PINK, fill_type="solid")
    header_fill = PatternFill(start_color="A51655", end_color="A51655", fill_type="solid")
    zebra_fill = PatternFill(start_color="FDF2F8", end_color="FDF2F8", fill_type="solid")
    white_fill = PatternFill(start_color=WHITE, end_color=WHITE, fill_type="solid")

    now_str = timezone.localtime(timezone.now()).strftime("%Y-%m-%d %I:%M:%S %p")

    # ====================================================
    # SHEET 1: EXECUTIVE SUMMARY & CATEGORY PERFORMANCE
    # ====================================================
    ws1 = wb.active
    ws1.title = "Executive Summary"
    ws1.views.sheetView[0].showGridLines = True

    # Title Banner
    ws1.merge_cells("A1:G1")
    t_cell = ws1["A1"]
    t_cell.value = "TIPSYCART — PRODUCT MANAGEMENT & SALES ANALYTICS"
    t_cell.font = title_font
    t_cell.fill = title_fill
    t_cell.alignment = center_align
    ws1.row_dimensions[1].height = 36

    ws1.merge_cells("A2:G2")
    m_cell = ws1["A2"]
    m_cell.value = f"Generated: {now_str} (IST)  |  Filter Scope: {filter_desc or 'All Records'}  |  Single Source of Truth: Django ORM"
    m_cell.font = Font(name="Calibri", size=10, italic=True, color=DARK_TEXT)
    m_cell.fill = meta_fill
    m_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws1.row_dimensions[2].height = 22

    # KPI Cards Section
    kpis = [
        ("Total Products", summary_data.get("total_products", 0), "#,##0"),
        ("Active Products", summary_data.get("active_products", 0), "#,##0"),
        ("Inactive Products", summary_data.get("inactive_products", 0), "#,##0"),
        ("Total Variants", summary_data.get("total_variants", 0), "#,##0"),
        ("Total Available Stock", summary_data.get("total_stock", 0), "#,##0"),
        ("Inventory Valuation", float(summary_data.get("inventory_valuation", 0)), "₹#,##0.00"),
        ("Low Stock (<=10)", summary_data.get("low_stock_count", 0), "#,##0"),
        ("Out of Stock (0)", summary_data.get("out_of_stock_count", 0), "#,##0"),
        ("Total Units Sold", summary_data.get("total_units_sold", 0), "#,##0"),
        ("Total Product Revenue", float(summary_data.get("total_revenue", 0)), "₹#,##0.00"),
    ]

    ws1.merge_cells("A4:G4")
    sec_cell = ws1["A4"]
    sec_cell.value = "1. INVENTORY & SALES KPI METRICS"
    sec_cell.font = section_font
    sec_cell.fill = PatternFill(start_color="831843", end_color="831843", fill_type="solid")
    sec_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws1.row_dimensions[4].height = 24

    ws1.cell(row=5, column=1, value="Metric Name").font = header_font
    ws1.cell(row=5, column=1).fill = header_fill
    ws1.cell(row=5, column=1).alignment = left_align
    ws1.cell(row=5, column=1).border = thin_border

    ws1.cell(row=5, column=2, value="Current Value").font = header_font
    ws1.cell(row=5, column=2).fill = header_fill
    ws1.cell(row=5, column=2).alignment = right_align
    ws1.cell(row=5, column=2).border = thin_border
    ws1.row_dimensions[5].height = 22

    r_idx = 6
    for lbl, val, fmt in kpis:
        c1 = ws1.cell(row=r_idx, column=1, value=lbl)
        c1.font = bold_data_font
        c1.alignment = left_align
        c1.border = thin_border
        c1.fill = zebra_fill if r_idx % 2 == 1 else white_fill

        c2 = ws1.cell(row=r_idx, column=2, value=val)
        c2.font = kpi_val_font
        c2.alignment = right_align
        c2.number_format = fmt
        c2.border = thin_border
        c2.fill = zebra_fill if r_idx % 2 == 1 else white_fill
        r_idx += 1

    # Category Performance Table
    cat_start = r_idx + 2
    ws1.merge_cells(f"A{cat_start}:G{cat_start}")
    cat_sec = ws1[f"A{cat_start}"]
    cat_sec.value = "2. CATEGORY-WISE INVENTORY & REVENUE PERFORMANCE"
    cat_sec.font = section_font
    cat_sec.fill = PatternFill(start_color="831843", end_color="831843", fill_type="solid")
    cat_sec.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws1.row_dimensions[cat_start].height = 24

    cat_headers = ["Category Name", "Total Products", "Stock Units", "Units Sold", "Total Revenue (₹)", "Revenue Share (%)"]
    for c_i, ch in enumerate(cat_headers, start=1):
        cell = ws1.cell(row=cat_start + 1, column=c_i, value=ch)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border
    ws1.row_dimensions[cat_start + 1].height = 24

    tot_rev = float(summary_data.get("total_revenue", 0)) or 1.0
    for idx, cp in enumerate(category_performance):
        c_row = cat_start + 2 + idx
        c_fill = zebra_fill if idx % 2 == 1 else white_fill
        rev_val = float(cp.get("revenue", 0))
        share = (rev_val / tot_rev) if tot_rev > 0 else 0.0

        vals = [
            cp.get("name", "Uncategorized"),
            cp.get("product_count", 0),
            cp.get("stock", 0),
            cp.get("units_sold", 0),
            rev_val,
            share,
        ]
        for c_i, v in enumerate(vals, start=1):
            cell = ws1.cell(row=c_row, column=c_i, value=v)
            cell.font = data_font
            cell.border = thin_border
            cell.fill = c_fill
            if c_i == 1:
                cell.alignment = left_align
            elif c_i in [2, 3, 4]:
                cell.alignment = right_align
                cell.number_format = "#,##0"
            elif c_i == 5:
                cell.alignment = right_align
                cell.number_format = "₹#,##0.00"
            elif c_i == 6:
                cell.alignment = right_align
                cell.number_format = "0.0%"

    for col in ws1.columns:
        col_letter = get_column_letter(col[0].column)
        ws1.column_dimensions[col_letter].width = 24
    ws1.column_dimensions["A"].width = 30

    # ====================================================
    # SHEET 2: TOP SELLING PRODUCTS
    # ====================================================
    ws2 = wb.create_sheet(title="Top Selling Products")
    ws2.views.sheetView[0].showGridLines = True

    ws2.merge_cells("A1:H1")
    t2 = ws2["A1"]
    t2.value = "TIPSYCART — TOP SELLING PRODUCTS (BY SALES & REVENUE)"
    t2.font = title_font
    t2.fill = title_fill
    t2.alignment = center_align
    ws2.row_dimensions[1].height = 36

    top_headers = ["Rank", "Product ID / SKU", "Product Name", "Category", "Current Stock", "Units Sold", "Total Revenue (₹)", "Status"]
    for c_i, th in enumerate(top_headers, start=1):
        cell = ws2.cell(row=3, column=c_i, value=th)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border
    ws2.row_dimensions[3].height = 24

    for idx, tp in enumerate(top_products, start=1):
        t_row = 3 + idx
        t_fill = zebra_fill if idx % 2 == 1 else white_fill
        row_vals = [
            idx,
            tp.get("sku", ""),
            tp.get("name", ""),
            tp.get("category", ""),
            tp.get("stock", 0),
            tp.get("units_sold", 0),
            float(tp.get("revenue", 0)),
            tp.get("status", "Active"),
        ]
        for c_i, v in enumerate(row_vals, start=1):
            cell = ws2.cell(row=t_row, column=c_i, value=v)
            cell.font = data_font
            cell.border = thin_border
            cell.fill = t_fill
            if c_i in [1, 2, 8]:
                cell.alignment = center_align
            elif c_i in [5, 6]:
                cell.alignment = right_align
                cell.number_format = "#,##0"
            elif c_i == 7:
                cell.alignment = right_align
                cell.number_format = "₹#,##0.00"
            else:
                cell.alignment = left_align

    ws2.freeze_panes = "A4"
    for col in ws2.columns:
        col_letter = get_column_letter(col[0].column)
        ws2.column_dimensions[col_letter].width = 20
    ws2.column_dimensions["C"].width = 34

    # ====================================================
    # SHEET 3: LOW STOCK & REORDER ALERTS
    # ====================================================
    ws3 = wb.create_sheet(title="Low Stock & Reorder Alert")
    ws3.views.sheetView[0].showGridLines = True

    ws3.merge_cells("A1:G1")
    t3 = ws3["A1"]
    t3.value = "TIPSYCART — INVENTORY LOW STOCK & REORDER ALERTS (STOCK <= 10)"
    t3.font = title_font
    t3.fill = PatternFill(start_color="991B1B", end_color="991B1B", fill_type="solid")
    t3.alignment = center_align
    ws3.row_dimensions[1].height = 36

    alert_headers = ["Product ID / SKU", "Product Name", "Category", "Type / Variant", "Available Stock", "Stock Status", "Price (₹)"]
    for c_i, ah in enumerate(alert_headers, start=1):
        cell = ws3.cell(row=3, column=c_i, value=ah)
        cell.font = header_font
        cell.fill = PatternFill(start_color="B91C1C", end_color="B91C1C", fill_type="solid")
        cell.alignment = center_align
        cell.border = thin_border
    ws3.row_dimensions[3].height = 24

    for idx, item in enumerate(low_stock_items, start=1):
        l_row = 3 + idx
        stock_val = item.get("stock", 0)
        status_text = "Out of Stock" if stock_val == 0 else "Low Stock"
        status_fill = PatternFill(start_color=RED_FILL if stock_val == 0 else AMBER_FILL,
                                  end_color=RED_FILL if stock_val == 0 else AMBER_FILL,
                                  fill_type="solid")
        
        row_vals = [
            item.get("sku", ""),
            item.get("name", ""),
            item.get("category", ""),
            item.get("variant_name", "Base"),
            stock_val,
            status_text,
            float(item.get("price", 0)),
        ]
        for c_i, v in enumerate(row_vals, start=1):
            cell = ws3.cell(row=l_row, column=c_i, value=v)
            cell.font = data_font
            cell.border = thin_border
            if c_i in [5, 6]:
                cell.fill = status_fill
                cell.font = bold_data_font
            else:
                cell.fill = zebra_fill if idx % 2 == 1 else white_fill

            if c_i in [1, 6]:
                cell.alignment = center_align
            elif c_i == 5:
                cell.alignment = right_align
                cell.number_format = "#,##0"
            elif c_i == 7:
                cell.alignment = right_align
                cell.number_format = "₹#,##0.00"
            else:
                cell.alignment = left_align

    ws3.freeze_panes = "A4"
    for col in ws3.columns:
        col_letter = get_column_letter(col[0].column)
        ws3.column_dimensions[col_letter].width = 22
    ws3.column_dimensions["B"].width = 34

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer

