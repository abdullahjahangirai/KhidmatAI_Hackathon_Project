(function () {
    "use strict";

    const toast = document.getElementById("toast");

    function showToast(message) {
        if (!toast) return;

        toast.textContent = message;
        toast.classList.add("show");

        clearTimeout(window.khToastTimer);
        window.khToastTimer = setTimeout(function () {
            toast.classList.remove("show");
        }, 2600);
    }

    function showAuthMessage(message, type) {
        const box = document.getElementById("authMessage");
        if (!box) return;

        box.textContent = message;
        box.className = "auth-message show " + (type || "error");
    }

    function validEmail(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    }

    function delay(ms) {
        return new Promise(function (resolve) {
            setTimeout(resolve, ms);
        });
    }

    /* Mobile navigation */
    const menuToggle = document.getElementById("menuToggle");
    const mainNav = document.getElementById("mainNav");

    if (menuToggle && mainNav) {
        menuToggle.addEventListener("click", function () {
            const isOpen = mainNav.classList.toggle("open");
            menuToggle.setAttribute("aria-expanded", String(isOpen));
        });

        mainNav.querySelectorAll("a").forEach(function (link) {
            link.addEventListener("click", function () {
                mainNav.classList.remove("open");
                menuToggle.setAttribute("aria-expanded", "false");
            });
        });
    }

    /* Language selector */
    const languageBtn = document.getElementById("languageBtn");
    const languageMenu = document.getElementById("languageMenu");
    const languageLabel = document.getElementById("languageLabel");

    if (languageBtn && languageMenu) {
        languageBtn.addEventListener("click", function (event) {
            event.stopPropagation();
            languageMenu.classList.toggle("open");
        });

        languageMenu.querySelectorAll("[data-language]").forEach(function (option) {
            option.addEventListener("click", function () {
                const language = option.dataset.language;

                if (languageLabel) {
                    languageLabel.textContent = language;
                }

                languageMenu.classList.remove("open");
                showToast("Selected language: " + language);
            });
        });

        document.addEventListener("click", function () {
            languageMenu.classList.remove("open");
        });
    }

    /* Category buttons */
    document.querySelectorAll("[data-category]").forEach(function (button) {
        button.addEventListener("click", function () {
            showToast(
                button.dataset.category +
                " support will be connected to the AI search flow next."
            );
        });
    });

    /* Password visibility */
    document.querySelectorAll(".password-toggle").forEach(function (button) {
        button.addEventListener("click", function () {
            const input = document.getElementById(button.dataset.target);
            if (!input) return;

            const showing = input.type === "text";
            input.type = showing ? "password" : "text";
            button.textContent = showing ? "Show" : "Hide";
        });
    });

    /* Forgot password */
    const forgotPassword = document.getElementById("forgotPassword");

    if (forgotPassword) {
        forgotPassword.addEventListener("click", function (event) {
            event.preventDefault();
            showAuthMessage(
                "Password reset will be connected to the backend in the authentication step.",
                "error"
            );
        });
    }

    /* Login */
    const loginForm = document.getElementById("loginForm");

    if (loginForm) {
        loginForm.addEventListener("submit", async function (event) {
            event.preventDefault();

            const email = document.getElementById("loginEmail").value.trim();
            const password = document.getElementById("loginPassword").value;
            const submit = loginForm.querySelector(".form-submit");

            if (!email || !password) {
                showAuthMessage("Please enter your email and password.", "error");
                return;
            }

            if (!validEmail(email)) {
                showAuthMessage("Please enter a valid email address.", "error");
                return;
            }

            submit.disabled = true;
            submit.textContent = "Signing in...";

            await delay(650);

            submit.disabled = false;
            submit.textContent = "Sign in";

            showAuthMessage(
                "Frontend is ready. Real login will be connected to FastAPI next.",
                "success"
            );
        });
    }

    /* Register */
    const registerForm = document.getElementById("registerForm");

    if (registerForm) {
        registerForm.addEventListener("submit", async function (event) {
            event.preventDefault();

            const firstName = document.getElementById("firstName").value.trim();
            const lastName = document.getElementById("lastName").value.trim();
            const email = document.getElementById("registerEmail").value.trim();
            const password = document.getElementById("registerPassword").value;
            const confirmPassword = document.getElementById("confirmPassword").value;
            const terms = document.getElementById("acceptTerms").checked;
            const submit = registerForm.querySelector(".form-submit");

            if (!firstName || !lastName || !email || !password || !confirmPassword) {
                showAuthMessage("Please complete all required fields.", "error");
                return;
            }

            if (!validEmail(email)) {
                showAuthMessage("Please enter a valid email address.", "error");
                return;
            }

            if (password.length < 8) {
                showAuthMessage("Password must contain at least 8 characters.", "error");
                return;
            }

            if (password !== confirmPassword) {
                showAuthMessage("Passwords do not match.", "error");
                return;
            }

            if (!terms) {
                showAuthMessage(
                    "Please accept the Terms of Service and Privacy Policy.",
                    "error"
                );
                return;
            }

            submit.disabled = true;
            submit.textContent = "Creating account...";

            await delay(650);

            submit.disabled = false;
            submit.textContent = "Create account";

            showAuthMessage(
                "Frontend is ready. Real registration will be connected to FastAPI next.",
                "success"
            );
        });
    }

    /* Password strength */
    const registerPassword = document.getElementById("registerPassword");
    const strengthBar = document.getElementById("strengthBar");
    const strengthText = document.getElementById("strengthText");

    if (registerPassword && strengthBar && strengthText) {
        registerPassword.addEventListener("input", function () {
            const password = registerPassword.value;
            let score = 0;

            if (password.length >= 8) score++;
            if (/[A-Z]/.test(password)) score++;
            if (/[0-9]/.test(password)) score++;
            if (/[^A-Za-z0-9]/.test(password)) score++;

            strengthBar.style.width = (score * 25) + "%";

            const labels = [
                "Use at least 8 characters.",
                "Weak password.",
                "Fair password.",
                "Good password.",
                "Strong password."
            ];

            strengthText.textContent = labels[score];
        });
    }

    /* Google placeholders */
    ["googleLogin", "googleRegister"].forEach(function (id) {
        const button = document.getElementById(id);

        if (button) {
            button.addEventListener("click", function () {
                showAuthMessage(
                    "Google authentication will be connected in the backend step.",
                    "error"
                );
            });
        }
    });
})();



/* =========================
   KhidmatAI Dashboard UI
   ========================= */

(function () {
  const sections = [...document.querySelectorAll('.dashboard-section')];
  const navLinks = [...document.querySelectorAll('.dash-nav-link[data-section]')];
  const pageTitle = document.getElementById('pageTitle');
  const sidebar = document.getElementById('dashboardSidebar');
  const sidebarToggle = document.getElementById('sidebarToggle');
  const toast = document.getElementById('dashboardToast');

  if (!sections.length) return;

  const titles = {
    overview: 'Overview',
    assistant: 'AI Assistant',
    eligibility: 'Eligibility Checker',
    programs: 'Welfare Programs',
    nearby: 'Nearby Help',
    saved: 'Saved Reports',
    emergency: 'Emergency Support'
  };

  function showSection(name, updateHash = true) {
    const target = document.getElementById(name) || document.getElementById('overview');
    const targetName = target.id;

    sections.forEach(section => {
      section.classList.toggle('active-section', section.id === targetName);
    });

    navLinks.forEach(link => {
      link.classList.toggle('active', link.dataset.section === targetName);
    });

    if (pageTitle) pageTitle.textContent = titles[targetName] || 'Overview';

    if (updateHash) {
      history.replaceState(null, '', '#' + targetName);
    }

    if (sidebar) sidebar.classList.remove('open');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  navLinks.forEach(link => {
    link.addEventListener('click', function (event) {
      event.preventDefault();
      showSection(this.dataset.section);
    });
  });

  document.querySelectorAll('[data-action]').forEach(button => {
    button.addEventListener('click', function () {
      showSection(this.dataset.action);
    });
  });

  if (sidebarToggle) {
    sidebarToggle.addEventListener('click', () => sidebar.classList.toggle('open'));
  }

  document.querySelectorAll('.suggestion').forEach(button => {
    button.addEventListener('click', () => {
      const input = document.getElementById('assistantInput');
      if (input) {
        input.value = button.textContent.trim();
        input.focus();
      }
    });
  });

  document.querySelectorAll('.choice-card').forEach(button => {
    button.addEventListener('click', () => {
      document.querySelectorAll('.choice-card').forEach(item => item.classList.remove('selected'));
      button.classList.add('selected');
      showToast('Selection saved. The eligibility flow will continue after backend integration.');
    });
  });

  document.querySelectorAll('.filter').forEach(button => {
    button.addEventListener('click', () => {
      document.querySelectorAll('.filter').forEach(item => item.classList.remove('active'));
      button.classList.add('active');
    });
  });

  const askAssistant = document.getElementById('askAssistant');
  if (askAssistant) {
    askAssistant.addEventListener('click', () => {
      const input = document.getElementById('assistantInput');
      const value = input ? input.value.trim() : '';
      if (!value) {
        showToast('Please type a question first.');
        input?.focus();
        return;
      }
      showToast('Your question is ready. AI backend will be connected next.');
    });
  }

  const notificationBtn = document.getElementById('notificationBtn');
  if (notificationBtn) {
    notificationBtn.addEventListener('click', () => {
      showToast('No new notifications.');
    });
  }

  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(window.khToastTimer);
    window.khToastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
  }

  const initial = window.location.hash.replace('#', '');
  showSection(titles[initial] ? initial : 'overview', false);
})();



/* =========================
   Shared theme + location
   ========================= */
(function () {
  const root = document.documentElement;
  const body = document.body;
  const themeBtn = document.getElementById("themeToggle");
  const themeIcon = document.getElementById("themeIcon");

  function applyTheme(mode) {
    const dark = mode === "dark";
    root.classList.toggle("dark-mode", dark);
    body.classList.toggle("dark-mode", dark);
    if (themeIcon) themeIcon.textContent = dark ? "☀" : "☾";
    if (themeBtn) themeBtn.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
  }

  const savedTheme = localStorage.getItem("khidmat-theme");
  applyTheme(savedTheme || "light");

  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      const next = root.classList.contains("dark-mode") ? "light" : "dark";
      localStorage.setItem("khidmat-theme", next);
      applyTheme(next);
    });
  }

  const locationBtn = document.getElementById("useLocation");
  if (locationBtn) {
    locationBtn.addEventListener("click", function () {
      if (!navigator.geolocation) {
        window.open("https://www.google.com/maps/search/welfare+support+near+me/", "_blank", "noopener");
        return;
      }
      locationBtn.disabled = true;
      locationBtn.textContent = "Finding you…";

      navigator.geolocation.getCurrentPosition(
        function (position) {
          const lat = position.coords.latitude;
          const lng = position.coords.longitude;
          const mapsUrl = "https://www.google.com/maps/search/welfare+support/@"
            + lat + "," + lng + ",14z";
          window.open(mapsUrl, "_blank", "noopener");
          locationBtn.disabled = false;
          locationBtn.textContent = "Use my location →";
        },
        function () {
          window.open("https://www.google.com/maps/search/welfare+support+near+me/", "_blank", "noopener");
          locationBtn.disabled = false;
          locationBtn.textContent = "Use my location →";
        },
        { enableHighAccuracy: true, timeout: 8000 }
      );
    });
  }
})();
