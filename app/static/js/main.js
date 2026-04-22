(function () {
    "use strict";

    // ── Header scroll shadow ──────────────────────────────────────────────────
    var header = document.getElementById("site-header");
    if (header) {
        window.addEventListener("scroll", function () {
            if (window.scrollY > 8) {
                header.classList.add("scrolled");
            } else {
                header.classList.remove("scrolled");
            }
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

        // Close menu when a nav link is tapped on mobile
        navLinks.querySelectorAll("a").forEach(function (link) {
            link.addEventListener("click", function () {
                navLinks.classList.remove("open");
                burger.setAttribute("aria-expanded", "false");
            });
        });

        // Close when clicking outside the nav
        document.addEventListener("click", function (e) {
            if (!header.contains(e.target)) {
                navLinks.classList.remove("open");
                burger.setAttribute("aria-expanded", "false");
            }
        });
    }
})();
