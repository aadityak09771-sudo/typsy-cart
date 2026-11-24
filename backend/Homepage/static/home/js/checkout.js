
document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("checkout-form");
    const itemsContainer = document.getElementById("checkout-items");
    const totalElement = document.getElementById("checkout-total");
    const message = document.getElementById("checkout-message");
    const submitButton = document.getElementById("place-order-button");

    let cartItems = [];
    let currentRawTotal = 0;
    let appliedCoupon = null;

    const couponInput = document.getElementById("coupon-code-input");
    const applyCouponBtn = document.getElementById("apply-coupon-btn");
    const couponFeedback = document.getElementById("coupon-feedback");
    const discountRow = document.getElementById("discount-row");
    const discountCodeBadge = document.getElementById("discount-code-badge");
    const discountAmountVal = document.getElementById("discount-amount-val");

    if (applyCouponBtn) {
        applyCouponBtn.addEventListener("click", async () => {
            const code = couponInput.value.trim().toUpperCase();
            if (!code) {
                if (couponFeedback) {
                    couponFeedback.textContent = "Please enter a coupon code.";
                    couponFeedback.style.color = "#dc2626";
                }
                return;
            }
            applyCouponBtn.disabled = true;
            applyCouponBtn.textContent = "Checking...";
            try {
                const res = await requestJSON("/orders/api/apply-coupon/", {
                    method: "POST",
                    body: JSON.stringify({ code: code, cart_total: currentRawTotal })
                });
                appliedCoupon = res;
                if (couponFeedback) {
                    couponFeedback.textContent = res.message || `Coupon ${res.code} applied!`;
                    couponFeedback.style.color = "#16a34a";
                }
                if (discountRow) {
                    discountRow.style.display = "flex";
                    discountCodeBadge.textContent = res.code;
                    discountAmountVal.textContent = res.discount_amount;
                }
                if (totalElement) {
                    totalElement.textContent = res.new_total;
                }
            } catch (err) {
                appliedCoupon = null;
                if (couponFeedback) {
                    couponFeedback.textContent = err.message;
                    couponFeedback.style.color = "#dc2626";
                }
                if (discountRow) {
                    discountRow.style.display = "none";
                }
                if (totalElement) {
                    totalElement.textContent = currentRawTotal.toFixed(2);
                }
            } finally {
                applyCouponBtn.disabled = false;
                applyCouponBtn.textContent = "Apply";
            }
        });
    }

    function getCookie(name) {
        const prefix = `${name}=`;
        const cookie = document.cookie
            .split("; ")
            .find(row => row.startsWith(prefix));

        return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : "";
    }

    function showMessage(text, isError = true) {
        message.textContent = text;
        message.style.color = isError ? "#b42318" : "#18794e";
    }

    async function requestJSON(url, options = {}) {
        const response = await fetch(url, {
            credentials: "same-origin",
            ...options,
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
                ...(options.headers || {})
            }
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Something went wrong.");
        }

        return data;
    }

    async function loadCart() {
        itemsContainer.textContent = "Loading your cart...";

        try {
            const data = await requestJSON("/orders/cart/", {
                method: "GET",
                headers: {}
            });

            cartItems = data.items || [];
            itemsContainer.replaceChildren();

            if (cartItems.length === 0) {
                // Check if items exist in localStorage and sync to server
                try {
                    const localSaved = JSON.parse(localStorage.getItem("tipsy_cart_website_guest_v1") || "[]");
                    if (Array.isArray(localSaved) && localSaved.length > 0) {
                        for (const it of localSaved) {
                            if (it.id && it.quantity) {
                                await fetch("/orders/cart/add/", {
                                    method: "POST",
                                    credentials: "same-origin",
                                    headers: {
                                        "Content-Type": "application/json",
                                        "X-CSRFToken": getCookie("csrftoken") || ""
                                    },
                                    body: JSON.stringify({
                                        product_id: it.id,
                                        quantity: it.quantity,
                                        variant_id: it.variant_id || null
                                    })
                                });
                            }
                        }
                        const refetched = await requestJSON("/orders/cart/", { method: "GET" });
                        if (refetched.items && refetched.items.length > 0) {
                            cartItems = refetched.items;
                        }
                    }
                } catch (e) {
                    console.warn("Could not auto-sync localStorage to backend:", e);
                }
            }

            if (cartItems.length === 0) {
                const empty = document.createElement("p");
                empty.textContent = "Your cart is empty. Please add products first.";
                itemsContainer.appendChild(empty);
                totalElement.textContent = "0.00";
                submitButton.disabled = true;
                return;
            }

            let total = 0;

            cartItems.forEach(item => {
                const price = Number(item.price);
                const quantity = Number(item.quantity);
                total += price * quantity;

                const row = document.createElement("div");
                row.className = "checkout-item";

                const name = document.createElement("span");
                const itemLabel = item.variant_title ? `${item.name} (${item.variant_title})` : (item.full_name || item.name);
                name.textContent = `${itemLabel} × ${quantity}`;

                const subtotal = document.createElement("span");
                subtotal.textContent = `₹${(price * quantity).toFixed(2)}`;

                row.append(name, subtotal);
                itemsContainer.appendChild(row);
            });

            currentRawTotal = total;
            if (appliedCoupon) {
                // If coupon was applied, re-verify with new total
                try {
                    const rec = await requestJSON("/orders/api/apply-coupon/", {
                        method: "POST",
                        body: JSON.stringify({ code: appliedCoupon.code, cart_total: currentRawTotal })
                    });
                    appliedCoupon = rec;
                    if (totalElement) totalElement.textContent = rec.new_total;
                    if (discountAmountVal) discountAmountVal.textContent = rec.discount_amount;
                } catch(e) {
                    appliedCoupon = null;
                    if (discountRow) discountRow.style.display = "none";
                    if (couponFeedback) couponFeedback.textContent = "";
                    totalElement.textContent = total.toFixed(2);
                }
            } else {
                totalElement.textContent = total.toFixed(2);
            }
            submitButton.disabled = false;
        } catch (error) {
            itemsContainer.textContent = error.message;
            submitButton.disabled = true;
        }
    }

    form.addEventListener("submit", async event => {
        event.preventDefault();
        showMessage("");

        if (cartItems.length === 0) {
            showMessage("Your cart is empty.");
            return;
        }

        if (!form.reportValidity()) {
            return;
        }

        const formData = new FormData(form);
        const payload = {
            full_name: formData.get("full_name").trim(),
            phone: formData.get("phone").trim(),
            address: formData.get("address").trim(),
            city: formData.get("city").trim(),
            state: formData.get("state").trim(),
            pincode: formData.get("pincode").trim(),
            payment_method: "COD",
            coupon_code: appliedCoupon ? appliedCoupon.code : ""
        };

        submitButton.disabled = true;
        submitButton.textContent = "Placing Order...";

        try {
            const result = await requestJSON(
                "/orders/checkout/place-order/",
                {
                    method: "POST",
                    body: JSON.stringify(payload)
                }
            );

            const modal = document.getElementById("order-success-modal");
            if (modal) {
                document.getElementById("modal-order-id").textContent = `#${result.order_id}`;
                document.getElementById("modal-order-total").textContent = `₹${result.total_amount}`;
                document.getElementById("modal-delivery-address").textContent = 
                    result.delivery_address || `${payload.full_name}, ${payload.address}, ${payload.city} - ${payload.pincode} (📞 ${payload.phone})`;
                
                const trackBtn = document.getElementById("modal-track-btn");
                if (trackBtn) {
                    trackBtn.href = result.redirect_url || `/dashboard/?order_placed=${result.order_id}#active-tracking`;
                }

                const itemsContainer = document.getElementById("modal-items-list");
                const itemsToShow = result.items && result.items.length ? result.items : cartItems;
                if (itemsContainer && itemsToShow.length) {
                    itemsContainer.innerHTML = itemsToShow.map(item => {
                        const itemName = item.name || item.product_name || "Product";
                        const varLabel = item.variant_title || item.variant_name || "";
                        const itemDisplayName = varLabel ? `${itemName} (${varLabel})` : itemName;
                        const itemQty = item.quantity || 1;
                        const itemPrice = item.price ? Number(item.price).toFixed(2) : "0.00";
                        const itemSub = item.subtotal ? Number(item.subtotal).toFixed(2) : (Number(itemPrice) * itemQty).toFixed(2);
                        const itemImg = item.image_url
                            ? `<img src="${item.image_url}" alt="${itemName}" class="modal-item-thumb" onerror="this.outerHTML='<span class=\\'modal-item-thumb\\'>🛍️</span>'">`
                            : `<span class="modal-item-thumb">🛍️</span>`;

                        return `
                            <div class="modal-item-row">
                                ${itemImg}
                                <div class="modal-item-meta">
                                    <strong>${itemDisplayName}</strong>
                                    <small>Qty: ${itemQty} &bull; ₹${itemPrice} each</small>
                                </div>
                                <strong style="color: #a52d55; font-size: 13px;">₹${itemSub}</strong>
                            </div>
                        `;
                    }).join("");
                }

                if (result.step_info) {
                    const stepBadge = document.getElementById("modal-step-badge");
                    if (stepBadge) {
                        stepBadge.textContent = `📍 Step ${result.step_info.step_num} of ${result.step_info.total_steps} Completed • ⏳ ${result.step_info.remaining} Steps Remaining`;
                    }
                }

                modal.style.display = "flex";
            } else {
                showMessage(`🎉 Order #${result.order_id} placed successfully!`, false);
                setTimeout(() => {
                    window.location.href = result.redirect_url || "/dashboard/";
                }, 1200);
            }

            try {
                localStorage.removeItem("tipsy_cart_website_guest_v1");
                if (window.updateGlobalCart) window.updateGlobalCart([]);
            } catch (e) {}

            form.reset();
            await loadCart();
        } catch (error) {
            showMessage(error.message);
        } finally {
            submitButton.textContent = "Place Order";
            submitButton.disabled = cartItems.length === 0;
        }
    });

    loadCart();
});
