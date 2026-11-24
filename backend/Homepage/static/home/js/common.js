

document.addEventListener("DOMContentLoaded", () => {
    const currentPath = window.location.pathname.replace(/\/+$/, "") || "/";

    document.querySelectorAll(".site-nav a").forEach(link => {
        const linkPath = link.pathname.replace(/\/+$/, "") || "/";

        if (linkPath === currentPath) {
            link.setAttribute("aria-current", "page");
        }
    });

    // ========================================================
    // GLOBAL FLIPKART / AMAZON STYLE CART DRAWER & CONTROLLER
    // ========================================================
    const CART_STORAGE_KEY = "tipsy_cart_website_guest_v1";

    const overlay = document.getElementById("side-cart-overlay");
    const drawer = document.getElementById("side-cart-drawer");
    const closeBtn = document.getElementById("close-drawer-btn");
    const floatingBtn = document.getElementById("floating-side-cart");
    const navCartBtn = document.getElementById("nav-cart-btn");
    const navBadge = document.getElementById("nav-cart-badge");
    const sideBadge = document.getElementById("side-cart-badge");
    const drawerCount = document.getElementById("drawer-items-count");
    const itemsContainer = document.getElementById("drawer-items-container");
    const drawerFooter = document.getElementById("drawer-footer");
    const drawerSubtotal = document.getElementById("drawer-items-subtotal");
    const drawerTotal = document.getElementById("drawer-total-amount");
    const clearBtn = document.getElementById("drawer-clear-btn");
    const continueBtn = document.getElementById("drawer-continue-btn");
    const toast = document.getElementById("cart-floating-toast");
    const toastText = document.getElementById("cart-toast-text");

    let toastTimer = null;

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== "") {
            const cookies = document.cookie.split(";");
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + "=")) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    function getLocalCart() {
        try {
            const saved = JSON.parse(localStorage.getItem(CART_STORAGE_KEY) || "[]");
            return Array.isArray(saved) ? saved : [];
        } catch {
            return [];
        }
    }

    function saveLocalCart(cart) {
        try {
            localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(cart));
        } catch (e) {
            console.warn("Could not save cart:", e);
        }
        updateGlobalCartBadges(cart);
    }

    function calculateTotalCount(cart) {
        return cart.reduce((sum, item) => sum + (Number(item.quantity) || 0), 0);
    }

    function calculateTotalAmount(cart) {
        return cart.reduce((sum, item) => sum + ((Number(item.price) || 0) * (Number(item.quantity) || 0)), 0);
    }

    function updateGlobalCartBadges(cartParam) {
        const cart = cartParam || getLocalCart();
        const count = calculateTotalCount(cart);

        if (navBadge) navBadge.textContent = count;
        if (sideBadge) {
            sideBadge.textContent = count;
            sideBadge.classList.add("bump");
            setTimeout(() => sideBadge.classList.remove("bump"), 300);
        }
        if (drawerCount) drawerCount.textContent = count;
    }

    function showCartToast(itemName) {
        if (!toast) return;
        if (toastText) {
            toastText.textContent = itemName ? `✓ Added "${itemName}" to Cart!` : `✓ Added to Cart!`;
        }
        toast.classList.add("show");
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => {
            toast.classList.remove("show");
        }, 2400);
    }

    async function syncBackendCartAdd(productId, quantity, variantId) {
        try {
            await fetch("/orders/cart/add/", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken") || ""
                },
                body: JSON.stringify({
                    product_id: productId,
                    quantity: quantity || 1,
                    variant_id: variantId || null
                })
            });
        } catch (e) {
            // Quiet ignore for guest users
        }
    }

    async function syncBackendCartRemove(productId, variantId) {
        try {
            await fetch("/orders/cart/remove/", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken") || ""
                },
                body: JSON.stringify({
                    product_id: productId,
                    variant_id: variantId || null
                })
            });
        } catch (e) {
            // Quiet ignore
        }
    }

    async function syncBackendCartClear() {
        try {
            await fetch("/orders/cart/clear/", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken") || ""
                }
            });
        } catch (e) {
            // Quiet ignore
        }
    }

    function renderCartDrawer() {
        const cart = getLocalCart();
        updateGlobalCartBadges(cart);

        if (!itemsContainer) return;

        if (cart.length === 0) {
            itemsContainer.innerHTML = `
                <div class="drawer-empty-state">
                    <div class="empty-icon">🛍️</div>
                    <h4>Your Cart is Empty</h4>
                    <p>Looks like you haven't added anything to your cart yet.</p>
                    <a href="/shop/" class="drawer-checkout-btn" style="display:inline-block; max-width:200px; padding:10px 18px; font-size:13px;">
                        Explore Shop →
                    </a>
                </div>
            `;
            if (drawerFooter) drawerFooter.style.display = "none";
            return;
        }

        if (drawerFooter) drawerFooter.style.display = "block";

        const totalAmount = calculateTotalAmount(cart);
        if (drawerSubtotal) drawerSubtotal.textContent = `₹${totalAmount.toFixed(2)}`;
        if (drawerTotal) drawerTotal.textContent = `₹${totalAmount.toFixed(2)}`;

        itemsContainer.innerHTML = cart.map(item => {
            const price = Number(item.price) || 0;
            const qty = Number(item.quantity) || 1;
            const subtotal = (price * qty).toFixed(2);
            const imgHtml = item.image_url
                ? `<img src="${item.image_url}" alt="${item.name}" onerror="this.outerHTML='<span class=\\'drawer-item-thumb\\'>🛍️</span>'">`
                : `🛍️`;
            const vIdAttr = item.variant_id ? `data-variant-id="${item.variant_id}"` : "";

            return `
                <div class="drawer-item-card" data-product-id="${item.id}" ${vIdAttr}>
                    <div class="drawer-item-thumb">${imgHtml}</div>
                    <div class="drawer-item-meta">
                        <strong>${item.name}</strong>
                        ${item.variant_title ? `<span style="display:block; font-size:12px; color:#a51655; font-weight:600; margin:1px 0;">Option: ${item.variant_title}</span>` : ""}
                        <span class="drawer-item-price">₹${price.toFixed(2)} each</span>
                        <div class="drawer-qty-stepper">
                            <button type="button" class="btn-qty-minus" data-id="${item.id}" ${vIdAttr} aria-label="Decrease quantity">−</button>
                            <span>${qty}</span>
                            <button type="button" class="btn-qty-plus" data-id="${item.id}" ${vIdAttr} aria-label="Increase quantity">+</button>
                        </div>
                    </div>
                    <div class="drawer-item-actions">
                        <span class="drawer-item-subtotal">₹${subtotal}</span>
                        <button type="button" class="drawer-remove-btn" data-id="${item.id}" ${vIdAttr} title="Remove item">🗑️</button>
                    </div>
                </div>
            `;
        }).join("");
    }

    function openCartDrawer() {
        renderCartDrawer();
        if (drawer) drawer.classList.add("open");
        if (overlay) overlay.classList.add("open");
        document.body.style.overflow = "hidden"; // Prevent body scrolling while viewing cart
    }

    function closeCartDrawer() {
        if (drawer) drawer.classList.remove("open");
        if (overlay) overlay.classList.remove("open");
        document.body.style.overflow = "";
    }

    // Event Listeners for drawer controls
    if (floatingBtn) floatingBtn.addEventListener("click", openCartDrawer);
    if (navCartBtn) navCartBtn.addEventListener("click", openCartDrawer);
    if (closeBtn) closeBtn.addEventListener("click", closeCartDrawer);
    if (overlay) overlay.addEventListener("click", closeCartDrawer);
    if (continueBtn) continueBtn.addEventListener("click", closeCartDrawer);

    if (clearBtn) {
        clearBtn.addEventListener("click", () => {
            if (confirm("Are you sure you want to clear your cart?")) {
                saveLocalCart([]);
                syncBackendCartClear();
                renderCartDrawer();
            }
        });
    }

    // Helper to match cart item by product ID and variant ID
    const matchCartItem = (item, id, vId) => {
        if (Number(item.id) !== Number(id)) return false;
        const itemVId = item.variant_id ? Number(item.variant_id) : null;
        const targetVId = vId ? Number(vId) : null;
        return itemVId === targetVId;
    };

    // Delegated actions inside itemsContainer (stepper +/- and delete)
    if (itemsContainer) {
        itemsContainer.addEventListener("click", event => {
            const plusBtn = event.target.closest(".btn-qty-plus");
            const minusBtn = event.target.closest(".btn-qty-minus");
            const removeBtn = event.target.closest(".drawer-remove-btn");

            if (plusBtn) {
                const id = Number(plusBtn.dataset.id);
                const vId = plusBtn.dataset.variantId ? Number(plusBtn.dataset.variantId) : null;
                let cart = getLocalCart();
                const item = cart.find(x => matchCartItem(x, id, vId));
                if (item) {
                    item.quantity += 1;
                    saveLocalCart(cart);
                    syncBackendCartAdd(id, 1, vId);
                    renderCartDrawer();
                }
            } else if (minusBtn) {
                const id = Number(minusBtn.dataset.id);
                const vId = minusBtn.dataset.variantId ? Number(minusBtn.dataset.variantId) : null;
                let cart = getLocalCart();
                const item = cart.find(x => matchCartItem(x, id, vId));
                if (item) {
                    if (item.quantity > 1) {
                        item.quantity -= 1;
                    } else {
                        cart = cart.filter(x => !matchCartItem(x, id, vId));
                    }
                    saveLocalCart(cart);
                    syncBackendCartRemove(id, vId);
                    renderCartDrawer();
                }
            } else if (removeBtn) {
                const id = Number(removeBtn.dataset.id);
                const vId = removeBtn.dataset.variantId ? Number(removeBtn.dataset.variantId) : null;
                let cart = getLocalCart().filter(x => !matchCartItem(x, id, vId));
                saveLocalCart(cart);
                syncBackendCartRemove(id, vId);
                renderCartDrawer();
            }
        });
    }

    // Initial badge update on page load
    updateGlobalCartBadges();

    // ========================================================
    // FOOTER NEWSLETTER SUBSCRIPTION HANDLER
    // ========================================================
    const newsletterForm = document.getElementById("tc-newsletter-form");
    const newsletterEmail = document.getElementById("tc-newsletter-email");
    const newsletterMsg = document.getElementById("tc-newsletter-msg");
    const newsletterBtn = document.getElementById("tc-newsletter-btn");

    if (newsletterForm && newsletterEmail && newsletterMsg) {
        newsletterForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const email = newsletterEmail.value.trim();
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

            if (!email || !emailRegex.test(email)) {
                newsletterMsg.textContent = "Please enter a valid email address.";
                newsletterMsg.className = "tc-newsletter-msg error";
                newsletterEmail.focus();
                return;
            }

            const csrfTokenInput = newsletterForm.querySelector('input[name="csrfmiddlewaretoken"]');
            const csrfToken = csrfTokenInput ? csrfTokenInput.value : "";

            if (newsletterBtn) {
                newsletterBtn.disabled = true;
                newsletterBtn.textContent = "Subscribing...";
            }
            newsletterMsg.textContent = "";

            try {
                const response = await fetch("/newsletter/subscribe/", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrfToken
                    },
                    body: JSON.stringify({ email })
                });

                const data = await response.json();

                if (response.ok && data.success) {
                    newsletterMsg.textContent = data.message || "Thank you for subscribing!";
                    newsletterMsg.className = "tc-newsletter-msg success";
                    newsletterEmail.value = "";
                } else {
                    newsletterMsg.textContent = data.message || "Subscription failed. Please check the email and try again.";
                    newsletterMsg.className = "tc-newsletter-msg error";
                }
            } catch (err) {
                newsletterMsg.textContent = "Connection error. Please try again.";
                newsletterMsg.className = "tc-newsletter-msg error";
            } finally {
                if (newsletterBtn) {
                    newsletterBtn.disabled = false;
                    newsletterBtn.textContent = "Subscribe";
                }
            }
        });
    }

    // ========================================================
    // APP STORE BADGES COMING SOON TOAST
    // ========================================================
    document.querySelectorAll(".tc-app-badge").forEach(badge => {
        badge.addEventListener("click", (e) => {
            e.preventDefault();
            const store = badge.getAttribute("data-store") || "App Store";
            if (typeof showCartToast === "function") {
                showCartToast(`TipsyCart on ${store} is launching soon in Kanpur! 🚀`);
            } else {
                alert(`TipsyCart on ${store} is launching soon for Kanpur! Stay tuned for fast deliveries.`);
            }
        });
    });

    // -------------------------------------------------------------------------
    // NAVBAR SEARCH & REAL-TIME AUTOCOMPLETE (BLINKIT STYLE)
    // -------------------------------------------------------------------------
    function escapeHtml(str) {
        return String(str ?? "").replace(/[&<>"']/g, char => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        })[char]);
    }

    const navSearchInput = document.getElementById("navbar-search-input");
    const navSearchClearBtn = document.getElementById("nav-search-clear-btn");
    const navSearchDropdown = document.getElementById("navbar-search-dropdown");
    const navSearchLoading = document.getElementById("nav-search-loading");
    const navSearchResultsList = document.getElementById("nav-search-results-list");
    const navSearchEmpty = document.getElementById("nav-search-empty");
    const navSearchEmptyQuery = document.getElementById("nav-search-empty-query");
    const navSearchFooter = document.getElementById("nav-search-footer");
    const navSearchViewAll = document.getElementById("nav-search-view-all");
    const navSearchViewAllQuery = document.getElementById("nav-search-view-all-query");

    if (navSearchInput && navSearchDropdown) {
        let debounceTimer = null;
        let currentQuery = "";
        let activeIndex = -1;

        function closeSearchDropdown() {
            navSearchDropdown.style.display = "none";
            activeIndex = -1;
        }

        function openSearchDropdown() {
            navSearchDropdown.style.display = "flex";
        }

        function updateClearButton() {
            if (navSearchClearBtn) {
                navSearchClearBtn.style.display = navSearchInput.value.trim().length > 0 ? "inline-flex" : "none";
            }
        }

        if (navSearchClearBtn) {
            navSearchClearBtn.addEventListener("click", () => {
                navSearchInput.value = "";
                updateClearButton();
                closeSearchDropdown();
                navSearchInput.focus();
            });
        }

        async function fetchSearchResults(query) {
            currentQuery = query;
            if (navSearchLoading) navSearchLoading.style.display = "flex";
            if (navSearchEmpty) navSearchEmpty.style.display = "none";
            if (navSearchResultsList) navSearchResultsList.innerHTML = "";
            if (navSearchFooter) navSearchFooter.style.display = "none";
            openSearchDropdown();

            try {
                const response = await fetch(`/api/search/?q=${encodeURIComponent(query)}`);
                if (!response.ok) throw new Error("Search request failed");
                const data = await response.json();

                if (query !== currentQuery) return;

                if (navSearchLoading) navSearchLoading.style.display = "none";
                const results = data.results || [];

                if (results.length === 0) {
                    if (navSearchEmptyQuery) navSearchEmptyQuery.textContent = query;
                    if (navSearchEmpty) navSearchEmpty.style.display = "block";
                    return;
                }

                if (navSearchResultsList) {
                    navSearchResultsList.innerHTML = results.map((item, idx) => {
                        const priceHtml = item.is_variable && item.price_range_display
                            ? `<span class="nav-search-price">${escapeHtml(item.price_range_display)}</span>`
                            : `<span class="nav-search-price">₹${escapeHtml(item.price)}</span>`;
                        const mrpHtml = item.discount_percentage > 0
                            ? `<span class="nav-search-mrp">₹${escapeHtml(item.original_price)}</span>`
                            : '';
                        const discountHtml = item.discount_percentage > 0
                            ? `<span class="nav-search-badge" style="background: #fdf2f8; color: #a51655;">${item.discount_percentage}% OFF</span>`
                            : '';
                        const categoryHtml = item.category
                            ? `<span class="nav-search-badge">${escapeHtml(item.category)}</span>`
                            : '';

                        return `
                            <a href="${escapeHtml(item.url)}" class="nav-search-item" data-index="${idx}" role="option">
                                <img src="${escapeHtml(item.image_url)}" alt="${escapeHtml(item.name)}" class="nav-search-thumb" loading="lazy">
                                <div class="nav-search-info">
                                    <div class="nav-search-title">${escapeHtml(item.name)}</div>
                                    <div class="nav-search-meta">
                                        ${item.brand ? `<span>${escapeHtml(item.brand)}</span> • ` : ''}
                                        ${categoryHtml}
                                        ${discountHtml}
                                    </div>
                                </div>
                                <div class="nav-search-price-wrap">
                                    ${priceHtml}
                                    ${mrpHtml}
                                </div>
                            </a>
                        `;
                    }).join("");
                }

                if (navSearchFooter && navSearchViewAll && navSearchViewAllQuery) {
                    navSearchViewAllQuery.textContent = query;
                    navSearchViewAll.href = `/search/?q=${encodeURIComponent(query)}`;
                    navSearchFooter.style.display = "block";
                }

            } catch (err) {
                console.warn("TipsyCart Navbar Search error:", err);
                if (navSearchLoading) navSearchLoading.style.display = "none";
            }
        }

        navSearchInput.addEventListener("input", (e) => {
            const query = e.target.value.trim();
            updateClearButton();
            clearTimeout(debounceTimer);

            if (query.length < 1) {
                closeSearchDropdown();
                return;
            }

            debounceTimer = setTimeout(() => {
                fetchSearchResults(query);
            }, 240);
        });

        navSearchInput.addEventListener("focus", () => {
            const query = navSearchInput.value.trim();
            if (query.length >= 1 && navSearchResultsList && navSearchResultsList.children.length > 0) {
                openSearchDropdown();
            }
        });

        // Keyboard navigation (Arrow down, Arrow up, Escape, Enter)
        navSearchInput.addEventListener("keydown", (e) => {
            if (!navSearchResultsList) return;
            const items = navSearchResultsList.querySelectorAll(".nav-search-item");
            if (e.key === "ArrowDown") {
                e.preventDefault();
                if (items.length > 0) {
                    activeIndex = (activeIndex + 1) % items.length;
                    highlightItem(items);
                }
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                if (items.length > 0) {
                    activeIndex = (activeIndex - 1 + items.length) % items.length;
                    highlightItem(items);
                }
            } else if (e.key === "Escape") {
                closeSearchDropdown();
            } else if (e.key === "Enter") {
                if (activeIndex >= 0 && items[activeIndex]) {
                    e.preventDefault();
                    items[activeIndex].click();
                }
            }
        });

        function highlightItem(items) {
            items.forEach((el, i) => {
                if (i === activeIndex) {
                    el.classList.add("highlighted");
                    el.scrollIntoView({ block: "nearest" });
                } else {
                    el.classList.remove("highlighted");
                }
            });
        }

        // Close on click outside
        document.addEventListener("click", (e) => {
            if (navSearchDropdown && navSearchInput && !navSearchDropdown.contains(e.target) && !navSearchInput.contains(e.target)) {
                closeSearchDropdown();
            }
        });

        updateClearButton();
    }

    // Unified global add-to-cart handler supporting simple & variable products
    window.addToCartGlobal = function(productId, name, price, imageUrl, quantity = 1, variantId = null, variantTitle = "") {
        let cart = getLocalCart();
        const pId = Number(productId);
        const vId = variantId ? Number(variantId) : null;
        const match = cart.find(x => Number(x.id) === pId && ((x.variant_id ? Number(x.variant_id) : null) === vId));
        if (match) {
            match.quantity += (quantity || 1);
            if (price) match.price = Number(price);
            if (imageUrl) match.image_url = imageUrl;
        } else {
            cart.push({
                id: pId,
                name: String(name),
                price: Number(price),
                image_url: imageUrl || "",
                quantity: quantity || 1,
                variant_id: vId,
                variant_title: variantTitle || ""
            });
        }
        saveLocalCart(cart);
        syncBackendCartAdd(pId, quantity || 1, vId);
        showCartToast(variantTitle ? `${name} (${variantTitle})` : `${name}`);
        renderCartDrawer();
        openCartDrawer();
    };

    // Export helpers globally so shop.js and script.js can call them
    window.updateGlobalCart = updateGlobalCartBadges;
    window.showCartToast = showCartToast;
    window.openCartDrawer = openCartDrawer;
    window.closeCartDrawer = closeCartDrawer;
    window.syncBackendCartAdd = syncBackendCartAdd;
});
