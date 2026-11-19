

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

    async function syncBackendCartAdd(productId, quantity) {
        try {
            await fetch("/orders/cart/add/", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken") || ""
                },
                body: JSON.stringify({ product_id: productId, quantity: quantity || 1 })
            });
        } catch (e) {
            // Quiet ignore for guest users
        }
    }

    async function syncBackendCartRemove(productId) {
        try {
            await fetch("/orders/cart/remove/", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken") || ""
                },
                body: JSON.stringify({ product_id: productId })
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

            return `
                <div class="drawer-item-card" data-product-id="${item.id}">
                    <div class="drawer-item-thumb">${imgHtml}</div>
                    <div class="drawer-item-meta">
                        <strong>${item.name}</strong>
                        <span class="drawer-item-price">₹${price.toFixed(2)} each</span>
                        <div class="drawer-qty-stepper">
                            <button type="button" class="btn-qty-minus" data-id="${item.id}" aria-label="Decrease quantity">−</button>
                            <span>${qty}</span>
                            <button type="button" class="btn-qty-plus" data-id="${item.id}" aria-label="Increase quantity">+</button>
                        </div>
                    </div>
                    <div class="drawer-item-actions">
                        <span class="drawer-item-subtotal">₹${subtotal}</span>
                        <button type="button" class="drawer-remove-btn" data-id="${item.id}" title="Remove item">🗑️</button>
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

    // Delegated actions inside itemsContainer (stepper +/- and delete)
    if (itemsContainer) {
        itemsContainer.addEventListener("click", event => {
            const plusBtn = event.target.closest(".btn-qty-plus");
            const minusBtn = event.target.closest(".btn-qty-minus");
            const removeBtn = event.target.closest(".drawer-remove-btn");

            if (plusBtn) {
                const id = Number(plusBtn.dataset.id);
                let cart = getLocalCart();
                const item = cart.find(x => x.id === id);
                if (item) {
                    item.quantity += 1;
                    saveLocalCart(cart);
                    syncBackendCartAdd(id, 1);
                    renderCartDrawer();
                }
            } else if (minusBtn) {
                const id = Number(minusBtn.dataset.id);
                let cart = getLocalCart();
                const item = cart.find(x => x.id === id);
                if (item) {
                    if (item.quantity > 1) {
                        item.quantity -= 1;
                    } else {
                        cart = cart.filter(x => x.id !== id);
                    }
                    saveLocalCart(cart);
                    syncBackendCartRemove(id);
                    renderCartDrawer();
                }
            } else if (removeBtn) {
                const id = Number(removeBtn.dataset.id);
                let cart = getLocalCart().filter(x => x.id !== id);
                saveLocalCart(cart);
                syncBackendCartRemove(id);
                renderCartDrawer();
            }
        });
    }

    // Initial badge update on page load
    updateGlobalCartBadges();

    // Export helpers globally so shop.js and script.js can call them
    window.updateGlobalCart = updateGlobalCartBadges;
    window.showCartToast = showCartToast;
    window.openCartDrawer = openCartDrawer;
    window.closeCartDrawer = closeCartDrawer;
    window.syncBackendCartAdd = syncBackendCartAdd;
});
