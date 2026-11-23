/**
 * TipsyCart Admin Dynamic Enhancements
 * - Instant Live Image Preview (File upload or direct URL)
 * - Dynamic Category -> Subcategory Filtering
 * - Live Price & Discount Preview & Auto-Calculation
 */

document.addEventListener("DOMContentLoaded", function () {
  // -------------------------------------------------------------
  // 1. LIVE IMAGE PREVIEW (Categories, Subcategories, Products, Banners)
  // -------------------------------------------------------------
  const fileInput = document.querySelector("#id_image");
  const urlInput = document.querySelector("#id_image_url");
  const clearCheckbox = document.querySelector("#image-clear_id");

  function escapeHtml(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  if (fileInput || urlInput) {
    // Determine the best anchor element to insert the Live Preview box below
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

    // Track active image mode: "file" | "saved" | "url" | "none"
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

      // 1. Newly selected local file from user's computer
      if (fileInput && fileInput.files && fileInput.files.length > 0) {
        currentMode = "file";
        const file = fileInput.files[0];
        const reader = new FileReader();
        reader.onload = function (e) {
          previewImg.src = e.target.result;
          previewImg.style.display = "block";
          previewStatus.innerHTML = `<span style="color: #16a34a; font-weight: 700;">✓ Local File Chosen:</span> ${escapeHtml(file.name)} (${(file.size / 1024).toFixed(1)} KB)`;
        };
        reader.readAsDataURL(file);
        return;
      }

      // 2. External URL entered in Option 2 (ignore if it's an old /media/ copy while file is present)
      if (rawUrl && (!savedUrl || !isLocalMedia || clearChecked)) {
        currentMode = "url";
        previewImg.src = rawUrl;
        previewImg.style.display = "block";
        previewStatus.innerHTML = `<span style="color: #4b5563;">Loading external image link...</span>`;
        return;
      }

      // 3. Previously saved uploaded file exists on this record
      if (savedUrl && !clearChecked) {
        currentMode = "saved";
        previewImg.src = savedUrl;
        previewImg.style.display = "block";
        const filename = savedUrl.split("/").pop();
        previewStatus.innerHTML = `<span style="color: #0284c7; font-weight: 700;">✓ Current Saved Image (from computer):</span> ${escapeHtml(decodeURIComponent(filename))}`;
        return;
      }

      // 4. Marked for clearing
      if (clearChecked) {
        currentMode = "none";
        previewImg.style.display = "none";
        previewStatus.innerHTML = `<span style="color: #d97706; font-weight: 600;">Image marked for removal on Save.</span>`;
        return;
      }

      // 5. No image at all
      currentMode = "none";
      previewImg.style.display = "none";
      previewStatus.innerHTML = `<span style="color: #6b7280;">No image chosen or URL entered.</span>`;
    }

    if (previewImg) {
      previewImg.onload = function () {
        if (currentMode === "url") {
          previewStatus.innerHTML = `<span style="color: #16a34a; font-weight: 700;">✓ External image loaded successfully</span>`;
        } else if (currentMode === "saved") {
          const savedUrl = getSavedUploadedUrl();
          const filename = savedUrl ? savedUrl.split("/").pop() : "image";
          previewStatus.innerHTML = `<span style="color: #0284c7; font-weight: 700;">✓ Current Saved Image (from computer):</span> ${escapeHtml(decodeURIComponent(filename))}`;
        }
      };

      previewImg.onerror = function () {
        if (currentMode === "url") {
          previewStatus.innerHTML = `<span style="color: #dc2626; font-weight: 700;">⚠️ Could not load image from this URL.</span> Please verify it is a direct public image link (e.g. ending in .jpg, .png, .webp).`;
        } else if (currentMode === "saved") {
          previewStatus.innerHTML = `<span style="color: #f59e0b; font-weight: 700;">⚠️ Saved local media file not found.</span> Please upload the image file again.`;
        }
      };
    }

    if (fileInput) {
      fileInput.addEventListener("change", renderLivePreview);
    }

    if (urlInput) {
      urlInput.addEventListener("input", function () {
        // If user manually types/pastes, render external preview
        renderLivePreview();
      });
    }

    if (clearCheckbox) {
      clearCheckbox.addEventListener("change", renderLivePreview);
    }

    // Initial render on page load
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
        .then(function (res) {
          return res.json();
        })
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
    });

    // Run on initial load if category already selected
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

  if (origPriceInput && sellingPriceInput) {
    const priceRow = sellingPriceInput.closest(".form-row, .field-price") || sellingPriceInput.parentElement;
    const badgeContainer = document.createElement("div");
    badgeContainer.className = "tc-badge-preview";
    badgeContainer.id = "tc-pricing-preview-badge";

    if (priceRow) {
      priceRow.appendChild(badgeContainer);
    }

    function calculateLivePrice() {
      const orig = parseFloat(origPriceInput.value) || 0;
      const isDiscount = discountEnabledCheck ? discountEnabledCheck.checked : false;
      const dType = discountTypeSelect ? discountTypeSelect.value : "percentage";
      const dVal = discountValInput ? parseFloat(discountValInput.value) || 0 : 0;

      if (orig <= 0) {
        badgeContainer.innerHTML = '<span style="color: #6b7280; font-size: 12px;">Enter Original MRP first.</span>';
        return;
      }

      if (!isDiscount || dVal <= 0) {
        sellingPriceInput.value = orig.toFixed(2);
        badgeContainer.innerHTML = `<span style="color: #1e293b; background: #f3f4f6; padding: 4px 10px; border-radius: 6px;">Regular Price: ₹${orig.toFixed(2)} (No Discount)</span>`;
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

    [origPriceInput, discountValInput].forEach(function (el) {
      if (el) el.addEventListener("input", calculateLivePrice);
    });

    [discountEnabledCheck, discountTypeSelect].forEach(function (el) {
      if (el) el.addEventListener("change", calculateLivePrice);
    });

    // Initial calculation on load
    calculateLivePrice();
  }
});
