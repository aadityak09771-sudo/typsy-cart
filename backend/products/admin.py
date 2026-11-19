
import csv
import io
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import path

from .models import Product


MAX_CSV_SIZE = 10 * 1024 * 1024


GROCERY_SUBCATEGORIES = [
    ("Fruits & Vegetables", "Fruits & Vegetables"),
    ("Atta, Rice & Pulses", "Atta, Rice & Pulses"),
    ("Dairy & Bakery", "Dairy & Bakery"),
    ("Snacks & Beverages", "Snacks & Beverages"),
    ("Household Essentials", "Household Essentials"),
]


class ProductAdminForm(forms.ModelForm):

    subcategory = forms.ChoiceField(
        choices=[("", "Select Subcategory")],
        required=False,
    )

    class Meta:
        model = Product
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        existing_subcategories = list(
            Product.objects.exclude(
                subcategory=""
            ).values_list(
                "subcategory",
                flat=True,
            ).distinct()
        )

        if self.instance and self.instance.pk:
            current_subcategory = self.instance.subcategory

            if (
                current_subcategory
                and current_subcategory not in existing_subcategories
            ):
                existing_subcategories.append(current_subcategory)

        choices = [("", "Select Subcategory")]

        added = set()

        for value, label in GROCERY_SUBCATEGORIES:
            choices.append((value, label))
            added.add(value)

        for value in sorted(existing_subcategories, key=str.casefold):
            if value not in added:
                choices.append((value, value))

        self.fields["subcategory"].choices = choices


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):

    form = ProductAdminForm

    list_display = (
        "id",
        "name",
        "category",
        "price",
        "stock",
        "is_active",
        "created_at",
    )

    list_filter = (
        "category",
        "is_active",
        "created_at",
    )

    search_fields = (
        "name",
        "description",
        "brand",
        "subcategory",
    )

    list_editable = (
        "price",
        "stock",
        "is_active",
    )

    list_display_links = ("id", "name")
    ordering = ("-created_at",)
    list_per_page = 25
    date_hierarchy = "created_at"

    change_list_template = (
        "admin/products/product/change_list.html"
    )

    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [
            path(
                "import-csv/",
                self.admin_site.admin_view(self.import_csv),
                name="products_product_import",
            ),
        ]

        return custom_urls + urls

    def validate_csv(self, uploaded_file):
        if uploaded_file.size > MAX_CSV_SIZE:
            raise ValueError(
                "CSV file must be smaller than 10 MB."
            )

        if not uploaded_file.name.lower().endswith(".csv"):
            raise ValueError("Only CSV files are allowed.")

        content = uploaded_file.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))

        required_columns = {
            "name",
            "description",
            "category",
            "subcategory",
            "brand",
            "price",
            "stock",
            "image_url",
            "is_active",
        }

        if not reader.fieldnames:
            raise ValueError("CSV file is empty.")

        reader.fieldnames = [
            (field or "").strip().lower()
            for field in reader.fieldnames
        ]

        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(
                "CSV contains duplicate column names."
            )

        missing = required_columns - set(reader.fieldnames)

        if missing:
            raise ValueError(
                "Missing columns: " + ", ".join(sorted(missing))
            )

        valid_categories = {
            choice[0] for choice in Product.CATEGORY_CHOICES
        }

        valid_rows = []
        errors = []
        duplicate_count = 0
        seen_in_file = set()

        for row_number, row in enumerate(reader, start=2):
            try:
                if None in row:
                    raise ValueError(
                        "Unexpected extra CSV columns."
                    )

                name = (row.get("name") or "").strip()
                description = (
                    row.get("description") or ""
                ).strip()
                category = (
                    row.get("category") or ""
                ).strip()
                subcategory = (
                    row.get("subcategory") or ""
                ).strip()
                brand = (row.get("brand") or "").strip()
                image_url = (
                    row.get("image_url") or ""
                ).strip()

                if not name:
                    raise ValueError(
                        "Product name is required."
                    )

                if category not in valid_categories:
                    raise ValueError(
                        f"Invalid category: {category}"
                    )

                price = Decimal(
                    (row.get("price") or "").strip()
                )

                if not price.is_finite() or price < 0:
                    raise ValueError(
                        "Price must be non-negative."
                    )

                stock = int(
                    (row.get("stock") or "0").strip()
                )

                if stock < 0:
                    raise ValueError(
                        "Stock cannot be negative."
                    )

                active_text = (
                    (row.get("is_active") or "true")
                    .strip()
                    .lower()
                )

                if active_text in ("true", "1", "yes"):
                    is_active = True
                elif active_text in ("false", "0", "no"):
                    is_active = False
                else:
                    raise ValueError(
                        "is_active must be true or false."
                    )

                if image_url:
                    URLValidator()(image_url)

                duplicate_key = (
                    name.casefold(),
                    brand.casefold(),
                    category,
                )

                if duplicate_key in seen_in_file:
                    duplicate_count += 1
                    continue

                seen_in_file.add(duplicate_key)

                if Product.objects.filter(
                    name__iexact=name,
                    brand__iexact=brand,
                    category=category,
                ).exists():
                    duplicate_count += 1
                    continue

                product = Product(
                    name=name,
                    description=description,
                    category=category,
                    subcategory=subcategory,
                    brand=brand,
                    price=price,
                    stock=stock,
                    image_url=image_url,
                    is_active=is_active,
                )

                product.full_clean()

                valid_rows.append({
                    "name": name,
                    "description": description,
                    "category": category,
                    "subcategory": subcategory,
                    "brand": brand,
                    "price": price,
                    "stock": stock,
                    "image_url": image_url,
                    "is_active": is_active,
                })

            except (
                ValueError,
                InvalidOperation,
                ValidationError,
                TypeError,
            ) as error:
                errors.append(
                    f"Row {row_number}: {error}"
                )

        return valid_rows, duplicate_count, errors

    def import_csv(self, request):
        if request.method == "POST":
            uploaded_file = request.FILES.get("csv_file")
            action = request.POST.get("action")

            if not uploaded_file:
                self.message_user(
                    request,
                    "Please select the CSV file again.",
                    level=messages.ERROR,
                )
                return redirect("..")

            if action not in ("preview", "confirm"):
                self.message_user(
                    request,
                    "Invalid import action.",
                    level=messages.ERROR,
                )
                return redirect("..")

            try:
                valid_rows, duplicate_count, errors = (
                    self.validate_csv(uploaded_file)
                )

            except (
                UnicodeDecodeError,
                csv.Error,
                ValueError,
            ) as error:
                context = {
                    **self.admin_site.each_context(request),
                    "title": "Import Products from CSV",
                    "opts": self.model._meta,
                    "fatal_error": str(error),
                }

                return render(
                    request,
                    "admin/product_import.html",
                    context,
                )

            if action == "preview":
                context = {
                    **self.admin_site.each_context(request),
                    "title": "Import Products from CSV",
                    "opts": self.model._meta,
                    "preview": True,
                    "valid_count": len(valid_rows),
                    "duplicate_count": duplicate_count,
                    "error_count": len(errors),
                    "errors": errors[:50],
                }

                return render(
                    request,
                    "admin/product_import.html",
                    context,
                )

            if errors:
                self.message_user(
                    request,
                    "Import stopped because the CSV has invalid rows. "
                    "Please correct them and preview again.",
                    level=messages.ERROR,
                )
                return redirect("..")

            imported = 0

            try:
                with transaction.atomic():
                    for row in valid_rows:
                        duplicate = Product.objects.filter(
                            name__iexact=row["name"],
                            brand__iexact=row["brand"],
                            category=row["category"],
                        ).exists()

                        if duplicate:
                            duplicate_count += 1
                            continue

                        product = Product(**row)
                        product.full_clean()
                        product.save()
                        imported += 1

            except Exception:
                raise

            self.message_user(
                request,
                f"{imported} products imported successfully. "
                f"{duplicate_count} duplicates skipped.",
                level=messages.SUCCESS,
            )

            return redirect("..")

        context = {
            **self.admin_site.each_context(request),
            "title": "Import Products from CSV",
            "opts": self.model._meta,
        }

        return render(
            request,
            "admin/product_import.html",
            context,
        )
