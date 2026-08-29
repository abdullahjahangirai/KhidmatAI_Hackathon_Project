const state = {
  saved: [],
  language: 'english',
  theme: 'light',
  evidence: [],
  autoTts: false,
  map: null,
  markersLayer: null,
  currentSlide: 0
};

const i18n = {
  english: {
    nav_dashboard: "Dashboard",
    nav_assistant: "AI Assistant",
    nav_eligibility: "Eligibility",
    nav_nearby: "Find Nearby",
    nav_programs: "Programs",
    nav_saved: "Saved",
    nav_emergency: "Emergency",
    nav_about: "About Us",
    nav_contact: "Contact",
    nav_settings: "Settings",
    nav_help: "Help"
  },
  roman: {
    nav_dashboard: "Dashboard",
    nav_assistant: "AI Madadgar",
    nav_eligibility: "Aheliyat",
    nav_nearby: "Qareebi Talash",
    nav_programs: "Programs",
    nav_saved: "Mehfooz",
    nav_emergency: "Hangaami",
    nav_about: "Hamare Baare Mein",
    nav_contact: "Rabta",
    nav_settings: "Settings",
    nav_help: "Madad"
  },
  urdu: {
    nav_dashboard: "ڈیش بورڈ",
    nav_assistant: "اے آئی مددگار",
    nav_eligibility: "اہلیت",
    nav_nearby: "قریبی تلاش",
    nav_programs: "پروگرامز",
    nav_saved: "محفوظ",
    nav_emergency: "ہنگامی",
    nav_about: "ہمارے بارے میں",
    nav_contact: "رابطہ",
    nav_settings: "ترتیبات",
    nav_help: "مدد"
  }
};

function getLanguage() {
  return state.language;
}

function setLanguage(val) {
  if (!['english', 'roman', 'urdu'].includes(val)) {
    val = 'english';
  }
  state.language = val;
  document.getElementById('languageSelector').value = val;
  applyTranslations(val);
}

function applyTranslations(lang) {
  const dict = i18n[lang] || i18n['english'];
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (dict[key]) {
      el.textContent = dict[key];
    }
  });
}

function openPage(pageId) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  
  const targetPage = document.getElementById(`page-${pageId}`);
  if (targetPage) {
    targetPage.classList.add('active');
  }
  
  const navItem = document.querySelector(`.nav-item[data-page="${pageId}"]`);
  if (navItem) {
    navItem.classList.add('active');
    const titleKey = navItem.querySelector('[data-i18n]')?.getAttribute('data-i18n');
    if (titleKey) {
      document.getElementById('pageTitle').setAttribute('data-i18n', titleKey);
      applyTranslations(state.language);
    }
  }

  if (window.innerWidth <= 768) {
    document.getElementById('sidebar').classList.remove('open');
  }

  if (pageId === 'nearby') {
    setTimeout(initMapIfNeeded, 100);
  }
  if (pageId === 'programs') {
    loadPrograms();
  }
  if (pageId === 'saved') {
    loadSaved();
  }
}

// Hero Slider Logic
let slideInterval;
function initHeroSlider(slides) {
  const slider = document.getElementById('heroSlider');
  const dotsContainer = document.getElementById('sliderDots');
  if (!slides || slides.length === 0) return;

  slider.innerHTML = '';
  dotsContainer.innerHTML = '';

  slides.forEach((slide, index) => {
    const div = document.createElement('div');
    div.className = `hero-slide ${index === 0 ? 'active' : ''}`;
    div.style.backgroundImage = `url('${slide.url}')`;
    div.innerHTML = `
      <div class="hero-slide-content">
        <h1 class="hero-heading">${slide.caption || 'KhidmatAI'}</h1>
      </div>
    `;
    slider.appendChild(div);

    const dot = document.createElement('div');
    dot.className = `dot ${index === 0 ? 'active' : ''}`;
    dot.onclick = () => goToSlide(index);
    dotsContainer.appendChild(dot);
  });

  state.currentSlide = 0;
  
  clearInterval(slideInterval);
  slideInterval = setInterval(() => nextSlide(), 5000);
}

function goToSlide(index) {
  const slides = document.querySelectorAll('.hero-slide');
  const dots = document.querySelectorAll('.dot');
  if (slides.length === 0) return;
  
  slides[state.currentSlide].classList.remove('active');
  if (dots[state.currentSlide]) dots[state.currentSlide].classList.remove('active');
  
  state.currentSlide = (index + slides.length) % slides.length;
  
  slides[state.currentSlide].classList.add('active');
  if (dots[state.currentSlide]) dots[state.currentSlide].classList.add('active');
}

function nextSlide() {
  goToSlide(state.currentSlide + 1);
}
function prevSlide() {
  goToSlide(state.currentSlide - 1);
}

async function loadHeroContent() {
  try {
    const res = await fetch('/api/public/settings');
    const data = await res.json();
    if (data.hero_slides && data.hero_slides.length > 0) {
      initHeroSlider(data.hero_slides);
    }
    if (data.ticker_text) {
      initTicker([data.ticker_text]);
    }
  } catch (e) {
    console.error("Could not load settings", e);
  }
}

function initTicker(textArray) {
  const track = document.getElementById('tickerTrack');
  track.innerHTML = '';
  const text = textArray.join(' | ');
  for (let i = 0; i < 3; i++) {
    const span = document.createElement('span');
    span.textContent = text + ' | ';
    span.style.paddingRight = '50px';
    track.appendChild(span);
  }
}

// Chat UI Placeholder
function quickAsk(msg) {
  document.getElementById('chatInput').value = msg;
  sendChat();
}

function sendChat() {
  const input = document.getElementById('chatInput');
  const val = input.value.trim();
  if (!val) return;
  
  const history = document.getElementById('chatHistory');
  const userMsg = document.createElement('div');
  userMsg.className = 'chat-msg user';
  userMsg.textContent = val;
  history.appendChild(userMsg);
  
  input.value = '';
  
  setTimeout(() => renderAnswer("This is a mock response."), 500);
}

function renderAnswer(text) {
  const history = document.getElementById('chatHistory');
  const botMsg = document.createElement('div');
  botMsg.className = 'chat-msg bot';
  botMsg.textContent = text;
  history.appendChild(botMsg);
  history.scrollTop = history.scrollHeight;
}

function renderEvidence() {}

function checkEligibilityWizard() {
  const cnic = document.getElementById('eligibilityCnic').value;
  const income = document.getElementById('eligibilityIncome').value;
  const result = document.getElementById('eligibilityResult');
  
  if (!cnic) {
    result.innerHTML = `<div style="color:var(--danger)">Please enter CNIC.</div>`;
    return;
  }
  
  result.innerHTML = `<div style="color:var(--primary)"><i class="fa-solid fa-circle-check"></i> Based on your profile, you are eligible for 3 programs.</div>`;
}

// Map Logic Placeholder
function initMapIfNeeded() {
  if (state.map) return;
  state.map = L.map('mapView').setView([30.3753, 69.3451], 5);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(state.map);
  state.markersLayer = L.layerGroup().addTo(state.map);
}

function searchNearbyMap() {
  if (!state.map) initMapIfNeeded();
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(pos => {
      const { latitude, longitude } = pos.coords;
      state.map.setView([latitude, longitude], 13);
      L.marker([latitude, longitude]).addTo(state.markersLayer)
        .bindPopup('You are here.').openPopup();
    });
  }
}

function loadPrograms() {
  const grid = document.getElementById('programsGrid');
  if (grid.children.length > 0) return; // already loaded mock
  const mockPrograms = [
    { title: "BISP", org: "Govt", type: "Finance" },
    { title: "Edhi Relief", org: "Edhi", type: "Food" }
  ];
  grid.innerHTML = mockPrograms.map(p => `
    <div class="program-card">
      <h4>${p.title}</h4>
      <p class="mb-2" style="color:var(--muted)">${p.org} - ${p.type}</p>
      <button class="btn btn-outline-white" style="color:var(--primary); border-color:var(--primary)">View Details</button>
    </div>
  `).join('');
}

function loadSaved() {
  const list = document.getElementById('savedList');
  list.innerHTML = '<p>No saved programs yet.</p>';
}

function loadEmergency() {}

function speakMessage() {}

async function submitOrgRegistration() {
  const payload = {
    name: document.getElementById('regOrgName').value,
    type: document.getElementById('regOrgType').value,
    contact: document.getElementById('regOrgContact').value,
    email: document.getElementById('regOrgEmail').value,
    address: document.getElementById('regOrgAddress').value,
    province: document.getElementById('regOrgProvince').value,
    description: document.getElementById('regOrgDesc').value
  };
  
  try {
    const res = await fetch('/api/organizations/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      alert("Registration submitted successfully!");
      document.getElementById('page-register').querySelector('form').reset();
    } else {
      alert("Error submitting registration.");
    }
  } catch (e) {
    alert("Error submitting registration.");
  }
}

document.addEventListener('DOMContentLoaded', () => {
  setLanguage(state.language);
  loadHeroContent();
  
  document.getElementById('languageSelector').addEventListener('change', (e) => {
    setLanguage(e.target.value);
  });
  
  document.getElementById('hamburgerBtn').addEventListener('click', () => {
    document.getElementById('sidebar').classList.toggle('open');
  });
  
  document.getElementById('themeToggle').addEventListener('click', () => {
    document.body.classList.toggle('dark');
    state.theme = document.body.classList.contains('dark') ? 'dark' : 'light';
  });

  document.getElementById('sliderPrev').addEventListener('click', prevSlide);
  document.getElementById('sliderNext').addEventListener('click', nextSlide);
});