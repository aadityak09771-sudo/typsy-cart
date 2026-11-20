
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

    const categories = [
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
        return {
            ...product,
            id: Number(product.id),
            name: String(product.name || "Product"),
            description: String(product.description || ""),
            category: String(product.category || ""),
            subcategory: String(product.subcategory || ""),
            brand: String(product.brand || ""),
            price: Math.max(0, Number(product.price) || 0),
            stock: Math.max(0, Number(product.stock) || 0),
            image_url: safeImageURL(product.image_url)
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

        return "";
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
        const imgSrc = product.image_url && product.image_url.trim() ? product.image_url : fallbackUrl;
        const altText = `${escapeHTML(product.name)} - Tipsy Cart Fresh Essentials`;

        const image = `
            <img
                src="${escapeHTML(imgSrc)}"
                alt="${altText}"
                loading="lazy"
                onerror="if (this.getAttribute('data-fallback') !== '1') { this.setAttribute('data-fallback', '1'); this.src = '${fallbackUrl}'; this.classList.add('tc-img-fallback'); }"
            >
        `;

        const outOfStock = product.stock <= 0;

        return `
            <article class="tc-product-card">
                <div class="tc-product-image">
                    ${image}
                    <span class="tc-product-label">TIPSY CART</span>
                </div>

                <div class="tc-product-info">
                    <p class="tc-product-category">
                        ${escapeHTML(product.category || "Essentials")}
                    </p>

                    <h3>${escapeHTML(product.name)}</h3>

                    ${product.brand
                        ? `<p class="tc-product-brand">${escapeHTML(product.brand)}</p>`
                        : ""
                    }

                    <div class="tc-product-bottom">
                        <strong>₹${formatPrice(product.price)}</strong>

                        <button
                            type="button"
                            data-add="${product.id}"
                            ${outOfStock ? "disabled" : ""}
                        >
                            ${outOfStock ? "Out of stock" : "Add +"}
                        </button>
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

            return `
                <section class="tc-product-shelf">
                    <div class="tc-product-shelf-heading">
                        <div>
                            <p class="eyebrow">TIPSY CART COLLECTION</p>

                            <h2>${escapeHTML(category.title)}</h2>

                            <p>${escapeHTML(category.description)}</p>
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

    // Keep cart updated across browser tabs.
    window.addEventListener("storage", event => {
        if (event.key === CART_STORAGE_KEY) {
            cart = loadSavedCart();
            renderCart();
        }
    });

    // --------------------------------
    // Start
    // --------------------------------

    renderCart();
    loadProducts();
});
