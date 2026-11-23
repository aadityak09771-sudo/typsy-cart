import io
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from products.services.zip_importer import ZipProductImporter

def test_xlsx_in_zip():
    xlsx_buf = io.BytesIO()
    with zipfile.ZipFile(xlsx_buf, "w") as xz:
        shared_strings = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="7" uniqueCount="7">\n'
            '<si><t>Product Number</t></si>\n'
            '<si><t>Product Name</t></si>\n'
            '<si><t>Image Filename</t></si>\n'
            '<si><t>Price (INR)</t></si>\n'
            '<si><t>TC-7001</t></si>\n'
            '<si><t>Excel Almond Milk</t></si>\n'
            '<si><t>almond.jpg</t></si>\n'
            '</sst>'
        )
        sheet1 = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">\n'
            '<sheetData>\n'
            '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c><c r="D1" t="s"><v>3</v></c></row>\n'
            '<row r="2"><c r="A2" t="s"><v>4</v></c><c r="B2" t="s"><v>5</v></c><c r="C2" t="s"><v>6</v></c><c r="D2"><v>140.00</v></c></row>\n'
            '</sheetData>\n'
            '</worksheet>'
        )
        xz.writestr("xl/sharedStrings.xml", shared_strings)
        xz.writestr("xl/worksheets/sheet1.xml", sheet1)

    xlsx_bytes = xlsx_buf.getvalue()

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("Products.xlsx", xlsx_bytes)
        zf.writestr("product_images/almond.jpg", b"\xff\xd8\xff\xe0\x00\x10JFIFdummyjpg")

    zip_buf.seek(0)
    importer = ZipProductImporter(zip_buf)
    res = importer.parse_and_validate()
    print("XLSX import parse success!")
    print("Spreadsheet detected:", res["spreadsheet_name"])
    print("Valid count:", res["valid_count"])
    print("Error count:", res["error_count"])
    print("Item name:", res["valid_products"][0]["name"])
    print("Price:", res["valid_products"][0]["price"])
    print("Image:", res["valid_products"][0]["image_filename"])
    assert res["valid_count"] == 1
    assert res["valid_products"][0]["name"] == "Excel Almond Milk"
    assert res["valid_products"][0]["price"] == "140.00"
    print("ALL XLSX TESTS PASSED!")

    print("Testing atomic execution...")
    from products.models import Product
    # Clean up prior test if any
    Product.objects.filter(product_number="TC-7001").delete()

    zip_buf.seek(0)
    exec_importer = ZipProductImporter(zip_buf, default_category="Groceries", default_stock=25)
    import_res = exec_importer.execute_import()
    print("Import execution result:", import_res)
    assert import_res["imported_count"] == 1
    p = Product.objects.get(product_number="TC-7001")
    assert p.name == "Excel Almond Milk"
    assert p.price == 140
    assert p.category == "Groceries"
    assert p.stock == 25
    assert p.image_url == "/static/home/images/products/almond.jpg"
    print("Product created and verified successfully in database!")
    # Clean up
    p.delete()
    print("Cleaned up test product.")

if __name__ == "__main__":
    test_xlsx_in_zip()
