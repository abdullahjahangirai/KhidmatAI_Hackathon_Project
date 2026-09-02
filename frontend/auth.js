/* ================================================================
   KhidmatAI — Authentication pages (auth.js)
   Real FastAPI auth: /api/auth/login · /api/auth/register ·
   /api/organizations/register
   ================================================================ */
(function () {
  "use strict";

  /* ---------- Shared theme ---------- */
  var root = document.documentElement;
  var body = document.body;
  var themeBtn = document.getElementById("themeToggle");
  var themeIcon = document.getElementById("themeIcon");

  function applyTheme(mode) {
    var dark = mode === "dark";
    root.classList.toggle("dark-mode", dark);
    body.classList.toggle("dark-mode", dark);
    if (themeIcon) themeIcon.textContent = dark ? "☀" : "☾";
  }
  applyTheme(localStorage.getItem("khidmat-theme") || "light");
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var next = root.classList.contains("dark-mode") ? "light" : "dark";
      localStorage.setItem("khidmat-theme", next);
      applyTheme(next);
    });
  }

  /* ---------- Helpers ---------- */
  var messageBox = document.getElementById("authMessage");

  function showAuthMessage(message, type) {
    if (!messageBox) return;
    messageBox.textContent = message;
    messageBox.className = "auth-message show " + (type || "error");
  }

  function clearAuthMessage() {
    if (!messageBox) return;
    messageBox.className = "auth-message";
    messageBox.textContent = "";
  }

  function validEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  }

  function friendlyError(err, fallback) {
    var msg = (err && err.message) || "";
    if (/failed to fetch|networkerror|load failed/i.test(msg)) {
      return "Cannot reach the KhidmatAI server. Please check your connection and try again.";
    }
    return msg || fallback;
  }

  function setBusy(form, busy, label) {
    var submit = form.querySelector(".form-submit");
    if (!submit) return;
    submit.disabled = busy;
    submit.textContent = busy ? label : submit.dataset.label || submit.textContent;
    if (!busy && submit.dataset.label) submit.textContent = submit.dataset.label;
  }

  function rememberSubmitLabel(form) {
    var submit = form.querySelector(".form-submit");
    if (submit && !submit.dataset.label) submit.dataset.label = submit.textContent;
  }

  /* ---------- Password visibility ---------- */
  document.querySelectorAll(".password-toggle").forEach(function (button) {
    button.addEventListener("click", function () {
      var input = document.getElementById(button.dataset.target);
      if (!input) return;
      var showing = input.type === "text";
      input.type = showing ? "password" : "text";
      button.textContent = showing ? "Show" : "Hide";
    });
  });

  /* ---------- Password strength ---------- */
  var regPassword = document.getElementById("regPassword");
  var strengthBar = document.getElementById("strengthBar");
  var strengthText = document.getElementById("strengthText");

  if (regPassword && strengthBar && strengthText) {
    regPassword.addEventListener("input", function () {
      var password = regPassword.value;
      var score = 0;
      if (password.length >= 8) score++;
      if (/[A-Z]/.test(password)) score++;
      if (/[0-9]/.test(password)) score++;
      if (/[^A-Za-z0-9]/.test(password)) score++;
      strengthBar.style.width = (score * 25) + "%";
      var labels = [
        "Use at least 8 characters.",
        "Weak password.",
        "Fair password.",
        "Good password.",
        "Strong password."
      ];
      strengthText.textContent = labels[score];
    });
  }

  /* ---------- Register page: tab switching ---------- */
  var tabIndividual = document.getElementById("tabIndividual");
  var tabOrganization = document.getElementById("tabOrganization");
  var registerForm = document.getElementById("registerForm");
  var orgForm = document.getElementById("orgForm");

  function switchRegTab(which) {
    var isOrg = which === "org";
    if (tabIndividual) {
      tabIndividual.classList.toggle("active", !isOrg);
      tabIndividual.setAttribute("aria-selected", String(!isOrg));
    }
    if (tabOrganization) {
      tabOrganization.classList.toggle("active", isOrg);
      tabOrganization.setAttribute("aria-selected", String(isOrg));
    }
    if (registerForm) registerForm.style.display = isOrg ? "none" : "block";
    if (orgForm) orgForm.style.display = isOrg ? "block" : "none";
    clearAuthMessage();
  }

  if (tabIndividual) tabIndividual.addEventListener("click", function () { switchRegTab("individual"); });
  if (tabOrganization) tabOrganization.addEventListener("click", function () { switchRegTab("org"); });

  /* ---------- Login ---------- */
  var loginForm = document.getElementById("loginForm");

  if (loginForm) {
    // Already signed in → straight to the dashboard
    try {
      var existing = JSON.parse(localStorage.getItem("kai_user") || "null");
      if (existing && existing.email) {
        location.replace("/dashboard");
        return;
      }
    } catch (e) { /* ignore malformed storage */ }

    // Signed in as an organization → straight to the org portal
    try {
      var existingOrg = JSON.parse(localStorage.getItem("kai_org") || "null");
      if (existingOrg && existingOrg.email) {
        location.replace("/org");
        return;
      }
    } catch (e) { /* ignore malformed storage */ }

    // Success notice carried over from registration
    try {
      var notice = sessionStorage.getItem("kh_auth_notice");
      if (notice) {
        sessionStorage.removeItem("kh_auth_notice");
        showAuthMessage(notice, "success");
      }
    } catch (e) { /* ignore */ }

    rememberSubmitLabel(loginForm);

    loginForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      clearAuthMessage();

      var email = document.getElementById("loginEmail").value.trim();
      var password = document.getElementById("loginPassword").value;

      if (!email || !password) {
        showAuthMessage("Please enter your email and password.", "error");
        return;
      }
      if (!validEmail(email)) {
        showAuthMessage("Please enter a valid email address.", "error");
        return;
      }

      setBusy(loginForm, true, "Signing in...");
      try {
        var r = await fetch("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: email, password: password })
        });
        var d = {};
        try { d = await r.json(); } catch (e) { /* non-JSON error */ }
        if (!r.ok) throw new Error(d.detail || "Invalid email or password.");

        var user = d.user || {};
        user.token = d.token || "";
        localStorage.setItem("kai_user", JSON.stringify(user));
        showAuthMessage("Signed in. Opening your dashboard...", "success");
        setTimeout(function () { location.replace("/dashboard"); }, 500);
      } catch (err) {
        setBusy(loginForm, false, "");
        showAuthMessage(friendlyError(err, "Login failed. Please try again."), "error");
      }
    });
  }

  /* ---------- Login page: Individual / Organization tabs ---------- */
  var loginTabIndividual = document.getElementById("loginTabIndividual");
  var loginTabOrganization = document.getElementById("loginTabOrganization");
  var orgLoginForm = document.getElementById("orgLoginForm");

  function switchLoginTab(which) {
    var isOrg = which === "org";
    if (loginTabIndividual) {
      loginTabIndividual.classList.toggle("active", !isOrg);
      loginTabIndividual.setAttribute("aria-selected", String(!isOrg));
    }
    if (loginTabOrganization) {
      loginTabOrganization.classList.toggle("active", isOrg);
      loginTabOrganization.setAttribute("aria-selected", String(isOrg));
    }
    if (loginForm) loginForm.style.display = isOrg ? "none" : "block";
    if (orgLoginForm) orgLoginForm.style.display = isOrg ? "block" : "none";
    clearAuthMessage();
  }

  if (loginTabIndividual) loginTabIndividual.addEventListener("click", function () { switchLoginTab("individual"); });
  if (loginTabOrganization) loginTabOrganization.addEventListener("click", function () { switchLoginTab("org"); });

  /* ---------- Organization login ---------- */
  if (orgLoginForm) {
    rememberSubmitLabel(orgLoginForm);

    orgLoginForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      clearAuthMessage();

      var email = document.getElementById("orgLoginEmail").value.trim();
      var password = document.getElementById("orgLoginPassword").value;

      if (!email || !password) {
        showAuthMessage("Please enter your organization email and password.", "error");
        return;
      }
      if (!validEmail(email)) {
        showAuthMessage("Please enter a valid email address.", "error");
        return;
      }

      setBusy(orgLoginForm, true, "Signing in...");
      try {
        var r = await fetch("/api/organizations/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: email, password: password })
        });
        var d = {};
        try { d = await r.json(); } catch (e) { /* non-JSON error */ }
        if (!r.ok) throw new Error(d.detail || "Invalid email or password.");

        var organization = d.organization || {};
        organization.token = d.token || "";
        localStorage.setItem("kai_org", JSON.stringify(organization));
        showAuthMessage("Signed in. Opening your organization dashboard...", "success");
        setTimeout(function () { location.replace("/org"); }, 500);
      } catch (err) {
        setBusy(orgLoginForm, false, "");
        showAuthMessage(friendlyError(err, "Login failed. Please try again."), "error");
      }
    });
  }

  /* ---------- Individual registration ---------- */
  if (registerForm) {
    rememberSubmitLabel(registerForm);

    registerForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      clearAuthMessage();

      var name = document.getElementById("regName").value.trim();
      var email = document.getElementById("regEmail").value.trim();
      var password = document.getElementById("regPassword").value;
      var confirm = document.getElementById("regConfirm").value;
      var phone = document.getElementById("regPhone").value.trim();
      var city = document.getElementById("regCity").value.trim();
      var cnic = document.getElementById("regCnic").value.trim();
      var terms = document.getElementById("acceptTerms").checked;

      if (!name || !email || !password || !confirm) {
        showAuthMessage("Please complete all required fields.", "error");
        return;
      }
      if (!validEmail(email)) {
        showAuthMessage("Please enter a valid email address.", "error");
        return;
      }
      if (password.length < 4) {
        showAuthMessage("Password must contain at least 4 characters.", "error");
        return;
      }
      if (password !== confirm) {
        showAuthMessage("Passwords do not match.", "error");
        return;
      }
      if (!terms) {
        showAuthMessage("Please accept the Terms of Service and Privacy Policy.", "error");
        return;
      }

      setBusy(registerForm, true, "Creating account...");
      try {
        var r = await fetch("/api/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: name, email: email, password: password,
            phone: phone, city: city, cnic: cnic
          })
        });
        var d = {};
        try { d = await r.json(); } catch (e) { /* non-JSON error */ }
        if (!r.ok) throw new Error(d.detail || "Registration failed.");

        showAuthMessage("Account created. Redirecting you to sign in...", "success");
        try { sessionStorage.setItem("kh_auth_notice", "Account created successfully. Please sign in."); } catch (e) { /* ignore */ }
        setTimeout(function () { location.replace("/login"); }, 1100);
      } catch (err) {
        setBusy(registerForm, false, "");
        showAuthMessage(friendlyError(err, "Registration failed. Please try again."), "error");
      }
    });
  }

  /* ---------- Organization registration ---------- */
  if (orgForm) {
    rememberSubmitLabel(orgForm);

    orgForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      clearAuthMessage();

      var body = {
        name: document.getElementById("regOrgName").value.trim(),
        org_type: document.getElementById("regOrgType").value,
        contact: document.getElementById("regOrgContact").value.trim(),
        email: document.getElementById("regOrgEmail").value.trim(),
        password: document.getElementById("regOrgPassword").value,
        address: document.getElementById("regOrgAddress").value.trim(),
        province: document.getElementById("regOrgProvince").value,
        description: document.getElementById("regOrgDesc").value.trim()
      };

      if (!body.name || !body.contact || !body.email || !body.address) {
        showAuthMessage("Please complete all required organization fields.", "error");
        return;
      }
      if (!validEmail(body.email)) {
        showAuthMessage("Please enter a valid organization email.", "error");
        return;
      }

      setBusy(orgForm, true, "Submitting...");
      try {
        var r = await fetch("/api/organizations/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body)
        });
        var d = {};
        try { d = await r.json(); } catch (e) { /* non-JSON error */ }
        if (!r.ok) throw new Error(d.detail || "Submission failed.");

        showAuthMessage(
          (d && d.message) ||
          "Registration submitted. Our admin team will review your organization before login is enabled.",
          "success"
        );
        orgForm.reset();
        setBusy(orgForm, false, "");
      } catch (err) {
        setBusy(orgForm, false, "");
        showAuthMessage(friendlyError(err, "Submission failed. Please try again."), "error");
      }
    });
  }
})();
