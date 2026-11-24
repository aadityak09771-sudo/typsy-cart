/**
 * TipsyCart Admin Dynamic Enhancements
 * - Instant Live Image Preview (File upload or direct URL)
 * - Dynamic Category -> Subcategory Filtering
 * - Live Price & Discount Preview & Auto-Calculation
 * - Step-by-Step Simplified Admin Organization
 * - Conditional Simple vs Variable Product Interface
 * - Global Colour Library Auto-Fill & Swatch Preview
 * - Real-Time Customer Product Card Live Preview in Step 8
 */

document.addEventListener("DOMContentLoaded", function () {
  function escapeHtml(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  // -------------------------------------------------------------
  // 1. LIVE IMAGE PREVIEW (Categories, Subcategories, Products, Banners)
  // -------------------------------------------------------------
  const fileInput = document.querySelector("#id_image");
  const urlInput = document.querySelector("#id_image_url");
  const clearCheckbox = document.querySelector("#image-clear_id");

  if (fileInput || urlInput) {
    const targetAnchor = (urlInput ? urlInput.closest(".form-row, .field-image_url, fieldset") : null) ||
                         (fileInput ? fileInput.closest(".form-row, .field-image, fieldset") : null);

    const previewBox = document.createElement("div");
    previewBox.className = "tc-live-image-preview-box";
    previewBox.innerHTML = `
      <span class="tc-preview-tag">🖼️ Live Image Preview</span>
      <div class="tc-preview-frame">
        <img id="tc-live-preview-img" style="display: none;" alt="Live Preview" />
        <p id="tc-preview-status" class="tc-preview-status" style="color: #6b7280;">No image chosen or URL entered.</p>
      </div>
    `;

    if (targetAnchor && targetAnchor.parentNode) {
      targetAnchor.parentNode.insertBefore(previewBox, targetAnchor.nextSibling);
    }

    const previewImg = document.getElementById("tc-live-preview-img");
    const previewStatus = document.getElementById("tc-preview-status");

    let currentMode = "none";

    function getSavedUploadedUrl() {
      const container = document.querySelector(".tc-current-image-container");
      if (container && container.dataset.currentUrl) {
        return container.dataset.currentUrl;
      }
      const fileUploadLink = document.querySelector(".file-upload a");
      if (fileUploadLink) {
        return fileUploadLink.getAttribute("href");
      }
      return "";
    }

    function renderLivePreview() {
      const clearChecked = clearCheckbox ? clearCheckbox.checked : false;
      const savedUrl = getSavedUploadedUrl();
      const rawUrl = urlInput ? urlInput.value.trim() : "";
      const isLocalMedia = rawUrl.startsWith("/media/") || rawUrl.startsWith("media/");

      // 1. Newly selected local file
      if (fileInput && fileInput.files && fileInput.files.length > 0) {
        currentMode = "file";
        const file = fileInput.files[0];
        const reader = new FileReader();
        reader.onload = function (e) {
          previewImg.src = e.target.result;
          previewImg.style.display = "block";
          previewStatus.innerHTML = `<span style="color: #16a34a; font-weight: 700;">✓ Local File Chosen:</span> ${escapeHtml(file.name)} (${(file.size / 1024).toFixed(1)} KB)`;
          updateCardPreview();
        };
        reader.readAsDataURL(file);
        return;
      }

      // 2. External URL
      if (rawUrl && (!savedUrl || !isLocalMedia || clearChecked)) {
        currentMode = "url";
        previewImg.src = rawUrl;
        previewImg.style.display = "block";
        previewStatus.innerHTML = `<span style="color: #4b5563;">Loading external image link...</span>`;
        updateCardPreview();
        return;
      }

      // 3. Saved uploaded file
      if (savedUrl && !clearChecked) {
        currentMode = "saved";
        previewImg.src = savedUrl;
        previewImg.style.display = "block";
        const filename = savedUrl.split("/").pop();
        previewStatus.innerHTML = `<span style="color: #0284c7; font-weight: 700;">✓ Current Saved Image:</span> ${escapeHtml(decodeURIComponent(filename))}`;
        updateCardPreview();
        return;
      }

      // 4. Marked for clearing
      if (clearChecked) {
        currentMode = "none";
        previewImg.style.display = "none";
        previewStatus.innerHTML = `<span style="color: #d97706; font-weight: 600;">Image marked for removal on Save.</span>`;
        updateCardPreview();
        return;
      }

      // 5. No image
      currentMode = "none";
      previewImg.style.display = "none";
      previewStatus.innerHTML = `<span style="color: #6b7280;">No image chosen or URL entered.</span>`;
      updateCardPreview();
    }

    if (previewImg) {
      previewImg.onload = function () {
        if (currentMode === "url") {
          previewStatus.innerHTML = `<span style="color: #16a34a; font-weight: 700;">✓ External image loaded successfully</span>`;
        }
        updateCardPreview();
      };

      previewImg.onerror = function () {
        if (currentMode === "url") {
          previewStatus.innerHTML = `<span style="color: #dc2626; font-weight: 700;">⚠️ Could not load image from this URL.</span>`;
        }
      };
    }

    if (fileInput) fileInput.addEventListener("change", renderLivePreview);
    if (urlInput) urlInput.addEventListener("input", renderLivePreview);
    if (clearCheckbox) clearCheckbox.addEventListener("change", renderLivePreview);

    renderLivePreview();
  }

  // -------------------------------------------------------------
  // 2. DYNAMIC SUBCATEGORY FILTERING (Product Form)
  // -------------------------------------------------------------
  const catSelect = document.querySelector("#id_category_ref");
  const subcatSelect = document.querySelector("#id_subcategory_ref");

  if (catSelect && subcatSelect) {
    function filterSubcategories(catId, preserveCurrent) {
      if (!catId) {
        subcatSelect.innerHTML = '<option value="">---------</option>';
        return;
      }

      const currentVal = preserveCurrent ? subcatSelect.value : "";

      fetch(`/admin/products/api/subcategories/?category_id=${catId}`)
        .then(function (res) { return res.json(); })
        .then(function (data) {
          let html = '<option value="">---------</option>';
          const subcats = data.subcategories || [];
          let hasMatch = false;

          subcats.forEach(function (sub) {
            const isSelected = String(sub.id) === String(currentVal) ? "selected" : "";
            if (isSelected) hasMatch = true;
            html += `<option value="${sub.id}" ${isSelected}>${sub.name}</option>`;
          });

          subcatSelect.innerHTML = html;
          if (!hasMatch && !preserveCurrent) {
            subcatSelect.value = "";
          }
        })
        .catch(function (err) {
          console.error("Failed to fetch subcategories:", err);
        });
    }

    catSelect.addEventListener("change", function () {
      filterSubcategories(this.value, false);
      updateCardPreview();
    });

    if (catSelect.value) {
      filterSubcategories(catSelect.value, true);
    }
  }

  // -------------------------------------------------------------
  // 3. LIVE PRICING & DISCOUNT PREVIEW (Product Form)
  // -------------------------------------------------------------
  const origPriceInput = document.querySelector("#id_original_price");
  const discountEnabledCheck = document.querySelector("#id_discount_enabled");
  const discountTypeSelect = document.querySelector("#id_discount_type");
  const discountValInput = document.querySelector("#id_discount_value");
  const sellingPriceInput = document.querySelector("#id_price");

  function calculateLivePrice() {
    if (!origPriceInput || !sellingPriceInput) return;
    const orig = parseFloat(origPriceInput.value) || 0;
    const isDiscount = discountEnabledCheck ? discountEnabledCheck.checked : false;
    const dType = discountTypeSelect ? discountTypeSelect.value : "percentage";
    const dVal = discountValInput ? parseFloat(discountValInput.value) || 0 : 0;
    const badgeContainer = document.getElementById("tc-pricing-preview-badge");

    if (orig <= 0) {
      if (badgeContainer) badgeContainer.innerHTML = '<span style="color: #6b7280; font-size: 12px;">Enter Original MRP first.</span>';
      updateCardPreview();
      return;
    }

    if (!isDiscount || dVal <= 0) {
      sellingPriceInput.value = orig.toFixed(2);
      if (badgeContainer) {
        badgeContainer.innerHTML = `<span style="color: #1e293b; background: #f3f4f6; padding: 4px 10px; border-radius: 6px;">Regular Price: ₹${orig.toFixed(2)} (No Discount)</span>`;
      }
    } else {
      let finalPrice = orig;
      let savings = 0;
      let discountPct = 0;

      if (dType === "percentage") {
        const pct = Math.min(99, Math.max(0, dVal));
        savings = orig * (pct / 100);
        finalPrice = Math.max(1, orig - savings);
        discountPct = Math.round(pct);
      } else {
        savings = Math.min(orig - 1, Math.max(0, dVal));
        finalPrice = Math.max(1, orig - savings);
        discountPct = Math.round((savings / orig) * 100);
      }

      sellingPriceInput.value = finalPrice.toFixed(2);
      if (badgeContainer) {
        badgeContainer.innerHTML = `
          <span style="color: #15803d; background: #dcfce7; padding: 4px 10px; border-radius: 6px;">
            ✨ Final Price: ₹${finalPrice.toFixed(2)}
          </span>
          <del style="color: #94a3b8; margin-left: 6px;">₹${orig.toFixed(2)}</del>
          <span style="color: #b91c1c; background: #fee2e2; padding: 2px 7px; border-radius: 4px; margin-left: 6px; font-size: 11px;">
            ${discountPct}% OFF (Save ₹${savings.toFixed(2)})
          </span>
        `;
      }
    }
    updateCardPreview();
  }

  if (origPriceInput && sellingPriceInput) {
    const priceRow = sellingPriceInput.closest(".form-row, .field-price") || sellingPriceInput.parentElement;
    if (priceRow && !document.getElementById("tc-pricing-preview-badge")) {
      const badgeContainer = document.createElement("div");
      badgeContainer.className = "tc-badge-preview";
      badgeContainer.id = "tc-pricing-preview-badge";
      priceRow.appendChild(badgeContainer);
    }

    [origPriceInput, discountValInput].forEach(function (el) {
      if (el) el.addEventListener("input", calculateLivePrice);
    });

    [discountEnabledCheck, discountTypeSelect].forEach(function (el) {
      if (el) el.addEventListener("change", calculateLivePrice);
    });

    calculateLivePrice();
  }

  // -------------------------------------------------------------
  // 4. CONDITIONAL SIMPLE VS VARIABLE PRODUCT INTERFACE
  // -------------------------------------------------------------
  const productTypeSelect = document.querySelector("#id_product_type");
  const coloursGroup = document.querySelector("#colours-group");
  const sizesGroup = document.querySelector("#sizes-group");
  const variantsGroup = document.querySelector("#variants-group");

  if (productTypeSelect) {
    const step3Fieldset = productTypeSelect.closest("fieldset");
    let noticeBanner = document.getElementById("tc-product-mode-banner");

    if (!noticeBanner && step3Fieldset) {
      noticeBanner = document.createElement("div");
      noticeBanner.id = "tc-product-mode-banner";
      noticeBanner.className = "tc-admin-notice-banner";
      step3Fieldset.appendChild(noticeBanner);
    }

    function updateProductTypeUI() {
      const mode = productTypeSelect.value;
      if (mode === "simple") {
        if (coloursGroup) coloursGroup.style.display = "none";
        if (sizesGroup) sizesGroup.style.display = "none";
        if (variantsGroup) variantsGroup.style.display = "none";

        if (noticeBanner) {
          noticeBanner.className = "tc-admin-notice-banner";
          noticeBanner.innerHTML = `
            <span>💡</span>
            <div>
              <strong>Simple Product Mode Active:</strong> This product is sold as a standard item with a single price & stock.
              You only need to complete Pricing in Step 4. Variant tables (Colours, Sizes, and Product Variants) are cleanly hidden.
            </div>
          `;
        }
      } else {
        if (coloursGroup) coloursGroup.style.display = "";
        if (sizesGroup) sizesGroup.style.display = "";
        if (variantsGroup) variantsGroup.style.display = "";

        if (noticeBanner) {
          noticeBanner.className = "tc-admin-notice-banner tc-variable-banner";
          noticeBanner.innerHTML = `
            <span>⚡</span>
            <div>
              <strong>Variable Product Mode Active:</strong> This product has multiple options (e.g. Weights, Volumes, Colours, or Sizes).
              Configure options in Steps 6 & 7. Each variant will have its own independent price, discount, SKU, and stock.
            </div>
          `;
        }
      }
    }

    productTypeSelect.addEventListener("change", updateProductTypeUI);
    updateProductTypeUI();
  }

  // -------------------------------------------------------------
  // 5. GLOBAL COLOUR MASTER LIBRARY AUTO-FILL & SWATCH PREVIEW
  // -------------------------------------------------------------
  document.addEventListener("change", function (e) {
    if (e.target && e.target.matches("select[name$='-color_master']")) {
      const row = e.target.closest("tr, .form-row");
      if (!row) return;

      const selectedOption = e.target.options[e.target.selectedIndex];
      if (!selectedOption || !selectedOption.value) return;

      const optText = selectedOption.textContent.trim();
      // Match pattern like "Sky Blue (#87CEEB)" or "Red (#FF0000)"
      const match = optText.match(/(.+?)\s*\((#[0-9A-Fa-f]{3,6})\)/);

      const nameInput = row.querySelector("input[name$='-name']");
      const hexInput = row.querySelector("input[name$='-color_code']");
      const swatchCircle = row.querySelector(".tc-colour-swatch-circle");

      if (match) {
        const cName = match[1].trim();
        const cHex = match[2].trim().toUpperCase();

        if (nameInput && (!nameInput.value || nameInput.value.trim() === "")) {
          nameInput.value = cName;
        }
        if (hexInput) {
          hexInput.value = cHex;
        }
        if (swatchCircle) {
          swatchCircle.style.backgroundColor = cHex;
        }
      }
    }
  });

  // Also update swatch circle when manual HEX input changes
  document.addEventListener("input", function (e) {
    if (e.target && e.target.matches("input[name$='-color_code']")) {
      const row = e.target.closest("tr, .form-row");
      if (!row) return;
      const swatchCircle = row.querySelector(".tc-colour-swatch-circle");
      if (swatchCircle) {
        const val = e.target.value.trim();
        if (val.startsWith("#") && (val.length === 4 || val.length === 7)) {
          swatchCircle.style.backgroundColor = val;
        }
      }
    }
  });

  // -------------------------------------------------------------
  // 6. REAL-TIME CUSTOMER PRODUCT CARD LIVE PREVIEW IN STEP 8
  // -------------------------------------------------------------
  const nameInput = document.querySelector("#id_name");
  const brandInput = document.querySelector("#id_brand");
  const unitTypeSelect = document.querySelector("#id_unit_type");
  const unitInput = document.querySelector("#id_unit");
  const unitValInput = document.querySelector("#id_unit_value");
  const isAvailableCheck = document.querySelector("#id_is_available");
  const stockInput = document.querySelector("#id_stock");

  function updateCardPreview() {
    const cardImg = document.getElementById("tc-card-preview-img");
    const cardName = document.getElementById("tc-card-preview-name");
    const cardBrand = document.getElementById("tc-card-preview-brand");
    const cardPrice = document.getElementById("tc-card-preview-price");
    const cardMrp = document.getElementById("tc-card-preview-mrp");
    const cardDisc = document.getElementById("tc-card-preview-discount");
    const cardUnit = document.getElementById("tc-card-preview-unit");
    const cardStock = document.getElementById("tc-card-preview-stock");

    if (!cardName) return;

    // Image
    const liveImg = document.getElementById("tc-live-preview-img");
    if (liveImg && liveImg.style.display !== "none" && liveImg.src) {
      cardImg.src = liveImg.src;
    }

    // Name & Brand
    const pName = nameInput && nameInput.value.trim() ? nameInput.value.trim() : "Product Name";
    const pBrand = brandInput && brandInput.value.trim() ? brandInput.value.trim() : "TipsyCart";
    cardName.textContent = pName;
    cardBrand.textContent = pBrand;

    // Prices & Discount
    const sellPrice = sellingPriceInput && parseFloat(sellingPriceInput.value) > 0 ? parseFloat(sellingPriceInput.value) : 0;
    const mrp = origPriceInput && parseFloat(origPriceInput.value) > 0 ? parseFloat(origPriceInput.value) : 0;

    cardPrice.textContent = `₹${sellPrice.toFixed(2)}`;

    if (mrp > sellPrice && sellPrice > 0) {
      cardMrp.textContent = `₹${mrp.toFixed(2)}`;
      cardMrp.style.display = "inline";
      const discPct = Math.round(((mrp - sellPrice) / mrp) * 100);
      cardDisc.textContent = `${discPct}% OFF`;
      cardDisc.style.display = "inline-block";
    } else {
      cardMrp.style.display = "none";
      cardDisc.style.display = "none";
    }

    // Unit
    const uVal = unitValInput ? unitValInput.value.trim() : "";
    const uUnit = unitInput ? unitInput.value.trim() : "";
    let unitLabel = "";
    if (uVal && uUnit) {
      unitLabel = `${uVal} ${uUnit}`;
    } else if (uUnit) {
      unitLabel = uUnit;
    }
    if (unitLabel) {
      cardUnit.textContent = unitLabel;
      cardUnit.style.display = "inline-block";
    } else {
      cardUnit.style.display = "none";
    }

    // Stock
    const isAvail = isAvailableCheck ? isAvailableCheck.checked : true;
    const stVal = stockInput ? parseInt(stockInput.value) : 10;
    if (!isAvail || stVal <= 0) {
      cardStock.textContent = "Out of Stock";
      cardStock.style.background = "#fee2e2";
      cardStock.style.color = "#b91c1c";
    } else if (stVal <= 5) {
      cardStock.textContent = `Only ${stVal} left`;
      cardStock.style.background = "#fef3c7";
      cardStock.style.color = "#92400e";
    } else {
      cardStock.textContent = "In Stock";
      cardStock.style.background = "#dcfce7";
      cardStock.style.color = "#15803d";
    }
  }

  [nameInput, brandInput, unitInput, unitValInput, stockInput].forEach(function (el) {
    if (el) el.addEventListener("input", updateCardPreview);
  });

  [unitTypeSelect, isAvailableCheck].forEach(function (el) {
    if (el) el.addEventListener("change", updateCardPreview);
  });

  updateCardPreview();
});
