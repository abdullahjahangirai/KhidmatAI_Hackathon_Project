/* ================================================================
   KhidmatAI — Landing page behaviour (landing.js)
   Mobile nav · theme toggle · login-aware CTAs
   ================================================================ */
(function () {
  "use strict";

  /* ---------- Mobile navigation ---------- */
  var menuToggle = document.getElementById("menuToggle");
  var mainNav = document.getElementById("mainNav");

  if (menuToggle && mainNav) {
    menuToggle.addEventListener("click", function () {
      var isOpen = mainNav.classList.toggle("open");
      menuToggle.setAttribute("aria-expanded", String(isOpen));
    });
    mainNav.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () {
        mainNav.classList.remove("open");
        menuToggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  /* ---------- Shared theme (persisted, used across all pages) ---------- */
  var root = document.documentElement;
  var body = document.body;
  var themeBtn = document.getElementById("themeToggle");
  var themeIcon = document.getElementById("themeIcon");

  function applyTheme(mode) {
    var dark = mode === "dark";
    root.classList.toggle("dark-mode", dark);
    body.classList.toggle("dark-mode", dark);
    if (themeIcon) themeIcon.textContent = dark ? "☀" : "☾";
    if (themeBtn) {
      themeBtn.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
    }
  }

  applyTheme(localStorage.getItem("khidmat-theme") || "light");

  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var next = root.classList.contains("dark-mode") ? "light" : "dark";
      localStorage.setItem("khidmat-theme", next);
      applyTheme(next);
    });
  }

  /* ---------- Login-aware CTAs ----------
     Signed-in visitors are sent straight to the dashboard;
     new visitors keep the Sign in / Get started journey. */
  function currentUser() {
    try {
      return JSON.parse(localStorage.getItem("kai_user") || "null");
    } catch (e) {
      return null;
    }
  }

  var user = currentUser();

  if (user && user.email) {
    var navLogin = document.getElementById("navLogin");
    var navCta = document.getElementById("navCta");
    var heroPrimary = document.getElementById("heroPrimary");
    var storyCta = document.getElementById("storyCta");
    var ctaOpen = document.getElementById("ctaOpen");

    if (navLogin) navLogin.style.display = "none";
    if (navCta) {
      navCta.textContent = "Dashboard";
      navCta.setAttribute("href", "/dashboard");
    }
    function retargetCta(el, label) {
      if (!el) return;
      el.setAttribute("href", "/dashboard");
      while (el.firstChild) el.removeChild(el.firstChild);
      el.appendChild(document.createTextNode(label + " "));
      var arrow = document.createElement("span");
      arrow.textContent = "\u2192";
      el.appendChild(arrow);
    }
    retargetCta(heroPrimary, "Go to your dashboard");
    retargetCta(storyCta, "Open your dashboard");
    if (ctaOpen) ctaOpen.setAttribute("href", "/dashboard");
  }

  /* ---------- Live settings (admin-managed via /api/public/settings) ----------
     The HTML ships with sensible defaults; these are replaced by whatever
     the admin has saved, so the landing page always mirrors current settings. */
  function applyContactInfo(ci) {
    if (!ci) return;
    var phone = document.getElementById("contactPhone");
    if (phone && ci.phone) {
      phone.textContent = ci.phone;
      phone.setAttribute("href", "tel:" + String(ci.phone).replace(/[^\d+]/g, ""));
    }
    var email = document.getElementById("contactEmail");
    if (email && ci.email) {
      email.textContent = ci.email;
      email.setAttribute("href", "mailto:" + ci.email);
      var emailCta = document.getElementById("contactEmailCta");
      if (emailCta) emailCta.setAttribute("href", "mailto:" + ci.email);
    }
    var helpline = document.getElementById("contactHelpline");
    if (helpline && ci.helpline) {
      helpline.textContent = ci.helpline;
      helpline.setAttribute("href", "tel:" + String(ci.helpline).replace(/[^\d+]/g, ""));
    }
    var address = document.getElementById("contactAddress");
    if (address && ci.address) address.textContent = ci.address;
  }

  /* ---------- Landing hero slider (admin-managed, fully separate from the dashboard hero) ----------
     Each slide can override the headline, description, media (image or muted
     looping video) and the primary CTA. Empty fields keep the current content.
     With no slides saved the static hero markup stays exactly as authored. */
  function initLandingHero(slides) {
    if (!slides || !slides.length) return;
    var grid = document.querySelector(".hero-grid");
    if (!grid) return;

    var titleEl = document.getElementById("heroTitle");
    var textEl = document.getElementById("heroText");
    var ctaEl = document.getElementById("heroPrimary");
    var photoEl = document.querySelector(".hero-photo");
    var dotsWrap = document.getElementById("heroDots");
    var signedIn = !!(user && user.email);
    var idx = 0;
    var timer = null;

    function setMedia(s) {
      if (!photoEl) return;
      var media;
      if (s.video) {
        media = document.createElement("video");
        media.src = s.video;
        media.muted = true;
        media.autoplay = true;
        media.loop = true;
        media.playsInline = true;
      } else if (s.image) {
        media = document.createElement("img");
        media.src = s.image;
        media.alt = "KhidmatAI — support for Pakistan";
        media.loading = "eager";
      } else {
        return; // keep whatever is currently displayed
      }
      var old = photoEl.querySelector("img, video");
      if (old) old.replaceWith(media);
      else photoEl.appendChild(media);
    }

    function apply(s) {
      if (s.title && titleEl) titleEl.textContent = s.title;
      if (s.description && textEl) textEl.textContent = s.description;
      if (!signedIn && ctaEl && s.button_text) {
        if (ctaEl.firstChild && ctaEl.firstChild.nodeType === 3) {
          ctaEl.firstChild.nodeValue = s.button_text + " ";
        }
        if (s.button_url) ctaEl.setAttribute("href", s.button_url);
      }
      setMedia(s);
    }

    function renderDots() {
      if (!dotsWrap) return;
      if (slides.length < 2) { dotsWrap.style.display = "none"; return; }
      dotsWrap.style.display = "flex";
      dotsWrap.innerHTML = "";
      slides.forEach(function (s, i) {
        var d = document.createElement("button");
        d.type = "button";
        d.className = "hero-dot" + (i === idx ? " active" : "");
        d.setAttribute("aria-label", "Show slide " + (i + 1));
        d.addEventListener("click", function () { go(i); });
        dotsWrap.appendChild(d);
      });
    }

    function go(i, instant) {
      idx = (i + slides.length) % slides.length;
      if (instant) {
        apply(slides[idx]);
        renderDots();
        return;
      }
      grid.classList.add("hero-switching");
      setTimeout(function () {
        apply(slides[idx]);
        renderDots();
        grid.classList.remove("hero-switching");
      }, 320);
    }

    function startRotation() {
      if (timer) clearInterval(timer);
      timer = setInterval(function () {
        if (document.hidden) return;
        go(idx + 1);
      }, 6500);
    }

    go(0, true);
    if (slides.length > 1) {
      startRotation();
      var hero = document.querySelector(".hero");
      if (hero) {
        hero.addEventListener("mouseenter", function () { if (timer) clearInterval(timer); });
        hero.addEventListener("mouseleave", startRotation);
      }
    }
  }

  fetch("/api/public/settings")
    .then(function (res) { return res.ok ? res.json() : null; })
    .then(function (data) {
      if (!data) return;
      applyContactInfo(data.contact_info);
      initLandingHero(data.landing_hero_slides);
    })
    .catch(function () { /* offline or API unavailable — static defaults stay */ });

  /* ---------- Contact anchor: gentle scroll for sticky header ---------- */
  var contactLink = document.querySelector('.main-nav a[href="#contact"]');
  if (contactLink) {
    contactLink.addEventListener("click", function () {
      var target = document.getElementById("contact");
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }
})();
