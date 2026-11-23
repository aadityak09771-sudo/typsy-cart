
"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const get = (id) => document.getElementById(id);

    // Shop elements
    const searchInput = get("search-input");
    const categoryFilter = get("category-filter");
    const sortFilter = get("sort-filter");
    const productGrid = get("product-grid");
    const emptyMessage = get("empty-message");
    const resultsCount = get("results-count");
    const subcategoryFilterContainer = get("subcategory-filter-container");
    const subcategoryFilterBar = get("subcategory-filter-bar");
    const subcategoryFilterLabel = get("subcat-filter-label");

    // Cart elements
    const cartPanel = get("cart-panel");
    const cartItems = get("cart-items");
    const cartTotal = get("cart-total");
    const cartCount = get("cart-count");
    const closeCart = get("close-cart");
    const clearCartButton = get("clear-cart");

    // Checkout elements
    const openCheckoutButton = get("open-checkout");
    const checkoutSection = get("checkout-section");
    const checkoutForm = get("checkout-form");
    const checkoutMessage = get("checkout-message");
    const placeOrderButton = get("place-order-button");
    const cancelCheckoutButton = get("cancel-checkout");
    const orderSuccess = get("order-success");
    const orderSuccessMessage = get("order-success-message");
    const continueShoppingButton = get("continue-shopping");

    // Existing storage and backend URLs are preserved.
    const CART_STORAGE_KEY = "tipsy_cart_website_guest_v1";
    const PRODUCTS_URL = "/orders/products/";
    const GUEST_CHECKOUT_URL = "/orders/checkout/guest-order/";

    if (!productGrid || !searchInput || !categoryFilter || !sortFilter) {
        console.error("Tipsy Cart: Required Shop HTML elements are missing.");
        return;
    }

    let products = [];
    let cart = loadSavedCart();
    let busy = false;
    let currentSubcategory = "all";

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
            const url = new URL(String(value), window.location.origin);

            if (url.protocol !== "http:" && url.protocol !== "https:") {
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
        if (cat.includes("plastic")) {
            return "/static/home/images/cat-plastic-items.jpg";
        }
        return "/static/home/images/cat-daily-essentials.jpg";
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
            console.warn("Saved cart could not be loaded:", error);
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
            alert("Cart save nahi ho paya. Browser storage check karein.");
        }
    }

    async function requestJSON(url, options = {}) {
        const response = await fetch(url, {
            credentials: "same-origin",
            ...options,
            headers: {
                ...(options.body
                    ? { "Content-Type": "application/json" }
                    : {}),
                ...options.headers
            }
        });

        const contentType = response.headers.get("content-type") || "";

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

        return data;
    }

    async function postJSON(url, payload) {
        return requestJSON(url, {
            method: "POST",
            body: JSON.stringify(payload)
        });
    }

    // --------------------------------
    // Category handling
    // --------------------------------

    function categorySlug(category) {
        const value = String(category || "")
            .trim()
            .toLowerCase()
            .replace(/[_\s]+/g, "-");

        if (["safety", "personal-safety"].includes(value)) {
            return "personal-safety";
        }

        if (
            ["personal-care", "personalcare"].includes(value)
        ) {
            return "personal-care";
        }

        if (
            ["daily-essentials", "dailyessential"].includes(value)
        ) {
            return "daily-essentials";
        }

        if (value === "groceries" || value === "grocery") {
            return "groceries";
        }

        if (value === "period-care") {
            return "period-care";
        }

        return value || "other";
    }

    function matchesCategory(product, selectedCategory) {
        if (selectedCategory === "all") return true;

        const category = product.categorySlug;

        const subcategory = String(product.subcategory || "")
            .toLowerCase()
            .replace(/[_-]+/g, " ");

        const name = String(product.name || "").toLowerCase();

        if (selectedCategory === "period-care") {
            return (
                category === "period-care" ||
                subcategory.includes("period") ||
                subcategory.includes("menstrual") ||
                subcategory.includes("sanitary") ||
                name.includes("sanitary") ||
                name.includes("menstrual") ||
                name.includes("period pad")
            );
        }

        return category === selectedCategory;
    }

    function subcategorySlug(value) {
        return String(value || "")
            .trim()
            .toLowerCase()
            .replace(/&/g, "and")
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-+|-+$/g, "");
    }

    function normalizeSubcat(val) {
        return String(val || "")
            .toLowerCase()
            .replace(/and/g, "")
            .replace(/[^a-z0-9]/g, "");
    }

    function matchesSubcategory(product, selectedSubcategory) {
        if (!selectedSubcategory || selectedSubcategory === "all") return true;
        const normSelected = normalizeSubcat(selectedSubcategory);
        const normProduct = normalizeSubcat(product.subcategory);
        return normProduct === normSelected;
    }

    // --------------------------------
    // Floating cart button
    // --------------------------------

    function createCartButtonIfMissing() {
        if (get("cart-toggle")) return;

        const button = document.createElement("button");

        button.id = "cart-toggle";
        button.type = "button";
        button.textContent = "🛒 Cart (0)";
        button.setAttribute("aria-label", "Shopping cart");
        button.setAttribute("aria-controls", "cart-panel");

        document.body.appendChild(button);
    }

    // --------------------------------
    // Load products from Django
    // --------------------------------

    async function loadProducts(options = {}) {
        const showLoading = options.showLoading !== false;

        if (showLoading) {
            productGrid.innerHTML = `
                <div class="loading-products">
                    <span class="loading-spinner"></span>
                    <p>Getting your essentials ready...</p>
                </div>
            `;
        }

        try {
            const data = await requestJSON(PRODUCTS_URL);

            if (!Array.isArray(data.products)) {
                throw new Error("Product list ka format sahi nahi hai.");
            }

            products = data.products.map(product => ({
                ...product,
                id: Number(product.id),
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
                name: String(product.name || "Product"),
                description: String(product.description || ""),
                category: String(product.category || ""),
                subcategory: String(product.subcategory || ""),
                brand: String(product.brand || ""),
                image_url: safeImageURL(product.image_url),
                categorySlug: product.category_slug || categorySlug(product.category),
                subcategorySlug: product.subcategory_slug || subcategorySlug(product.subcategory)
            })).filter(product =>
                Number.isInteger(product.id) && product.id > 0
            );

            // Update existing cart entries using current database data.
            cart = cart
                .filter(item => products.some(p => p.id === item.id))
                .map(item => {
                    const product = products.find(p => p.id === item.id);

                    return {
                        id: product.id,
                        name: product.name,
                        price: product.price,
                        quantity: Math.min(
                            item.quantity,
                            100,
                            product.stock > 0 ? product.stock : item.quantity
                        )
                    };
                });

            saveCart();
            renderSubcategories();
            renderProducts();
            renderCart();

            return true;

        } catch (error) {
            console.error("Products load failed:", error);

            if (showLoading || products.length === 0) {
                productGrid.innerHTML = `
                    <div class="loading-products">
                        <p>Products load nahi hue: ${escapeHTML(error.message)}</p>
                        <button type="button" id="retry-products" class="primary-button">
                            Try Again
                        </button>
                    </div>
                `;

                const retryButton = get("retry-products");

                retryButton?.addEventListener("click", () => {
                    loadProducts();
                });
            }

            return false;
        }
    }

    // --------------------------------
    // Subcategory Filtering (Admin Linked)
    // --------------------------------

    function renderSubcategories() {
        if (!subcategoryFilterContainer || !subcategoryFilterBar) return;

        const selectedCategory = categoryFilter.value;

        // Find products matching current category (without subcategory filter)
        const categoryProducts = products.filter(product =>
            matchesCategory(product, selectedCategory)
        );

        // Collect unique subcategories with counts
        const subcatMap = new Map();
        categoryProducts.forEach(product => {
            const sub = String(product.subcategory || "").trim();
            if (sub) {
                subcatMap.set(sub, (subcatMap.get(sub) || 0) + 1);
            }
        });

        if (subcatMap.size === 0) {
            subcategoryFilterContainer.hidden = true;
            currentSubcategory = "all";
            return;
        }

        subcategoryFilterContainer.hidden = false;

        let labelText = "Explore Subcategories:";
        if (selectedCategory === "groceries") {
            labelText = "Groceries Subcategories:";
        } else if (selectedCategory === "daily-essentials") {
            labelText = "Daily Essentials Subcategories:";
        }
        if (subcategoryFilterLabel) {
            subcategoryFilterLabel.textContent = labelText;
        }

        const isAllActive = (currentSubcategory === "all");
        let categoryDisplayTitle = "Items";
        if (selectedCategory === "groceries") categoryDisplayTitle = "Groceries";
        else if (selectedCategory === "daily-essentials") categoryDisplayTitle = "Daily Essentials";
        else if (selectedCategory === "period-care") categoryDisplayTitle = "Period Care";
        else if (selectedCategory === "personal-safety") categoryDisplayTitle = "Safety";
        else if (selectedCategory === "personal-care") categoryDisplayTitle = "Personal Care";

        let pillsHTML = `
            <button
                type="button"
                class="subcat-pill ${isAllActive ? 'active' : ''}"
                data-subcat="all"
                role="tab"
                aria-selected="${isAllActive}"
            >
                All ${escapeHTML(categoryDisplayTitle)} (${categoryProducts.length})
            </button>
        `;

        subcatMap.forEach((count, subcatName) => {
            const slug = subcategorySlug(subcatName);
            const isActive = (currentSubcategory === slug || currentSubcategory.toLowerCase() === subcatName.toLowerCase());
            pillsHTML += `
                <button
                    type="button"
                    class="subcat-pill ${isActive ? 'active' : ''}"
                    data-subcat="${escapeHTML(slug)}"
                    role="tab"
                    aria-selected="${isActive}"
                >
                    ${escapeHTML(subcatName)} (${count})
                </button>
            `;
        });

        subcategoryFilterBar.innerHTML = pillsHTML;

        subcategoryFilterBar.querySelectorAll(".subcat-pill").forEach(button => {
            button.addEventListener("click", () => {
                currentSubcategory = button.getAttribute("data-subcat") || "all";

                const url = new URL(window.location.href);
                if (currentSubcategory !== "all") {
                    url.searchParams.set("subcategory", currentSubcategory);
                } else {
                    url.searchParams.delete("subcategory");
                }
                window.history.replaceState({}, "", url.toString());

                renderSubcategories();
                renderProducts();
            });
        });
    }

    // --------------------------------
    // Render products
    // --------------------------------

    function renderProducts() {
        const query = searchInput.value.trim().toLowerCase();
        const selectedCategory = categoryFilter.value;

        let filtered = products.filter(product => {
            const searchableText = [
                product.name,
                product.description,
                product.category,
                product.subcategory,
                product.brand
            ].join(" ").toLowerCase();

            return (
                searchableText.includes(query) &&
                matchesCategory(product, selectedCategory) &&
                matchesSubcategory(product, currentSubcategory)
            );
        });

        // When browsing 'all' categories, deduplicate identical cross-category items so customers see unique products
        if (selectedCategory === "all") {
            const seen = new Set();
            filtered = filtered.filter(product => {
                const key = `${product.name.trim().toLowerCase()}|${product.brand.trim().toLowerCase()}`;
                if (seen.has(key)) return false;
                seen.add(key);
                return true;
            });
        }

        if (sortFilter.value === "low") {
            filtered.sort((a, b) => a.price - b.price);
        } else if (sortFilter.value === "high") {
            filtered.sort((a, b) => b.price - a.price);
        } else if (sortFilter.value === "name") {
            filtered.sort((a, b) => a.name.localeCompare(b.name));
        }

        productGrid.innerHTML = filtered.map(product => {
            const fallbackUrl = getCategoryFallbackImage(product.category);
            const imgSrc = product.image_url && product.image_url.trim() ? product.image_url : fallbackUrl;
            const altText = `${escapeHTML(product.name)} - Tipsy Cart Essentials`;

            const image = `
                <img
                    class="product-image"
                    src="${escapeHTML(imgSrc)}"
                    alt="${altText}"
                    loading="lazy"
                    onerror="if (this.getAttribute('data-fallback') !== '1') { this.setAttribute('data-fallback', '1'); this.src = '${fallbackUrl}'; this.classList.add('tc-img-fallback'); }"
                >
            `;

            const inStock = product.stock > 0;

            return `
                <article class="product-card">
                    <div class="product-card-media">
                        ${image}
                        <div class="product-tag-row">
                            <span class="product-tag-cat">${escapeHTML(product.category || "Essentials")}</span>
                            ${product.subcategory ? `<span class="product-tag-subcat">${escapeHTML(product.subcategory)}</span>` : ""}
                        </div>
                    </div>

                    <h2>${escapeHTML(product.name)}</h2>

                    ${product.brand
                        ? `<p class="product-brand">${escapeHTML(product.brand)}</p>`
                        : ""}

                    <p>${escapeHTML(product.description)}</p>

                    <div class="product-price">
                        ${renderProductPriceHTML(product)}
                    </div>

                    <p class="product-stock ${inStock ? "" : "out-of-stock"}">
                        ${inStock
                            ? `${product.stock} available`
                            : "Out of stock"}
                    </p>

                    <button
                        type="button"
                        data-add="${product.id}"
                        ${!inStock ? "disabled" : ""}
                    >
                        ${inStock ? "Add to Cart" : "Out of Stock"}
                    </button>
                </article>
            `;
        }).join("");

        if (resultsCount) {
            resultsCount.textContent =
                `${filtered.length} product(s) found`;
        }

        if (emptyMessage) {
            emptyMessage.hidden = filtered.length > 0;
        }
    }

    // --------------------------------
    // Cart calculations
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

    // --------------------------------
    // Render cart
    // --------------------------------

    function renderCart() {
        const quantity = getCartQuantity();
        const total = getCartTotal();

        const toggle = get("cart-toggle");

        if (toggle) {
            toggle.textContent = `🛒 Cart (${quantity})`;
            toggle.setAttribute(
                "aria-label",
                `Shopping cart, ${quantity} items`
            );
        }

        if (cartCount) {
            cartCount.textContent = quantity;
        }

        if (cartItems) {
            cartItems.innerHTML = cart.length
                ? cart.map(item => `
                    <div class="cart-item">
                        <span>
                            ${escapeHTML(item.name)} × ${item.quantity}
                        </span>

                        <span>
                            ₹${formatPrice(item.price * item.quantity)}

                            <button
                                type="button"
                                data-remove="${item.id}"
                                aria-label="Remove one ${escapeHTML(item.name)}"
                            >−</button>
                        </span>
                    </div>
                `).join("")
                : "<p>Your cart is empty.</p>";
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
    // Add to cart
    // --------------------------------

    function addToCart(id, button) {
        if (busy) return;

        const product = products.find(p => p.id === id);

        if (!product || product.stock <= 0) {
            alert("Ye product abhi available nahi hai.");
            return;
        }

        const existing = cart.find(item => item.id === id);
        const currentQuantity = existing ? existing.quantity : 0;

        if (currentQuantity >= product.stock) {
            alert("Is product ka available stock itna hi hai.");
            return;
        }

        if (currentQuantity >= 100) {
            alert("Ek product ke maximum 100 items add kar sakte hain.");
            return;
        }

        if (existing) {
            existing.quantity += 1;
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

        if (button) {
            const originalText = "Add to Cart";

            button.textContent = "Added ✓";

            window.setTimeout(() => {
                if (button.isConnected && !button.disabled) {
                    button.textContent = originalText;
                }
            }, 1000);
        }
    }

    // --------------------------------
    // Remove from cart
    // --------------------------------

    function removeFromCart(id) {
        const item = cart.find(entry => entry.id === id);

        if (!item) return;

        if (item.quantity > 1) {
            item.quantity -= 1;
        } else {
            cart = cart.filter(entry => entry.id !== id);
        }

        saveCart();
        renderCart();
    }

    // --------------------------------
    // Clear cart
    // --------------------------------

    function clearCart() {
        if (!cart.length) {
            alert("Cart pehle se empty hai.");
            return;
        }

        if (!confirm("Kya aap poora cart clear karna chahte hain?")) {
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
            alert("Bhai, pehle cart mein product add karo.");
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

    // --------------------------------
    // Cancel checkout
    // --------------------------------

    function cancelCheckout() {
        if (checkoutSection) {
            checkoutSection.hidden = true;
        }

        if (checkoutMessage) {
            checkoutMessage.textContent = "";
        }
    }

    // --------------------------------
    // Place order
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
            full_name: String(formData.get("full_name") || "").trim(),
            phone: String(formData.get("phone") || "").trim(),
            address: String(formData.get("address") || "").trim(),
            city: String(formData.get("city") || "").trim(),
            state: String(formData.get("state") || "").trim(),
            pincode: String(formData.get("pincode") || "").trim(),
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
            const data = await postJSON(
                GUEST_CHECKOUT_URL,
                payload
            );

            if (!data.success || !data.order_id) {
                throw new Error(
                    data.error || "Order confirmation nahi mila."
                );
            }

            // Backend has confirmed order creation.
            // Only now clear the local cart.
            cart = [];
            saveCart();
            renderCart();

            if (checkoutSection) {
                checkoutSection.hidden = true;
            }

            if (cartPanel) {
                cartPanel.hidden = true;
            }

            if (orderSuccessMessage) {
                const orderId = escapeHTML(data.order_id);
                const total = formatPrice(data.total_amount);

                orderSuccessMessage.innerHTML = `
                    <p>Thank you for shopping with Tipsy Cart!</p>
                    <p><strong>Order ID:</strong> #${orderId}</p>
                    <p><strong>Order Total:</strong> ₹${total}</p>
                    <p><strong>Payment:</strong> Cash on Delivery</p>
                    <p><strong>Order Status:</strong> ${escapeHTML(data.status || "Pending")}</p>
                    <p>Our team will process your order shortly.</p>
                `;
            }

            if (orderSuccess) {
                orderSuccess.hidden = false;

                orderSuccess.scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });
            }

            checkoutForm.reset();

            if (checkoutMessage) {
                checkoutMessage.textContent = "";
            }

            // Refresh products separately.
            // A refresh failure must NOT show "order failed"
            // after the backend has already confirmed the order.
            const refreshed = await loadProducts({
                showLoading: false
            });

            if (!refreshed) {
                console.warn(
                    "Order was successful, but product refresh failed."
                );
            }

        } catch (error) {
            console.error("Guest checkout failed:", error);

            if (checkoutMessage) {
                checkoutMessage.textContent =
                    error.message ||
                    "Order place nahi hua. Dobara try karein.";
            } else {
                alert(error.message || "Order place nahi hua.");
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

        if (cartPanel) {
            cartPanel.hidden = true;
        }

        if (checkoutMessage) {
            checkoutMessage.textContent = "";
        }

        productGrid.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
    }

    // --------------------------------
    // Event listeners
    // --------------------------------

    productGrid.addEventListener("click", event => {
        const button = event.target.closest("[data-add]");

        if (button) {
            addToCart(Number(button.dataset.add), button);
        }
    });

    cartItems?.addEventListener("click", event => {
        const button = event.target.closest("[data-remove]");

        if (button) {
            removeFromCart(Number(button.dataset.remove));
        }
    });

    searchInput.addEventListener("input", renderProducts);

    categoryFilter.addEventListener("change", () => {
        currentSubcategory = "all";
        const url = new URL(window.location.href);
        if (categoryFilter.value !== "all") {
            url.searchParams.set("category", categoryFilter.value);
        } else {
            url.searchParams.delete("category");
        }
        url.searchParams.delete("subcategory");
        window.history.replaceState({}, "", url.toString());

        renderSubcategories();
        renderProducts();
    });

    sortFilter.addEventListener("change", renderProducts);

    document.addEventListener("click", event => {
        if (event.target.closest("#cart-toggle")) {
            if (window.openCartDrawer) {
                window.openCartDrawer();
            } else if (cartPanel) {
                cartPanel.hidden = !cartPanel.hidden;
            }
        }
    });

    closeCart?.addEventListener("click", () => {
        if (cartPanel) {
            cartPanel.hidden = true;
        }
    });

    clearCartButton?.addEventListener("click", clearCart);
    openCheckoutButton?.addEventListener("click", openCheckout);
    cancelCheckoutButton?.addEventListener("click", cancelCheckout);
    checkoutForm?.addEventListener("submit", placeOrder);
    continueShoppingButton?.addEventListener("click", continueShopping);

    // --------------------------------
    // Category & Subcategory links from URL
    // --------------------------------

    const params = new URLSearchParams(window.location.search);
    const requestedCategory = params.get("category");
    const requestedSubcategory = params.get("subcategory");

    if (
        requestedCategory &&
        [...categoryFilter.options].some(
            option => option.value === requestedCategory
        )
    ) {
        categoryFilter.value = requestedCategory;
    }

    if (requestedSubcategory) {
        currentSubcategory = subcategorySlug(requestedSubcategory);
    }

    // --------------------------------
    // Start
    // --------------------------------

    createCartButtonIfMissing();
    renderCart();
    loadProducts();
});
