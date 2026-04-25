(function () {
    "use strict";

    // ── Header scroll shadow ──────────────────────────────────────────────────
    var header = document.getElementById("site-header");
    if (header) {
        window.addEventListener("scroll", function () {
            header.classList.toggle("scrolled", window.scrollY > 8);
        }, { passive: true });
    }

    // ── Mobile burger menu ────────────────────────────────────────────────────
    var burger = document.getElementById("nav-burger");
    var navLinks = document.getElementById("nav-links");
    if (burger && navLinks) {
        burger.addEventListener("click", function () {
            var open = navLinks.classList.toggle("open");
            burger.setAttribute("aria-expanded", open ? "true" : "false");
        });
        navLinks.querySelectorAll("a").forEach(function (link) {
            link.addEventListener("click", function () {
                navLinks.classList.remove("open");
                burger.setAttribute("aria-expanded", "false");
            });
        });
        document.addEventListener("click", function (e) {
            if (!header.contains(e.target)) {
                navLinks.classList.remove("open");
                burger.setAttribute("aria-expanded", "false");
            }
        });
    }

    // ── Scroll reveal ─────────────────────────────────────────────────────────
    // Auto-tag elements that should reveal on scroll (not the hero — it has CSS animation)
    var revealGroups = [
        { sel: ".boat-card",          step: 75 },
        { sel: ".service-card",       step: 80 },
        { sel: ".accessory-card",     step: 60 },
        { sel: ".contact-card",       step: 80 },
        { sel: ".coverage-card",      step: 100 },
        { sel: ".spec-block",         step: 60 },
        { sel: ".doc-card",           step: 80 },
        { sel: ".section-head",       step: 0 },
        { sel: ".page-banner",        step: 0 },
        { sel: ".cta-band h2",        step: 0 },
        { sel: ".cta-band p",         step: 80 },
        { sel: ".cta-band .cta-row",  step: 160 },
        { sel: ".content-2col > *",   step: 120 },
        { sel: ".step-list li",       step: 80 },
        { sel: ".footer-col",         step: 60 },
    ];

    revealGroups.forEach(function (g) {
        document.querySelectorAll(g.sel).forEach(function (el, i) {
            if (el.classList.contains("reveal")) return;
            el.classList.add("reveal");
            el.style.setProperty("--reveal-delay", Math.min(i * g.step, 320) + "ms");
        });
    });

    if (window.IntersectionObserver) {
        var revealIO = new IntersectionObserver(function (entries) {
            entries.forEach(function (e) {
                if (e.isIntersecting) {
                    e.target.classList.add("visible");
                    revealIO.unobserve(e.target);
                }
            });
        }, { threshold: 0.1, rootMargin: "0px 0px -30px 0px" });

        document.querySelectorAll(".reveal").forEach(function (el) {
            revealIO.observe(el);
        });
    } else {
        // Fallback: just show everything
        document.querySelectorAll(".reveal").forEach(function (el) {
            el.classList.add("visible");
        });
    }

    // ── Counter animation ─────────────────────────────────────────────────────
    if (window.IntersectionObserver) {
        var countIO = new IntersectionObserver(function (entries) {
            entries.forEach(function (e) {
                if (!e.isIntersecting) return;
                var el = e.target;
                var target = parseFloat(el.dataset.count);
                var suffix = el.dataset.suffix !== undefined ? el.dataset.suffix : "";
                var decimals = (el.dataset.count.indexOf(".") >= 0)
                    ? el.dataset.count.split(".")[1].length : 0;
                var start = null, dur = 900;
                requestAnimationFrame(function tick(ts) {
                    if (!start) start = ts;
                    var p = Math.min((ts - start) / dur, 1);
                    // ease out cubic
                    var val = target * (1 - Math.pow(1 - p, 3));
                    el.textContent = val.toFixed(decimals) + suffix;
                    if (p < 1) requestAnimationFrame(tick);
                    else el.textContent = target.toFixed(decimals) + suffix;
                });
                countIO.unobserve(el);
            });
        }, { threshold: 0.6 });

        document.querySelectorAll("[data-count]").forEach(function (el) {
            // Store original text as suffix if data-suffix not set explicitly
            countIO.observe(el);
        });
    }

    // ── Hero parallax (desktop only, after entrance animation finishes) ───────
    setTimeout(function () {
        if (window.matchMedia("(max-width: 1023px)").matches) return;
        var visuals = document.querySelectorAll(".hero-visual-img");
        if (!visuals.length) return;
        var speeds = [0.05, 0.10, 0.07];
        var ticking = false;
        window.addEventListener("scroll", function () {
            if (ticking) return;
            requestAnimationFrame(function () {
                var y = window.scrollY;
                visuals.forEach(function (el, i) {
                    el.style.transform = "translateY(" + (y * speeds[i]) + "px)";
                });
                ticking = false;
            });
            ticking = true;
        }, { passive: true });
    }, 1400);

})();
