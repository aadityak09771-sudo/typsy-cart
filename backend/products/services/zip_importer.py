import base64
import csv
import io
import logging
import mimetypes
import os
import re
import shutil
import zipfile
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.db import transaction
from products.models import Product

logger = logging.getLogger(__name__)

MAX_ZIP_SIZE = 50 * 1024 * 1024         # 50 MB
MAX_TOTAL_UNCOMPRESSED = 150 * 1024 * 1024 # 150 MB
MAX_FILE_COUNT = 1000
MAX_SINGLE_FILE = 20 * 1024 * 1024       # 20 MB

SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

COLUMN_ALIASES = {
    "product_number": {
        "product number", "product_number", "product code", "product_code",
        "sku", "sku code", "code", "item code", "tc_number", "product id"
    },
    "name": {
        "product name", "product_name", "name", "title", "item name", "product"
    },
    "image_filename": {
        "image filename", "image_filename", "image file", "image", "image name",
        "photo", "picture", "filename", "img"
    },
    "price": {
        "price (inr)", "price(inr)", "price in inr", "price (rs)", "price(rs)",
        "price in rs", "price", "mrp", "rate", "cost", "amount"
    },
    "category": {
        "category", "category name", "cat"
    },
    "subcategory": {
        "subcategory", "sub_category", "sub category"
    },
    "brand": {
        "brand", "brand name", "company", "manufacturer"
    },
    "stock": {
        "stock", "quantity", "qty", "inventory"
    },
    "description": {
        "description", "desc", "details", "info"
    },
}


def sanitize_zip_path(raw_name: str) -> str:
    """
    Prevents Zip Slip / Directory Traversal attacks.
    Ensures path does not contain '..' or absolute components.
    """
    cleaned = raw_name.replace("\\", "/").strip()
    norm = os.path.normpath(cleaned).replace("\\", "/")
    if (
        norm.startswith("../")
        or norm.startswith("..")
        or norm.startswith("/")
        or ":" in norm
        or norm.startswith("~")
    ):
        raise ValueError(f"Insecure file path detected in ZIP: {raw_name}")
    return norm


def col_letter_to_index(col_str: str) -> int:
    num = 0
    for char in col_str.upper():
        if "A" <= char <= "Z":
            num = num * 26 + (ord(char) - ord("A") + 1)
    return max(0, num - 1)


def parse_xlsx_from_bytes(file_bytes: bytes) -> list[list[str]]:
    """
    Parses an Excel .xlsx workbook using standard library zipfile + ElementTree.
    Does not require third-party libraries.
    """
    zf = zipfile.ZipFile(io.BytesIO(file_bytes))
    ns = {"ns": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

    # 1. Shared strings table
    shared_strings = []
    if "xl/sharedStrings.xml" in zf.namelist():
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        for si in root.findall(".//ns:si", ns):
            text = "".join(t.text or "" for t in si.findall(".//ns:t", ns))
            shared_strings.append(text)

    # 2. Locate first sheet
    sheet_name = "xl/worksheets/sheet1.xml"
    if sheet_name not in zf.namelist():
        for name in zf.namelist():
            if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"):
                sheet_name = name
                break

    if sheet_name not in zf.namelist():
        raise ValueError("Could not find any worksheet in the XLSX workbook.")

    sheet_root = ET.fromstring(zf.read(sheet_name))
    parsed_rows = []

    for row in sheet_root.findall(".//ns:row", ns):
        row_cells = {}
        max_col = 0
        for c in row.findall("ns:c", ns):
            r_attr = c.get("r", "")
            m = re.match(r"([A-Za-z]+)(\d+)", r_attr)
            if m:
                col_idx = col_letter_to_index(m.group(1))
            else:
                col_idx = len(row_cells)

            max_col = max(max_col, col_idx)
            cell_type = c.get("t", "")
            val_node = c.find("ns:v", ns)
            val = ""

            if cell_type == "s" and val_node is not None and val_node.text:
                try:
                    s_idx = int(val_node.text)
                    val = shared_strings[s_idx] if s_idx < len(shared_strings) else ""
                except (ValueError, IndexError):
                    val = ""
            elif cell_type == "inlineStr":
                is_node = c.find(".//ns:t", ns)
                val = is_node.text if is_node is not None else ""
            elif val_node is not None and val_node.text:
                val = val_node.text

            row_cells[col_idx] = str(val or "").strip()

        if row_cells:
            row_list = [row_cells.get(i, "") for i in range(max_col + 1)]
            if any(cell for cell in row_list):
                parsed_rows.append(row_list)

    return parsed_rows


def parse_csv_from_bytes(file_bytes: bytes) -> list[list[str]]:
    """
    Parses a CSV file from bytes, handling UTF-8-BOM and Latin-1 fallbacks.
    """
    try:
        content = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = file_bytes.decode("latin-1", errors="replace")

    reader = csv.reader(io.StringIO(content))
    rows = []
    for r in reader:
        if any(cell.strip() for cell in r):
            rows.append([cell.strip() for cell in r])
    return rows


def map_headers(header_row: list[str]) -> dict[str, int]:
    """
    Maps logical field names (product_number, name, image_filename, price)
    to column indices based on aliases.
    """
    col_map = {}
    for idx, raw_header in enumerate(header_row):
        norm = re.sub(r"\s+", " ", str(raw_header).strip().lower())
        for canonical, aliases in COLUMN_ALIASES.items():
            if norm in aliases or norm == canonical:
                if canonical not in col_map:
                    col_map[canonical] = idx
                break

    return col_map


class ZipProductImporter:
    """
    Manages safe preview, validation, and execution of bulk product imports
    from a ZIP archive containing a spreadsheet (CSV/XLSX) and product images.
    """

    def __init__(self, zip_file_or_bytes, default_category="Daily Essentials", default_stock=50):
        self.raw_data = zip_file_or_bytes
        self.default_category = default_category or "Daily Essentials"
        self.default_stock = int(default_stock or 50)
        self.zf = None
        self.image_entries = {}       # normalized basename -> zip entry path
        self.spreadsheet_path = None
        self.spreadsheet_type = None

    def _open_zip(self):
        if hasattr(self.raw_data, "read"):
            data_bytes = self.raw_data.read()
        elif isinstance(self.raw_data, (bytes, bytearray)):
            data_bytes = bytes(self.raw_data)
        else:
            raise ValueError("Invalid file input: must be file object or bytes.")

        if len(data_bytes) > MAX_ZIP_SIZE:
            raise ValueError(f"ZIP file size ({len(data_bytes)/(1024*1024):.1f} MB) exceeds maximum allowed {MAX_ZIP_SIZE/(1024*1024):.0f} MB.")

        self.zf = zipfile.ZipFile(io.BytesIO(data_bytes))
        total_size = 0
        file_count = 0

        for info in self.zf.infolist():
            file_count += 1
            if file_count > MAX_FILE_COUNT:
                raise ValueError(f"ZIP contains too many files (over {MAX_FILE_COUNT}).")
            if info.file_size > MAX_SINGLE_FILE:
                raise ValueError(f"ZIP contains file '{info.filename}' exceeding {MAX_SINGLE_FILE/(1024*1024):.0f} MB.")
            total_size += info.file_size
            if total_size > MAX_TOTAL_UNCOMPRESSED:
                raise ValueError(f"Total uncompressed ZIP size exceeds {MAX_TOTAL_UNCOMPRESSED/(1024*1024):.0f} MB.")

            # Validate path safety
            sanitize_zip_path(info.filename)

        # Index spreadsheet and image entries
        for name in self.zf.namelist():
            if name.endswith("/") or name.endswith("\\"):
                continue
            lower_name = name.lower()
            if "__macosx" in lower_name or "/." in lower_name or lower_name.startswith("."):
                continue

            base = os.path.basename(name).strip()
            _, ext = os.path.splitext(base.lower())

            # Detect spreadsheet
            if ext in (".csv", ".xlsx"):
                if not self.spreadsheet_path or "product" in base.lower():
                    self.spreadsheet_path = name
                    self.spreadsheet_type = ext

            # Detect images
            if ext in SUPPORTED_IMAGE_EXTS:
                self.image_entries[base.lower()] = name

        if not self.spreadsheet_path:
            raise ValueError("No valid spreadsheet (.csv or .xlsx) found inside the ZIP archive.")

    def parse_and_validate(self) -> dict:
        self._open_zip()

        # Read spreadsheet
        sheet_bytes = self.zf.read(self.spreadsheet_path)
        if self.spreadsheet_type == ".xlsx":
            rows = parse_xlsx_from_bytes(sheet_bytes)
        else:
            rows = parse_csv_from_bytes(sheet_bytes)

        if not rows or len(rows) < 2:
            raise ValueError("The spreadsheet in the ZIP is empty or has no data rows.")

        header_row = rows[0]
        col_map = map_headers(header_row)

        required = ["name", "price"]
        missing_required = [req for req in required if req not in col_map]
        if missing_required:
            raise ValueError(
                f"Missing required columns in spreadsheet: {', '.join(missing_required)}. "
                f"Found columns: {', '.join(header_row)}"
            )

        valid_categories = {choice[0] for choice in Product.CATEGORY_CHOICES}
        valid_products = []
        duplicate_products = []
        invalid_rows = []
        seen_pnums = set()
        seen_names = set()

        # Preload existing DB product numbers and names for duplicate check
        db_pnums = set(
            Product.objects.exclude(product_number="")
            .values_list("product_number", flat=True)
        )
        db_names = set(
            Product.objects.values_list("name", flat=True)
        )
        db_names_lower = {n.lower() for n in db_names}

        for row_idx, r in enumerate(rows[1:], start=2):
            errors = []

            def get_col(field_name, default=""):
                if field_name in col_map and col_map[field_name] < len(r):
                    return str(r[col_map[field_name]] or "").strip()
                return default

            pnum = get_col("product_number")
            name = get_col("name")
            img_file = get_col("image_filename")
            price_raw = get_col("price")
            category = get_col("category", self.default_category)
            subcategory = get_col("subcategory", "")
            brand = get_col("brand", "TipsyCart")
            description = get_col("description", "")
            stock_raw = get_col("stock", str(self.default_stock))

            if not name:
                errors.append("Product Name is required.")

            if not pnum:
                # If no product_number column was provided, auto-generate temporary code
                pnum = f"TC-IMP-{row_idx:04d}"

            # Duplicate check in spreadsheet
            pnum_lower = pnum.lower()
            name_lower = name.lower()

            if pnum_lower in seen_pnums:
                errors.append(f"Duplicate product number '{pnum}' appears multiple times in spreadsheet.")
            seen_pnums.add(pnum_lower)

            # Price validation
            price_val = None
            try:
                # Remove currency symbols and whitespace, preserve sign and decimal
                clean_price = re.sub(r"[^\d.\-+]", "", price_raw.strip())
                price_val = Decimal(clean_price)
                if not price_val.is_finite() or price_val <= 0:
                    errors.append(f"Price must be a positive number greater than 0 (got '{price_raw}').")
            except (InvalidOperation, ValueError, TypeError):
                errors.append(f"Invalid price format '{price_raw}'.")

            # Stock validation
            stock_val = self.default_stock
            if stock_raw:
                try:
                    clean_stock = int(re.sub(r"[^\d]", "", stock_raw) or "0")
                    stock_val = max(0, clean_stock)
                except ValueError:
                    stock_val = self.default_stock

            # Image matching
            matched_zip_path = None
            thumbnail_b64 = None
            if img_file:
                clean_img_base = os.path.basename(img_file).strip().lower()
                matched_zip_path = self.image_entries.get(clean_img_base)
                if not matched_zip_path:
                    errors.append(f"Image '{img_file}' was not found in the ZIP archive.")
                else:
                    try:
                        img_bytes = self.zf.read(matched_zip_path)
                        mime_type, _ = mimetypes.guess_type(clean_img_base)
                        mime = mime_type or "image/jpeg"
                        # Create small preview thumbnail (limit size to 256KB for preview)
                        preview_bytes = img_bytes if len(img_bytes) <= 256 * 1024 else img_bytes[:256*1024]
                        thumbnail_b64 = f"data:{mime};base64,{base64.b64encode(preview_bytes).decode('ascii')}"
                    except Exception as e:
                        logger.warning(f"Failed to read image thumbnail for {img_file}: {e}")
            else:
                errors.append("Image Filename is required.")

            # Category validation
            if category not in valid_categories:
                category = self.default_category

            # Description fallback
            if not description:
                description = f"{name} by {brand or 'TipsyCart'}. Premium daily essentials available at TipsyCart."

            # DB duplicate check
            is_db_duplicate = False
            dup_reason = ""
            if pnum in db_pnums:
                is_db_duplicate = True
                dup_reason = f"Product Number '{pnum}' already exists in database."
            elif name_lower in db_names_lower:
                is_db_duplicate = True
                dup_reason = f"Product Name '{name}' already exists in database."

            item_data = {
                "row_number": row_idx,
                "product_number": pnum,
                "name": name,
                "price": str(price_val) if price_val else price_raw,
                "price_decimal": price_val,
                "category": category,
                "subcategory": subcategory,
                "brand": brand or "TipsyCart",
                "description": description,
                "stock": stock_val,
                "image_filename": img_file,
                "matched_zip_path": matched_zip_path,
                "thumbnail_b64": thumbnail_b64,
                "errors": errors,
            }

            if errors:
                invalid_rows.append(item_data)
            elif is_db_duplicate:
                item_data["duplicate_reason"] = dup_reason
                duplicate_products.append(item_data)
            else:
                valid_products.append(item_data)

        # Unmatched images inside ZIP
        used_zip_paths = {p["matched_zip_path"] for p in valid_products + duplicate_products if p.get("matched_zip_path")}
        unmatched_images = [
            os.path.basename(path) for path in self.image_entries.values() if path not in used_zip_paths
        ]

        return {
            "success": True,
            "spreadsheet_name": os.path.basename(self.spreadsheet_path),
            "spreadsheet_type": self.spreadsheet_type,
            "total_rows": len(rows) - 1,
            "valid_count": len(valid_products),
            "duplicate_count": len(duplicate_products),
            "error_count": len(invalid_rows),
            "valid_products": valid_products,
            "duplicate_products": duplicate_products,
            "invalid_rows": invalid_rows,
            "unmatched_images": unmatched_images,
        }

    def execute_import(self, selected_category=None, default_stock=None) -> dict:
        """
        Extracts images to static/media storage and atomically creates Product records.
        """
        analysis = self.parse_and_validate()
        valid_items = analysis["valid_products"]

        if not valid_items:
            raise ValueError("No valid products available to import. Please correct errors and retry.")

        # Target directory for product static images
        app_static_dir = os.path.join(
            settings.BASE_DIR, "Homepage", "static", "home", "images", "products"
        )
        os.makedirs(app_static_dir, exist_ok=True)

        # Also write to STATIC_ROOT if collectstatic was previously run
        staticfiles_dir = os.path.join(
            getattr(settings, "STATIC_ROOT", "") or "", "home", "images", "products"
        )
        if getattr(settings, "STATIC_ROOT", None):
            try:
                os.makedirs(staticfiles_dir, exist_ok=True)
            except Exception:
                pass

        media_products_dir = os.path.join(settings.MEDIA_ROOT, "products")
        os.makedirs(media_products_dir, exist_ok=True)

        imported_products = []

        with transaction.atomic():
            for item in valid_items:
                clean_img_base = os.path.basename(item["image_filename"]).strip()
                dest_path = os.path.join(app_static_dir, clean_img_base)

                # Extract image content safely
                if item["matched_zip_path"]:
                    img_data = self.zf.read(item["matched_zip_path"])
                    with open(dest_path, "wb") as f:
                        f.write(img_data)

                    # Also copy to staticfiles if exists
                    if os.path.isdir(staticfiles_dir):
                        try:
                            with open(os.path.join(staticfiles_dir, clean_img_base), "wb") as f2:
                                f2.write(img_data)
                        except Exception:
                            pass

                    # Also copy to media/products
                    try:
                        with open(os.path.join(media_products_dir, clean_img_base), "wb") as f3:
                            f3.write(img_data)
                    except Exception:
                        pass

                cat = selected_category or item["category"] or self.default_category
                stock_val = default_stock if default_stock is not None else item["stock"]

                product = Product(
                    product_number=item["product_number"],
                    name=item["name"],
                    description=item["description"],
                    category=cat,
                    subcategory=item["subcategory"],
                    brand=item["brand"],
                    price=item["price_decimal"],
                    stock=stock_val,
                    image_url=f"/static/home/images/products/{clean_img_base}",
                    is_active=True,
                )
                product.full_clean()
                product.save()
                imported_products.append(product)

        return {
            "imported_count": len(imported_products),
            "skipped_duplicates": analysis["duplicate_count"],
            "skipped_invalid": analysis["error_count"],
            "imported_ids": [p.id for p in imported_products],
        }
