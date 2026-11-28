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

    function updateFileAttachmentBanner(fileOrUrl, isNew) {
      if (!fileInput) return;
      const fileRow = fileInput.closest(".form-row.field-image, .field-image") || fileInput.parentElement;
      if (!fileRow) return;

      let banner = document.getElementById("tc-file-attachment-banner");
      if (!banner) {
        banner = document.createElement("div");
        banner.id = "tc-file-attachment-banner";
        fileRow.insertBefore(banner, fileRow.firstChild);
      }

      if (isNew && fileOrUrl) {
        banner.style.display = "block";
        banner.className = "tc-file-attachment-banner tc-file-new-selected";
        banner.innerHTML = `
          <div class="tc-file-attachment-header">
            <span class="tc-status-dot-blue"></span>
            <strong>New Replacement File Selected:</strong>
            <code class="tc-attached-filename">${escapeHtml(fileOrUrl.name)} (${(fileOrUrl.size / 1024).toFixed(1)} KB)</code>
          </div>
          <div class="tc-file-attachment-note">
            ✨ This new image will replace the previous photo when you click <em>Save</em>.
          </div>
        `;
      } else if (fileOrUrl) {
        banner.style.display = "block";
        banner.className = "tc-file-attachment-banner";
        const fname = String(fileOrUrl).split("/").pop();
        banner.innerHTML = `
          <div class="tc-file-attachment-header">
            <span class="tc-status-dot-green"></span>
            <strong>File Currently Attached &amp; Saved on Server:</strong>
            <code class="tc-attached-filename">${escapeHtml(decodeURIComponent(fname))}</code>
          </div>
          <div class="tc-file-attachment-note">
            🛡️ <strong>No re-upload needed!</strong> Your existing image is active and safely stored. It will remain attached when you click <em>Save</em>.
          </div>
          <div class="tc-file-replace-hint">
            🔄 <em>To replace with a new image, select a new file below:</em>
          </div>
        `;
      } else {
        banner.style.display = "none";
      }
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
        updateFileAttachmentBanner(file, true);
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
        updateFileAttachmentBanner(null, false);
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
        updateFileAttachmentBanner(savedUrl, false);
        updateCardPreview();
        return;
      }

      // 4. Marked for clearing
      if (clearChecked) {
        currentMode = "none";
        previewImg.style.display = "none";
        previewStatus.innerHTML = `<span style="color: #d97706; font-weight: 600;">Image marked for removal on Save.</span>`;
        updateFileAttachmentBanner(null, false);
        updateCardPreview();
        return;
      }

      // 5. No image
      currentMode = "none";
      previewImg.style.display = "none";
      previewStatus.innerHTML = `<span style="color: #6b7280;">No image chosen or URL entered.</span>`;
      updateFileAttachmentBanner(null, false);
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
  // 3. LIVE PRICING & TWO-WAY SMART DISCOUNT PREVIEW (Product Form)
  // -------------------------------------------------------------
  const origPriceInput = document.querySelector("#id_original_price");
  const discountEnabledCheck = document.querySelector("#id_discount_enabled");
  const discountTypeSelect = document.querySelector("#id_discount_type");
  const discountValInput = document.querySelector("#id_discount_value");
  const sellingPriceInput = document.querySelector("#id_price");

  let isUpdatingPrice = false;

  function updatePricingBadge(orig, finalPrice, savings, discountPct) {
    const badgeContainer = document.getElementById("tc-pricing-preview-badge");
    if (!badgeContainer) return;

    if (orig <= 0) {
      badgeContainer.innerHTML = '<span style="color: #6b7280; font-size: 12px;">Enter Original MRP first.</span>';
      return;
    }

    if (savings > 0 && discountPct > 0) {
      badgeContainer.innerHTML = `
        <span style="color: #15803d; background: #dcfce7; padding: 4px 10px; border-radius: 6px; font-weight: 700;">
          ✨ Final Selling Price: ₹${finalPrice.toFixed(2)}
        </span>
        <del style="color: #94a3b8; margin-left: 6px;">₹${orig.toFixed(2)}</del>
        <span style="color: #b91c1c; background: #fee2e2; padding: 2px 7px; border-radius: 4px; margin-left: 6px; font-size: 11px; font-weight: 800;">
          ${discountPct}% OFF (Save ₹${savings.toFixed(2)})
        </span>
      `;
    } else {
      badgeContainer.innerHTML = `<span style="color: #1e293b; background: #f3f4f6; padding: 4px 10px; border-radius: 6px;">Regular Price: ₹${finalPrice.toFixed(2)} (No Discount)</span>`;
    }
  }

  // Called when user edits Selling Price manually: auto-calculates Discount %
  function onSellingPriceManualInput() {
    if (isUpdatingPrice || !origPriceInput || !sellingPriceInput) return;
    isUpdatingPrice = true;
    try {
      const orig = parseFloat(origPriceInput.value) || 0;
      const sellPrice = parseFloat(sellingPriceInput.value) || 0;

      if (orig > 0 && sellPrice > 0 && orig > sellPrice) {
        const savings = orig - sellPrice;
        const discountPct = Math.round((savings / orig) * 100);
        if (discountEnabledCheck) discountEnabledCheck.checked = true;
        if (discountTypeSelect) discountTypeSelect.value = "percentage";
        if (discountValInput) discountValInput.value = discountPct;
        updatePricingBadge(orig, sellPrice, savings, discountPct);
      } else {
        if (discountEnabledCheck) discountEnabledCheck.checked = false;
        if (discountValInput) discountValInput.value = "0.00";
        updatePricingBadge(orig, sellPrice || orig, 0, 0);
      }
    } finally {
      isUpdatingPrice = false;
      updateCardPreview();
    }
  }

  // Called when user edits Discount % or MRP: auto-calculates Selling Price
  function onDiscountOrMrpInput() {
    if (isUpdatingPrice || !origPriceInput || !sellingPriceInput) return;
    isUpdatingPrice = true;
    try {
      const orig = parseFloat(origPriceInput.value) || 0;
      const isDiscount = discountEnabledCheck ? discountEnabledCheck.checked : false;
      const dType = discountTypeSelect ? discountTypeSelect.value : "percentage";
      const dVal = discountValInput ? parseFloat(discountValInput.value) || 0 : 0;

      if (orig <= 0) {
        updatePricingBadge(0, 0, 0, 0);
        return;
      }

      if (!isDiscount || dVal <= 0) {
        // If discount is not enabled, but sellingPrice is already set and lower than MRP, keep it!
        const currentSell = parseFloat(sellingPriceInput.value) || 0;
        if (currentSell > 0 && currentSell < orig) {
          const savings = orig - currentSell;
          const discountPct = Math.round((savings / orig) * 100);
          if (discountEnabledCheck) discountEnabledCheck.checked = true;
          if (discountValInput) discountValInput.value = discountPct;
          updatePricingBadge(orig, currentSell, savings, discountPct);
        } else {
          sellingPriceInput.value = orig.toFixed(2);
          updatePricingBadge(orig, orig, 0, 0);
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
        updatePricingBadge(orig, finalPrice, savings, discountPct);
      }
    } finally {
      isUpdatingPrice = false;
      updateCardPreview();
    }
  }

  if (origPriceInput && sellingPriceInput) {
    const priceRow = sellingPriceInput.closest(".form-row, .field-price") || sellingPriceInput.parentElement;
    if (priceRow && !document.getElementById("tc-pricing-preview-badge")) {
      const badgeContainer = document.createElement("div");
      badgeContainer.className = "tc-badge-preview";
      badgeContainer.id = "tc-pricing-preview-badge";
      priceRow.appendChild(badgeContainer);
    }

    sellingPriceInput.addEventListener("input", onSellingPriceManualInput);

    [origPriceInput, discountValInput].forEach(function (el) {
      if (el) el.addEventListener("input", onDiscountOrMrpInput);
    });

    [discountEnabledCheck, discountTypeSelect].forEach(function (el) {
      if (el) el.addEventListener("change", onDiscountOrMrpInput);
    });

    onDiscountOrMrpInput();
  }

  // -------------------------------------------------------------
  // 4. CONDITIONAL SIMPLE VS VARIABLE PRODUCT INTERFACE & TEAM GUIDE
  // -------------------------------------------------------------
  const productTypeSelect = document.querySelector("#id_product_type");
  const coloursGroup = document.querySelector("#colours-group");
  const sizesGroup = document.querySelector("#sizes-group");
  const variantsGroup = document.querySelector("#variants-group");

  if (productTypeSelect) {
    const step3Fieldset = productTypeSelect.closest("fieldset");

    // Inject permanent team guide card
    let guideCard = document.getElementById("tc-team-guide-card");
    if (!guideCard && step3Fieldset) {
      guideCard = document.createElement("div");
      guideCard.id = "tc-team-guide-card";
      guideCard.className = "tc-guide-card";
      guideCard.innerHTML = `
        <div class="tc-guide-title">
          <span>📖 Product Types Guide for Store Managers &amp; Team</span>
        </div>
        <div class="tc-guide-grid">
          <div class="tc-guide-box simple">
            <h5>📦 Simple Product (Single Standard Item)</h5>
            <p>Sold as 1 standalone item with <strong>1 fixed price &amp; 1 stock</strong>. No sizes or colours needed.</p>
            <p><strong>Examples:</strong> 1 Bottle of Sauce, 1 Box of Gajak, 1 Mobile Charger.</p>
            <p><strong>Setup:</strong> Select <em>Simple Product</em> above, then set MRP, Price, and Stock in <strong>Section 4</strong>. Sections 6 &amp; 7 are hidden.</p>
          </div>
          <div class="tc-guide-box variable">
            <h5>⚡ Variable Product (Multiple Sizes, Weights or Colours)</h5>
            <p>Sold in <strong>multiple size/weight options</strong> where each option has its own independent price, discount, SKU, and stock.</p>
            <p><strong>Examples:</strong> Basa Fish (250g, 500g, 1 kg), Atta (1 kg, 5 kg, 10 kg), T-Shirt (S, M, L, XL).</p>
            <p><strong>Setup Workflow:</strong></p>
            <ol>
              <li>Select <strong>Variable Product</strong> &amp; click <strong>"Save and continue editing"</strong> below.</li>
              <li>In <strong>Section 6</strong>, add your Sizes/Weights (e.g. <code>250g</code>, <code>500g</code>, <code>1 kg</code>). <em>(⚠️ Enter weights only, not product name!)</em></li>
              <li>In <strong>Section 7</strong>, click <strong>"⚡ Auto-Generate All Variant Combinations"</strong>.</li>
              <li>Enter independent Selling Price, MRP, and Stock for each size in Section 7!</li>
            </ol>
          </div>
        </div>
      `;
      step3Fieldset.appendChild(guideCard);
    }

    let noticeBanner = document.getElementById("tc-product-mode-banner");
    if (!noticeBanner && step3Fieldset) {
      noticeBanner = document.createElement("div");
      noticeBanner.id = "tc-product-mode-banner";
      noticeBanner.className = "tc-admin-notice-banner";
      step3Fieldset.appendChild(noticeBanner);
    }

    function updateProductTypeUI() {
      const mode = productTypeSelect.value;
      const styleRow = document.querySelector(".field-variant_display_style");
      const guideEl = document.getElementById("tc-collapsible-guide");
      const sizePresetsEl = document.getElementById("tc-size-presets-bar");
      const paletteEl = document.getElementById("tc-lipstick-palette-bar");

      if (mode === "simple") {
        if (coloursGroup) coloursGroup.style.display = "none";
        if (sizesGroup) sizesGroup.style.display = "none";
        if (variantsGroup) variantsGroup.style.display = "none";
        if (styleRow) styleRow.style.display = "none";
        if (guideEl) guideEl.style.display = "none";
        if (sizePresetsEl) sizePresetsEl.style.display = "none";
        if (paletteEl) paletteEl.style.display = "none";

        if (noticeBanner) {
          noticeBanner.className = "tc-admin-notice-banner";
          noticeBanner.innerHTML = `
            <span>💡</span>
            <div>
              <strong>Simple Product Mode Active:</strong> Standard single-item product.
              Configure price and stock in <strong>Section 4 (Pricing &amp; Inventory)</strong>. Variant tables (Colours, Sizes, and Product Variants) are cleanly hidden.
            </div>
          `;
        }
      } else {
        if (coloursGroup) coloursGroup.style.display = "";
        if (sizesGroup) sizesGroup.style.display = "";
        if (variantsGroup) variantsGroup.style.display = "";
        if (styleRow) styleRow.style.display = "";
        if (guideEl) guideEl.style.display = "";
        if (sizePresetsEl) sizePresetsEl.style.display = "";
        if (paletteEl) paletteEl.style.display = "";

        if (noticeBanner) {
          noticeBanner.className = "tc-admin-notice-banner tc-variable-banner";
          noticeBanner.innerHTML = `
            <span>⚡</span>
            <div>
              <strong>Variable Product Mode Active:</strong> This product offers multiple options (e.g. Weights, Volumes, Colours, or Sizes).
              Configure options in <strong>Section 6 (Colours &amp; Sizes)</strong> &amp; <strong>Section 7 (Variants)</strong> below. Each variant has its own independent price, discount, SKU, and stock.
            </div>
          `;
        }
      }
    }

    productTypeSelect.addEventListener("change", updateProductTypeUI);
    updateProductTypeUI();
  }

  // -------------------------------------------------------------
  // GALLERY IMAGES INLINE FILE STATUS BADGES
  // -------------------------------------------------------------
  function enhanceGalleryInlineRows() {
    const galleryGroup = document.querySelector("#gallery_images-group");
    if (!galleryGroup) return;

    const rows = galleryGroup.querySelectorAll("tr.form-row, tr[id^='gallery_images-']");
    rows.forEach(function (row) {
      const fileInp = row.querySelector("input[type='file'][name$='-image']");
      if (!fileInp) return;

      const existingLink = row.querySelector(".file-upload a") || row.querySelector("td.field-image a");
      const urlInput = row.querySelector("input[name$='-image_url']");
      const existingUrl = existingLink ? existingLink.getAttribute("href") : (urlInput && urlInput.value ? urlInput.value : "");

      let badge = row.querySelector(".tc-inline-file-badge");
      if (existingUrl && !badge) {
        const fname = existingUrl.split("/").pop();
        badge = document.createElement("div");
        badge.className = "tc-inline-file-badge";
        badge.innerHTML = `<span>✅ File Attached:</span> <code style="font-size: 11px;">${escapeHtml(decodeURIComponent(fname))}</code>`;

        const cell = fileInp.parentElement;
        cell.insertBefore(badge, fileInp);

        const tip = document.createElement("small");
        tip.className = "tc-inline-keep-note";
        tip.textContent = "Preserved automatically. Choose file only to replace.";
        cell.appendChild(tip);
      }

      if (!fileInp.dataset.hasListener) {
        fileInp.dataset.hasListener = "true";
        fileInp.addEventListener("change", function () {
          if (this.files && this.files.length > 0) {
            let rowBadge = row.querySelector(".tc-inline-file-badge");
            if (!rowBadge) {
              rowBadge = document.createElement("div");
              rowBadge.className = "tc-inline-file-badge new";
              this.parentElement.insertBefore(rowBadge, this);
            } else {
              rowBadge.className = "tc-inline-file-badge new";
            }
            rowBadge.innerHTML = `<span>🔵 New file selected:</span> <code style="font-size: 11px;">${escapeHtml(this.files[0].name)}</code>`;
          }
        });
      }
    });
  }

  enhanceGalleryInlineRows();

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

        if (nameInput) {
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

  // -------------------------------------------------------------
  // 7. INJECT COLLAPSIBLE ADMIN HELP GUIDE & QUICK SIZE PRESETS
  // -------------------------------------------------------------
  function injectCollapsibleGuide() {
    const coloursGroup = document.querySelector("#colours-group");
    if (!coloursGroup || document.getElementById("tc-collapsible-guide")) return;

    const guide = document.createElement("details");
    guide.id = "tc-collapsible-guide";
    guide.className = "tc-collapsible-guide";
    guide.innerHTML = `
      <summary class="tc-guide-summary">
        <div class="tc-guide-summary-left">
          <span class="tc-guide-icon">📖</span>
          <span class="tc-guide-title">How to Add Product Colours, Sizes &amp; Variants?</span>
        </div>
        <span class="tc-guide-toggle-badge">Click to Expand Guide ▾</span>
      </summary>
      <div class="tc-guide-body">
        <div class="tc-guide-steps-grid">
          <div class="tc-guide-step-card">
            <span class="tc-step-badge">Step 1</span>
            <h6>Product Type</h6>
            <p>In <strong>Section 3</strong>, select <strong>Variable Product</strong> and click <em>Save and continue editing</em> below.</p>
          </div>
          <div class="tc-guide-step-card">
            <span class="tc-step-badge">Step 2</span>
            <h6>Display Style</h6>
            <p>Select your customer display preference: <strong>Display by Colour</strong>, <strong>Display by Variant Name</strong>, or <strong>Both</strong>.</p>
          </div>
          <div class="tc-guide-step-card">
            <span class="tc-step-badge">Step 3</span>
            <h6>Add Colours (Optional)</h6>
            <p>In <strong>Section 6 (Colours)</strong>, pick colours from the Global Library or enter custom names and HEX codes.</p>
          </div>
          <div class="tc-guide-step-card">
            <span class="tc-step-badge">Step 4</span>
            <h6>Multiple Photos per Colour</h6>
            <p>Upload front, side, and detail photos for each colour. Choose which photo is <strong>Primary (★)</strong> and set display order.</p>
          </div>
          <div class="tc-guide-step-card">
            <span class="tc-step-badge">Step 5</span>
            <h6>Add Sizes / Weights (Optional)</h6>
            <p>In <strong>Section 6 (Sizes)</strong>, add sizes or use 1-click presets (Clothing, Groceries, Cosmetics). Optional—leave empty if not needed.</p>
          </div>
          <div class="tc-guide-step-card">
            <span class="tc-step-badge">Step 6</span>
            <h6>Generate Variants</h6>
            <p>In <strong>Section 7</strong>, click <strong>"⚡ Auto-Generate All Variant Combinations"</strong> to create all independent selling options.</p>
          </div>
          <div class="tc-guide-step-card">
            <span class="tc-step-badge">Step 7</span>
            <h6>Prices, Stock &amp; Save</h6>
            <p>Set independent Selling Price, MRP, and Stock for each variant in Section 7. Each variant can also have its own image. Click Save!</p>
          </div>
        </div>
      </div>
    `;
    coloursGroup.parentNode.insertBefore(guide, coloursGroup);
  }

  function injectSizePresetsBar() {
    const sizesGroup = document.querySelector("#sizes-group");
    if (!sizesGroup || document.getElementById("tc-size-presets-bar")) return;

    const bar = document.createElement("div");
    bar.id = "tc-size-presets-bar";
    bar.className = "tc-size-presets-bar";
    bar.innerHTML = `
      <div class="tc-size-presets-header">
        <span class="tc-presets-icon">⚡</span>
        <strong>Quick Size &amp; Weight Presets:</strong>
        <span class="tc-presets-subtitle">Click to auto-populate standard sizes/weights (or enter custom sizes below)</span>
      </div>
      <div class="tc-preset-buttons">
        <button type="button" class="tc-preset-pill" data-preset="clothing">👕 Clothing (S, M, L, XL, XXL)</button>
        <button type="button" class="tc-preset-pill" data-preset="groceries">🥦 Groceries (250g, 500g, 1kg, 2kg)</button>
        <button type="button" class="tc-preset-pill" data-preset="cosmetics">💄 Cosmetics (5ml, 10ml, 20ml)</button>
        <button type="button" class="tc-preset-pill" data-preset="general">📦 General (Small, Medium, Large)</button>
        <button type="button" class="tc-preset-pill tc-preset-clear" data-preset="clear">✕ Clear Options</button>
      </div>
    `;

    const presets = {
      clothing: ["S", "M", "L", "XL", "XXL"],
      groceries: ["250g", "500g", "1kg", "2kg"],
      cosmetics: ["5ml", "10ml", "20ml"],
      general: ["Small", "Medium", "Large"],
    };

    bar.addEventListener("click", function (e) {
      const btn = e.target.closest(".tc-preset-pill");
      if (!btn) return;
      const pKey = btn.dataset.preset;

      if (pKey === "clear") {
        const rows = sizesGroup.querySelectorAll("tr.form-row, tr[id^='sizes-']");
        rows.forEach(r => {
          const inp = r.querySelector("input[name$='-name']");
          const delCheck = r.querySelector("input[name$='-DELETE']");
          if (delCheck) {
            delCheck.checked = true;
          } else if (inp) {
            inp.value = "";
          }
        });
        return;
      }

      const items = presets[pKey];
      if (!items) return;

      items.forEach((itemText, idx) => {
        let rows = sizesGroup.querySelectorAll("tr.form-row:not(.empty-form), tr[id^='sizes-']:not(.empty-form)");

        // Skip if this size is already present in an active row
        for (let r of rows) {
          const delCheck = r.querySelector("input[name$='-DELETE']");
          if (delCheck && delCheck.checked) continue;
          const inp = r.querySelector("input[name$='-name']");
          if (inp && inp.value.trim().toLowerCase() === itemText.trim().toLowerCase()) {
            return;
          }
        }

        let targetRow = null;
        for (let r of rows) {
          const inp = r.querySelector("input[name$='-name']");
          if (inp && (!inp.value || inp.value.trim() === "")) {
            targetRow = r;
            break;
          }
        }

        if (!targetRow) {
          const addBtn = sizesGroup.querySelector(".add-row a");
          if (addBtn) {
            addBtn.click();
            rows = sizesGroup.querySelectorAll("tr.form-row:not(.empty-form), tr[id^='sizes-']:not(.empty-form)");
            targetRow = rows[rows.length - 1];
          }
        }

        if (targetRow) {
          const inp = targetRow.querySelector("input[name$='-name']");
          const orderInp = targetRow.querySelector("input[name$='-display_order']");
          const activeCheck = targetRow.querySelector("input[name$='-is_active']");
          if (inp) inp.value = itemText;
          if (orderInp) orderInp.value = idx + 1;
          if (activeCheck) activeCheck.checked = true;
        }
      });
    });

    const anchor = sizesGroup.querySelector("table, .tabular, fieldset") || sizesGroup.firstChild;
    sizesGroup.insertBefore(bar, anchor);
  }

  function injectLipstickPaletteBar() {
    const coloursGroup = document.querySelector("#colours-group");
    if (!coloursGroup || document.getElementById("tc-lipstick-palette-bar")) return;

    const bar = document.createElement("div");
    bar.id = "tc-lipstick-palette-bar";
    bar.className = "tc-lipstick-palette-bar";
    bar.innerHTML = `
      <div class="tc-lipstick-palette-header">
        <span class="tc-palette-icon">💄</span>
        <div>
          <strong>Lipstick &amp; Beauty Shades Palette:</strong>
          <span class="tc-palette-subtitle">Click any shade below to auto-fill its exact colour name, HEX code and visual swatch:</span>
        </div>
      </div>
      <div class="tc-lipstick-palette-pills">
        <button type="button" class="tc-shade-pill" data-name="Red" data-hex="#D0112B" title="Red (#D0112B)"><span class="tc-shade-dot" style="background:#D0112B;"></span><span>Red</span></button>
        <button type="button" class="tc-shade-pill" data-name="Young Pink" data-hex="#DE5B7B" title="Young Pink (#DE5B7B)"><span class="tc-shade-dot" style="background:#DE5B7B;"></span><span>Young Pink</span></button>
        <button type="button" class="tc-shade-pill" data-name="Cherry Red" data-hex="#B8142A" title="Cherry Red (#B8142A)"><span class="tc-shade-dot" style="background:#B8142A;"></span><span>Cherry Red</span></button>
        <button type="button" class="tc-shade-pill" data-name="Tree Oil" data-hex="#9C5B3E" title="Tree Oil (#9C5B3E)"><span class="tc-shade-dot" style="background:#9C5B3E;"></span><span>Tree Oil</span></button>
        <button type="button" class="tc-shade-pill" data-name="Marron Mature" data-hex="#6B2026" title="Marron Mature (#6B2026)"><span class="tc-shade-dot" style="background:#6B2026;"></span><span>Marron Mature</span></button>
        <button type="button" class="tc-shade-pill" data-name="Dark Orange" data-hex="#C84B22" title="Dark Orange (#C84B22)"><span class="tc-shade-dot" style="background:#C84B22;"></span><span>Dark Orange</span></button>
        <button type="button" class="tc-shade-pill" data-name="Chrome Red" data-hex="#9E1228" title="Chrome Red (#9E1228)"><span class="tc-shade-dot" style="background:#9E1228;"></span><span>Chrome Red</span></button>
        <button type="button" class="tc-shade-pill" data-name="Poppy Red" data-hex="#D4222E" title="Poppy Red (#D4222E)"><span class="tc-shade-dot" style="background:#D4222E;"></span><span>Poppy Red</span></button>
        <button type="button" class="tc-shade-pill" data-name="Skin Kiss" data-hex="#C97A7E" title="Skin Kiss (#C97A7E)"><span class="tc-shade-dot" style="background:#C97A7E;"></span><span>Skin Kiss</span></button>
        <button type="button" class="tc-shade-pill" data-name="Grape" data-hex="#68255F" title="Grape (#68255F)"><span class="tc-shade-dot" style="background:#68255F;"></span><span>Grape</span></button>
        <button type="button" class="tc-shade-pill" data-name="Blood Red" data-hex="#850B18" title="Blood Red (#850B18)"><span class="tc-shade-dot" style="background:#850B18;"></span><span>Blood Red</span></button>
        <button type="button" class="tc-shade-pill" data-name="Dark Purple" data-hex="#42163E" title="Dark Purple (#42163E)"><span class="tc-shade-dot" style="background:#42163E;"></span><span>Dark Purple</span></button>
        <button type="button" class="tc-shade-pill" data-name="Nude" data-hex="#C99B7D" title="Nude (#C99B7D)"><span class="tc-shade-dot" style="background:#C99B7D;"></span><span>Nude</span></button>
        <button type="button" class="tc-shade-pill" data-name="Rose Pink" data-hex="#DC5E84" title="Rose Pink (#DC5E84)"><span class="tc-shade-dot" style="background:#DC5E84;"></span><span>Rose Pink</span></button>
        <button type="button" class="tc-shade-pill" data-name="Coral" data-hex="#E86358" title="Coral (#E86358)"><span class="tc-shade-dot" style="background:#E86358;"></span><span>Coral</span></button>

        <span style="display:inline-block; width:1px; height:20px; background:#e2e8f0; margin:0 4px; vertical-align:middle;"></span>
        <button type="button" class="tc-shade-pill" data-name="Ivory Glow" data-hex="#F5E0CD" title="Ivory Glow (#F5E0CD) - Foundation"><span class="tc-shade-dot" style="background:#F5E0CD; border:1px solid #d4bda8;"></span><span>Ivory Glow</span></button>
        <button type="button" class="tc-shade-pill" data-name="Creme Glow" data-hex="#E8C8A6" title="Creme Glow (#E8C8A6) - Foundation"><span class="tc-shade-dot" style="background:#E8C8A6; border:1px solid #c9aa88;"></span><span>Creme Glow</span></button>
        <button type="button" class="tc-shade-pill" data-name="Nude Glow" data-hex="#D1A57B" title="Nude Glow (#D1A57B) - Foundation"><span class="tc-shade-dot" style="background:#D1A57B; border:1px solid #b38860;"></span><span>Nude Glow</span></button>
      </div>
    `;

    bar.addEventListener("click", function (e) {
      const btn = e.target.closest(".tc-shade-pill");
      if (!btn) return;
      const sName = btn.dataset.name;
      const sHex = btn.dataset.hex;

      let colourRows = coloursGroup.querySelectorAll(".inline-related:not(.empty-form)");

      // Check if shade already exists in any row to prevent accidental duplicates
      for (let r of colourRows) {
        const delCheck = r.querySelector("input[name$='-DELETE']");
        if (delCheck && delCheck.checked) continue;
        const nameInp = r.querySelector("input[name$='-name']");
        if (nameInp && nameInp.value.trim().toLowerCase() === sName.trim().toLowerCase()) {
          r.scrollIntoView({ behavior: 'smooth', block: 'center' });
          r.style.transition = 'box-shadow 0.3s ease';
          r.style.boxShadow = '0 0 0 3px #a51655';
          setTimeout(() => { r.style.boxShadow = ''; }, 1500);
          return;
        }
      }

      let targetRow = null;
      for (let r of colourRows) {
        const nameInp = r.querySelector("input[name$='-name']");
        if (nameInp && (!nameInp.value || nameInp.value.trim() === "")) {
          targetRow = r;
          break;
        }
      }

      if (!targetRow) {
        const addBtn = coloursGroup.querySelector(".add-row a");
        if (addBtn) {
          addBtn.click();
          colourRows = coloursGroup.querySelectorAll(".inline-related:not(.empty-form)");
          targetRow = colourRows[colourRows.length - 1];
        }
      }

      if (targetRow) {
        const nameInp = targetRow.querySelector("input[name$='-name']");
        const hexInp = targetRow.querySelector("input[name$='-color_code']");
        const swatchCircle = targetRow.querySelector(".tc-colour-swatch-circle");
        const cmSelect = targetRow.querySelector("select[name$='-color_master']");

        if (nameInp) nameInp.value = sName;
        if (hexInp) hexInp.value = sHex;
        if (swatchCircle) swatchCircle.style.backgroundColor = sHex;

        if (cmSelect) {
          for (let opt of cmSelect.options) {
            if (opt.textContent.toLowerCase().includes(sName.toLowerCase())) {
              cmSelect.value = opt.value;
              break;
            }
          }
        }
      }
    });

    const anchor = coloursGroup.querySelector(".inline-related, fieldset, table") || coloursGroup.firstChild;
    coloursGroup.insertBefore(bar, anchor);
  }

  injectCollapsibleGuide();
  injectLipstickPaletteBar();
  injectSizePresetsBar();
});

// -------------------------------------------------------------
// GLOBAL HANDLERS FOR COLOUR MULTI-IMAGE WIDGET
// -------------------------------------------------------------
window.tcHandleColourFilesPicked = function (input, prefix) {
  function esc(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  const container = document.getElementById(`tc-colour-pending-previews-${prefix}`);
  if (!container) return;
  container.innerHTML = "";
  if (!input.files || input.files.length === 0) return;

  Array.from(input.files).forEach((file, idx) => {
    const card = document.createElement("div");
    card.className = "tc-cim-pending-card";
    const imgId = `tc-cim-pending-img-${prefix}-${idx}`;
    card.innerHTML = `
      <div class="tc-cim-pending-thumb">
        <img id="${imgId}" src="" alt="Pending preview" />
      </div>
      <div class="tc-cim-pending-meta">
        <span class="tc-cim-pending-name">${esc(file.name)}</span>
        <span class="tc-cim-pending-status">Ready to save (${(file.size / 1024).toFixed(1)} KB)</span>
      </div>
    `;
    container.appendChild(card);

    const reader = new FileReader();
    reader.onload = function (e) {
      const img = document.getElementById(imgId);
      if (img) img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  });
};

window.tcHandleColourPrimaryChange = function (radio, prefix) {
  const wrap = radio.closest(".tc-colour-images-manager-wrap");
  if (!wrap) return;
  wrap.querySelectorAll(".tc-cim-card").forEach(c => c.classList.remove("is-primary"));
  const card = radio.closest(".tc-cim-card");
  if (card && radio.checked) {
    card.classList.add("is-primary");
  }
};

window.tcHandleColourDeleteToggle = function (checkbox, imgId) {
  const card = document.getElementById(`tc-cim-card-${imgId}`);
  if (!card) return;
  card.classList.toggle("marked-for-delete", checkbox.checked);
};
