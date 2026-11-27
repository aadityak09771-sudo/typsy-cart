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
    setupRailControls("#tc-explore-rail", "#tc-explore-prev", "#tc-explore-next", 340);

    // 1B. SEAMLESS INFINITE CONTINUOUS AUTO-SCROLLER FOR TODAY'S DEALS
    function setupInfiniteDealsScroller() {
        const rail = document.querySelector("#tc-deals-rail");
        const prevBtn = document.querySelector("#tc-deals-prev");
        const nextBtn = document.querySelector("#tc-deals-next");
        if (!rail) return;

        const originalCards = Array.from(rail.querySelectorAll(".tc-product-card-wrap:not([data-clone='true'])"));
        if (originalCards.length < 2) return;

        // Clone cards to create an unbroken seamless infinite loop (2 cloned sets = 3 sets total)
        for (let s = 0; s < 2; s++) {
            originalCards.forEach((card) => {
                const clone = card.cloneNode(true);
                clone.setAttribute("data-clone", "true");
                clone.querySelectorAll("[id]").forEach((el) => el.removeAttribute("id"));
                rail.appendChild(clone);
            });
        }

        // Sync stepper states on all cards (including the newly added clones)
        if (window.syncAllCardSteppers) {
            window.syncAllCardSteppers();
        }

        // Measure single set width (sum of outer widths of original cards + gaps)
        let singleSetWidth = 0;
        function calculateSingleSetWidth() {
            let total = 0;
            const gap = parseFloat(window.getComputedStyle(rail).gap) || 18;
            originalCards.forEach((card) => {
                total += card.getBoundingClientRect().width + gap;
            });
            if (total > 0) singleSetWidth = total;
        }

        calculateSingleSetWidth();
        window.addEventListener("resize", calculateSingleSetWidth);
        window.addEventListener("load", calculateSingleSetWidth);

        // Continuous scrolling state
        let isPaused = false;
        let resumeTimer = null;
        const scrollSpeed = 0.85; // Pixels per frame (~50px/sec: silky-smooth, readable pace)

        function pauseTemporarily(durationMs = 2500) {
            isPaused = true;
            if (resumeTimer) clearTimeout(resumeTimer);
            resumeTimer = setTimeout(() => {
                isPaused = false;
            }, durationMs);
        }

        function tick() {
            if (!isPaused) {
                rail.scrollLeft += scrollSpeed;

                // When scrolled past the first full set, seamlessly wrap back to 0
                // Because the cloned set is identical down to the exact pixel, ZERO jump occurs!
                if (singleSetWidth > 0 && rail.scrollLeft >= singleSetWidth) {
                    rail.scrollLeft -= singleSetWidth;
                }
            }
            requestAnimationFrame(tick);
        }

        requestAnimationFrame(tick);

        // Pause on mouse hover (so customer can browse or add to cart without moving target)
        rail.addEventListener("mouseenter", () => {
            isPaused = true;
            if (resumeTimer) clearTimeout(resumeTimer);
        });

        rail.addEventListener("mouseleave", () => {
            if (resumeTimer) clearTimeout(resumeTimer);
            resumeTimer = setTimeout(() => {
                isPaused = false;
            }, 400);
        });

        // Touch & pointer interactions (mobile drag / swipe)
        rail.addEventListener("touchstart", () => {
            isPaused = true;
            if (resumeTimer) clearTimeout(resumeTimer);
        }, { passive: true });

        rail.addEventListener("touchend", () => {
            pauseTemporarily(2000);
        }, { passive: true });

        // Prev & Next navigation buttons
        if (prevBtn) {
            prevBtn.addEventListener("click", (e) => {
                e.preventDefault();
                pauseTemporarily(2500);
                const step = 260;
                if (singleSetWidth > 0 && rail.scrollLeft - step <= 0) {
                    rail.scrollLeft += singleSetWidth;
                }
                rail.scrollBy({ left: -step, behavior: "smooth" });
            });
        }

        if (nextBtn) {
            nextBtn.addEventListener("click", (e) => {
                e.preventDefault();
                pauseTemporarily(2500);
                const step = 260;
                if (singleSetWidth > 0 && rail.scrollLeft + step >= singleSetWidth * 2) {
                    rail.scrollLeft -= singleSetWidth;
                }
                rail.scrollBy({ left: step, behavior: "smooth" });
            });
        }
    }

    setupInfiniteDealsScroller();

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
