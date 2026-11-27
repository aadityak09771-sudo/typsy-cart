
"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const get = id => document.getElementById(id);

    const CART_STORAGE_KEY = "tipsy_cart_website_guest_v1";
    const PRODUCTS_URL = "/orders/products/";
    const GUEST_CHECKOUT_URL = "/orders/checkout/guest-order/";

    const dataElement = get("homepage-products-data");

    const searchInput = get("searchInput");
    const categoryFilter = get("categoryFilter");
    const sortFilter = get("sortFilter");

    const categoryShelves = get("categoryShelves");
    const filteredProductsSection = get("filteredProductsSection");
    const productGrid = get("productGrid");
    const filteredProductsTitle = get("filteredProductsTitle");
    const filteredProductsCount = get("filteredProductsCount");
    const emptyMessage = get("emptyMessage");

    const cartSection = get("cartSection");
    const cartItems = get("cartItems");
    const cartTotal = get("cartTotal");
    const closeCart = get("closeCart");
    const clearCartButton = get("clearCart");
    const openCheckoutButton = get("openHomeCheckout");

    const checkoutSection = get("homeCheckoutSection");
    const checkoutForm = get("homeCheckoutForm");
    const checkoutMessage = get("homeCheckoutMessage");
    const placeOrderButton = get("homePlaceOrderButton");
    const cancelCheckoutButton = get("cancelHomeCheckout");

    const orderSuccess = get("homeOrderSuccess");
    const orderSuccessMessage = get("homeOrderSuccessMessage");
    const continueShoppingButton = get("homeContinueShopping");

    let products = [];
    let cart = loadSavedCart();
    let busy = false;

    let categories = [];
    try {
        const catScript = document.getElementById("homepage-categories-data");
        if (catScript) {
            categories = JSON.parse(catScript.textContent || "[]");
        }
    } catch (e) {
        console.warn("Failed to parse homepage categories:", e);
    }
    if (!Array.isArray(categories) || categories.length === 0) {
        categories = [
            {
                slug: "period-care",
                title: "Period Care",
                description: "Menstrual hygiene and period care essentials."
            },
            {
                slug: "personal-safety",
                title: "Personal Safety",
                description: "Everyday personal safety essentials."
            },
            {
                slug: "personal-care",
                title: "Personal Care",
                description: "Skincare, hygiene and personal care."
            },
            {
                slug: "daily-essentials",
                title: "Daily Essentials",
                description: "Useful products for your everyday routine."
            },
            {
                slug: "groceries",
                title: "Groceries",
                description: "Everyday groceries and food essentials."
            }
        ];
    }

    // --------------------------------
    // Safe helpers
    // --------------------------------

    function escapeHTML(value) {
        return String(value ?? "").replace(/[&<>"']/g, char => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        })[char]);
    }

    function safeImageURL(value) {
        if (!value) return "";

        try {
            const url = new URL(
                String(value).trim(),
                window.location.origin
            );

            if (
                url.protocol !== "https:" &&
                url.protocol !== "http:"
            ) {
                return "";
            }

            return url.href;
        } catch {
            return "";
        }
    }

    function formatPrice(value) {
        const price = Number(value);

        return Number.isFinite(price) && price >= 0
            ? price.toFixed(2)
            : "0.00";
    }

    function formatCurrency(value) {
        const price = Number(value);
        if (!Number.isFinite(price) || price < 0) return "0";
        return price % 1 === 0 ? price.toFixed(0) : price.toFixed(2);
    }

    function renderProductPriceHTML(product) {
        const finalPrice = Math.max(0, Number(product.price) || 0);
        const originalPrice = Number(product.original_price);
        const isDiscountEnabled = Boolean(
            product.discount_enabled === true ||
            product.discount_enabled === "true" ||
            product.discount_enabled === 1 ||
            (Number.isFinite(originalPrice) && originalPrice > finalPrice)
        );

        const hasValidDiscount = isDiscountEnabled &&
            Number.isFinite(originalPrice) &&
            originalPrice > finalPrice &&
            finalPrice > 0;

        if (!hasValidDiscount) {
            return `
                <div class="tc-price-wrap">
                    <div class="tc-price-row">
                        <span class="tc-price-current">₹${formatCurrency(finalPrice)}</span>
                    </div>
                </div>
            `;
        }

        const savings = Math.max(0, Number(product.savings_amount) || (originalPrice - finalPrice));
        let discountPct = Number(product.discount_percentage);
        if (!Number.isFinite(discountPct) || discountPct <= 0) {
            discountPct = Math.round(((originalPrice - finalPrice) / originalPrice) * 100);
        }
        discountPct = Math.min(99, Math.max(1, Math.round(discountPct)));

        return `
            <div class="tc-price-wrap has-discount">
                <div class="tc-price-row">
                    <span class="tc-price-current">₹${formatCurrency(finalPrice)}</span>
                    <span class="tc-price-original">₹${formatCurrency(originalPrice)}</span>
                    <span class="tc-price-discount">${discountPct}% OFF</span>
                </div>
                <div class="tc-price-savings">You save ₹${formatCurrency(savings)}</div>
            </div>
        `;
    }

    function formatUnit(val, unit) {
        if (!val && !unit) return "";
        const num = Number(val);
        let strVal = "";
        if (Number.isFinite(num) && num > 0) {
            strVal = num % 1 === 0 ? num.toFixed(0) : num.toFixed(2).replace(/\.?0+$/, "");
        } else if (val) {
            strVal = String(val);
        }
        return [strVal, unit].filter(Boolean).join(" ");
    }

    function categorySlug(value) {
        return String(value || "")
            .trim()
            .toLowerCase()
            .replace(/[_\s]+/g, "-");
    }

    // --------------------------------
    // Product normalization
    // --------------------------------

    function normalizeProduct(product) {
        const galleryImgs = Array.isArray(product.gallery_images) && product.gallery_images.length
            ? product.gallery_images.map(img => safeImageURL(img)).filter(Boolean)
            : [safeImageURL(product.image_url)].filter(Boolean);

        return {
            ...product,
            id: Number(product.id),
            name: String(product.name || "Product"),
            description: String(product.description || ""),
            category: String(product.category || ""),
            subcategory: String(product.subcategory || ""),
            brand: String(product.brand || ""),
            price: Math.max(0, Number(product.price) || 0),
            original_price: Number(product.original_price) || Math.max(0, Number(product.price) || 0),
            discount_enabled: Boolean(
                product.discount_enabled === true ||
                product.discount_enabled === "true" ||
                product.discount_enabled === 1
            ),
            discount_type: String(product.discount_type || "percentage"),
            discount_value: Number(product.discount_value) || 0,
            discount_percentage: Number(product.discount_percentage) || 0,
            savings_amount: Number(product.savings_amount) || 0,
            stock: Math.max(0, Number(product.stock) || 0),
            image_url: safeImageURL(product.image_url),
            gallery_images: galleryImgs.length ? galleryImgs : [getCategoryFallbackImage(product.category)],
            unit_type: product.unit_type || "none",
            unit: String(product.unit || ""),
            unit_value: product.unit_value !== undefined && product.unit_value !== null ? String(product.unit_value) : "",
            unit_selector_label: product.unit_selector_label || "Select Option",
            is_variable: Boolean(product.is_variable || product.product_type === "variable"),
            variants: Array.isArray(product.variants) ? product.variants : [],
            sizes: Array.isArray(product.sizes) ? product.sizes : [],
            colours: Array.isArray(product.colours) ? product.colours : [],
        };
    }

    function normalizeProductList(list) {
        if (!Array.isArray(list)) return [];

        return list
            .map(normalizeProduct)
            .filter(product =>
                Number.isInteger(product.id) &&
                product.id > 0
            );
    }

    // --------------------------------
    // Homepage embedded product fallback
    // --------------------------------

    function loadHomepageProducts() {
        try {
            const loaded = JSON.parse(
                dataElement?.textContent || "[]"
            );

            return normalizeProductList(loaded);

        } catch (error) {
            console.error(
                "Homepage products could not be loaded:",
                error
            );

            return [];
        }
    }

    // --------------------------------
    // Load latest products from Django
    // --------------------------------

    async function loadProductsFromAPI() {
        const response = await fetch(PRODUCTS_URL, {
            method: "GET",
            credentials: "same-origin",
            headers: {
                "Accept": "application/json"
            }
        });

        if (!response.ok) {
            throw new Error(
                `Products API failed (HTTP ${response.status}).`
            );
        }

        const contentType =
            response.headers.get("content-type") || "";

        if (!contentType.toLowerCase().includes("application/json")) {
            throw new Error("Products API returned an invalid response.");
        }

        const data = await response.json();

        // Supports the existing Django API response formats.
        const productList = Array.isArray(data)
            ? data
            : Array.isArray(data.products)
                ? data.products
                : Array.isArray(data.results)
                    ? data.results
                    : [];

        return normalizeProductList(productList);
    }

    async function loadProducts() {
        try {
            const apiProducts = await loadProductsFromAPI();

            if (apiProducts.length > 0) {
                products = apiProducts;
            } else {
                products = loadHomepageProducts();
            }

        } catch (error) {
            console.warn(
                "Using homepage product data as fallback:",
                error
            );

            products = loadHomepageProducts();
        }

        syncCartWithProducts();
        renderProducts();
        renderCart();
    }

    // --------------------------------
    // Cart storage
    // --------------------------------

    function loadSavedCart() {
        try {
            const saved = JSON.parse(
                localStorage.getItem(CART_STORAGE_KEY) || "[]"
            );

            if (!Array.isArray(saved)) return [];

            return saved
                .filter(item =>
                    Number.isInteger(Number(item.id)) &&
                    Number(item.id) > 0 &&
                    Number.isInteger(Number(item.quantity)) &&
                    Number(item.quantity) > 0 &&
                    Number(item.quantity) <= 100
                )
                .map(item => ({
                    id: Number(item.id),
                    name: String(item.name || "Product"),
                    price: Math.max(0, Number(item.price) || 0),
                    quantity: Number(item.quantity)
                }));

        } catch (error) {
            console.warn(
                "Saved cart could not be loaded:",
                error
            );

            return [];
        }
    }

    function saveCart() {
        try {
            localStorage.setItem(
                CART_STORAGE_KEY,
                JSON.stringify(cart)
            );

        } catch (error) {
            console.error("Cart could not be saved:", error);

            alert(
                "Cart save nahi ho paya. Browser storage check karein."
            );
        }
    }

    function syncCartWithProducts() {
        if (!products.length || !cart.length) return;

        cart = cart
            .map(item => {
                const product = products.find(
                    p => p.id === item.id
                );

                if (!product || product.stock <= 0) {
                    return null;
                }

                return {
                    id: product.id,
                    name: product.name,
                    price: product.price,
                    quantity: Math.min(
                        item.quantity,
                        product.stock,
                        100
                    )
                };
            })
            .filter(Boolean);

        saveCart();
    }

    // --------------------------------
    // Product category classification
    // --------------------------------

    function getProductCategory(product) {
        const category = categorySlug(product.category);
        const subcategory = categorySlug(product.subcategory);

        const name = String(product.name || "").toLowerCase();

        const periodKeywords = [
            "period",
            "menstrual",
            "sanitary",
            "sanitary-pad"
        ];

        const isPeriodCare =
            category === "period-care" ||
            periodKeywords.some(word =>
                subcategory.includes(word) ||
                name.includes(word)
            );

        if (isPeriodCare) {
            return "period-care";
        }

        if (
            category === "safety" ||
            category === "personal-safety"
        ) {
            return "personal-safety";
        }

        if (
            category === "personal-care" ||
            category === "personalcare"
        ) {
            return "personal-care";
        }

        if (
            category === "daily-essentials" ||
            category === "dailyessential"
        ) {
            return "daily-essentials";
        }

        if (
            category === "groceries" ||
            category === "grocery"
        ) {
            return "groceries";
        }

        return category || "";
    }

    // --------------------------------
    // Sorting
    // --------------------------------

    function getSortedProducts(list) {
        const sorted = [...list];

        if (sortFilter?.value === "low") {
            sorted.sort((a, b) => a.price - b.price);

        } else if (sortFilter?.value === "high") {
            sorted.sort((a, b) => b.price - a.price);

        } else if (sortFilter?.value === "name") {
            sorted.sort((a, b) =>
                a.name.localeCompare(b.name)
            );
        }

        return sorted;
    }

    // --------------------------------
    // Product card & category fallback
    // --------------------------------

    function getCategoryFallbackImage(category) {
        const cat = (category || "").toLowerCase();
        if (cat.includes("grocer")) {
            return "/static/home/images/cat-groceries.jpg";
        }
        if (cat.includes("period")) {
            return "/static/home/images/cat-period-care.jpg";
        }
        if (cat.includes("safety")) {
            return "/static/home/images/cat-personal-safety.jpg";
        }
        if (cat.includes("personal")) {
            return "/static/home/images/cat-personal-care.jpg";
        }
        return "/static/home/images/cat-daily-essentials.jpg";
    }

    function productCard(product) {
        const fallbackUrl = getCategoryFallbackImage(product.category);
        const images = Array.isArray(product.gallery_images) && product.gallery_images.length
            ? product.gallery_images
            : [product.image_url || fallbackUrl];
        const altText = `${escapeHTML(product.name)} - Tipsy Cart Fresh Essentials`;

        const isVariable = Boolean(product.is_variable || product.product_type === "variable");
        const activeVariants = isVariable && Array.isArray(product.variants) ? product.variants : [];
        const hasVariants = activeVariants.length > 0;

        const firstAvailableVariant = activeVariants.find(v => v.is_available && v.stock > 0) || activeVariants[0] || null;
        const selectedVariantId = firstAvailableVariant ? firstAvailableVariant.id : "";
        const currentPrice = firstAvailableVariant ? Number(firstAvailableVariant.price) : product.price;
        const origPrice = firstAvailableVariant ? (Number(firstAvailableVariant.original_price) || currentPrice) : product.original_price;
        const discountPct = firstAvailableVariant ? (firstAvailableVariant.discount_percentage || 0) : product.discount_percentage;
        const inStock = firstAvailableVariant ? (firstAvailableVariant.is_available && firstAvailableVariant.stock > 0) : (product.stock > 0);

        // Unit badge - only show for simple products or variable products without active variant chips
        let unitBadgeHtml = "";
        const unitText = formatUnit(product.unit_value, product.unit);
        if (unitText && !(isVariable && hasVariants)) {
            unitBadgeHtml = `<div class="tc-card-unit-badge">${escapeHTML(unitText)}</div>`;
        }

        // Variant chips
        let variantChipsHtml = "";
        if (isVariable && hasVariants) {
            variantChipsHtml = `
                <div class="tc-card-variants">
                    ${activeVariants.map((v, i) => {
                        const isSelected = v.id === selectedVariantId;
                        const chipLabel = v.size_name || formatUnit(v.unit_value, v.unit) || v.variant_name || v.title || `Opt ${i+1}`;
                        return `
                            <span
                                class="tc-variant-chip ${isSelected ? 'active' : ''}"
                                data-variant-id="${v.id}"
                                data-price="${formatCurrency(v.price)}"
                                data-orig-price="${formatCurrency(v.original_price || v.price)}"
                                data-discount="${v.discount_percentage || 0}"
                                data-stock="${v.stock}"
                                data-image="${escapeHTML(v.image_url || '')}"
                                data-title="${escapeHTML(chipLabel)}"
                                title="${escapeHTML(v.title || chipLabel)}"
                            >
                                ${escapeHTML(chipLabel)}
                            </span>
                        `;
                    }).join("")}
                </div>
            `;
        }

        // Slider markup - click on track navigates to product details, while arrows & dots only navigate photos
        const sliderHtml = `
            <div class="tc-card-slider" data-images="${escapeHTML(JSON.stringify(images))}" data-current-index="0">
                ${discountPct > 0 ? `<span class="tc-card-discount-badge tc-discount-badge">${discountPct}% OFF</span>` : ""}
                <div class="tc-slider-track" onclick="if(window.saveShopNavState)window.saveShopNavState(); window.location.href='/product/${product.id}/';" style="cursor:pointer;" title="View ${escapeHTML(product.name)}">
                    <img
                        class="product-image tc-slider-img"
                        src="${escapeHTML(images[0])}"
                        alt="${altText}"
                        loading="lazy"
                        onerror="if (this.getAttribute('data-fallback') !== '1') { this.setAttribute('data-fallback', '1'); this.src = '${fallbackUrl}'; this.classList.add('tc-img-fallback'); }"
                    >
                </div>
                ${images.length > 1 ? `
                    <button type="button" class="tc-slider-arrow tc-slider-prev" onclick="event.preventDefault(); event.stopPropagation();" aria-label="Previous image">‹</button>
                    <button type="button" class="tc-slider-arrow tc-slider-next" onclick="event.preventDefault(); event.stopPropagation();" aria-label="Next image">›</button>
                    <div class="tc-slider-dots">
                        ${images.map((_, i) => `<span class="tc-slider-dot ${i === 0 ? 'active' : ''}" data-index="${i}" onclick="event.preventDefault(); event.stopPropagation();"></span>`).join("")}
                    </div>
                ` : ""}
            </div>
        `;

        const currentQty = window.getCartItemQty ? window.getCartItemQty(product.id, selectedVariantId) : 0;
        const actionHtml = `
            <div class="tc-card-action-wrap">
                ${currentQty > 0 ? `
                    <div class="tc-card-stepper" data-product-id="${product.id}">
                        <button type="button" class="tc-stepper-btn tc-stepper-dec" aria-label="Decrease quantity">−</button>
                        <span class="tc-stepper-qty">${currentQty}</span>
                        <button type="button" class="tc-stepper-btn tc-stepper-inc" aria-label="Increase quantity">+</button>
                    </div>
                ` : (inStock ? `
                    <button type="button" class="tc-card-add-btn">
                        Add to Cart 🛒
                    </button>
                ` : `
                    <button type="button" class="tc-card-add-btn disabled" disabled>
                        Out of Stock
                    </button>
                `)}
            </div>
        `;

        return `
            <article
                class="tc-product-card"
                data-card-product-id="${product.id}"
                data-product-name="${escapeHTML(product.name)}"
                data-selected-variant-id="${selectedVariantId}"
                data-is-out-of-stock="${inStock ? 'false' : 'true'}"
            >
                ${sliderHtml}

                <div class="tc-product-info">
                    <p class="tc-product-category">
                        <span>${escapeHTML(product.category || "Essentials")}</span>
                        ${product.subcategory ? `<span class="tc-product-subcat-badge"> • ${escapeHTML(product.subcategory)}</span>` : ""}
                    </p>

                    <h3 style="margin: 4px 0;">
                        <a href="/product/${product.id}/" style="color:inherit; text-decoration:none;">
                            ${escapeHTML(product.name)}
                        </a>
                    </h3>

                    ${product.brand
                        ? `<p class="tc-product-brand">${escapeHTML(product.brand)}</p>`
                        : ""
                    }

                    ${unitBadgeHtml}
                    ${variantChipsHtml}

                    <div class="tc-product-bottom" style="margin-top:auto; padding-top:6px; display:flex; flex-direction:column; gap:6px;">
                        <div class="tc-price-wrap">
                            <div class="tc-price-row">
                                <span class="tc-price-current">₹${formatCurrency(currentPrice)}</span>
                                ${origPrice && origPrice > currentPrice ? `<span class="tc-price-original">₹${formatCurrency(origPrice)}</span>` : ""}
                            </div>
                        </div>

                        ${actionHtml}
                    </div>
                </div>
            </article>
        `;
    }

    // --------------------------------
    // Homepage category shelves
    // Maximum 10 products per category
    // --------------------------------

    function renderCategoryShelves() {
        if (!categoryShelves) return;

        categoryShelves.innerHTML = categories.map(category => {
            const matchingProducts = products
                .filter(product =>
                    getProductCategory(product) === category.slug
                )
                .slice(0, 10);

            if (!matchingProducts.length) {
                return "";
            }

            let subcatsHTML = "";
            if (category.slug === "groceries") {
                subcatsHTML = `
                    <div class="tc-shelf-subcats">
                        <a href="/shop/?category=groceries&subcategory=fruits-and-vegetables" class="tc-shelf-subcat-chip">Fruits & Veg</a>
                        <a href="/shop/?category=groceries&subcategory=atta-rice-and-pulses" class="tc-shelf-subcat-chip">Atta & Rice</a>
                        <a href="/shop/?category=groceries&subcategory=dairy-and-bakery" class="tc-shelf-subcat-chip">Dairy & Bakery</a>
                        <a href="/shop/?category=groceries&subcategory=snacks-and-beverages" class="tc-shelf-subcat-chip">Snacks</a>
                        <a href="/shop/?category=groceries&subcategory=household-essentials" class="tc-shelf-subcat-chip">Household</a>
                    </div>
                `;
            } else if (category.slug === "daily-essentials") {
                subcatsHTML = `
                    <div class="tc-shelf-subcats">
                        <a href="/shop/?category=daily-essentials&subcategory=home-cleaning" class="tc-shelf-subcat-chip">Home Cleaning</a>
                        <a href="/shop/?category=daily-essentials&subcategory=personal-care-and-bath" class="tc-shelf-subcat-chip">Personal Care & Bath</a>
                        <a href="/shop/?category=daily-essentials&subcategory=oral-care-and-grooming" class="tc-shelf-subcat-chip">Oral Care</a>
                        <a href="/shop/?category=daily-essentials&subcategory=utilities-and-protection" class="tc-shelf-subcat-chip">Utilities</a>
                    </div>
                `;
            } else if (category.slug === "personal-care") {
                subcatsHTML = `
                    <div class="tc-shelf-subcats">
                        <a href="/shop/?category=personal-care&subcategory=personal-care-and-bath" class="tc-shelf-subcat-chip">Personal Care & Bath</a>
                        <a href="/shop/?category=personal-care&subcategory=hygiene-and-sanitization" class="tc-shelf-subcat-chip">Hygiene & Wipes</a>
                    </div>
                `;
            }

            return `
                <section class="tc-product-shelf">
                    <div class="tc-product-shelf-heading">
                        <div>
                            <p class="eyebrow">TIPSY CART COLLECTION</p>

                            <h2>${escapeHTML(category.title)}</h2>

                            <p>${escapeHTML(category.description)}</p>

                            ${subcatsHTML}
                        </div>

                        <a
                            class="tc-view-all"
                            href="/shop/?category=${encodeURIComponent(category.slug)}"
                        >
                            View All <span>→</span>
                        </a>
                    </div>

                    <div class="tc-shelf-grid">
                        ${matchingProducts.map(productCard).join("")}
                    </div>
                </section>
            `;
        }).join("");

        if (!categoryShelves.innerHTML.trim()) {
            categoryShelves.innerHTML = `
                <p class="tc-shelves-loading">
                    Products will appear here once they are added in the Admin Panel.
                </p>
            `;
        }
    }

    // --------------------------------
    // Search and category filtering
    // --------------------------------

    function renderFilteredProducts() {
        if (
            !searchInput ||
            !categoryFilter ||
            !sortFilter ||
            !categoryShelves ||
            !filteredProductsSection ||
            !productGrid
        ) {
            return;
        }

        const query = searchInput.value.trim().toLowerCase();
        const selectedCategory = categoryFilter.value;

        const isFiltering =
            query.length > 0 ||
            selectedCategory !== "all" ||
            sortFilter.value !== "default";

        categoryShelves.hidden = isFiltering;
        filteredProductsSection.hidden = !isFiltering;

        if (!isFiltering) return;

        let filtered = products.filter(product => {
            const searchableText = [
                product.name,
                product.description,
                product.category,
                product.subcategory,
                product.brand
            ].join(" ").toLowerCase();

            const matchesSearch =
                searchableText.includes(query);

            const matchesCategory =
                selectedCategory === "all" ||
                getProductCategory(product) === selectedCategory;

            return matchesSearch && matchesCategory;
        });

        filtered = getSortedProducts(filtered);

        productGrid.innerHTML =
            filtered.map(productCard).join("");

        if (filteredProductsTitle) {
            filteredProductsTitle.textContent =
                selectedCategory === "all"
                    ? "Matching Products"
                    : categories.find(
                        item => item.slug === selectedCategory
                    )?.title || "Matching Products";
        }

        if (filteredProductsCount) {
            filteredProductsCount.textContent =
                `${filtered.length} product(s) found`;
        }

        if (emptyMessage) {
            emptyMessage.hidden = filtered.length > 0;
        }
    }

    function renderProducts() {
        renderCategoryShelves();
        renderFilteredProducts();
        if (window.syncAllCardSteppers) {
            window.syncAllCardSteppers();
        }
    }

    // --------------------------------
    // Cart calculations and display
    // --------------------------------

    function getCartQuantity() {
        return cart.reduce(
            (sum, item) => sum + item.quantity,
            0
        );
    }

    function getCartTotal() {
        return cart.reduce(
            (sum, item) => sum + item.price * item.quantity,
            0
        );
    }

    function renderCart() {
        const quantity = getCartQuantity();
        const total = getCartTotal();

        if (cartItems) {
            cartItems.innerHTML = cart.length
                ? cart.map(item => `
                    <div class="tc-cart-row">
                        <div>
                            <strong>${escapeHTML(item.name)}</strong>

                            <small>
                                ₹${formatPrice(item.price)} × ${item.quantity}
                            </small>
                        </div>

                        <div class="tc-cart-row-actions">
                            <strong>
                                ₹${formatPrice(item.price * item.quantity)}
                            </strong>

                            <button
                                type="button"
                                data-remove="${item.id}"
                                aria-label="Remove one ${escapeHTML(item.name)}"
                            >−</button>
                        </div>
                    </div>
                `).join("")
                : `
                    <p class="tc-empty-cart">
                        Your cart is empty. Let's find something lovely!
                    </p>
                `;
        }

        if (cartTotal) {
            cartTotal.textContent = total.toFixed(2);
        }

        if (openCheckoutButton) {
            openCheckoutButton.disabled = quantity === 0;
        }

        if (clearCartButton) {
            clearCartButton.disabled = quantity === 0;
        }
    }

    // --------------------------------
    // Add product to cart
    // --------------------------------

    function addToCart(id, button) {
        if (busy) return;

        const product = products.find(
            item => item.id === id
        );

        if (!product || product.stock <= 0) {
            alert("Ye product abhi available nahi hai.");
            return;
        }

        const existing = cart.find(
            item => item.id === id
        );

        const currentQuantity = existing
            ? existing.quantity
            : 0;

        if (currentQuantity >= product.stock) {
            alert("Is product ka available stock itna hi hai.");
            return;
        }

        if (currentQuantity >= 100) {
            alert(
                "Ek product ke maximum 100 items add kar sakte hain."
            );
            return;
        }

        if (existing) {
            existing.quantity += 1;
            existing.name = product.name;
            existing.price = product.price;

        } else {
            cart.push({
                id: product.id,
                name: product.name,
                price: product.price,
                quantity: 1
            });
        }

        saveCart();
        renderCart();

        // Update Flipkart/Amazon style floating side cart & toast without scrolling the page!
        if (window.updateGlobalCart) {
            window.updateGlobalCart(cart);
        }
        if (window.showCartToast) {
            window.showCartToast(product.name);
        }
        if (window.syncBackendCartAdd) {
            window.syncBackendCartAdd(product.id, 1);
        }

        if (checkoutSection) {
            checkoutSection.hidden = true;
        }

        if (orderSuccess) {
            orderSuccess.hidden = true;
        }

        if (button) {
            button.textContent = "Added ✓";

            window.setTimeout(() => {
                if (button.isConnected && !button.disabled) {
                    button.textContent = "Add +";
                }
            }, 1000);
        }
    }

    // --------------------------------
    // Remove item
    // --------------------------------

    function removeFromCart(id) {
        const item = cart.find(
            entry => entry.id === id
        );

        if (!item) return;

        if (item.quantity > 1) {
            item.quantity -= 1;
        } else {
            cart = cart.filter(
                entry => entry.id !== id
            );
        }

        saveCart();
        renderCart();
    }

    // --------------------------------
    // Clear cart
    // --------------------------------

    function clearCart() {
        if (!cart.length) return;

        if (!confirm(
            "Kya aap poora cart clear karna chahte hain?"
        )) {
            return;
        }

        cart = [];

        saveCart();
        renderCart();

        if (checkoutSection) {
            checkoutSection.hidden = true;
        }

        if (checkoutMessage) {
            checkoutMessage.textContent = "";
        }
    }

    // --------------------------------
    // Open checkout
    // --------------------------------

    function openCheckout() {
        if (!cart.length) {
            alert("Pehle cart mein product add karein.");
            return;
        }

        if (orderSuccess) {
            orderSuccess.hidden = true;
        }

        if (checkoutSection) {
            checkoutSection.hidden = false;

            checkoutSection.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });
        }

        if (checkoutMessage) {
            checkoutMessage.textContent = "";
        }
    }

    function cancelCheckout() {
        if (checkoutSection) {
            checkoutSection.hidden = true;
        }

        if (checkoutMessage) {
            checkoutMessage.textContent = "";
        }
    }

    // --------------------------------
    // Place guest order
    // --------------------------------

    async function placeOrder(event) {
        event.preventDefault();

        if (busy) return;

        if (!cart.length) {
            if (checkoutMessage) {
                checkoutMessage.textContent =
                    "Aapka cart empty hai. Pehle product add karein.";
            }

            return;
        }

        if (!checkoutForm || !checkoutForm.reportValidity()) {
            return;
        }

        const formData = new FormData(checkoutForm);

        const payload = {
            full_name: String(
                formData.get("full_name") || ""
            ).trim(),

            phone: String(
                formData.get("phone") || ""
            ).trim(),

            address: String(
                formData.get("address") || ""
            ).trim(),

            city: String(
                formData.get("city") || ""
            ).trim(),

            state: String(
                formData.get("state") || ""
            ).trim(),

            pincode: String(
                formData.get("pincode") || ""
            ).trim(),

            payment_method: "COD",

            items: cart.map(item => ({
                product_id: item.id,
                quantity: item.quantity
            }))
        };

        busy = true;

        if (checkoutMessage) {
            checkoutMessage.textContent =
                "Aapka order place ho raha hai. Kripya wait karein...";
        }

        if (placeOrderButton) {
            placeOrderButton.disabled = true;
            placeOrderButton.textContent = "Placing Order...";
        }

        try {
            const response = await fetch(
                GUEST_CHECKOUT_URL,
                {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    },
                    body: JSON.stringify(payload)
                }
            );

            const contentType =
                response.headers.get("content-type") || "";

            if (!contentType.toLowerCase().includes("application/json")) {
                throw new Error(
                    `Server se valid JSON response nahi mila (HTTP ${response.status}).`
                );
            }

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.error || `Request failed (${response.status}).`
                );
            }

            if (!data.success || !data.order_id) {
                throw new Error(
                    data.error || "Order confirmation nahi mila."
                );
            }

            // Clear cart only after backend confirms the order.
            cart = [];

            saveCart();
            renderCart();

            if (checkoutSection) {
                checkoutSection.hidden = true;
            }

            if (orderSuccessMessage) {
                orderSuccessMessage.innerHTML = `
                    <p>Thank you for shopping with Tipsy Cart!</p>

                    <p>
                        <strong>Order ID:</strong>
                        #${escapeHTML(data.order_id)}
                    </p>

                    <p>
                        <strong>Order Total:</strong>
                        ₹${formatPrice(data.total_amount)}
                    </p>

                    <p>
                        <strong>Payment:</strong>
                        Cash on Delivery
                    </p>

                    <p>
                        <strong>Order Status:</strong>
                        ${escapeHTML(data.status || "Pending")}
                    </p>

                    <p>
                        Our team will process your order shortly.
                    </p>
                `;
            }

            if (orderSuccess) {
                orderSuccess.hidden = false;

                orderSuccess.scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });
            }

            if (checkoutForm) {
                checkoutForm.reset();
            }

            if (checkoutMessage) {
                checkoutMessage.textContent = "";
            }

            // Refresh product list after successful order.
            // Do not report checkout failure if refresh fails.
            try {
                await loadProducts();
            } catch (refreshError) {
                console.warn(
                    "Order succeeded, but products could not refresh:",
                    refreshError
                );
            }

        } catch (error) {
            console.error(
                "Homepage guest checkout failed:",
                error
            );

            if (checkoutMessage) {
                checkoutMessage.textContent =
                    error.message ||
                    "Order place nahi hua. Dobara try karein.";
            }

        } finally {
            busy = false;

            if (placeOrderButton) {
                placeOrderButton.disabled = false;
                placeOrderButton.textContent = "Place Order (COD)";
            }
        }
    }

    // --------------------------------
    // Continue shopping
    // --------------------------------

    function continueShopping() {
        if (orderSuccess) {
            orderSuccess.hidden = true;
        }

        if (checkoutSection) {
            checkoutSection.hidden = true;
        }

        if (cartSection) {
            cartSection.hidden = true;
        }

        if (checkoutMessage) {
            checkoutMessage.textContent = "";
        }

        get("products")?.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
    }

    // --------------------------------
    // Event listeners
    // --------------------------------

    document.addEventListener("click", event => {
        const addButton = event.target.closest("[data-add]");

        if (addButton) {
            addToCart(
                Number(addButton.dataset.add),
                addButton
            );

            return;
        }

        const removeButton = event.target.closest("[data-remove]");

        if (removeButton) {
            removeFromCart(
                Number(removeButton.dataset.remove)
            );
        }
    });

    searchInput?.addEventListener(
        "input",
        renderFilteredProducts
    );

    categoryFilter?.addEventListener(
        "change",
        renderFilteredProducts
    );

    sortFilter?.addEventListener(
        "change",
        renderFilteredProducts
    );

    clearCartButton?.addEventListener(
        "click",
        clearCart
    );

    openCheckoutButton?.addEventListener(
        "click",
        openCheckout
    );

    closeCart?.addEventListener("click", () => {
        if (cartSection) {
            cartSection.hidden = true;
        }
    });

    cancelCheckoutButton?.addEventListener(
        "click",
        cancelCheckout
    );

    checkoutForm?.addEventListener(
        "submit",
        placeOrder
    );

    continueShoppingButton?.addEventListener(
        "click",
        continueShopping
    );

    // Keep cart updated across browser tabs and unified controller.
    window.addEventListener("storage", event => {
        if (event.key === CART_STORAGE_KEY) {
            cart = loadSavedCart();
            renderCart();
        }
    });

    window.addEventListener("tipsy:cartUpdated", () => {
        cart = loadSavedCart();
        renderCart();
    });

    // --------------------------------
    // Start
    // --------------------------------

    renderCart();
    loadProducts();
});
