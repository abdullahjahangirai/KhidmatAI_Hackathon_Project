/* ================================================================
   KhidmatAI — User Dashboard (dashboard.js)
   Auth-guarded hub: programs, eligibility, applications,
   saved items, nearby map, emergency, profile.
   ================================================================ */
(function () {
  "use strict";

  /* ---------- Auth guard ---------- */
  var user = null;
  try {
    user = JSON.parse(localStorage.getItem("kai_user") || "null");
  } catch (e) { user = null; }
  if (!user || !user.email) {
    location.replace("/login");
    return;
  }

  var S = {
    saved: [],
    map: null,
    markers: null,
    wizStep: 1,
    currentDetail: null,
    progDebounce: null
  };
  try { S.saved = JSON.parse(localStorage.getItem("kai_saved") || "[]"); } catch (e) { S.saved = []; }

  window._allProgs = window._allProgs || [];

  /* ---------- Helpers ---------- */
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function byId(id) { return document.getElementById(id); }

  function truncate(text, n) {
    text = String(text || "");
    return text.length > n ? text.slice(0, n) + "..." : text;
  }

  function initials(name) {
    var parts = String(name || "K").trim().split(/\s+/);
    return (parts[0].charAt(0) + (parts[1] ? parts[1].charAt(0) : "")).toUpperCase();
  }

  var toastEl = byId("dashboardToast");
  var toastTimer = null;
  function showToast(message) {
    if (!toastEl) return;
    toastEl.textContent = message;
    toastEl.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove("show"); }, 2800);
  }

  function persistSaved() {
    localStorage.setItem("kai_saved", JSON.stringify(S.saved));
  }

  function findProgram(id) {
    return window._allProgs.find(function (p) { return p.id === id; }) || null;
  }

  /* ---------- Theme ---------- */
  var root = document.documentElement;
  var themeBtn = byId("themeToggle");
  var themeIcon = byId("themeIcon");

  function applyTheme(mode) {
    var dark = mode === "dark";
    root.classList.toggle("dark-mode", dark);
    document.body.classList.toggle("dark-mode", dark);
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

  /* ---------- Language (English / اردو / Roman Urdu) ---------- */
  var I18N = {
    english: {
      "menu": "MENU", "support": "SUPPORT",
      "nav.overview": "Overview", "nav.assistant": "AI Assistant", "nav.eligibility": "Eligibility",
      "nav.programs": "Programs", "nav.organizations": "Organizations", "nav.saved": "Saved",
      "nav.nearby": "Nearby Help", "nav.emergency": "Emergency", "nav.profile": "My Profile",
      "sidebar.helpTitle": "Ask KhidmatAI",
      "sidebar.helpText": "Describe your need and get source-linked guidance instantly.",
      "sidebar.openAssistant": "Open assistant →", "logout": "Log out", "topbar.ask": "Ask KhidmatAI",
      "hero.welcome": "WELCOME BACK", "hero.hello": "Hello,", "hero.spot": "SPOTLIGHT",
      "hero.text": "Find verified welfare programs, check your eligibility and take the next step — with AI guidance that always links official sources.",
      "hero.ask": "Ask KhidmatAI", "hero.browse": "Browse programs",
      "quick.search": "Search programs", "quick.searchSub": "Explore the verified welfare directory",
      "quick.elig": "Check eligibility", "quick.eligSub": "Simple step-by-step checker",
      "quick.apply": "Apply now", "quick.applySub": "Start a welfare application",
      "quick.nearby": "Find nearby", "quick.nearbySub": "Hospitals & welfare centers on map",
      "trust.programs": "Programs", "trust.centers": "Support centers", "trust.all": "All",
      "trust.citizens": "Citizens welcome", "trust.free": "Free to use",
      "reco.kicker": "RECOMMENDED", "reco.title": "Programs for you", "reco.viewAll": "View all →",
      "act.kicker": "ACTIVITY", "act.title": "My applications", "act.recent": "Recent activity", "act.live": "Live",
      "ticker.label": "UPDATES",
      "sec.assistant": "AI Assistant",
      "sec.assistantSub": "Ask anything about welfare — scholarships, medical aid, rations, financial support.",
      "assist.kicker": "ASK KHIDMATAI", "assist.title": "Your welfare questions, answered clearly.",
      "assist.text": "Describe your situation in plain words. KhidmatAI searches verified programs and official sources, then gives you a short, clear answer with the next steps.",
      "assist.start": "Start a conversation", "assist.tryTitle": "Try asking",
      "assist.trySub": "Click a suggestion to open it in the assistant.",
      "sugg.1": "I need a scholarship for university",
      "sugg.2": "Where can I get free medical treatment?",
      "sugg.3": "How do I apply for BISP Kafaalat?",
      "sugg.4": "I need ration support",
      "sec.eligibility": "Eligibility Checker",
      "sec.eligibilitySub": "A few quick questions — we match you with programs you may qualify for.",
      "elig.step": "STEP 1 — YOUR SITUATION", "elig.tell": "Tell us about yourself",
      "elig.income": "Monthly household income (Rs.)", "elig.employment": "Employment status",
      "emp.unemployed": "Unemployed", "emp.employed": "Employed", "emp.self": "Self-employed",
      "emp.student": "Student", "emp.retired": "Retired", "emp.disabled": "Disabled",
      "elig.city": "City", "elig.cnic": "CNIC (optional)", "elig.check": "Check my eligibility",
      "sec.programs": "Welfare Programs",
      "sec.programsSub": "Verified programs with sources, eligibility and how to apply.",
      "programs.searchPh": "Search programs...",
      "cat.all": "All categories", "cat.education": "Education", "cat.healthcare": "Healthcare",
      "cat.financial": "Financial Aid", "cat.food": "Food Support", "cat.employment": "Employment",
      "cat.disability": "Disability", "cat.disaster": "Disaster Relief",
      "sec.organizations": "Organizations",
      "sec.organizationsSub": "Verified universities, hospitals, government bodies, NGOs and welfare organizations — plus the programs they publish.",
      "sec.saved": "Saved Programs", "sec.savedSub": "Programs you bookmarked for later.",
      "sec.nearby": "Nearby Help",
      "sec.nearbySub": "Hospitals, welfare centers and universities close to you.",
      "nearby.allCities": "All cities", "nearby.allTypes": "All types", "nearby.hospitals": "Hospitals",
      "nearby.welfare": "Welfare centers", "nearby.universities": "Universities",
      "nearby.refresh": "Refresh map", "nearby.locate": "Use my location",
      "nearby.note": "Round markers are curated centers · square markers are geo-verified (OpenStreetMap) facilities.",
      "emer.title": "Emergency Support",
      "emer.text": "Immediate helplines and emergency services across Pakistan. In a life-threatening situation, call Rescue 1122 right away.",
      "emer.call1122": "Call Rescue 1122", "emer.call115": "Edhi Ambulance 115",
      "sec.profile": "My Profile", "sec.profileSub": "Your KhidmatAI account details.",
      "profile.logout": "Log out of KhidmatAI",
      "modal.verified": "Verified program", "modal.support": "Support provided",
      "modal.eligibility": "Eligibility", "modal.documents": "Documents required",
      "modal.apply": "How to apply", "modal.source": "Official source", "modal.applyBtn": "Apply now",
      "wiz.title": "Welfare Program Application", "wiz.sub": "Four quick steps to submit your application.",
      "wiz.step1": "Program", "wiz.step2": "Personal", "wiz.step3": "Documents", "wiz.step4": "Review",
      "wiz.selectProgram": "Select program", "wiz.choose": "-- Choose a program --",
      "wiz.cnic": "CNIC", "wiz.phone": "Phone", "wiz.income": "Monthly income (Rs.)",
      "wiz.docsIntro": "Please confirm you have these documents ready:",
      "wiz.back": "Back", "wiz.next": "Next", "wiz.submit": "Submit application",
      "card.view": "View details", "card.save": "Save", "card.saved": "Saved ✓", "card.source": "Source",
      "card.apply": "Apply", "card.verified": "✓ Verified", "saved.view": "View", "saved.remove": "Remove",
      "empty.saved": "No saved programs yet. Browse the directory and tap Save on any program.",
      "orgs.searchPh": "Search organizations...",
      "orgs.allTypes": "All types", "orgs.university": "University", "orgs.hospital": "Hospital",
      "orgs.government": "Government", "orgs.ngo": "NGO", "orgs.welfare": "Welfare",
      "orgs.private": "Private", "orgs.community": "Community", "orgs.refresh": "Refresh",
      "orgs.kicker": "DIRECTORY", "orgs.directoryTitle": "Verified organizations",
      "orgs.postsKicker": "FROM ORGANIZATIONS", "orgs.postsTitle": "Latest posts",
      "orgs.ctaTitle": "Is your organization offering welfare services?",
      "orgs.ctaText": "Register on KhidmatAI, get verified by our admin team, and publish your programs, scholarships and events to citizens nationwide.",
      "orgs.ctaLink": "Register your organization →",
      "orgs.empty": "No organizations match your search yet. Organizations appear here after admin verification.",
      "orgs.emptyPosts": "No organization posts yet. Verified organizations will publish their programs and events here.",
      "orgs.loadFail": "Could not load organizations right now. Please try again.",
      "orgs.verified": "✓ Verified Organization",
      "orgs.free": "Free", "orgs.subsidized": "Subsidized", "orgs.paid": "Paid",
      "orgs.services": "Services", "orgs.hours": "Hours", "orgs.discount": "Discount",
      "orgs.website": "Website", "orgs.map": "Map",
      "empty.noAppsTitle": "No applications yet",
      "empty.noAppsText": "Your welfare applications will appear here once you apply.",
      "empty.browse": "Browse programs", "loading.programs": "Loading programs...",
      "error.programs": "Could not load programs right now. Please try again.",
      "empty.noMatch": "No programs match your search. Try a different category or keyword.",
      "checking": "Checking programs for you...",
      "empty.noElig": "No strong matches found. Try adjusting your income or city, or ask the AI assistant.",
      "elig.matchOne": "1 program matches your profile",
      "elig.matchesFound": "{n} programs match your profile",
      "error.elig": "Could not check eligibility right now. Please try again.",
      "match.potential": "Potential match",
      "toast.saved": "Program saved.", "toast.unsaved": "Removed from saved programs.",
      "toast.applied": "Application submitted successfully!",
      "toast.applyFail": "Could not submit your application. Please try again.",
      "toast.langChanged": "Language updated.",
      "toast.selectProgram": "Please select a program first.", "toast.enterCnic": "Please enter your CNIC.",
      "toast.submitting": "Submitting...", "submitted": "Submitted",
      "pf.name": "Full name", "pf.email": "Email", "pf.phone": "Phone", "pf.city": "City",
      "pf.cnic": "CNIC", "pf.account": "Account", "pf.citizen": "Citizen",
      "menu.settings": "Account settings",
      "pf.editHint": "Update your details below. Your email is your login and cannot be changed.",
      "pf.save": "Save changes", "pf.cancel": "Cancel",
      "pf.nameReq": "Please enter your full name.", "pf.cnicHint": "CNIC format: 42101-1234567-1",
      "toast.profileSaved": "Profile updated successfully.",
      "toast.profileError": "Could not save your profile. Please try again.",
      "rv.program": "Program", "rv.income": "Monthly income",
      "toast.noDetail": "Program details are not available.",
      "detail.applyFallback": "Visit the official portal to apply.",
      "detail.listFallback": "Check the official source for details."
    },
    urdu: {
      "menu": "مینو", "support": "معاونت",
      "nav.overview": "جائزہ", "nav.assistant": "اے آئی اسسٹنٹ", "nav.eligibility": "اہلیت",
      "nav.programs": "پروگرامز", "nav.organizations": "ادارے", "nav.saved": "محفوظ شدہ",
      "nav.nearby": "قریبی مدد", "nav.emergency": "ایمرجنسی", "nav.profile": "میرا پروفائل",
      "sidebar.helpTitle": "KhidmatAI سے پوچھیں",
      "sidebar.helpText": "اپنی ضرورت بتائیں اور سرکاری ذرائع سے منسلک رہنمائی فوراً حاصل کریں۔",
      "sidebar.openAssistant": "اسسٹنٹ کھولیں ←", "logout": "لاگ آؤٹ", "topbar.ask": "KhidmatAI سے پوچھیں",
      "hero.welcome": "خوش آمدید", "hero.hello": "خوش آمدید،", "hero.spot": "نمایاں",
      "hero.text": "تصدیق شدہ فلاحی پروگرام تلاش کریں، اپنی اہلیت چیک کریں اور اگلا قدم اٹھائیں — ایسی اے آئی رہنمائی کے ساتھ جو ہمیشہ سرکاری ذرائع سے جوڑتی ہے۔",
      "hero.ask": "KhidmatAI سے پوچھیں", "hero.browse": "پروگرام دیکھیں",
      "quick.search": "پروگرام تلاش کریں", "quick.searchSub": "تصدیق شدہ فلاحی ڈائریکٹری دیکھیں",
      "quick.elig": "اہلیت چیک کریں", "quick.eligSub": "آسان مرحلہ وار چیکر",
      "quick.apply": "ابھی درخواست دیں", "quick.applySub": "فلاحی درخواست شروع کریں",
      "quick.nearby": "قریبی تلاش کریں", "quick.nearbySub": "نقشے پر اسپتال اور فلاحی مراکز",
      "trust.programs": "پروگرامز", "trust.centers": "معاونتی مراکز", "trust.all": "تمام",
      "trust.citizens": "شہری خوش آمدید", "trust.free": "مفت استعمال",
      "reco.kicker": "تجویز کردہ", "reco.title": "آپ کے لیے پروگرام", "reco.viewAll": "سب دیکھیں ←",
      "act.kicker": "سرگرمی", "act.title": "میری درخواستیں", "act.recent": "حالیہ سرگرمی", "act.live": "لائیو",
      "ticker.label": "تازہ ترین",
      "sec.assistant": "اے آئی اسسٹنٹ",
      "sec.assistantSub": "فلاح و بہبود کے بارے میں کچھ بھی پوچھیں — سکالرشپ، طبی امداد، راشن، مالی معاونت۔",
      "assist.kicker": "KHIDMATAI سے پوچھیں", "assist.title": "آپ کے فلاحی سوالات کا واضح جواب۔",
      "assist.text": "اپنا مسئلہ سادہ الفاظ میں بیان کریں۔ KhidmatAI تصدیق شدہ پروگرام اور سرکاری ذرائع تلاش کرتا ہے اور مختصر، واضح جواب کے ساتھ اگلے مراحل بتاتا ہے۔",
      "assist.start": "گفتگو شروع کریں", "assist.tryTitle": "آزمالیں",
      "assist.trySub": "کسی تجویز پر کلک کر کے اسسٹنٹ میں کھولیں۔",
      "sugg.1": "مجھے یونیورسٹی کے لیے سکالرشپ چاہیے",
      "sugg.2": "میں مفت طبی علاج کہاں حاصل کر سکتا ہوں؟",
      "sugg.3": "بی آئی ایس پی کفالت کے لیے درخواست کیسے دیں؟",
      "sugg.4": "مجھے اپنے خاندان کے لیے راشن سپورٹ چاہیے",
      "sec.eligibility": "اہلیت چیکر",
      "sec.eligibilitySub": "چند آسان سوالات — ہم آپ کو ان پروگرام سے ملاتے ہیں جن کے اہل ہو سکتے ہیں۔",
      "elig.step": "مرحلہ ۱ — آپ کی صورتحال", "elig.tell": "اپنے بارے میں بتائیں",
      "elig.income": "ماہانہ گھریلو آمدنی (روپے)", "elig.employment": "روزگار کی حیثیت",
      "emp.unemployed": "بے روزگار", "emp.employed": "ملازم", "emp.self": "خود کاروبار",
      "emp.student": "طالب علم", "emp.retired": "ریٹائرڈ", "emp.disabled": "معذور",
      "elig.city": "شہر", "elig.cnic": "شناختی کارڈ (اختیاری)", "elig.check": "میری اہلیت چیک کریں",
      "sec.programs": "فلاحی پروگرام",
      "sec.programsSub": "ذرائع، اہلیت اور درخواست کے طریقے کے ساتھ تصدیق شدہ پروگرام۔",
      "programs.searchPh": "پروگرام تلاش کریں...",
      "cat.all": "تمام اقسام", "cat.education": "تعلیم", "cat.healthcare": "صحت",
      "cat.financial": "مالی امداد", "cat.food": "خوراک معاونت", "cat.employment": "روزگار",
      "cat.disability": "معذوری", "cat.disaster": "آفت سے نجات",
      "sec.organizations": "ادارے",
      "sec.organizationsSub": "تصدیق شدہ جامعات، اسپتال، سرکاری ادارے، این جی اوز اور فلاحی تنظیمیں — اور ان کے جاری کردہ پروگرام۔",
      "sec.saved": "محفوظ شدہ پروگرام", "sec.savedSub": "بعد میں دیکھنے کے لیے محفوظ کیے گئے پروگرام۔",
      "sec.nearby": "قریبی مدد",
      "sec.nearbySub": "آپ کے قریب اسپتال، فلاحی مراکز اور جامعات۔",
      "nearby.allCities": "تمام شہر", "nearby.allTypes": "تمام اقسام", "nearby.hospitals": "اسپتال",
      "nearby.welfare": "فلاحی مراکز", "nearby.universities": "جامعات",
      "nearby.refresh": "نقشہ تازہ کریں", "nearby.locate": "میری لوکیشن استعمال کریں",
      "nearby.note": "گول نشانات منتخب مراکز ہیں · چوکور نشانات جیو تصدیق شدہ (OpenStreetMap) سہولیات ہیں۔",
      "emer.title": "ایمرجنسی معاونت",
      "emer.text": "پاکستان بھر میں فوری ہیلپ لائن اور ایمرجنسی خدمات۔ جان کو خطرہ ہو تو فوراً ریسکیو 1122 پر کال کریں۔",
      "emer.call1122": "ریسکیو 1122 کو کال کریں", "emer.call115": "ایڈی ایمبولینس 115",
      "sec.profile": "میرا پروفائل", "sec.profileSub": "آپ کے KhidmatAI اکاؤنٹ کی تفصیلات۔",
      "profile.logout": "KhidmatAI سے لاگ آؤٹ کریں",
      "modal.verified": "تصدیق شدہ پروگرام", "modal.support": "فراہم کردہ معاونت",
      "modal.eligibility": "اہلیت", "modal.documents": "مطلوبہ دستاویزات",
      "modal.apply": "درخواست کیسے دیں", "modal.source": "سرکاری ذریعہ", "modal.applyBtn": "ابھی درخواست دیں",
      "wiz.title": "فلاحی پروگرام درخواست", "wiz.sub": "درخواست جمع کرانے کے چار آسان مراحل۔",
      "wiz.step1": "پروگرام", "wiz.step2": "ذاتی معلومات", "wiz.step3": "دستاویزات", "wiz.step4": "جائزہ",
      "wiz.selectProgram": "پروگرام منتخب کریں", "wiz.choose": "-- پروگرام منتخب کریں --",
      "wiz.cnic": "شناختی کارڈ", "wiz.phone": "فون", "wiz.income": "ماہانہ آمدنی (روپے)",
      "wiz.docsIntro": "براہ کرم تصدیق کریں کہ یہ دستاویزات آپ کے پاس موجود ہیں:",
      "wiz.back": "واپس", "wiz.next": "اگلا", "wiz.submit": "درخواست جمع کریں",
      "card.view": "تفصیل دیکھیں", "card.save": "محفوظ کریں", "card.saved": "محفوظ ✓", "card.source": "ماخذ",
      "card.apply": "درخواست دیں", "card.verified": "✓ تصدیق شدہ", "saved.view": "دیکھیں", "saved.remove": "ہٹائیں",
      "empty.saved": "ابھی کوئی پروگرام محفوظ نہیں۔ ڈائریکٹری دیکھیں اور کسی پروگرام پر محفوظ کریں دبائیں۔",
      "orgs.searchPh": "ادارے تلاش کریں...",
      "orgs.allTypes": "تمام اقسام", "orgs.university": "جامعہ", "orgs.hospital": "اسپتال",
      "orgs.government": "سرکاری", "orgs.ngo": "این جی او", "orgs.welfare": "فلاحی",
      "orgs.private": "نجی", "orgs.community": "برادری", "orgs.refresh": "تازہ کریں",
      "orgs.kicker": "ڈائریکٹری", "orgs.directoryTitle": "تصدیق شدہ ادارے",
      "orgs.postsKicker": "اداروں کی جانب سے", "orgs.postsTitle": "تازہ پوسٹس",
      "orgs.ctaTitle": "کیا آپ کا ادارہ فلاحی خدمات فراہم کرتا ہے؟",
      "orgs.ctaText": "KhidmatAI پر رجسٹر کریں، ایڈمن ٹیم سے تصدیق حاصل کریں، اور اپنے پروگرام، سکالرشپ اور ایونٹس ملک بھر کے شہریوں تک پہنچائیں۔",
      "orgs.ctaLink": "اپنا ادارہ رجسٹر کریں ←",
      "orgs.empty": "آپ کی تلاش سے ابھی کوئی ادارہ نہیں ملا۔ ایڈمن کی تصدیق کے بعد ادارے یہاں ظاہر ہوتے ہیں۔",
      "orgs.emptyPosts": "ابھی کوئی ادارے کی پوسٹ نہیں۔ تصدیق شدہ ادارے اپنے پروگرام اور ایونٹس یہاں شائع کریں گے۔",
      "orgs.loadFail": "ابھی ادارے لوڈ نہیں ہو سکے۔ دوبارہ کوشش کریں۔",
      "orgs.verified": "✓ تصدیق شدہ ادارہ",
      "orgs.free": "مفت", "orgs.subsidized": "سبسڈی والا", "orgs.paid": "ادائیگی",
      "orgs.services": "خدمات", "orgs.hours": "اوقات", "orgs.discount": "رعایت",
      "orgs.website": "ویب سائٹ", "orgs.map": "نقشہ",
      "empty.noAppsTitle": "ابھی کوئی درخواست نہیں",
      "empty.noAppsText": "آپ کی فلاحی درخواستیں یہاں ظاہر ہوں گی جیسے ہی آپ درخواست دیں۔",
      "empty.browse": "پروگرام دیکھیں", "loading.programs": "پروگرام لوڈ ہو رہے ہیں...",
      "error.programs": "ابھی پروگرام لوڈ نہیں ہو سکے۔ دوبارہ کوشش کریں۔",
      "empty.noMatch": "آپ کی تلاش سے کوئی پروگرام نہیں ملتا۔ دوسری قسم یا لفظ آزمائیں۔",
      "checking": "آپ کے لیے پروگرام چیک ہو رہے ہیں...",
      "empty.noElig": "کوئی مضبوط میچ نہیں ملا۔ آمدنی یا شہر تبدیل کریں، یا اے آئی اسسٹنٹ سے پوچھیں۔",
      "elig.matchOne": "ایک پروگرام آپ کے پروفائل سے ملتا ہے",
      "elig.matchesFound": "{n} پروگرام آپ کے پروفائل سے ملتے ہیں",
      "error.elig": "ابھی اہلیت چیک نہیں ہو سکی۔ دوبارہ کوشش کریں۔",
      "match.potential": "ممکنہ میچ",
      "toast.saved": "پروگرام محفوظ ہو گیا۔", "toast.unsaved": "محفوظ پروگرام سے ہٹا دیا گیا۔",
      "toast.applied": "درخواست کامیابی سے جمع ہو گئی!",
      "toast.applyFail": "درخواست جمع نہیں ہو سکی۔ دوبارہ کوشش کریں۔",
      "toast.langChanged": "زبان تبدیل ہو گئی۔",
      "toast.selectProgram": "براہ کرم پہلے پروگرام منتخب کریں۔", "toast.enterCnic": "براہ کرم اپنا شناختی کارڈ نمبر درج کریں۔",
      "toast.submitting": "جمع ہو رہی ہے...", "submitted": "جمع کرائی گئی",
      "pf.name": "پورا نام", "pf.email": "ای میل", "pf.phone": "فون", "pf.city": "شہر",
      "pf.cnic": "شناختی کارڈ", "pf.account": "اکاؤنٹ", "pf.citizen": "شہری",
      "menu.settings": "اکاؤنٹ سیٹنگز",
      "pf.editHint": "نیچے اپنی تفصیلات اپ ڈیٹ کریں۔ آپ کا ای میل آپ کی لاگ این ہے اور تبدیل نہیں ہو سکتا۔",
      "pf.save": "تبدیلیاں محفوظ کریں", "pf.cancel": "منسوخ کریں",
      "pf.nameReq": "براہ کرم اپنا پورا نام درج کریں۔", "pf.cnicHint": "شناختی کارڈ کا فارمیٹ: 42101-1234567-1",
      "toast.profileSaved": "پروفائل کامیابی سے اپ ڈیٹ ہو گئی۔",
      "toast.profileError": "پروفائل محفوظ نہیں ہو سکی۔ دوبارہ کوشش کریں۔",
      "rv.program": "پروگرام", "rv.income": "ماہانہ آمدنی",
      "toast.noDetail": "پروگرام کی تفصیلات دستیاب نہیں۔",
      "detail.applyFallback": "درخواست کے لیے سرکاری پورٹل ملاحظہ کریں۔",
      "detail.listFallback": "تفصیلات کے لیے سرکاری ذریعہ دیکھیں۔"
    },
    roman: {
      "menu": "MENU", "support": "MADAD",
      "nav.overview": "Khulasa", "nav.assistant": "AI Madadgar", "nav.eligibility": "Ahaliat",
      "nav.programs": "Programs", "nav.organizations": "Idare", "nav.saved": "Mehfooz",
      "nav.nearby": "Qareebi Madad", "nav.emergency": "Emergency", "nav.profile": "Mera Profile",
      "sidebar.helpTitle": "KhidmatAI se poochein",
      "sidebar.helpText": "Apni zaroorat batayein aur foran sources se judi rahnumai hasil karein.",
      "sidebar.openAssistant": "Assistant kholein →", "logout": "Log out", "topbar.ask": "KhidmatAI se poochein",
      "hero.welcome": "KHUSH AAMDEED", "hero.hello": "Hello,", "hero.spot": "KHAAS",
      "hero.text": "Verified welfare programs talash karein, apni ahaliat check karein aur agla qadam uthayein — AI rahnumai ke saath jo hamesha official sources se joti hai.",
      "hero.ask": "KhidmatAI se poochein", "hero.browse": "Programs dekhein",
      "quick.search": "Programs talash karein", "quick.searchSub": "Verified welfare directory dekhein",
      "quick.elig": "Ahaliat check karein", "quick.eligSub": "Aasan step-by-step checker",
      "quick.apply": "Abhi apply karein", "quick.applySub": "Welfare darkhwast shuru karein",
      "quick.nearby": "Qareebi talash karein", "quick.nearbySub": "Nakshe par hospitals aur welfare markaz",
      "trust.programs": "Programs", "trust.centers": "Madad ke markaz", "trust.all": "Sab",
      "trust.citizens": "Shehri khush aamdeed", "trust.free": "Bilkul muft",
      "reco.kicker": "TAJVEEZ SHUDA", "reco.title": "Aap ke liye programs", "reco.viewAll": "Sab dekhein →",
      "act.kicker": "ACTIVITY", "act.title": "Meri darkhwastein", "act.recent": "Taaza activity", "act.live": "Live",
      "ticker.label": "UPDATES",
      "sec.assistant": "AI Madadgar",
      "sec.assistantSub": "Welfare ke baray mein kuch bhi poochein — scholarships, medical madad, ration, maali madad.",
      "assist.kicker": "KHIDMATAI SE POOCHEIN", "assist.title": "Aap ke welfare sawal, wazah jawab ke saath.",
      "assist.text": "Apna masla aasan alfaaz mein batayein. KhidmatAI verified programs aur official sources talash karta hai aur mukhtasir, wazah jawab agle marahil ke saath deta hai.",
      "assist.start": "Guftagu shuru karein", "assist.tryTitle": "Aazma kar dekhein",
      "assist.trySub": "Kisi tajveez par click karein.",
      "sugg.1": "Mujhe university ke liye scholarship chahiye",
      "sugg.2": "Main muft ilaj kahan karwa sakta hoon?",
      "sugg.3": "BISP Kafaalat ke liye apply kaise karoon?",
      "sugg.4": "Mujhe apne khandan ke liye ration support chahiye",
      "sec.eligibility": "Ahaliat Checker",
      "sec.eligibilitySub": "Chand aasan sawal — hum aap ko un programs se milate hain jin ke ahal ho sakte hain.",
      "elig.step": "STEP 1 — AAP KI SURAT-E-HAAL", "elig.tell": "Apne baray mein batayein",
      "elig.income": "Mahana gharana aamdani (Rs.)", "elig.employment": "Rozgar ki haalat",
      "emp.unemployed": "Be-rozgar", "emp.employed": "Mulaazim", "emp.self": "Khud ka kaam",
      "emp.student": "Talib ilm", "emp.retired": "Retired", "emp.disabled": "Mazoor",
      "elig.city": "Sheher", "elig.cnic": "CNIC (ikhtiyari)", "elig.check": "Meri ahaliat check karein",
      "sec.programs": "Welfare Programs",
      "sec.programsSub": "Sources, ahaliat aur apply ke tareeqe ke saath verified programs.",
      "programs.searchPh": "Programs talash karein...",
      "cat.all": "Tamam iqsam", "cat.education": "Taleem", "cat.healthcare": "Sehat",
      "cat.financial": "Maali Imdad", "cat.food": "Khurak Madad", "cat.employment": "Rozgar",
      "cat.disability": "Mazoori", "cat.disaster": "Aafat Se Nijaat",
      "sec.organizations": "Idare",
      "sec.organizationsSub": "Verified universities, hospitals, sarkari idare, NGOs aur welfare tanzeemein — aur un ke jari kiye gaye programs.",
      "sec.saved": "Mehfooz Programs", "sec.savedSub": "Woh programs jo aap ne baad ke liye mehfooz kiye hain.",
      "sec.nearby": "Qareebi Madad",
      "sec.nearbySub": "Aap ke qareeb hospitals, welfare markaz aur universities.",
      "nearby.allCities": "Tamam shehr", "nearby.allTypes": "Tamam iqsam", "nearby.hospitals": "Hospitals",
      "nearby.welfare": "Welfare markaz", "nearby.universities": "Universities",
      "nearby.refresh": "Naksha taza karein", "nearby.locate": "Meri location istemal karein",
      "nearby.note": "Gol nishanat muntakhab markaz hain · chaukor nishanat geo-verified (OpenStreetMap) sahulatain hain.",
      "emer.title": "Emergency Madad",
      "emer.text": "Poore Pakistan mein fori helplines aur emergency khidmaat. Jaan ko khatra ho to foran Rescue 1122 par call karein.",
      "emer.call1122": "Rescue 1122 ko call karein", "emer.call115": "Edhi Ambulance 115",
      "sec.profile": "Mera Profile", "sec.profileSub": "Aap ke KhidmatAI account ki tafseelat.",
      "profile.logout": "KhidmatAI se log out karein",
      "modal.verified": "Verified program", "modal.support": "Di gayi madad",
      "modal.eligibility": "Ahaliyat", "modal.documents": "Zaroori dastawezat",
      "modal.apply": "Apply kaise karein", "modal.source": "Official source", "modal.applyBtn": "Abhi apply karein",
      "wiz.title": "Welfare Program Darkhwast", "wiz.sub": "Darkhwast jama karne ke chaar aasan marahil.",
      "wiz.step1": "Program", "wiz.step2": "Zaati maloomat", "wiz.step3": "Dastawezat", "wiz.step4": "Jaiza",
      "wiz.selectProgram": "Program muntakhib karein", "wiz.choose": "-- Program muntakhib karein --",
      "wiz.cnic": "CNIC", "wiz.phone": "Phone", "wiz.income": "Mahana aamdani (Rs.)",
      "wiz.docsIntro": "Barah-e-karam tasdeeq karein ke yeh dastawezat aap ke paas hain:",
      "wiz.back": "Wapas", "wiz.next": "Agla", "wiz.submit": "Darkhwast jama karein",
      "card.view": "Tafseel dekhein", "card.save": "Mehfooz karein", "card.saved": "Mehfooz ✓", "card.source": "Source",
      "card.apply": "Apply karein", "card.verified": "✓ Verified", "saved.view": "Dekhein", "saved.remove": "Hatayein",
      "empty.saved": "Abhi koi program mehfooz nahi. Directory dekhein aur kisi program par Save dabayein.",
      "orgs.searchPh": "Idare talash karein...",
      "orgs.allTypes": "Tamam iqsam", "orgs.university": "University", "orgs.hospital": "Hospital",
      "orgs.government": "Sarkari", "orgs.ngo": "NGO", "orgs.welfare": "Welfare",
      "orgs.private": "Private", "orgs.community": "Community", "orgs.refresh": "Taza karein",
      "orgs.kicker": "DIRECTORY", "orgs.directoryTitle": "Verified idare",
      "orgs.postsKicker": "IDARON KI TARAF SE", "orgs.postsTitle": "Taaza posts",
      "orgs.ctaTitle": "Kya aap ka idara welfare khidmaat faraham karta hai?",
      "orgs.ctaText": "KhidmatAI par register karein, admin team se tasdeeq hasil karein, aur apne programs, scholarships aur events poore mulk ke shehriyon tak pohanchein.",
      "orgs.ctaLink": "Apna idara register karein →",
      "orgs.empty": "Aap ki talash se abhi koi idara nahi mila. Admin ki verification ke baad idare yahan aate hain.",
      "orgs.emptyPosts": "Abhi koi idare ki post nahi. Verified idare apne programs aur events yahan share karenge.",
      "orgs.loadFail": "Abhi idare load nahi ho sake. Dobara koshish karein.",
      "orgs.verified": "✓ Verified Idara",
      "orgs.free": "Muft", "orgs.subsidized": "Subsidized", "orgs.paid": "Paid",
      "orgs.services": "Khidmaat", "orgs.hours": "Waqt", "orgs.discount": "Reayat",
      "orgs.website": "Website", "orgs.map": "Naksha",
      "empty.noAppsTitle": "Abhi koi darkhwast nahi",
      "empty.noAppsText": "Aap ki welfare darkhwastein yahan aayengi jaise hi aap apply karein.",
      "empty.browse": "Programs dekhein", "loading.programs": "Programs load ho rahe hain...",
      "error.programs": "Abhi programs load nahi ho sake. Dobara koshish karein.",
      "empty.noMatch": "Aap ki talash se koi program nahi mila. Doosri category ya lafz aazmaayein.",
      "checking": "Aap ke liye programs check ho rahe hain...",
      "empty.noElig": "Koi mazboot match nahi mila. Aamdani ya sheher tabdeel karein, ya AI madadgar se poochein.",
      "elig.matchOne": "1 program aap ke profile se milta hai",
      "elig.matchesFound": "{n} program aap ke profile se milte hain",
      "error.elig": "Abhi ahaliat check nahi ho saki. Dobara koshish karein.",
      "match.potential": "Mumkin match",
      "toast.saved": "Program mehfooz ho gaya.", "toast.unsaved": "Mehfooz programs se hata diya gaya.",
      "toast.applied": "Darkhwast kamyabi se jama ho gayi!",
      "toast.applyFail": "Darkhwast jama nahi ho saki. Dobara koshish karein.",
      "toast.langChanged": "Zaban tabdeel ho gayi.",
      "toast.selectProgram": "Barah-e-karam pehle program muntakhib karein.", "toast.enterCnic": "Barah-e-karam apna CNIC likhein.",
      "toast.submitting": "Jama ho rahi hai...", "submitted": "Jama ki gayi",
      "pf.name": "Poora naam", "pf.email": "Email", "pf.phone": "Phone", "pf.city": "Sheher",
      "pf.cnic": "CNIC", "pf.account": "Account", "pf.citizen": "Shehri",
      "menu.settings": "Account settings",
      "pf.editHint": "Neeche apni tafseelat update karein. Email aap ki login hai aur tabdeel nahi ho sakti.",
      "pf.save": "Tabdeeliyan mehfooz karein", "pf.cancel": "Mansookh karein",
      "pf.nameReq": "Barah-e-karam apna poora naam likhein.", "pf.cnicHint": "CNIC format: 42101-1234567-1",
      "toast.profileSaved": "Profile kamyabi se update ho gayi.",
      "toast.profileError": "Profile mehfooz nahi ho saki. Dobara koshish karein.",
      "rv.program": "Program", "rv.income": "Mahana aamdani",
      "toast.noDetail": "Program ki tafseelat mojood nahi.",
      "detail.applyFallback": "Apply karne ke liye official portal mulaahiza karein.",
      "detail.listFallback": "Tafseelat ke liye official source dekhein."
    }
  };

  S.lang = "english";
  try {
    var storedLang = localStorage.getItem("kai_lang");
    if (I18N[storedLang]) S.lang = storedLang;
  } catch (e) { /* keep default */ }

  function t(key) {
    var dict = I18N[S.lang] || I18N.english;
    if (dict[key] != null) return dict[key];
    if (I18N.english[key] != null) return I18N.english[key];
    return key;
  }

  var SECTION_TITLE_KEYS = {
    overview: "nav.overview", assistant: "sec.assistant", eligibility: "sec.eligibility",
    programs: "sec.programs", organizations: "sec.organizations", saved: "sec.saved",
    nearby: "sec.nearby", emergency: "emer.title", profile: "sec.profile"
  };

  function applyLanguage(langCode) {
    S.lang = I18N[langCode] ? langCode : "english";
    try { localStorage.setItem("kai_lang", S.lang); } catch (e) { /* private mode */ }
    var dict = I18N[S.lang];
    document.querySelectorAll("[data-i18n]").forEach(function (node) {
      var key = node.getAttribute("data-i18n");
      if (dict[key] != null) node.textContent = dict[key];
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach(function (node) {
      var key = node.getAttribute("data-i18n-placeholder");
      if (dict[key] != null) node.setAttribute("placeholder", dict[key]);
    });
    var isRtl = S.lang === "urdu";
    document.documentElement.dir = isRtl ? "rtl" : "ltr";
    document.body.classList.toggle("urdu-font", isRtl);
    if (byId("langSelect")) byId("langSelect").value = S.lang;
    if (S.currentSection && byId("pageTitle")) {
      byId("pageTitle").textContent = t(SECTION_TITLE_KEYS[S.currentSection] || "nav.overview");
    }
    renderProfile();
    if (loaded.saved) renderSaved();
    if (loaded.programs) loadPrograms();
    if (loaded.overview) { loadRecommended(); loadRecentApps(); }
    if (loaded.organizations) loadOrganizationsSection();
    if (S.heroSlides) buildHeroSlider(S.heroSlides);
  }

  if (byId("langSelect")) {
    byId("langSelect").addEventListener("change", function () {
      applyLanguage(this.value);
      showToast(t("toast.langChanged"));
    });
  }

  /* ---------- User identity (re-rendered after profile updates) ---------- */
  function renderIdentity() {
    var displayName = user.name || user.email;
    ["sidebarUserName", "topbarUserName", "dropdownUserName"].forEach(function (id) { if (byId(id)) byId(id).textContent = displayName; });
    ["sidebarAvatar", "topbarAvatar"].forEach(function (id) { if (byId(id)) byId(id).textContent = initials(displayName); });
    if (byId("sidebarUserEmail")) byId("sidebarUserEmail").textContent = user.email;
    if (byId("dropdownUserEmail")) byId("dropdownUserEmail").textContent = user.email;
    if (byId("heroUserName")) byId("heroUserName").textContent = displayName.split(" ")[0];
    if (byId("topbarUserCity")) byId("topbarUserCity").textContent = user.city || "Pakistan";
  }
  renderIdentity();

  /* ---------- Topbar user dropdown ---------- */
  var profileBtn = byId("topbarProfileBtn");
  var profileDropdown = byId("topbarDropdown");

  function closeProfileDropdown() {
    if (profileDropdown) profileDropdown.classList.remove("open");
    if (profileBtn) profileBtn.setAttribute("aria-expanded", "false");
  }

  if (profileBtn && profileDropdown) {
    profileBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      var open = profileDropdown.classList.toggle("open");
      profileBtn.setAttribute("aria-expanded", String(open));
    });
    profileDropdown.addEventListener("click", function (e) { e.stopPropagation(); });
    document.addEventListener("click", closeProfileDropdown);
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeProfileDropdown(); });
    if (byId("dropdownProfile")) byId("dropdownProfile").addEventListener("click", function () { closeProfileDropdown(); showSection("profile"); });
    if (byId("dropdownSettings")) byId("dropdownSettings").addEventListener("click", function () { closeProfileDropdown(); showSection("profile"); });
    if (byId("dropdownLogout")) byId("dropdownLogout").addEventListener("click", function () { closeProfileDropdown(); doLogout(); });
  }

  /* ---------- Logout ---------- */
  function doLogout() {
    localStorage.removeItem("kai_user");
    try { speechSynthesis.cancel(); } catch (e) { /* ignore */ }
    location.replace("/");
  }
  if (byId("logoutBtn")) byId("logoutBtn").addEventListener("click", doLogout);
  if (byId("logoutBtn2")) byId("logoutBtn2").addEventListener("click", doLogout);

  /* ---------- Sidebar toggle (mobile) ---------- */
  var sidebar = byId("dashboardSidebar");
  var sidebarToggle = byId("sidebarToggle");
  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener("click", function () { sidebar.classList.toggle("open"); });
  }

  /* ---------- Section navigation ---------- */
  var sections = Array.prototype.slice.call(document.querySelectorAll(".dashboard-section"));
  var navLinks = Array.prototype.slice.call(document.querySelectorAll(".dash-nav-link[data-section]"));
  var loaded = {};

  function showSection(name, updateHash) {
    if (!SECTION_TITLE_KEYS[name]) name = "overview";
    S.currentSection = name;
    sections.forEach(function (s) { s.classList.toggle("active-section", s.id === name); });
    navLinks.forEach(function (l) { l.classList.toggle("active", l.dataset.section === name); });
    if (byId("pageTitle")) byId("pageTitle").textContent = t(SECTION_TITLE_KEYS[name]);
    if (updateHash !== false) history.replaceState(null, "", "#" + name);
    if (sidebar) sidebar.classList.remove("open");
    window.scrollTo({ top: 0, behavior: "smooth" });

    // Lazy-load section data once
    if (!loaded[name]) {
      loaded[name] = true;
      if (name === "programs") loadPrograms();
      if (name === "saved") renderSaved();
      if (name === "nearby") { initMap(); loadFacilitiesMap(); }
      if (name === "emergency") loadEmergency();
      if (name === "organizations") loadOrganizationsSection();
      if (name === "overview") { loadRecommended(); loadRecentApps(); loadStats(); }
    }
  }

  navLinks.forEach(function (link) {
    link.addEventListener("click", function (event) {
      event.preventDefault();
      showSection(this.dataset.section);
    });
  });

  document.addEventListener("click", function (event) {
    var action = event.target.closest("[data-action]");
    if (action) {
      event.preventDefault();
      showSection(action.dataset.action);
    }
  });

  if (byId("quickApply")) {
    byId("quickApply").addEventListener("click", function () { openWizard(); });
  }

  /* =====================
     PROGRAMS
     ===================== */
  var CAT_MARKS = {
    "Education": "", "Healthcare": " teal-mark", "Financial Aid": " gold-mark",
    "Food Support": " gold-mark", "Employment": " blue-mark",
    "Disability": " blue-mark", "Disaster Relief": " teal-mark"
  };

  function markText(category) {
    var words = String(category || "GEN").split(/\s+/);
    return words.length > 1 ? (words[0].slice(0, 2)).toUpperCase() : words[0].slice(0, 3).toUpperCase();
  }

  function programCard(p, compact) {
    var card = el("div", "program-card");
    card.appendChild(el("div", "program-mark" + (CAT_MARKS[p.category] || ""), markText(p.category)));

    var body = el("div", "program-body");
    var top = el("div", "program-top");
    top.appendChild(el("span", "verified-badge", t("card.verified")));
    top.appendChild(el("span", "program-tag", p.category || "General"));
    body.appendChild(top);

    body.appendChild(el("h3", null, p.title || "Program"));
    body.appendChild(el("p", null, truncate(p.description, compact ? 90 : 150)));

    var support = Array.isArray(p.support) ? p.support.slice(0, 3).join(" · ") : "";
    if (support) body.appendChild(el("p", null, support));

    var actions = el("div", "program-actions");

    var view = el("button", "pill-btn", t("card.view"));
    view.setAttribute("data-detail", p.id);
    actions.appendChild(view);

    var isSaved = S.saved.some(function (s) { return s.id === p.id; });
    var save = el("button", "pill-btn", isSaved ? t("card.saved") : t("card.save"));
    save.setAttribute("data-save", p.id);
    actions.appendChild(save);

    if (p.source_url) {
      var src = el("a", "pill-btn", t("card.source"));
      src.href = p.source_url;
      src.target = "_blank";
      src.rel = "noopener";
      actions.appendChild(src);
    }

    var apply = el("button", "pill-btn solid", t("card.apply"));
    apply.setAttribute("data-apply", p.id);
    actions.appendChild(apply);

    body.appendChild(actions);
    card.appendChild(body);
    return card;
  }

  async function loadPrograms() {
    var cat = byId("progCategory") ? byId("progCategory").value : "all";
    var q = byId("progSearch") ? byId("progSearch").value.trim() : "";
    var grid = byId("programsList");
    if (!grid) return;
    grid.innerHTML = "";
    grid.appendChild(el("p", "section-note", t("loading.programs")));
    try {
      var r = await fetch("/api/programs?category=" + encodeURIComponent(cat) + "&q=" + encodeURIComponent(q));
      var data = await r.json();
      window._allProgs = data;
      renderPrograms(data);
    } catch (e) {
      grid.innerHTML = "";
      grid.appendChild(el("div", "empty-list", t("error.programs")));
    }
  }

  function renderPrograms(progs) {
    var grid = byId("programsList");
    if (!grid) return;
    grid.innerHTML = "";
    if (!progs.length) {
      grid.appendChild(el("div", "empty-list", t("empty.noMatch")));
      return;
    }
    progs.slice(0, 40).forEach(function (p) { grid.appendChild(programCard(p, false)); });
  }

  async function loadRecommended() {
    var list = byId("recommendedList");
    if (!list) return;
    try {
      if (!window._allProgs.length) {
        var r = await fetch("/api/programs");
        window._allProgs = await r.json();
      }
      list.innerHTML = "";
      window._allProgs.slice(0, 3).forEach(function (p) { list.appendChild(programCard(p, true)); });
    } catch (e) { /* silent */ }
  }

  async function loadStats() {
    try {
      var r = await fetch("/api/health");
      var d = await r.json();
      if (byId("statPrograms") && d.programs_count) {
        byId("statPrograms").textContent = d.programs_count + "+";
      }
    } catch (e) { /* silent */ }
  }

  /* ---------- Saved programs ---------- */
  function saveProgram(id) {
    var p = findProgram(id);
    if (!p) return;
    var idx = S.saved.findIndex(function (s) { return s.id === id; });
    if (idx >= 0) {
      S.saved.splice(idx, 1);
      showToast(t("toast.unsaved"));
    } else {
      S.saved.push({ id: p.id, title: p.title });
      showToast(t("toast.saved"));
    }
    persistSaved();
    loadPrograms();
    if (loaded.saved) renderSaved();
  }

  function renderSaved() {
    var list = byId("savedList");
    if (!list) return;
    list.innerHTML = "";
    if (!S.saved.length) {
      list.appendChild(el("div", "empty-list", t("empty.saved")));
      return;
    }
    S.saved.forEach(function (s) {
      var row = el("div", "saved-row");
      var icon = el("i", "fa-solid fa-bookmark");
      icon.style.color = "#087b5c";
      row.appendChild(icon);
      row.appendChild(el("span", null, s.title));
      var view = el("button", "pill-btn", t("saved.view"));
      view.setAttribute("data-detail", s.id);
      row.appendChild(view);
      var remove = el("button", "pill-btn", t("saved.remove"));
      remove.setAttribute("data-remove-saved", s.id);
      row.appendChild(remove);
      list.appendChild(row);
    });
  }

  /* ---------- Program detail modal ---------- */
  function openDetail(id) {
    var p = findProgram(id);
    if (!p) { showToast(t("toast.noDetail")); return; }
    S.currentDetail = p;

    byId("detailTitle").textContent = p.title || "Program";
    byId("detailMeta").textContent = [p.category, p.type, p.verified_at ? "Verified " + p.verified_at : ""].filter(Boolean).join(" · ");
    byId("detailDesc").textContent = p.description || "";

    var fill = function (listId, items) {
      var ul = byId(listId);
      ul.innerHTML = "";
      (Array.isArray(items) && items.length ? items : [t("detail.listFallback")]).forEach(function (x) {
        ul.appendChild(el("li", null, x));
      });
    };
    fill("detailSupport", p.support);
    fill("detailEligibility", p.eligibility);
    fill("detailDocuments", p.documents);
    byId("detailApplication").textContent = p.application || t("detail.applyFallback");

    var srcBtn = byId("detailSource");
    if (p.source_url) { srcBtn.href = p.source_url; srcBtn.style.display = ""; }
    else { srcBtn.style.display = "none"; }

    var saved = S.saved.some(function (s) { return s.id === p.id; });
    byId("detailSaveText").textContent = saved ? t("card.saved") : t("card.save");

    byId("detailModal").style.display = "flex";
  }

  /* =====================
     ELIGIBILITY
     ===================== */
  async function checkEligibility() {
    var btn = byId("eligCheckBtn");
    var box = byId("eligibilityResult");
    var body = {
      income: byId("eligIncome").value,
      employment_status: byId("eligEmployment").value,
      city: byId("eligCity").value || user.city || "Karachi",
      cnic: byId("eligCnic").value,
      category: "all", education_level: "", special_criteria: []
    };
    box.innerHTML = "";
    box.appendChild(el("p", "section-note", t("checking")));
    btn.disabled = true;
    try {
      var r = await fetch("/api/eligibility", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      var d = await r.json();
      box.innerHTML = "";
      var matches = d.matches || [];
      if (!matches.length) {
        box.appendChild(el("div", "empty-list", t("empty.noElig")));
        return;
      }
      var headText = matches.length === 1 ? t("elig.matchOne") : t("elig.matchesFound").replace("{n}", String(matches.length));
      var head = el("h4", null, headText);
      head.style.cssText = "margin:18px 0 4px;color:#17362e;";
      box.appendChild(head);
      var results = el("div", "elig-results");
      matches.forEach(function (m) {
        var card = el("div", "elig-card");
        var head2 = el("div", "elig-head");
        head2.appendChild(el("strong", null, m.program ? m.program.title : "Program"));
        var score = el("span", "elig-score", m.score + "%");
        score.style.background = m.score >= 75 ? "#0b7a5b" : m.score >= 50 ? "#d99a26" : "#8a9895";
        head2.appendChild(score);
        card.appendChild(head2);
        card.appendChild(el("span", "elig-badge", m.match_level || "Potential match"));
        if (Array.isArray(m.reasons) && m.reasons.length) {
          var ul = el("ul");
          m.reasons.forEach(function (r2) { ul.appendChild(el("li", null, r2)); });
          card.appendChild(ul);
        }
        results.appendChild(card);
      });
      box.appendChild(results);
    } catch (e) {
      box.innerHTML = "";
      box.appendChild(el("div", "empty-list", t("error.elig")));
    } finally {
      btn.disabled = false;
    }
  }

  /* =====================
     ORGANIZATIONS (ecosystem: verified org directory + org posts)
     ===================== */
  var orgEcoCache = { orgs: [], posts: [] };

  function pricingLabel(pricing) {
    var p = String(pricing || "Free").toLowerCase();
    if (p === "paid") return t("orgs.paid");
    if (p === "subsidized") return t("orgs.subsidized");
    return t("orgs.free");
  }

  function orgMetaItem(icon, text) {
    var span = el("span");
    span.appendChild(el("i", "fa-solid " + icon));
    span.appendChild(document.createTextNode(text));
    return span;
  }

  function orgDirectoryCard(o) {
    var card = el("div", "org-directory-card");
    var head = el("h3");
    head.appendChild(document.createTextNode(o.name || "Organization"));
    head.appendChild(el("span", "chip chip-approved", t("orgs.verified")));
    card.appendChild(head);

    var typeLine = [o.org_type, o.city, o.province].filter(Boolean).join(" · ");
    if (typeLine) card.appendChild(el("span", "section-note", typeLine));
    if (o.description) card.appendChild(el("p", null, truncate(o.description, 190)));

    var meta = el("div", "org-directory-meta");
    if (o.services) meta.appendChild(orgMetaItem("fa-hand-holding-heart", t("orgs.services") + ": " + truncate(o.services, 90)));
    if (o.opening_hours) meta.appendChild(orgMetaItem("fa-clock", t("orgs.hours") + ": " + truncate(o.opening_hours, 60)));
    if (o.pricing) meta.appendChild(orgMetaItem("fa-tag", pricingLabel(o.pricing)));
    if (o.discount) meta.appendChild(orgMetaItem("fa-percent", t("orgs.discount") + ": " + truncate(o.discount, 40)));
    if (o.contact) meta.appendChild(orgMetaItem("fa-phone", o.contact));
    if (meta.childNodes.length) card.appendChild(meta);

    var actions = el("div", "org-post-actions");
    if (o.website && /^https?:\/\//i.test(o.website)) {
      var link = el("a", "pill-btn", t("orgs.website"));
      link.href = o.website;
      link.target = "_blank";
      link.rel = "noopener";
      actions.appendChild(link);
    }
    if (o.address) {
      var maps = el("a", "pill-btn", t("orgs.map"));
      maps.href = "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent(o.address);
      maps.target = "_blank";
      maps.rel = "noopener";
      actions.appendChild(maps);
    }
    if (actions.childNodes.length) card.appendChild(actions);
    return card;
  }

  function orgEcoPostCard(p) {
    var card = el("div", "org-eco-post");
    card.appendChild(el("h4", null, p.title || "Post"));

    var chips = el("div", "org-post-chips");
    chips.appendChild(el("span", "chip chip-neutral", p.org_name || "Organization"));
    if (p.category) chips.appendChild(el("span", "chip chip-neutral", p.category));
    if (p.post_type) chips.appendChild(el("span", "chip chip-neutral", p.post_type));
    chips.appendChild(el("span", "chip chip-free", pricingLabel(p.pricing)));
    card.appendChild(chips);

    if (p.description) card.appendChild(el("p", null, truncate(p.description, 230)));

    var meta = el("div", "org-post-meta");
    if (p.location) meta.appendChild(orgMetaItem("fa-location-dot", p.location));
    if (p.contact) meta.appendChild(orgMetaItem("fa-phone", p.contact));
    if (p.website && /^https?:\/\//i.test(p.website)) {
      var link = el("a");
      link.href = p.website;
      link.target = "_blank";
      link.rel = "noopener";
      link.style.cssText = "display:inline-flex;align-items:center;gap:6px;color:#0b805f;text-decoration:none;font-weight:700;";
      link.appendChild(el("i", "fa-solid fa-arrow-up-right-from-square"));
      link.appendChild(document.createTextNode(t("orgs.website")));
      meta.appendChild(link);
    }
    if (Array.isArray(p.eligibility) && p.eligibility.length) {
      meta.appendChild(orgMetaItem("fa-user-check", t("modal.eligibility") + ": " + truncate(p.eligibility.join(" · "), 90)));
    }
    if (Array.isArray(p.documents) && p.documents.length) {
      meta.appendChild(orgMetaItem("fa-file-lines", t("modal.documents") + ": " + truncate(p.documents.join(" · "), 90)));
    }
    if (meta.childNodes.length) card.appendChild(meta);
    return card;
  }

  function renderOrganizationsSection() {
    var grid = byId("orgDirectoryGrid");
    var feed = byId("orgPostsFeed");
    var q = byId("orgSearch") ? byId("orgSearch").value.trim().toLowerCase() : "";
    var type = byId("orgTypeFilter") ? byId("orgTypeFilter").value : "all";

    if (grid) {
      grid.innerHTML = "";
      var filtered = orgEcoCache.orgs.filter(function (o) {
        if (type !== "all" && (o.org_type || "") !== type) return false;
        if (q) {
          var hay = [o.name, o.org_type, o.city, o.province, o.services, o.description]
            .map(function (x) { return String(x || "").toLowerCase(); }).join(" ");
          if (hay.indexOf(q) === -1) return false;
        }
        return true;
      });
      if (!filtered.length) {
        grid.appendChild(el("div", "empty-list", t("orgs.empty")));
      } else {
        filtered.slice(0, 30).forEach(function (o) { grid.appendChild(orgDirectoryCard(o)); });
      }
    }

    if (feed) {
      feed.innerHTML = "";
      if (!orgEcoCache.posts.length) {
        feed.appendChild(el("div", "empty-list", t("orgs.emptyPosts")));
      } else {
        orgEcoCache.posts.slice(0, 12).forEach(function (p) { feed.appendChild(orgEcoPostCard(p)); });
      }
    }
  }

  async function loadOrganizationsSection() {
    var grid = byId("orgDirectoryGrid");
    var feed = byId("orgPostsFeed");
    if (!grid && !feed) return;
    if (grid) { grid.innerHTML = ""; grid.appendChild(el("p", "section-note", t("loading.programs"))); }
    if (feed) { feed.innerHTML = ""; feed.appendChild(el("p", "section-note", t("loading.programs"))); }
    try {
      var results = await Promise.all([
        fetch("/api/public/approved-organizations").then(function (r) { return r.json(); }).catch(function () { return { organizations: [] }; }),
        fetch("/api/org-posts").then(function (r) { return r.json(); }).catch(function () { return { posts: [] }; })
      ]);
      orgEcoCache.orgs = (results[0] && results[0].organizations) || [];
      orgEcoCache.posts = (results[1] && results[1].posts) || [];
      renderOrganizationsSection();
    } catch (e) {
      if (grid) { grid.innerHTML = ""; grid.appendChild(el("div", "empty-list", t("orgs.loadFail"))); }
      if (feed) feed.innerHTML = "";
    }
  }

  if (byId("orgSearch")) byId("orgSearch").addEventListener("input", function () { renderOrganizationsSection(); });
  if (byId("orgTypeFilter")) byId("orgTypeFilter").addEventListener("change", function () { renderOrganizationsSection(); });
  if (byId("orgsRefresh")) byId("orgsRefresh").addEventListener("click", function () { loadOrganizationsSection(); });

  async function fetchApplications() {
    try {
      var r = await fetch("/api/user/applications", { headers: { "X-User-Email": user.email } });
      var d = await r.json();
      return d.applications || [];
    } catch (e) { return []; }
  }

  function applicationRow(a) {
    var prog = findProgram(a.program_id);
    var row = el("div", "app-row");
    var left = el("div");
    left.appendChild(el("strong", null, prog ? prog.title : a.program_id));
    var date = a.submitted_at ? new Date(a.submitted_at).toLocaleDateString() : "";
    left.appendChild(el("small", null, t("submitted") + " " + date + (a.id ? " · " + a.id : "")));
    row.appendChild(left);
    var status = el("span", "status-pill " + (a.status || "pending"), a.status || "pending");
    row.appendChild(status);
    return row;
  }

  async function loadRecentApps() {
    var box = byId("recentApps");
    if (!box) return;
    var apps = await fetchApplications();
    box.innerHTML = "";
    if (!apps.length) {
      var empty = el("div", "activity-empty");
      var icon = el("div", "empty-icon", "📄");
      empty.appendChild(icon);
      empty.appendChild(el("strong", null, t("empty.noAppsTitle")));
      var p = el("p", null, t("empty.noAppsText"));
      empty.appendChild(p);
      var cta = el("button", "outline-small", t("empty.browse"));
      cta.setAttribute("data-action", "programs");
      empty.appendChild(cta);
      box.appendChild(empty);
      return;
    }
    apps.slice(-3).reverse().forEach(function (a) { box.appendChild(applicationRow(a)); });
  }

  /* =====================
     NEARBY MAP
     ===================== */
  function initMap() {
    if (S.map) return;
    S.map = L.map("mapView").setView([30.3753, 69.3451], 5);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "&copy; OpenStreetMap" }).addTo(S.map);
    S.markers = L.layerGroup().addTo(S.map);
  }

  async function loadFacilitiesMap() {
    if (!S.map) initMap();
    var city = byId("nearbyCity") ? byId("nearbyCity").value : "all";
    var cat = byId("nearbyCategory") ? byId("nearbyCategory").value : "all";
    try {
      var r = await fetch("/api/facilities?city=" + encodeURIComponent(city) + "&category=" + encodeURIComponent(cat));
      var d = await r.json();
      S.markers.clearLayers();

      var dbFacs = [];
      try {
        var r2 = await fetch("/api/facilities/db?city=" + encodeURIComponent(city) + "&category=" + encodeURIComponent(cat));
        var d2 = await r2.json();
        dbFacs = d2.facilities || [];
      } catch (e) { /* silent */ }

      var markerColors = { hospital: "#dc2626", welfare: "#087b5c", university: "#2563eb" };

      (d.facilities || []).forEach(function (f) {
        var color = markerColors[f.category] || "#64748b";
        var icon = L.divIcon({
          className: "custom-marker",
          html: '<div style="background:' + color + ';width:24px;height:24px;border-radius:50%;border:2px solid white;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 6px rgba(0,0,0,0.3);"><i class="fa-solid fa-' + (f.category === "hospital" ? "hospital" : f.category === "university" ? "graduation-cap" : "hand-holding-heart") + '" style="color:white;font-size:11px;"></i></div>',
          iconSize: [24, 24], iconAnchor: [12, 12]
        });
        L.marker([f.lat, f.lon], { icon: icon }).addTo(S.markers)
          .bindPopup("<strong>" + f.name + "</strong><br><em>" + f.type + "</em><br>" + (f.phone || "") + "<br><small>Curated center</small>");
      });

      dbFacs.forEach(function (f) {
        var color = markerColors[f.category] || "#64748b";
        var icon = L.divIcon({
          className: "custom-marker",
          html: '<div style="background:' + color + ';width:20px;height:20px;border-radius:4px;border:2px solid white;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 6px rgba(0,0,0,0.3);opacity:0.85;"><i class="fa-solid fa-location-dot" style="color:white;font-size:10px;"></i></div>',
          iconSize: [20, 20], iconAnchor: [10, 10]
        });
        L.marker([f.lat, f.lon], { icon: icon }).addTo(S.markers)
          .bindPopup("<strong>" + f.name + "</strong><br><em>" + (f.facility_type || f.category) + "</em><br>" + (f.address || "") + "<br><small>Geo-verified (OpenStreetMap)</small>");
      });

      var all = (d.facilities || []).concat(dbFacs);
      if (all.length) S.map.setView([all[0].lat, all[0].lon], 11);
      else showToast("No facilities found for this filter.");
    } catch (e) {
      showToast("Could not load the map right now.");
    }
  }

  function locateMe() {
    if (!S.map) initMap();
    if (!navigator.geolocation) { showToast("Geolocation is not supported by your browser."); return; }
    navigator.geolocation.getCurrentPosition(function (pos) {
      S.map.setView([pos.coords.latitude, pos.coords.longitude], 13);
      L.marker([pos.coords.latitude, pos.coords.longitude]).addTo(S.markers).bindPopup("You are here").openPopup();
    }, function () {
      showToast("Could not get your location. Please allow location access.");
    });
  }

  /* =====================
     EMERGENCY
     ===================== */
  async function loadEmergency() {
    var list = byId("emergencyList");
    if (!list) return;
    try {
      var r = await fetch("/api/emergency");
      var data = await r.json();
      list.innerHTML = "";
      data.forEach(function (e2) {
        var item = el("div", "emergency-item");
        var icon = el("i", "fa-solid fa-phone");
        item.appendChild(icon);
        var body = el("div", "ei-body");
        var line = el("div");
        line.appendChild(el("strong", null, e2.name));
        var num = el("span", "ei-number", e2.number);
        line.appendChild(num);
        body.appendChild(line);
        body.appendChild(el("small", null, e2.type + " — " + e2.coverage));
        item.appendChild(body);
        list.appendChild(item);
      });
    } catch (e) { /* keep static */ }
  }

  /* =====================
     PROFILE
     ===================== */
  function renderProfile() {
    var grid = byId("profileGrid");
    if (!grid) return;
    grid.innerHTML = "";

    var card = el("div", "profile-edit-card");
    var head = el("div", "profile-edit-head");
    head.appendChild(el("span", "avatar", (user.name || user.email).trim().charAt(0).toUpperCase()));
    var headCopy = el("div", "profile-edit-headcopy");
    headCopy.appendChild(el("strong", null, user.name || user.email));
    headCopy.appendChild(el("small", null, user.email));
    head.appendChild(headCopy);
    card.appendChild(head);

    card.appendChild(el("p", "profile-edit-hint", t("pf.editHint")));

    function field(labelText, inputId, value, opts) {
      opts = opts || {};
      var wrap = el("div", "profile-edit-field");
      wrap.appendChild(el("label", "field-label", labelText));
      var input = document.createElement("input");
      input.type = "text";
      input.className = "kh-input";
      input.id = inputId;
      input.value = value || "";
      if (opts.readonly) { input.readOnly = true; input.classList.add("profile-readonly"); }
      if (opts.placeholder) input.placeholder = opts.placeholder;
      wrap.appendChild(input);
      return wrap;
    }

    var row1 = el("div", "form-row-2");
    row1.appendChild(field(t("pf.name"), "profileNameInput", user.name));
    row1.appendChild(field(t("pf.email"), "profileEmailInput", user.email, { readonly: true }));
    card.appendChild(row1);

    var row2 = el("div", "form-row-2");
    row2.appendChild(field(t("pf.phone"), "profilePhoneInput", user.phone, { placeholder: "0300-1234567" }));
    row2.appendChild(field(t("pf.city"), "profileCityInput", user.city, { placeholder: "Karachi" }));
    card.appendChild(row2);

    card.appendChild(field(t("pf.cnic"), "profileCnicInput", user.cnic, { placeholder: "42101-1234567-1" }));

    var actions = el("div", "profile-edit-actions");
    var cancelBtn = el("button", "secondary-dashboard-btn", t("pf.cancel"));
    cancelBtn.type = "button";
    cancelBtn.addEventListener("click", renderProfile);
    var saveBtn = el("button", "primary-dashboard-btn", t("pf.save"));
    saveBtn.type = "button";
    saveBtn.id = "profileSaveBtn";
    saveBtn.addEventListener("click", saveProfile);
    actions.appendChild(cancelBtn);
    actions.appendChild(saveBtn);
    card.appendChild(actions);

    grid.appendChild(card);
  }

  async function saveProfile() {
    var nameInput = byId("profileNameInput");
    var phoneInput = byId("profilePhoneInput");
    var cityInput = byId("profileCityInput");
    var cnicInput = byId("profileCnicInput");
    var saveBtn = byId("profileSaveBtn");
    if (!nameInput || !saveBtn) return;

    var name = nameInput.value.trim();
    if (!name) { showToast(t("pf.nameReq")); nameInput.focus(); return; }
    var cnic = (cnicInput.value || "").trim();
    if (cnic && !/^\d{5}-\d{7}-\d$/.test(cnic)) { showToast(t("pf.cnicHint")); cnicInput.focus(); return; }

    saveBtn.disabled = true;
    try {
      var r = await fetch("/api/user/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json", "X-User-Email": user.email },
        body: JSON.stringify({
          name: name,
          phone: (phoneInput.value || "").trim(),
          city: (cityInput.value || "").trim(),
          cnic: cnic
        })
      });
      var d = {};
      try { d = await r.json(); } catch (e) { /* non-JSON error */ }
      if (!r.ok || !d.success) throw new Error(d.detail || "failed");
      user = d.user || user;
      try { localStorage.setItem("kai_user", JSON.stringify(user)); } catch (e) { /* private mode */ }
      renderIdentity();
      renderProfile();
      showToast(t("toast.profileSaved"));
    } catch (err) {
      showToast(t("toast.profileError"));
    }
    saveBtn.disabled = false;
  }

  /* =====================
     APPLICATION WIZARD
     ===================== */
  async function openWizard(programId) {
    S.wizStep = 1;
    var sel = byId("wizProgram");
    sel.innerHTML = "";
    sel.appendChild(el("option", null, "-- Choose a program --")).value = "";
    try {
      if (!window._allProgs.length) {
        var r = await fetch("/api/programs");
        window._allProgs = await r.json();
      }
      window._allProgs.slice(0, 150).forEach(function (p) {
        var o = el("option", null, p.title);
        o.value = p.id;
        sel.appendChild(o);
      });
      if (programId) sel.value = programId;
    } catch (e) { /* silent */ }
    updateWizardUI();
    byId("wizardModal").style.display = "flex";
  }

  function wizardNav(dir) {
    var newStep = S.wizStep + dir;
    if (newStep < 1 || newStep > 4) return;
    if (dir > 0 && S.wizStep === 1 && !byId("wizProgram").value) { showToast(t("toast.selectProgram")); return; }
    if (dir > 0 && S.wizStep === 2 && !byId("wizCnic").value.trim()) { showToast(t("toast.enterCnic")); return; }
    if (dir > 0 && S.wizStep === 4) { submitWizardApp(); return; }
    S.wizStep = newStep;
    updateWizardUI();
  }

  function updateWizardUI() {
    document.querySelectorAll(".wizard-step").forEach(function (s) {
      s.classList.toggle("active", +s.dataset.step <= S.wizStep);
    });
    for (var i = 1; i <= 4; i++) byId("wizStep" + i).style.display = i === S.wizStep ? "block" : "none";
    byId("wizPrev").style.display = S.wizStep > 1 ? "inline-flex" : "none";
    byId("wizNext").textContent = S.wizStep === 4 ? t("wiz.submit") : t("wiz.next");

    if (S.wizStep === 3) {
      var prog = findProgram(byId("wizProgram").value);
      var docs = prog && Array.isArray(prog.documents) && prog.documents.length
        ? prog.documents : ["CNIC", "Proof of Residence / Income"];
      var box = byId("wizDocChecklist");
      box.innerHTML = "";
      docs.forEach(function (d) {
        var label = el("label", "doc-check");
        var cb = document.createElement("input");
        cb.type = "checkbox";
        cb.checked = true;
        label.appendChild(cb);
        label.appendChild(document.createTextNode(" " + d));
        box.appendChild(label);
      });
    }

    if (S.wizStep === 4) {
      var prog2 = findProgram(byId("wizProgram").value);
      var box2 = byId("wizReview");
      box2.innerHTML = "";
      [[t("rv.program"), prog2 ? prog2.title : byId("wizProgram").value],
       [t("wiz.cnic"), byId("wizCnic").value],
       [t("wiz.phone"), byId("wizPhone").value],
       [t("elig.city"), byId("wizCity").value],
       [t("rv.income"), "Rs. " + byId("wizIncome").value]].forEach(function (row) {
        var r = el("div", "review-row");
        r.appendChild(el("strong", null, row[0] + ":"));
        r.appendChild(el("span", null, row[1] || "—"));
        box2.appendChild(r);
      });
    }
  }

  async function submitWizardApp() {
    var pid = byId("wizProgram").value;
    var btn = byId("wizNext");
    btn.disabled = true;
    btn.textContent = t("toast.submitting");
    try {
      var r = await fetch("/api/user/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-User-Email": user.email },
        body: JSON.stringify({ program_id: pid, status: "pending", notes: "" })
      });
      if (!r.ok) throw new Error("failed");
      byId("wizardModal").style.display = "none";
      showToast(t("toast.applied"));
      loaded.applications = false;
      if (loaded.overview) { loaded.overview = false; }
      showSection("applications");
    } catch (e) {
      showToast(t("toast.applyFail"));
    } finally {
      btn.disabled = false;
      btn.textContent = t("wiz.submit");
    }
  }

  /* =====================
     GLOBAL EVENT WIRING
     ===================== */
  document.addEventListener("click", function (event) {
    var detail = event.target.closest("[data-detail]");
    if (detail) { openDetail(detail.dataset.detail); return; }

    var save = event.target.closest("[data-save]");
    if (save) { saveProgram(save.dataset.save); return; }

    var apply = event.target.closest("[data-apply]");
    if (apply) { openWizard(apply.dataset.apply); return; }

    var removeSaved = event.target.closest("[data-remove-saved]");
    if (removeSaved) {
      S.saved = S.saved.filter(function (s) { return s.id !== removeSaved.dataset.removeSaved; });
      persistSaved();
      renderSaved();
      showToast(t("toast.unsaved"));
      return;
    }

    var close = event.target.closest("[data-close]");
    if (close) { byId(close.dataset.close).style.display = "none"; return; }

    // Close modals when clicking the overlay backdrop
    if (event.target.classList && event.target.classList.contains("modal-overlay")) {
      event.target.style.display = "none";
    }
  });

  if (byId("detailSave")) {
    byId("detailSave").addEventListener("click", function () {
      if (S.currentDetail) saveProgram(S.currentDetail.id);
      var saved = S.saved.some(function (s) { return s.id === (S.currentDetail || {}).id; });
      byId("detailSaveText").textContent = saved ? t("card.saved") : t("card.save");
    });
  }

  if (byId("detailApply")) {
    byId("detailApply").addEventListener("click", function () {
      if (!S.currentDetail) return;
      byId("detailModal").style.display = "none";
      openWizard(S.currentDetail.id);
    });
  }

  if (byId("eligCheckBtn")) byId("eligCheckBtn").addEventListener("click", checkEligibility);
  if (byId("wizNext")) byId("wizNext").addEventListener("click", function () { wizardNav(1); });
  if (byId("wizPrev")) byId("wizPrev").addEventListener("click", function () { wizardNav(-1); });
  if (byId("nearbyRefresh")) byId("nearbyRefresh").addEventListener("click", loadFacilitiesMap);
  if (byId("nearbyLocate")) byId("nearbyLocate").addEventListener("click", locateMe);
  if (byId("nearbyCity")) byId("nearbyCity").addEventListener("change", loadFacilitiesMap);
  if (byId("nearbyCategory")) byId("nearbyCategory").addEventListener("change", loadFacilitiesMap);

  if (byId("progCategory")) byId("progCategory").addEventListener("change", loadPrograms);
  if (byId("progSearch")) {
    byId("progSearch").addEventListener("input", function () {
      clearTimeout(S.progDebounce);
      S.progDebounce = setTimeout(loadPrograms, 350);
    });
  }

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      byId("detailModal").style.display = "none";
      byId("wizardModal").style.display = "none";
    }
  });

  /* =====================
     HERO SLIDER + TICKER (public settings from admin)
     ===================== */
  var heroTimer = null;

  async function loadPublicSettings() {
    try {
      var r = await fetch("/api/public/settings");
      var d = await r.json();
      var alerts = (d.alerts && d.alerts.length)
        ? d.alerts
        : (Array.isArray(d.ticker_text) ? d.ticker_text.map(function (txt, i) {
            return { id: "legacy_" + i, text: txt, active: true, order: i };
          }) : []);
      buildHeroSlider(d.hero_slides || []);
      buildTicker(alerts);
    } catch (e) {
      /* network error: keep existing hero fallback + no ticker */
    }
  }

  function buildHeroSlider(slides) {
    var track = byId("heroSlideTrack");
    var fallback = byId("heroFallback");
    var visual = byId("heroVisual");
    var controls = byId("heroSliderControls");
    var dots = byId("heroDots");
    if (!track || !fallback) return;

    S.heroSlides = (slides || []).filter(function (s) {
      return s && (s.title || s.description || s.image || s.video);
    });

    if (!S.heroSlides.length) {
      track.innerHTML = "";
      fallback.style.display = "";
      if (visual) visual.style.display = "";
      if (controls) controls.style.display = "none";
      stopHeroTimer();
      return;
    }

    fallback.style.display = "none";
    if (visual) visual.style.display = "none";
    if (controls) controls.style.display = "flex";

    track.innerHTML = "";
    if (dots) dots.innerHTML = "";

    S.heroSlides.forEach(function (s, i) {
      var slide = el("div", "hero-slide" + (i === 0 ? " active" : ""));

      // Video preferred; image as fallback when no video exists.
      if (s.video) {
        var v = document.createElement("video");
        v.className = "hero-media";
        v.src = s.video;
        v.autoplay = true;
        v.muted = true;
        v.loop = true;
        v.playsInline = true;
        v.setAttribute("playsinline", "");
        v.setAttribute("muted", "");
        slide.appendChild(v);
      } else if (s.image) {
        var img = document.createElement("img");
        img.className = "hero-media";
        img.src = s.image;
        img.alt = s.title || "KhidmatAI";
        img.loading = "lazy";
        slide.appendChild(img);
      } else if (s.bg_color) {
        slide.style.background = s.bg_color;
      }
      slide.appendChild(el("div", "hero-media-overlay"));

      var copy = el("div", "hero-copy hero-slide-copy");
      copy.appendChild(el("span", "eyebrow-pill", t("hero.spot")));
      if (s.title) copy.appendChild(el("h1", null, s.title));
      if (s.description) copy.appendChild(el("p", null, s.description));
      if (s.button_text && s.button_url) {
        var actions = el("div", "hero-actions");
        var isHttp = /^https?:\/\//i.test(s.button_url);
        var btn;
        if (isHttp) {
          btn = el("a", "primary-dashboard-btn", s.button_text);
          btn.href = s.button_url;
          btn.target = "_blank";
          btn.rel = "noopener";
        } else {
          var sectionName = String(s.button_url).replace(/^#/, "");
          btn = el("button", "primary-dashboard-btn", s.button_text);
          btn.type = "button";
          if (SECTION_TITLE_KEYS[sectionName]) btn.setAttribute("data-action", sectionName);
        }
        actions.appendChild(btn);
        copy.appendChild(actions);
      }
      slide.appendChild(copy);
      track.appendChild(slide);

      if (dots) {
        var dot = document.createElement("button");
        dot.type = "button";
        dot.className = "hero-dot" + (i === 0 ? " active" : "");
        dot.setAttribute("aria-label", "Slide " + (i + 1));
        dot.setAttribute("data-hero-dot", String(i));
        dots.appendChild(dot);
      }
    });

    S.heroIndex = 0;
    startHeroTimer();
  }

  function showHeroSlide(i) {
    var slideNodes = document.querySelectorAll("#heroSlideTrack .hero-slide");
    var dotNodes = document.querySelectorAll("#heroDots .hero-dot");
    if (!slideNodes.length) return;
    S.heroIndex = (i + slideNodes.length) % slideNodes.length;
    slideNodes.forEach(function (s, idx) { s.classList.toggle("active", idx === S.heroIndex); });
    dotNodes.forEach(function (d, idx) { d.classList.toggle("active", idx === S.heroIndex); });
  }

  function startHeroTimer() {
    stopHeroTimer();
    if (S.heroSlides && S.heroSlides.length > 1) {
      heroTimer = setInterval(function () { showHeroSlide(S.heroIndex + 1); }, 7000);
    }
  }

  function stopHeroTimer() {
    if (heroTimer) { clearInterval(heroTimer); heroTimer = null; }
  }

  if (byId("heroNext")) byId("heroNext").addEventListener("click", function () { showHeroSlide(S.heroIndex + 1); startHeroTimer(); });
  if (byId("heroPrev")) byId("heroPrev").addEventListener("click", function () { showHeroSlide(S.heroIndex - 1); startHeroTimer(); });

  document.addEventListener("click", function (event) {
    var dot = event.target.closest("[data-hero-dot]");
    if (dot) { showHeroSlide(+dot.dataset.heroDot); startHeroTimer(); }
  });

  var heroBox = byId("dashboardHero");
  if (heroBox) {
    heroBox.addEventListener("mouseenter", stopHeroTimer);
    heroBox.addEventListener("mouseleave", startHeroTimer);
  }

  /* ---------- Ticker & alerts bar ---------- */
  function buildTicker(alerts) {
    var bar = byId("tickerBar");
    var track2 = byId("tickerTrack");
    if (!bar || !track2) return;
    var items = (alerts || []).map(function (a) { return (a && a.text ? String(a.text) : "").trim(); }).filter(Boolean);
    if (!items.length) { bar.style.display = "none"; return; }
    bar.style.display = "flex";
    track2.innerHTML = "";

    // Repeat items so the marquee covers the viewport, then duplicate once
    // for a seamless translateX(-50%) loop.
    var base = items.slice();
    while (base.length < 6) base = base.concat(items);
    var seq = base.concat(base);
    seq.forEach(function (txt) {
      var item = el("span", "ticker-item", txt);
      track2.appendChild(item);
    });
    track2.style.animationDuration = Math.max(24, seq.length * 4) + "s";
  }

  /* ---------- Boot ---------- */
  applyLanguage(S.lang);
  renderProfile();
  var initial = window.location.hash.replace("#", "");
  showSection(SECTION_TITLE_KEYS[initial] ? initial : "overview", false);
  loadPublicSettings();
})();
