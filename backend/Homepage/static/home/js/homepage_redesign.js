/**
 * TipsyCart Homepage Redesign Client Script
 * Handles hero carousel, horizontal scroll rails, deals countdown timer,
 * and Explore Categories tab switching.
 */
document.addEventListener("DOMContentLoaded", () => {
    // 1. HORIZONTAL RAIL SCROLL HELPERS
    function setupRailControls(railSelector, prevBtnSelector, nextBtnSelector, scrollStep = 320) {
        const rail = document.querySelector(railSelector);
        const prevBtn = document.querySelector(prevBtnSelector);
        const nextBtn = document.querySelector(nextBtnSelector);

        if (!rail) return;

        if (prevBtn) {
            prevBtn.addEventListener("click", (e) => {
                e.preventDefault();
                rail.scrollBy({ left: -scrollStep, behavior: "smooth" });
            });
        }
        if (nextBtn) {
            nextBtn.addEventListener("click", (e) => {
                e.preventDefault();
                rail.scrollBy({ left: scrollStep, behavior: "smooth" });
            });
        }
    }

    // Connect rails
    setupRailControls("#tc-category-rail", "#tc-cat-prev", "#tc-cat-next", 280);
    setupRailControls("#tc-deals-rail", "#tc-deals-prev", "#tc-deals-next", 340);
    setupRailControls("#tc-explore-rail", "#tc-explore-prev", "#tc-explore-next", 340);

    // 2. TODAY'S DEALS COUNTDOWN TIMER (ADMIN-CONTROLLED & DYNAMIC)
    const countdownEl = document.getElementById("tc-deals-countdown");
    if (countdownEl) {
        const badgeEl = countdownEl.closest(".tc-countdown-badge");
        const dealsMode = badgeEl?.getAttribute("data-deals-mode") || "daily_midnight";
        const dealsEndStr = badgeEl?.getAttribute("data-deals-end") || "";

        function updateCountdown() {
            const now = new Date();
            let targetTime;

            if (dealsMode === "fixed_datetime" && dealsEndStr) {
                targetTime = new Date(dealsEndStr);
            } else {
                // Default: Daily midnight reset
                targetTime = new Date(now);
                targetTime.setHours(24, 0, 0, 0);
            }

            let diffMs = targetTime - now;
            if (diffMs <= 0) {
                countdownEl.textContent = "00 : 00 : 00";
                return;
            }

            const totalSec = Math.floor(diffMs / 1000);
            const days = Math.floor(totalSec / 86400);
            const hours = Math.floor((totalSec % 86400) / 3600);
            const minutes = Math.floor((totalSec % 3600) / 60);
            const seconds = totalSec % 60;

            const pad = (n) => String(n).padStart(2, "0");

            if (days > 0) {
                countdownEl.textContent = `${days}d : ${pad(hours)}h : ${pad(minutes)}m : ${pad(seconds)}s`;
            } else {
                countdownEl.textContent = `${pad(hours)} : ${pad(minutes)} : ${pad(seconds)}`;
            }
        }
        updateCountdown();
        setInterval(updateCountdown, 1000);
    }

    // 3. EXPLORE CATEGORIES TAB SWITCHING
    const tabChips = document.querySelectorAll(".tc-tab-chip");
    const explorePanels = document.querySelectorAll(".tc-explore-panel");
    const viewAllLink = document.querySelector(".tc-explore-view-all");

    tabChips.forEach((chip) => {
        chip.addEventListener("click", () => {
            const targetSlug = chip.getAttribute("data-category-slug");

            tabChips.forEach(c => c.classList.remove("active"));
            chip.classList.add("active");

            explorePanels.forEach(panel => {
                if (panel.getAttribute("data-panel-slug") === targetSlug) {
                    panel.classList.add("active");
                } else {
                    panel.classList.remove("active");
                }
            });

            if (viewAllLink && targetSlug) {
                viewAllLink.href = `/shop/?category=${encodeURIComponent(targetSlug)}`;
            }

            // Sync any cart steppers in newly revealed panel
            if (window.syncAllCardSteppers) {
                window.syncAllCardSteppers();
            }
        });
    });

    // 4. HERO SLIDER LOGIC (IF MULTIPLE BANNERS)
    const heroSlider = document.querySelector(".tc-hero-slider");
    if (heroSlider) {
        const slides = heroSlider.querySelectorAll(".tc-hero-slide");
        const dots = document.querySelectorAll(".tc-hero-dot");
        const prevArrow = document.querySelector(".tc-hero-prev");
        const nextArrow = document.querySelector(".tc-hero-next");
        let currentIndex = 0;
        let autoPlayTimer = null;

        function showSlide(index) {
            if (!slides.length) return;
            if (index < 0) index = slides.length - 1;
            if (index >= slides.length) index = 0;
            currentIndex = index;

            slides.forEach((slide, i) => {
                slide.style.display = i === currentIndex ? "flex" : "none";
            });

            dots.forEach((dot, i) => {
                dot.classList.toggle("active", i === currentIndex);
            });
        }

        if (slides.length > 1) {
            showSlide(0);

            if (prevArrow) {
                prevArrow.addEventListener("click", () => {
                    clearInterval(autoPlayTimer);
                    showSlide(currentIndex - 1);
                    startAutoPlay();
                });
            }
            if (nextArrow) {
                nextArrow.addEventListener("click", () => {
                    clearInterval(autoPlayTimer);
                    showSlide(currentIndex + 1);
                    startAutoPlay();
                });
            }
            dots.forEach((dot, i) => {
                dot.addEventListener("click", () => {
                    clearInterval(autoPlayTimer);
                    showSlide(i);
                    startAutoPlay();
                });
            });

            function startAutoPlay() {
                autoPlayTimer = setInterval(() => {
                    showSlide(currentIndex + 1);
                }, 6000);
            }
            startAutoPlay();
        }
    }

    // 5. MOBILE CATEGORY "VIEW ALL / SHOW LESS" TOGGLE
    const catToggleBtn = document.getElementById("tc-cat-toggle-more");
    const catRail = document.getElementById("tc-category-rail");
    if (catToggleBtn && catRail) {
        catToggleBtn.addEventListener("click", () => {
            const isExpanded = catRail.classList.toggle("tc-show-all-mobile");
            const textSpan = catToggleBtn.querySelector(".tc-cat-more-text");
            const arrowSpan = catToggleBtn.querySelector(".tc-cat-more-arrow");
            if (isExpanded) {
                if (textSpan) textSpan.textContent = "Show Less Categories";
                if (arrowSpan) arrowSpan.textContent = "↑";
            } else {
                const total = catRail.querySelectorAll(".tc-cat-card-item").length;
                if (textSpan) textSpan.textContent = `View All Categories (${total})`;
                if (arrowSpan) arrowSpan.textContent = "↓";
            }
        });
    }
});
