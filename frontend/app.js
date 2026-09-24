/* ==========================================================================
   MULTI-BUSINESS AI BOOKING ASSISTANT - FRONTEND CONTROLLER
   ========================================================================== */

const API_BASE = "http://127.0.0.1:8000";

let currentUser = null; // { id, username, phone, role, business_id }
let businesses = [];
let services = [];
let staff = [];
let selectedBusinessId = null;
let ownerTestingMode = false;
let speechEnabled = false;

document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

function initApp() {
  setupEventListeners();
  setup3DRobotTracking();
  setupDraggableChatWidget();
  checkAuthSession();
}

/* ==========================================================================
   1. AUTHENTICATION & SESSION MANAGEMENT
   ========================================================================== */
function checkAuthSession() {
  const savedUser = localStorage.getItem("booking_ai_user");
  if (savedUser) {
    try {
      currentUser = JSON.parse(savedUser);
    } catch (e) {
      currentUser = null;
    }
  }

  const loginModal = document.getElementById("loginModal");
  if (!currentUser) {
    if (loginModal) loginModal.classList.add("open");
    return;
  }

  if (loginModal) loginModal.classList.remove("open");

  // Update Header User Profile Badge
  const nameEl = document.getElementById("headerUserName");
  const roleEl = document.getElementById("headerUserRole");
  const avatarEl = document.getElementById("headerUserAvatar");
  const appRoleSub = document.getElementById("appRoleSub");

  if (nameEl) nameEl.textContent = currentUser.username;
  if (roleEl) roleEl.textContent = currentUser.role === "superadmin" ? "👑 Superadmin" : (currentUser.role === "owner" ? "Business Owner" : "Customer");
  if (avatarEl) avatarEl.src = `https://api.dicebear.com/7.x/bottts/svg?seed=${encodeURIComponent(currentUser.username)}`;
  if (appRoleSub) appRoleSub.textContent = currentUser.role === "superadmin" ? "Superadmin Master Control" : (currentUser.role === "owner" ? "Owner Dashboard" : "Customer Hub");

  // Setup Navigation according to role
  const userNavMenu = document.getElementById("userNavMenu");
  const ownerNavMenu = document.getElementById("ownerNavMenu");
  const superadminNavMenu = document.getElementById("superadminNavMenu");
  const btnTestPage = document.getElementById("btnTestCustomerPage");
  const headerBizSelectWrapper = document.getElementById("headerBizSelectWrapper");
  const btnHeaderBookAppt = document.getElementById("btnHeaderBookAppt");

  if (currentUser.role === "superadmin") {
    document.body.classList.remove("owner-colorful-theme");
    if (userNavMenu) userNavMenu.style.display = "none";
    if (ownerNavMenu) ownerNavMenu.style.display = "none";
    if (superadminNavMenu) superadminNavMenu.style.display = "flex";
    if (btnTestPage) btnTestPage.style.display = "none";
    if (headerBizSelectWrapper) headerBizSelectWrapper.style.display = "flex";
    if (btnHeaderBookAppt) btnHeaderBookAppt.style.display = "none";

    showSection("superadminDashboardView");
    loadSuperadminDashboard();
  } else if (currentUser.role === "owner") {
    document.body.classList.add("owner-colorful-theme");
    if (userNavMenu) userNavMenu.style.display = "none";
    if (ownerNavMenu) ownerNavMenu.style.display = "flex";
    if (superadminNavMenu) superadminNavMenu.style.display = "none";
    if (btnTestPage) btnTestPage.style.display = "inline-flex";
    // Owner owns a specific business - hide global business select dropdown completely
    if (headerBizSelectWrapper) headerBizSelectWrapper.style.display = "none";
    if (btnHeaderBookAppt) btnHeaderBookAppt.style.display = "none";

    showSection("ownerDashboardView");
    if (!currentUser.business_id) {
      loadOwnerDashboard().catch(() => openBusinessOnboardModal());
    } else {
      selectedBusinessId = currentUser.business_id;
      loadOwnerDashboard();
    }
  } else {
    document.body.classList.remove("owner-colorful-theme");
    if (userNavMenu) userNavMenu.style.display = "flex";
    if (ownerNavMenu) ownerNavMenu.style.display = "none";
    if (superadminNavMenu) superadminNavMenu.style.display = "none";
    if (btnTestPage) btnTestPage.style.display = "none";
    if (headerBizSelectWrapper) headerBizSelectWrapper.style.display = "flex";
    if (btnHeaderBookAppt) btnHeaderBookAppt.style.display = "inline-flex";

    showSection("customerBookingPage");
    loadBusinesses();
  }
}

function getAuthHeaders() {
  const headers = { "Content-Type": "application/json" };
  if (currentUser) {
    headers["X-User-Phone"] = currentUser.phone;
    headers["X-User-Role"] = currentUser.role;
  }
  return headers;
}

function switchAuthTab(tab) {
  const loginForm = document.getElementById("loginForm");
  const registerForm = document.getElementById("registerForm");
  const tabBtnLogin = document.getElementById("tabBtnLogin");
  const tabBtnRegister = document.getElementById("tabBtnRegister");

  if (tab === "register") {
    if (loginForm) loginForm.style.display = "none";
    if (registerForm) registerForm.style.display = "block";
    if (tabBtnLogin) tabBtnLogin.className = "btn btn-sm btn-glass";
    if (tabBtnRegister) tabBtnRegister.className = "btn btn-sm btn-primary";
  } else {
    if (loginForm) loginForm.style.display = "block";
    if (registerForm) registerForm.style.display = "none";
    if (tabBtnLogin) tabBtnLogin.className = "btn btn-sm btn-primary";
    if (tabBtnRegister) tabBtnRegister.className = "btn btn-sm btn-glass";
  }
}

// Sign In Form Submit Handler (Existing Users)
document.getElementById("loginForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = document.getElementById("loginUsername").value.trim();
  const password = document.getElementById("loginPassword").value.trim();

  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });

    if (!res.ok) {
      const err = await res.json();
      alert(`Sign In failed: ${err.detail || "Invalid credentials"}`);
      return;
    }

    const data = await res.json();
    currentUser = data.user;
    localStorage.setItem("booking_ai_user", JSON.stringify(currentUser));

    alert(data.message);
    checkAuthSession();
  } catch (err) {
    console.error("Login error:", err);
    alert("Connection error signing in. Please check backend server.");
  }
});

// Registration Form Submit Handler (Business Owners)
document.getElementById("registerForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = document.getElementById("regUsername").value.trim();
  const phone = document.getElementById("regPhone").value.trim();
  const password = document.getElementById("regPassword").value.trim();
  const confirmPassword = document.getElementById("regConfirmPassword").value.trim();
  const role = "owner";

  if (password !== confirmPassword) {
    alert("❌ Passwords do not match! Please check and re-enter.");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, phone, password, role })
    });

    if (!res.ok) {
      const err = await res.json();
      alert(`Registration failed: ${err.detail || "Unable to register"}`);
      return;
    }

    const data = await res.json();
    currentUser = data.user;
    localStorage.setItem("booking_ai_user", JSON.stringify(currentUser));

    alert(data.message);
    checkAuthSession();
  } catch (err) {
    console.error("Registration error:", err);
    alert("Connection error registering. Please check backend server.");
  }
});

function logoutUser() {
  if (confirm("Are you sure you want to log out?")) {
    localStorage.removeItem("booking_ai_user");
    currentUser = null;
    ownerTestingMode = false;
    document.body.classList.remove("owner-colorful-theme");
    window.location.reload();
  }
}

function handleProfileHeaderClick() {
  if (currentUser && currentUser.role === "user") {
    openUserProfileModal();
  } else if (currentUser && currentUser.role === "owner") {
    showOwnerTab("ownerBusinessInfo");
  }
}

/* ==========================================================================
   2. SECTION NAVIGATION & OWNER TESTING MODE
   ========================================================================== */
function showSection(sectionId) {
  document.querySelectorAll(".section").forEach((sec) => sec.classList.remove("active-section"));
  const target = document.getElementById(sectionId);
  if (target) target.classList.add("active-section");

  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.classList.remove("active");
    if (btn.getAttribute("onclick")?.includes(sectionId)) btn.classList.add("active");
  });

  const titles = {
    customerBookingPage: ["Customer Booking Page", "Select business, services, check slots & book"],
    customerServicesView: ["Services Catalog", "Explore all services and availability"],
    assistant: ["AI Booking Workspace", "Voice & Chat assistant for bookings"],
    ownerDashboardView: ["Owner Dashboard", "Manage your business, services, staff & rules"],
    superadminDashboardView: ["👑 Superadmin Master Control", "View system-wide metrics, users, businesses & appointments"]
  };

  if (titles[sectionId]) {
    document.getElementById("page-title").textContent = titles[sectionId][0];
    document.getElementById("page-subtitle").textContent = titles[sectionId][1];
  }

  // Ensure headerBizSelectWrapper is hidden for owner across all tab views
  const headerBizSelectWrapper = document.getElementById("headerBizSelectWrapper");
  if (headerBizSelectWrapper) {
    if (currentUser && currentUser.role === "owner") {
      headerBizSelectWrapper.style.display = "none";
    } else {
      headerBizSelectWrapper.style.display = "flex";
    }
  }

  if (sectionId === "customerBookingPage" || sectionId === "customerServicesView") {
    loadCustomerBookingData();
  }
}

function showSuperadminTab(tabId) {
  showSection("superadminDashboardView");

  document.querySelectorAll(".superadmin-tab").forEach((t) => (t.style.display = "none"));
  const targetTab = document.getElementById(tabId);
  if (targetTab) targetTab.style.display = "block";

  document.querySelectorAll("#superadminNavMenu .nav-item").forEach((btn) => {
    btn.classList.remove("active");
    if (btn.getAttribute("onclick")?.includes(tabId)) btn.classList.add("active");
  });

  if (tabId === "saOverview") loadSuperadminDashboard();
  if (tabId === "saUsers") loadSuperadminUsers();
  if (tabId === "saBusinesses") loadSuperadminBusinesses();
  if (tabId === "saCustomers") loadSuperadminCustomers();
  if (tabId === "saAppointments") loadSuperadminAppointments();
}

async function loadSuperadminDashboard() {
  if (!currentUser || currentUser.role !== "superadmin") return;

  try {
    const res = await fetch(`${API_BASE}/superadmin/dashboard`, { headers: getAuthHeaders() });
    if (!res.ok) return;

    const data = await res.json();
    document.getElementById("saMetricTotalUsers").textContent = data.metrics.total_users;
    document.getElementById("saMetricTotalOwners").textContent = data.metrics.total_owners;
    document.getElementById("saMetricTotalBusinesses").textContent = data.metrics.total_businesses;
    document.getElementById("saMetricTotalAppts").textContent = data.metrics.total_appointments;

    const tbody = document.getElementById("saRecentUsersTable");
    if (tbody) {
      tbody.innerHTML = data.recent_users.length === 0
        ? `<tr><td colspan="6" style="text-align:center; padding:15px; color:#94a3b8;">No registered users yet.</td></tr>`
        : data.recent_users.map((u) => `
          <tr>
            <td>#${u.id}</td>
            <td><strong>${escapeHtml(u.username)}</strong></td>
            <td>${escapeHtml(u.phone)}</td>
            <td><span class="chip" style="font-size:11px; background:rgba(0,242,254,0.15); color:#00f2fe;">${escapeHtml(u.role.toUpperCase())}</span></td>
            <td>${u.business_id ? `#${u.business_id}` : '-'}</td>
            <td>${u.created_at}</td>
          </tr>
        `).join('');
    }
  } catch (err) {
    console.error("Superadmin dashboard error:", err);
  }
}

async function loadSuperadminUsers() {
  try {
    const res = await fetch(`${API_BASE}/superadmin/users`, { headers: getAuthHeaders() });
    const list = await res.json();
    const tbody = document.getElementById("saAllUsersTable");
    if (!tbody) return;

    tbody.innerHTML = list.length === 0
      ? `<tr><td colspan="7" style="text-align:center; padding:15px; color:#94a3b8;">No registered users.</td></tr>`
      : list.map((u) => `
        <tr>
          <td>#${u.id}</td>
          <td><strong>${escapeHtml(u.username)}</strong></td>
          <td>${escapeHtml(u.phone)}</td>
          <td><span class="chip" style="font-size:11px; background:rgba(168,85,247,0.15); color:#a855f7;">${escapeHtml(u.role.toUpperCase())}</span></td>
          <td>${escapeHtml(u.business_name)}</td>
          <td>${u.created_at}</td>
          <td>
            ${u.role !== 'superadmin' ? `<button class="btn btn-sm btn-glass" onclick="deleteUserAccount(${u.id})" style="color:#ef4444;"><i class="fa-solid fa-trash"></i> Delete</button>` : '<span style="font-size:11px; color:#10b981;">Protected</span>'}
          </td>
        </tr>
      `).join('');
  } catch (err) {
    console.error("Superadmin users error:", err);
  }
}

async function deleteUserAccount(userId) {
  if (confirm(`Are you sure you want to delete user account #${userId}?`)) {
    try {
      const res = await fetch(`${API_BASE}/superadmin/users/${userId}`, { method: "DELETE", headers: getAuthHeaders() });
      const data = await res.json();
      alert(data.message);
      loadSuperadminUsers();
      loadSuperadminDashboard();
    } catch (err) {
      console.error("Delete user error:", err);
    }
  }
}

async function loadSuperadminBusinesses() {
  try {
    const res = await fetch(`${API_BASE}/superadmin/businesses`, { headers: getAuthHeaders() });
    const list = await res.json();
    const tbody = document.getElementById("saAllBusinessesTable");
    if (!tbody) return;

    tbody.innerHTML = list.length === 0
      ? `<tr><td colspan="8" style="text-align:center; padding:15px; color:#94a3b8;">No registered businesses found.</td></tr>`
      : list.map((b) => `
        <tr>
          <td>#${b.id}</td>
          <td><strong>${escapeHtml(b.name)}</strong></td>
          <td>${escapeHtml(b.category)}</td>
          <td>${escapeHtml(b.owner_name || '-')}</td>
          <td>${escapeHtml(b.phone)}</td>
          <td>${escapeHtml(b.operating_hours || '-')}</td>
          <td><span class="badge" style="background:rgba(56,189,248,0.15); color:#38bdf8;">${b.metrics.appointments} Appts</span></td>
          <td><span class="status-badge confirmed">${escapeHtml(b.status)}</span></td>
        </tr>
      `).join('');
  } catch (err) {
    console.error("Superadmin businesses error:", err);
  }
}

async function loadSuperadminCustomers() {
  try {
    const res = await fetch(`${API_BASE}/superadmin/customers`, { headers: getAuthHeaders() });
    const list = await res.json();
    const tbody = document.getElementById("saAllCustomersTable");
    if (!tbody) return;

    tbody.innerHTML = list.length === 0
      ? `<tr><td colspan="7" style="text-align:center; padding:15px; color:#94a3b8;">No customer profiles found.</td></tr>`
      : list.map((c) => `
        <tr>
          <td>#${c.id}</td>
          <td><strong>${escapeHtml(c.business_name)}</strong></td>
          <td>${escapeHtml(c.name)}</td>
          <td>${escapeHtml(c.phone)}</td>
          <td>${escapeHtml(c.email || '-')}</td>
          <td>${c.appointments_count} Appts</td>
          <td>${c.created_at}</td>
        </tr>
      `).join('');
  } catch (err) {
    console.error("Superadmin customers error:", err);
  }
}

async function loadSuperadminAppointments() {
  try {
    const res = await fetch(`${API_BASE}/superadmin/appointments`, { headers: getAuthHeaders() });
    const list = await res.json();
    const tbody = document.getElementById("saAllAppointmentsTable");
    if (!tbody) return;

    tbody.innerHTML = list.length === 0
      ? `<tr><td colspan="8" style="text-align:center; padding:15px; color:#94a3b8;">No appointments scheduled in the system.</td></tr>`
      : list.map((a) => `
        <tr>
          <td>#${a.id}</td>
          <td><strong>${escapeHtml(a.business_name)}</strong></td>
          <td>${escapeHtml(a.customer_name)}</td>
          <td>${escapeHtml(a.customer_phone)}</td>
          <td>${escapeHtml(a.service_name)}</td>
          <td>${escapeHtml(a.staff_name)}</td>
          <td>${a.appointment_date} at ${a.appointment_time}</td>
          <td><span class="status-badge ${a.status.toLowerCase()}">${escapeHtml(a.status)}</span></td>
        </tr>
      `).join('');
  } catch (err) {
    console.error("Superadmin appointments error:", err);
  }
}

function showOwnerTab(tabId) {
  showSection("ownerDashboardView");

  document.querySelectorAll(".owner-tab").forEach((t) => (t.style.display = "none"));
  const targetTab = document.getElementById(tabId);
  if (targetTab) targetTab.style.display = "block";

  document.querySelectorAll("#ownerNavMenu .nav-item").forEach((btn) => {
    btn.classList.remove("active");
    if (btn.getAttribute("onclick")?.includes(tabId)) btn.classList.add("active");
  });

  if (tabId === "ownerOverview") loadOwnerDashboard();
  if (tabId === "ownerBusinessInfo") loadOwnerBusinessInfo();
  if (tabId === "ownerServices") loadOwnerServices();
  if (tabId === "ownerStaff") loadOwnerStaff();
  if (tabId === "ownerHoursRules") {
    loadOwnerRules();
    loadOwnerWeeklyHours();
  }
  if (tabId === "ownerDocuments") loadOwnerDocuments();
  if (tabId === "ownerCustomers") loadOwnerCustomers();
  if (tabId === "ownerAppointments") loadOwnerAppointments();
}

function toggleOwnerCustomerTestingMode() {
  ownerTestingMode = !ownerTestingMode;
  const banner = document.getElementById("ownerTestNoticeBanner");
  const testBtn = document.getElementById("btnTestCustomerPage");
  const headerBizSelectWrapper = document.getElementById("headerBizSelectWrapper");
  const btnHeaderBookAppt = document.getElementById("btnHeaderBookAppt");

  if (ownerTestingMode) {
    if (banner) banner.style.display = "flex";
    if (testBtn) testBtn.innerHTML = '<i class="fa-solid fa-arrow-left"></i> Return to Dashboard';
    // When owner is in customer preview mode, keep global business select hidden because owner only has their business
    if (headerBizSelectWrapper) headerBizSelectWrapper.style.display = "none";
    if (btnHeaderBookAppt) btnHeaderBookAppt.style.display = "inline-flex";
    selectedBusinessId = currentUser.business_id;
    showSection("customerBookingPage");
    loadCustomerBookingData();
  } else {
    if (banner) banner.style.display = "none";
    if (testBtn) testBtn.innerHTML = '<i class="fa-solid fa-eye"></i> Open Customer Booking Page';
    if (headerBizSelectWrapper) headerBizSelectWrapper.style.display = "none";
    if (btnHeaderBookAppt) btnHeaderBookAppt.style.display = "none";
    showSection("ownerDashboardView");
    loadOwnerDashboard();
  }
}

/* ==========================================================================
   3. CUSTOMER BOOKING PAGE DATA & UI
   ========================================================================== */
async function loadBusinesses() {
  try {
    const res = await fetch(`${API_BASE}/businesses`);
    businesses = await res.json();

    const select = document.getElementById("globalBusinessSelect");
    const apptBizSelect = document.getElementById("appointmentBusinessSelect");
    const headerBizSelectWrapper = document.getElementById("headerBizSelectWrapper");

    if (currentUser && currentUser.role === "owner") {
      if (headerBizSelectWrapper) headerBizSelectWrapper.style.display = "none";
    }

    if (select) {
      select.innerHTML = '<option value="">🏢 Select Business</option>';
      businesses.forEach((b) => {
        const opt = document.createElement("option");
        opt.value = b.id;
        opt.textContent = `${b.name} (${b.category})`;
        select.appendChild(opt);
      });

      if (!selectedBusinessId && businesses.length > 0) {
        selectedBusinessId = businesses[0].id;
      }
      select.value = selectedBusinessId || "";
    }

    if (apptBizSelect) {
      apptBizSelect.innerHTML = '<option value="">Select business...</option>';
      businesses.forEach((b) => {
        const opt = document.createElement("option");
        opt.value = b.id;
        opt.textContent = `${b.name} (${b.category})`;
        apptBizSelect.appendChild(opt);
      });
    }

    loadCustomerBookingData();
  } catch (err) {
    console.error("Load businesses error:", err);
  }
}

function onBusinessSelectChange(bizId) {
  selectedBusinessId = bizId ? parseInt(bizId) : null;
  loadCustomerBookingData();
}

async function loadCustomerBookingData() {
  if (!selectedBusinessId && businesses.length > 0) {
    selectedBusinessId = businesses[0].id;
  }
  if (!selectedBusinessId) return;

  const currentBiz = businesses.find((b) => String(b.id) === String(selectedBusinessId));

  const heroBizTitle = document.getElementById("heroBizTitle");
  const heroBizNameHeader = document.getElementById("heroBizNameHeader");
  const heroBizDesc = document.getElementById("heroBizDesc");
  const testBannerBizName = document.getElementById("testBannerBizName");

  if (currentBiz) {
    if (heroBizTitle) heroBizTitle.textContent = currentBiz.name;
    if (heroBizNameHeader) heroBizNameHeader.textContent = currentBiz.name;
    if (heroBizDesc) {
      heroBizDesc.setAttribute("data-custom", "true");
      heroBizDesc.textContent = `${currentBiz.category} • Hours: ${currentBiz.operating_hours || '10 AM - 8 PM'} • ${currentBiz.location || 'Central Location'}`;
    }
    if (testBannerBizName) testBannerBizName.textContent = currentBiz.name;

    if (typeof applyBusinessTheme === "function") {
      applyBusinessTheme(currentBiz);
    }
  }

  // Fetch services for selected business
  try {
    const sRes = await fetch(`${API_BASE}/businesses/${selectedBusinessId}/services`);
    services = await sRes.json();
    renderCustomerServicesGrid();
  } catch (err) {
    console.error("Fetch services error:", err);
  }

  // Fetch staff for selected business
  try {
    const stRes = await fetch(`${API_BASE}/businesses/${selectedBusinessId}/staff`);
    staff = await stRes.json();
    renderCustomerStaffGrid();
  } catch (err) {
    console.error("Fetch staff error:", err);
  }
}

function getServiceThumbnail(service, biz) {
  const name = (service.name || "").toLowerCase();
  const cat = (service.category || (biz ? biz.category : "") || "").toLowerCase();

  // 1. Hair & Styling
  if (name.includes("hair") || name.includes("cut") || name.includes("styling") || name.includes("color") || name.includes("blowdry") || name.includes("keratin") || name.includes("shave") || name.includes("barber")) {
    return "https://images.unsplash.com/photo-1560066984-138dadb4c035?auto=format&fit=crop&w=600&q=80";
  }
  // 2. Facial & Skincare
  if (name.includes("facial") || name.includes("skin") || name.includes("clean") || name.includes("glow") || name.includes("peel") || name.includes("derma") || name.includes("anti-aging") || name.includes("acne")) {
    return "https://images.unsplash.com/photo-1570172619644-dfd03ed5d881?auto=format&fit=crop&w=600&q=80";
  }
  // 3. Massage & Spa
  if (name.includes("massage") || name.includes("spa") || name.includes("therapy") || name.includes("aromatherapy") || name.includes("ayurvedic") || name.includes("deep tissue") || name.includes("relax")) {
    return "https://images.unsplash.com/photo-1544161515-4ab6ce6db874?auto=format&fit=crop&w=600&q=80";
  }
  // 4. Nails & Manicure
  if (name.includes("nail") || name.includes("mani") || name.includes("pedi") || name.includes("polish") || name.includes("gel")) {
    return "https://images.unsplash.com/photo-1632345031435-8727f6897d53?auto=format&fit=crop&w=600&q=80";
  }
  // 5. Dental & Teeth
  if (name.includes("dent") || name.includes("tooth") || name.includes("teeth") || name.includes("root canal") || name.includes("braces") || name.includes("whitening") || name.includes("oral") || cat.includes("dental")) {
    return "https://images.unsplash.com/photo-1588776814546-1ffcf47267a5?auto=format&fit=crop&w=600&q=80";
  }
  // 6. Medical Consultation & Health Checkup
  if (name.includes("doctor") || name.includes("consult") || name.includes("checkup") || name.includes("health") || name.includes("cardio") || name.includes("pediatric") || name.includes("physician") || cat.includes("clinic") || cat.includes("medic")) {
    return "https://images.unsplash.com/photo-1629909613654-28e377c37b09?auto=format&fit=crop&w=600&q=80";
  }
  // 7. Fitness / Gym / Training / Workout
  if (name.includes("gym") || name.includes("train") || name.includes("workout") || name.includes("hiit") || name.includes("strength") || name.includes("fitness") || name.includes("pt session") || name.includes("cardio") || cat.includes("gym") || cat.includes("fit")) {
    return "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=600&q=80";
  }
  // 8. Yoga & Pilates
  if (name.includes("yoga") || name.includes("pilates") || name.includes("meditat") || name.includes("stretch") || name.includes("asana")) {
    return "https://images.unsplash.com/photo-1545205597-3d9d02c29597?auto=format&fit=crop&w=600&q=80";
  }
  // 9. Dining / Food / Table Reservation
  if (name.includes("table") || name.includes("dine") || name.includes("buffet") || name.includes("food") || name.includes("menu") || name.includes("chef") || name.includes("dish") || name.includes("lunch") || name.includes("dinner") || name.includes("wine") || cat.includes("restaurant") || cat.includes("hotel")) {
    return "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=600&q=80";
  }
  // 10. Wedding & Event Management
  if (name.includes("wedding") || name.includes("banquet") || name.includes("hall") || name.includes("decor") || name.includes("party") || name.includes("birthday") || name.includes("reception") || name.includes("catering") || cat.includes("event") || cat.includes("wedding")) {
    return "https://images.unsplash.com/photo-1519741497674-611481863552?auto=format&fit=crop&w=600&q=80";
  }
  // 11. Automotive & Garage
  if (name.includes("car") || name.includes("auto") || name.includes("oil") || name.includes("repair") || name.includes("brake") || name.includes("wheel") || name.includes("tyre") || name.includes("tire") || name.includes("engine") || name.includes("wash") || cat.includes("auto") || cat.includes("garage")) {
    return "https://images.unsplash.com/photo-1619642751034-765dfdf7c58e?auto=format&fit=crop&w=600&q=80";
  }
  // 12. Consulting & Legal
  if (name.includes("legal") || name.includes("law") || name.includes("audit") || name.includes("tax") || name.includes("advis") || name.includes("strategy") || name.includes("review") || name.includes("contract") || cat.includes("consult") || cat.includes("legal")) {
    return "https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=600&q=80";
  }

  return "https://images.unsplash.com/photo-1522071820081-009f0129c71c?auto=format&fit=crop&w=600&q=80";
}

function renderCustomerServicesGrid() {
  const grid1 = document.getElementById("customerServicesGrid");
  const grid2 = document.getElementById("fullServicesCatalogGrid");

  const buildHtml = () => {
    if (!services || services.length === 0) {
      return `<div class="empty-state-box" style="grid-column: 1/-1; padding: 30px; text-align: center; color: #94a3b8;"><i class="fa-solid fa-concierge-bell" style="font-size:32px; margin-bottom:12px; display:block; color:var(--biz-primary);"></i>No services listed for this business yet.</div>`;
    }
    const currentBiz = businesses.find((b) => String(b.id) === String(selectedBusinessId)) || {};
    const currency = currentBiz.currency || "₹";

    return services.map((s) => {
      const imgUrl = getServiceThumbnail(s, currentBiz);
      return `
      <div class="service-card card">
        <div class="service-card-image-wrap">
          <img class="service-card-img" src="${imgUrl}" alt="${escapeHtml(s.name)}" loading="lazy" onerror="this.src='https://images.unsplash.com/photo-1522071820081-009f0129c71c?auto=format&fit=crop&w=600&q=80'">
          <div class="service-card-img-overlay"></div>
          <span class="service-card-category-tag"><i class="fa-solid fa-tag"></i> ${escapeHtml(s.category || 'General')}</span>
          <span class="service-card-duration-tag"><i class="fa-solid fa-clock"></i> ${s.duration_minutes}m</span>
        </div>
        <div class="service-card-content">
          <div class="service-card-title-row">
            <h3>${escapeHtml(s.name)}</h3>
            <span class="service-card-price">${currency} ${parseFloat(s.price || 0).toFixed(2)}</span>
          </div>
          <div class="service-card-desc">
            ${escapeHtml(s.description || 'Professional, high quality service tailored to your requirements.')}
          </div>
          <div class="service-card-meta">
            <span><i class="fa-solid fa-percent" style="color:var(--biz-primary);"></i> Deposit: ${s.deposit_percentage || 0}%</span>
            ${s.required_resource_type ? `<span><i class="fa-solid fa-door-open" style="color:var(--biz-accent);"></i> ${escapeHtml(s.required_resource_type)}</span>` : ''}
          </div>
          <button class="btn btn-sm btn-primary btn-block" onclick="openBookModalWithService(${s.id})" style="margin-top:auto;">
            <i class="fa-solid fa-calendar-check"></i> Book This Service
          </button>
        </div>
      </div>
    `;
    }).join('');
  };

  const html = buildHtml();
  if (grid1) grid1.innerHTML = html;
  if (grid2) grid2.innerHTML = html;
}

function renderCustomerStaffGrid() {
  const grid = document.getElementById("customerStaffGrid");
  if (!grid) return;

  if (!staff || staff.length === 0) {
    grid.innerHTML = `<div class="empty-state-box" style="grid-column: 1/-1; padding: 20px; text-align: center; color: #94a3b8;"><i class="fa-solid fa-user-doctor" style="font-size:28px; margin-bottom:8px; display:block; color:#a855f7;"></i>No specific staff or doctors configured. Bookings will be auto-assigned.</div>`;
    return;
  }

  grid.innerHTML = staff.map((st) => `
    <div class="staff-card card" style="background: rgba(15,23,42,0.8); border: 1px solid rgba(168,85,247,0.3); border-radius: 12px; padding: 15px;">
      <div style="display:flex; align-items:center; gap:12px;">
        <img src="https://api.dicebear.com/7.x/bottts/svg?seed=${encodeURIComponent(st.name)}" style="width:45px; height:45px; border-radius:50%; border:2px solid #a855f7;">
        <div>
          <h4 style="color:#e2e8f0; font-size:15px; margin:0;">${escapeHtml(st.name)}</h4>
          <span style="font-size:12px; color:#a855f7;">${escapeHtml(st.role || 'Specialist')}</span>
        </div>
      </div>
      <div style="margin-top:10px; font-size:12px; color:#94a3b8;">
        <p><i class="fa-solid fa-calendar-days"></i> Working Days: ${escapeHtml(st.working_days || 'Mon-Sat')}</p>
        <p><i class="fa-solid fa-clock"></i> Hours: ${st.working_start || '10:00'} - ${st.working_end || '19:00'}</p>
      </div>
    </div>
  `).join('');
}

/* ==========================================================================
   4. USER PROFILE & HISTORY MODAL
   ========================================================================== */
async function openUserProfileModal() {
  if (!currentUser) return;

  const modal = document.getElementById("userProfileModal");
  if (modal) modal.classList.add("open");

  document.getElementById("upUsername").textContent = currentUser.username;
  document.getElementById("upPhone").textContent = currentUser.phone;
  document.getElementById("upRoleBadge").textContent = currentUser.role.toUpperCase();

  try {
    const res = await fetch(`${API_BASE}/user/profile`, { headers: getAuthHeaders() });
    if (!res.ok) return;

    const data = await res.json();
    renderUserProfileTables(data.upcoming_bookings, data.previous_history);
  } catch (err) {
    console.error("Load user profile error:", err);
  }
}

function closeUserProfileModal() {
  document.getElementById("userProfileModal")?.classList.remove("open");
}

function switchProfileSubTab(tabType) {
  const btnUp = document.getElementById("btnUpcomingTab");
  const btnHist = document.getElementById("btnHistoryTab");
  const secUp = document.getElementById("userUpcomingSection");
  const secHist = document.getElementById("userHistorySection");

  if (tabType === "upcoming") {
    btnUp.className = "btn btn-sm btn-primary";
    btnHist.className = "btn btn-sm btn-glass";
    secUp.style.display = "block";
    secHist.style.display = "none";
  } else {
    btnUp.className = "btn btn-sm btn-glass";
    btnHist.className = "btn btn-sm btn-primary";
    secUp.style.display = "none";
    secHist.style.display = "block";
  }
}

function renderUserProfileTables(upcoming, history) {
  const upTbody = document.getElementById("userUpcomingTable");
  const histTbody = document.getElementById("userHistoryTable");

  if (upTbody) {
    upTbody.innerHTML = upcoming.length === 0
      ? `<tr><td colspan="7" style="text-align:center; padding:15px; color:#94a3b8;">No active upcoming bookings.</td></tr>`
      : upcoming.map((a) => `
        <tr>
          <td>#${a.id}</td>
          <td><strong>${escapeHtml(a.business_name)}</strong></td>
          <td>${escapeHtml(a.service_name)}</td>
          <td>${escapeHtml(a.staff_name)}</td>
          <td>${a.appointment_date} at ${a.appointment_time}</td>
          <td><span class="status-badge ${a.status.toLowerCase()}">${escapeHtml(a.status)}</span></td>
          <td>
            <button class="btn btn-sm btn-glass" onclick="userCancelBooking(${a.id})" style="color:#ef4444; padding:4px 8px; font-size:11px;" title="Cancel this appointment">
              <i class="fa-solid fa-xmark"></i> Cancel
            </button>
          </td>
        </tr>
      `).join('');
  }

  if (histTbody) {
    histTbody.innerHTML = history.length === 0
      ? `<tr><td colspan="6" style="text-align:center; padding:15px; color:#94a3b8;">No past booking history found.</td></tr>`
      : history.map((a) => `
        <tr>
          <td>#${a.id}</td>
          <td><strong>${escapeHtml(a.business_name)}</strong></td>
          <td>${escapeHtml(a.service_name)}</td>
          <td>${escapeHtml(a.staff_name)}</td>
          <td>${a.appointment_date} at ${a.appointment_time}</td>
          <td><span class="status-badge ${a.status.toLowerCase()}">${escapeHtml(a.status)}</span></td>
        </tr>
      `).join('');
  }
}

async function userCancelBooking(apptId) {
  if (!confirm(`Are you sure you want to cancel appointment #${apptId}?`)) return;
  try {
    const res = await fetch(`${API_BASE}/appointments/${apptId}/cancel`, {
      method: "POST"
    });
    if (res.ok) {
      alert(`✅ Appointment #${apptId} has been cancelled successfully.`);
      openUserProfileModal();
    } else {
      const err = await res.json();
      alert(`❌ Cancellation failed: ${err.detail || "Unable to cancel"}`);
    }
  } catch (e) {
    alert("❌ Error: " + e.message);
  }
}

/* ==========================================================================
   DYNAMIC BUSINESS TYPE VISUAL IDENTITY THEME & VOCABULARY ENGINE
   ========================================================================== */
function getBusinessTheme(categoryStr, nameStr) {
  const cat = `${categoryStr || ""} ${nameStr || ""}`.toLowerCase();

  // 1. Medical / Healthcare / Clinic / Hospital / Dental / Doctor / Therapy
  if (cat.includes("clinic") || cat.includes("doctor") || cat.includes("health") || cat.includes("dental") || cat.includes("hospital") || cat.includes("therap") || cat.includes("med")) {
    return {
      type: "clinic",
      badgeText: "Medical & Healthcare",
      iconClass: "fa-solid fa-stethoscope",
      staffIconClass: "fa-solid fa-user-doctor",
      serviceIconClass: "fa-solid fa-kit-medical",
      customerIconClass: "fa-solid fa-hospital-user",
      colors: {
        primary: "#06b6d4",
        secondary: "#0284c7",
        accent: "#38bdf8",
        glow: "rgba(6, 182, 212, 0.4)",
        gradient: "linear-gradient(135deg, #06b6d4 0%, #0ea5e9 100%)",
        border: "rgba(6, 182, 212, 0.35)"
      },
      bgBaseColor: "#041525",
      bgMesh: "radial-gradient(ellipse at 15% 15%, rgba(6, 182, 212, 0.45) 0%, transparent 60%), radial-gradient(ellipse at 85% 20%, rgba(59, 130, 246, 0.4) 0%, transparent 60%), radial-gradient(ellipse at 50% 85%, rgba(14, 165, 233, 0.35) 0%, transparent 60%), linear-gradient(140deg, #031424 0%, #062642 45%, #051c33 100%)",
      heroCover: "https://images.unsplash.com/photo-1629909613654-28e377c37b09?auto=format&fit=crop&w=1600&q=80",
      logoSvg: `<svg viewBox="0 0 100 100" class="hero-biz-logo-svg" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="medGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#38bdf8" />
            <stop offset="100%" stop-color="#0284c7" />
          </linearGradient>
        </defs>
        <circle cx="50" cy="50" r="46" fill="url(#medGrad)" opacity="0.2" />
        <rect x="42" y="22" width="16" height="56" rx="8" fill="url(#medGrad)" />
        <rect x="22" y="42" width="56" height="16" rx="8" fill="url(#medGrad)" />
        <circle cx="50" cy="50" r="8" fill="#ffffff" />
      </svg>`,
      staffNavLabel: "Doctors & Specialists",
      servicesNavLabel: "Consultations & Care",
      customersNavLabel: "Patients Directory",
      apptsNavLabel: "Consultations",
      todayApptsMetric: "Today's Consultations",
      totalApptsMetric: "Total Consultations",
      servicesMetric: "Active Medical Services",
      staffMetric: "Active Doctors / Specialists",
      servicesTitle: "Medical Services & Consultations",
      servicesDesc: "Clinical procedures, checkups, and consultation options",
      addServiceBtn: "+ Add Medical Service",
      staffTitle: "Doctors & Medical Specialists",
      staffDesc: "Specialists, licenses, and clinical duty hours",
      addStaffBtn: "+ Add Doctor/Specialist",
      customersTitle: "Patient Health Records & Directory",
      customerColumnLabel: "Patient Name",
      apptCustomerColumnLabel: "Patient",
      serviceModalTitle: "Add Medical Consultation / Service",
      serviceNamePlaceholder: "e.g. Root Canal Treatment / General Consultation",
      staffModalTitle: "Add Doctor / Specialist",
      staffNamePlaceholder: "e.g. Dr. Rajesh Patel, M.D.",
      staffRolePlaceholder: "e.g. Senior Cardiologist / Dentist",
      userShowcaseServices: "Available Medical Services & Consultations",
      userShowcaseStaff: "Consulting Doctors & Specialists",
      userHeroDesc: "Choose your required medical consultation, select a doctor, or book instantly with AI."
    };
  }

  // 2. Salon / Spa / Beauty / Hair / Nails / Barber / Parlour
  if (cat.includes("salon") || cat.includes("spa") || cat.includes("beauty") || cat.includes("hair") || cat.includes("barber") || cat.includes("parlour") || cat.includes("cosmetic")) {
    return {
      type: "salon",
      badgeText: "Salon & Wellness",
      iconClass: "fa-solid fa-scissors",
      staffIconClass: "fa-solid fa-hand-sparkles",
      serviceIconClass: "fa-solid fa-spa",
      customerIconClass: "fa-solid fa-users-line",
      colors: {
        primary: "#ec4899",
        secondary: "#a855f7",
        accent: "#f472b6",
        glow: "rgba(236, 72, 153, 0.45)",
        gradient: "linear-gradient(135deg, #ec4899 0%, #8b5cf6 100%)",
        border: "rgba(236, 72, 153, 0.35)"
      },
      bgBaseColor: "#1d0620",
      bgMesh: "radial-gradient(ellipse at 15% 15%, rgba(236, 72, 153, 0.48) 0%, transparent 60%), radial-gradient(ellipse at 85% 20%, rgba(168, 85, 247, 0.45) 0%, transparent 60%), radial-gradient(ellipse at 50% 85%, rgba(244, 63, 94, 0.35) 0%, transparent 60%), linear-gradient(140deg, #1b0621 0%, #350e38 45%, #1e0728 100%)",
      heroCover: "https://images.unsplash.com/photo-1560066984-138dadb4c035?auto=format&fit=crop&w=1600&q=80",
      logoSvg: `<svg viewBox="0 0 100 100" class="hero-biz-logo-svg" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="spaGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#ec4899" />
            <stop offset="100%" stop-color="#8b5cf6" />
          </linearGradient>
        </defs>
        <circle cx="50" cy="50" r="46" fill="url(#spaGrad)" opacity="0.2" />
        <path d="M50 16 C53 32, 68 40, 78 48 C66 54, 58 68, 50 82 C42 68, 34 54, 22 48 C32 40, 47 32, 50 16 Z" fill="url(#spaGrad)" />
        <circle cx="50" cy="48" r="8" fill="#ffffff" />
        <circle cx="50" cy="26" r="3" fill="#fbcfe8" />
        <circle cx="68" cy="42" r="2.5" fill="#fbcfe8" />
        <circle cx="32" cy="42" r="2.5" fill="#fbcfe8" />
      </svg>`,
      staffNavLabel: "Stylists & Therapists",
      servicesNavLabel: "Treatments & Styling",
      customersNavLabel: "Client Directory",
      apptsNavLabel: "Bookings",
      todayApptsMetric: "Today's Appointments",
      totalApptsMetric: "Total Appointments",
      servicesMetric: "Active Treatments",
      staffMetric: "Active Stylists & Crew",
      servicesTitle: "Hair, Beauty & Spa Treatments",
      servicesDesc: "Styling sessions, wellness packages, and prices",
      addServiceBtn: "+ Add Treatment",
      staffTitle: "Stylists & Spa Therapists",
      staffDesc: "Stylists, colorists, and chair rosters",
      addStaffBtn: "+ Add Stylist/Therapist",
      customersTitle: "Client Directory & Beauty Profiles",
      customerColumnLabel: "Client Name",
      apptCustomerColumnLabel: "Client",
      serviceModalTitle: "Add Styling / Spa Treatment",
      serviceNamePlaceholder: "e.g. Keratin Hair Spa & Blowdry",
      staffModalTitle: "Add Stylist / Aesthetician",
      staffNamePlaceholder: "e.g. Priya Sharma",
      staffRolePlaceholder: "e.g. Master Stylist / Nail Artist",
      userShowcaseServices: "Available Hair, Skin & Spa Treatments",
      userShowcaseStaff: "Our Expert Stylists & Specialists",
      userHeroDesc: "Select your makeover service, choose your favorite stylist, or let AI book your slot."
    };
  }

  // 3. Fitness / Gym / Yoga / Crossfit / Pilates / Studio / Sports
  if (cat.includes("gym") || cat.includes("fit") || cat.includes("yoga") || cat.includes("crossfit") || cat.includes("pilates") || cat.includes("sport") || cat.includes("train")) {
    return {
      type: "fitness",
      badgeText: "Fitness & Training Studio",
      iconClass: "fa-solid fa-dumbbell",
      staffIconClass: "fa-solid fa-person-running",
      serviceIconClass: "fa-solid fa-fire",
      customerIconClass: "fa-solid fa-id-badge",
      colors: {
        primary: "#f97316",
        secondary: "#ef4444",
        accent: "#fb923c",
        glow: "rgba(249, 115, 22, 0.45)",
        gradient: "linear-gradient(135deg, #f97316 0%, #dc2626 100%)",
        border: "rgba(249, 115, 22, 0.35)"
      },
      bgBaseColor: "#220803",
      bgMesh: "radial-gradient(ellipse at 15% 15%, rgba(249, 115, 22, 0.5) 0%, transparent 60%), radial-gradient(ellipse at 85% 20%, rgba(239, 68, 68, 0.45) 0%, transparent 60%), radial-gradient(ellipse at 50% 85%, rgba(245, 158, 11, 0.35) 0%, transparent 60%), linear-gradient(140deg, #240903 0%, #441407 45%, #1e0602 100%)",
      heroCover: "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=1600&q=80",
      logoSvg: `<svg viewBox="0 0 100 100" class="hero-biz-logo-svg" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="fitGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#f97316" />
            <stop offset="100%" stop-color="#ef4444" />
          </linearGradient>
        </defs>
        <circle cx="50" cy="50" r="46" fill="url(#fitGrad)" opacity="0.2" />
        <path d="M36 28 C36 22, 64 22, 64 28 L64 36 C58 34, 42 34, 36 36 Z" fill="none" stroke="url(#fitGrad)" stroke-width="7" stroke-linecap="round" />
        <rect x="26" y="38" width="48" height="42" rx="14" fill="url(#fitGrad)" />
        <circle cx="50" cy="58" r="9" fill="#ffffff" />
      </svg>`,
      staffNavLabel: "Trainers & Coaches",
      servicesNavLabel: "Classes & Packages",
      customersNavLabel: "Member Directory",
      apptsNavLabel: "Sessions",
      todayApptsMetric: "Today's Sessions",
      totalApptsMetric: "Total Workout Sessions",
      servicesMetric: "Active Programs & Classes",
      staffMetric: "Active Personal Trainers",
      servicesTitle: "Workout Classes & Training Packages",
      servicesDesc: "Strength classes, HIIT, Yoga, and PT packages",
      addServiceBtn: "+ Add Class / Package",
      staffTitle: "Personal Trainers & Fitness Coaches",
      staffDesc: "Certified instructors, workout slots, and specialties",
      addStaffBtn: "+ Add Trainer/Coach",
      customersTitle: "Gym Members Directory & Attendance",
      customerColumnLabel: "Member Name",
      apptCustomerColumnLabel: "Member",
      serviceModalTitle: "Add Training Package / Class",
      serviceNamePlaceholder: "e.g. 1-on-1 Personal Training (60 mins)",
      staffModalTitle: "Add Fitness Trainer / Coach",
      staffNamePlaceholder: "e.g. Abhi Coach",
      staffRolePlaceholder: "e.g. Strength & Conditioning Coach",
      userShowcaseServices: "Available Workout Classes & Training Packages",
      userShowcaseStaff: "Certified Trainers & Fitness Coaches",
      userHeroDesc: "Book your personal training slot, reserve workout sessions, or check trainer availability."
    };
  }

  // 4. Restaurant / Cafe / Dining / Food / Bistro / Chinese / Bakery / Bar
  if (cat.includes("restaurant") || cat.includes("dine") || cat.includes("dining") || cat.includes("cafe") || cat.includes("food") || cat.includes("bistro") || cat.includes("chinese") || cat.includes("bakery") || cat.includes("bar") || cat.includes("eatery")) {
    return {
      type: "restaurant",
      badgeText: "Dining & Gourmet Restaurant",
      iconClass: "fa-solid fa-utensils",
      staffIconClass: "fa-solid fa-bell-concierge",
      serviceIconClass: "fa-solid fa-wine-glass",
      customerIconClass: "fa-solid fa-user-group",
      colors: {
        primary: "#eab308",
        secondary: "#f97316",
        accent: "#fde047",
        glow: "rgba(234, 179, 8, 0.45)",
        gradient: "linear-gradient(135deg, #eab308 0%, #ea580c 100%)",
        border: "rgba(234, 179, 8, 0.35)"
      },
      bgBaseColor: "#201202",
      bgMesh: "radial-gradient(ellipse at 15% 15%, rgba(234, 179, 8, 0.48) 0%, transparent 60%), radial-gradient(ellipse at 85% 20%, rgba(249, 115, 22, 0.42) 0%, transparent 60%), radial-gradient(ellipse at 50% 85%, rgba(225, 29, 72, 0.32) 0%, transparent 60%), linear-gradient(140deg, #221302 0%, #3e1f04 45%, #1d0c02 100%)",
      heroCover: "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=1600&q=80",
      logoSvg: `<svg viewBox="0 0 100 100" class="hero-biz-logo-svg" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="restGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#fde047" />
            <stop offset="100%" stop-color="#ea580c" />
          </linearGradient>
        </defs>
        <circle cx="50" cy="50" r="46" fill="url(#restGrad)" opacity="0.2" />
        <circle cx="50" cy="28" r="6" fill="#ffffff" />
        <path d="M22 62 C24 38, 76 38, 78 62 Z" fill="url(#restGrad)" />
        <rect x="18" y="64" width="64" height="8" rx="4" fill="#ffffff" opacity="0.9" />
      </svg>`,
      staffNavLabel: "Chefs & Floor Staff",
      servicesNavLabel: "Dining & Table Bookings",
      customersNavLabel: "Guest Directory",
      apptsNavLabel: "Table Reservations",
      todayApptsMetric: "Today's Reservations",
      totalApptsMetric: "Total Reservations",
      servicesMetric: "Active Dining Offerings",
      staffMetric: "Active Staff & Chefs",
      servicesTitle: "Dining Experiences & Table Reservations",
      servicesDesc: "Tables, banquet halls, tasting menus, and catering",
      addServiceBtn: "+ Add Table / Dining Package",
      staffTitle: "Floor Staff, Hosts & Head Chefs",
      staffDesc: "Service captains, sommeliers, and floor crew",
      addStaffBtn: "+ Add Staff / Chef",
      customersTitle: "Restaurant Guest Directory & VIPs",
      customerColumnLabel: "Guest Name",
      apptCustomerColumnLabel: "Guest",
      serviceModalTitle: "Add Dining Service / Table Slot",
      serviceNamePlaceholder: "e.g. VIP Rooftop Table for 4 / Buffet Booking",
      staffModalTitle: "Add Floor Captain / Chef",
      staffNamePlaceholder: "e.g. Master Chef Lin",
      staffRolePlaceholder: "e.g. Head Chef / Floor Manager",
      userShowcaseServices: "Dining Experiences & Table Reservation Options",
      userShowcaseStaff: "Hosts, Sommeliers & Service Staff",
      userHeroDesc: "Reserve dining tables, explore special menus, or schedule banquet banquets with AI."
    };
  }

  // 5. Event Management / Weddings / Celebrations / Banquets
  if (cat.includes("event") || cat.includes("wedding") || cat.includes("celebrat") || cat.includes("banquet") || cat.includes("party")) {
    return {
      type: "event",
      badgeText: "Events & Luxury Weddings",
      iconClass: "fa-solid fa-champagne-glasses",
      staffIconClass: "fa-solid fa-user-tie",
      serviceIconClass: "fa-solid fa-ring",
      customerIconClass: "fa-solid fa-users",
      colors: {
        primary: "#a855f7",
        secondary: "#ec4899",
        accent: "#c084fc",
        glow: "rgba(168, 85, 247, 0.45)",
        gradient: "linear-gradient(135deg, #a855f7 0%, #db2777 100%)",
        border: "rgba(168, 85, 247, 0.35)"
      },
      bgBaseColor: "#1a042a",
      bgMesh: "radial-gradient(ellipse at 15% 15%, rgba(168, 85, 247, 0.52) 0%, transparent 60%), radial-gradient(ellipse at 85% 20%, rgba(236, 72, 153, 0.45) 0%, transparent 60%), radial-gradient(ellipse at 50% 85%, rgba(192, 132, 252, 0.35) 0%, transparent 60%), linear-gradient(140deg, #1a042b 0%, #390c55 45%, #170326 100%)",
      heroCover: "https://images.unsplash.com/photo-1519741497674-611481863552?auto=format&fit=crop&w=1600&q=80",
      logoSvg: `<svg viewBox="0 0 100 100" class="hero-biz-logo-svg" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="eventGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#c084fc" />
            <stop offset="100%" stop-color="#ec4899" />
          </linearGradient>
        </defs>
        <circle cx="50" cy="50" r="46" fill="url(#eventGrad)" opacity="0.2" />
        <path d="M22 64 L26 34 L40 48 L50 24 L60 48 L74 34 L78 64 Z" fill="url(#eventGrad)" />
        <circle cx="50" cy="20" r="4" fill="#fbbf24" />
        <circle cx="26" cy="30" r="3.5" fill="#ffffff" />
        <circle cx="74" cy="30" r="3.5" fill="#ffffff" />
        <rect x="20" y="66" width="60" height="6" rx="3" fill="#ffffff" opacity="0.85" />
      </svg>`,
      staffNavLabel: "Planners & Coordinators",
      servicesNavLabel: "Packages & Themes",
      customersNavLabel: "Hosts & Clients",
      apptsNavLabel: "Event Consultations",
      todayApptsMetric: "Today's Consultations",
      totalApptsMetric: "Total Events Booked",
      servicesMetric: "Active Event Packages",
      staffMetric: "Active Event Planners",
      servicesTitle: "Wedding & Celebration Packages",
      servicesDesc: "Banquets, decors, catering packages, and consultation slots",
      addServiceBtn: "+ Add Event Package",
      staffTitle: "Event Planners & Coordinators",
      staffDesc: "Creative directors, decor leads, and hosts",
      addStaffBtn: "+ Add Event Planner",
      customersTitle: "Event Hosts & Wedding Clients",
      customerColumnLabel: "Client Name",
      apptCustomerColumnLabel: "Host",
      serviceModalTitle: "Add Event Package / Venue Slot",
      serviceNamePlaceholder: "e.g. Grand Royal Wedding Package / Gala Dinner",
      staffModalTitle: "Add Event Coordinator",
      staffNamePlaceholder: "e.g. Udayan Lead Planner",
      staffRolePlaceholder: "e.g. Master Wedding Coordinator",
      userShowcaseServices: "Available Wedding & Event Packages",
      userShowcaseStaff: "Our Expert Event Planners",
      userHeroDesc: "Explore grand event halls, bespoke decor themes, or schedule venue viewing appointments."
    };
  }

  // 6. Automotive / Garage / Car Repair / Mechanics
  if (cat.includes("auto") || cat.includes("garage") || cat.includes("car") || cat.includes("motor") || cat.includes("mechanic")) {
    return {
      type: "automotive",
      badgeText: "Auto Garage & Services",
      iconClass: "fa-solid fa-wrench",
      staffIconClass: "fa-solid fa-screwdriver-wrench",
      serviceIconClass: "fa-solid fa-car",
      customerIconClass: "fa-solid fa-user",
      colors: {
        primary: "#38bdf8",
        secondary: "#2563eb",
        accent: "#60a5fa",
        glow: "rgba(56, 189, 248, 0.45)",
        gradient: "linear-gradient(135deg, #38bdf8 0%, #1d4ed8 100%)",
        border: "rgba(56, 189, 248, 0.35)"
      },
      bgBaseColor: "#041424",
      bgMesh: "radial-gradient(ellipse at 15% 15%, rgba(56, 189, 248, 0.48) 0%, transparent 60%), radial-gradient(ellipse at 85% 20%, rgba(37, 99, 235, 0.45) 0%, transparent 60%), radial-gradient(ellipse at 50% 85%, rgba(99, 102, 241, 0.35) 0%, transparent 60%), linear-gradient(140deg, #041426 0%, #092a4a 45%, #051628 100%)",
      heroCover: "https://images.unsplash.com/photo-1619642751034-765dfdf7c58e?auto=format&fit=crop&w=1600&q=80",
      logoSvg: `<svg viewBox="0 0 100 100" class="hero-biz-logo-svg" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="autoGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#38bdf8" />
            <stop offset="100%" stop-color="#2563eb" />
          </linearGradient>
        </defs>
        <circle cx="50" cy="50" r="46" fill="url(#autoGrad)" opacity="0.2" />
        <circle cx="50" cy="50" r="28" fill="none" stroke="url(#autoGrad)" stroke-width="8" stroke-dasharray="10 4" />
        <circle cx="50" cy="50" r="14" fill="#ffffff" />
        <rect x="46" y="16" width="8" height="68" rx="4" fill="url(#autoGrad)" opacity="0.8" />
        <rect x="16" y="46" width="68" height="8" rx="4" fill="url(#autoGrad)" opacity="0.8" />
      </svg>`,
      staffNavLabel: "Technicians & Mechanics",
      servicesNavLabel: "Repairs & Maintenance",
      customersNavLabel: "Vehicle Owners",
      apptsNavLabel: "Service Bookings",
      todayApptsMetric: "Today's Service Bookings",
      totalApptsMetric: "Total Vehicles Serviced",
      servicesMetric: "Active Repair Services",
      staffMetric: "Active Technicians",
      servicesTitle: "Vehicle Repairs & Diagnostic Packages",
      servicesDesc: "Periodic maintenance, engine tuning, and part replacements",
      addServiceBtn: "+ Add Repair Package",
      staffTitle: "Certified Mechanics & Technicians",
      staffDesc: "Master technicians, inspectors, and bay operators",
      addStaffBtn: "+ Add Mechanic",
      customersTitle: "Customer & Vehicle Directory",
      customerColumnLabel: "Owner Name",
      apptCustomerColumnLabel: "Owner",
      serviceModalTitle: "Add Automotive Service Package",
      serviceNamePlaceholder: "e.g. Full Synthetic Oil & Filter Service",
      staffModalTitle: "Add Technician",
      staffNamePlaceholder: "e.g. Anil Chief Mechanic",
      staffRolePlaceholder: "e.g. Senior Diagnostic Specialist",
      userShowcaseServices: "Available Automotive Repair & Maintenance Services",
      userShowcaseStaff: "Certified Technicians & Mechanics",
      userHeroDesc: "Schedule your vehicle maintenance, book inspection bays, or check mechanic availability."
    };
  }

  // 7. Hotel / Hospitality / Resort / Stay
  if (cat.includes("hotel") || cat.includes("resort") || cat.includes("stay") || cat.includes("hospitality")) {
    return {
      type: "hotel",
      badgeText: "Luxury Hotel & Hospitality",
      iconClass: "fa-solid fa-hotel",
      staffIconClass: "fa-solid fa-concierge-bell",
      serviceIconClass: "fa-solid fa-bed",
      customerIconClass: "fa-solid fa-user-check",
      colors: {
        primary: "#10b981",
        secondary: "#06b6d4",
        accent: "#34d399",
        glow: "rgba(16, 185, 129, 0.45)",
        gradient: "linear-gradient(135deg, #10b981 0%, #0891b2 100%)",
        border: "rgba(16, 185, 129, 0.35)"
      },
      bgBaseColor: "#031c14",
      bgMesh: "radial-gradient(ellipse at 15% 15%, rgba(16, 185, 129, 0.5) 0%, transparent 60%), radial-gradient(ellipse at 85% 20%, rgba(6, 182, 212, 0.45) 0%, transparent 60%), radial-gradient(ellipse at 50% 85%, rgba(52, 211, 153, 0.35) 0%, transparent 60%), linear-gradient(140deg, #031c14 0%, #073b2a 45%, #031710 100%)",
      heroCover: "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=1600&q=80",
      logoSvg: `<svg viewBox="0 0 100 100" class="hero-biz-logo-svg" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="hotelGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#34d399" />
            <stop offset="100%" stop-color="#059669" />
          </linearGradient>
        </defs>
        <circle cx="50" cy="50" r="46" fill="url(#hotelGrad)" opacity="0.2" />
        <path d="M50 18 L76 38 L76 78 L24 78 L24 38 Z" fill="url(#hotelGrad)" />
        <rect x="42" y="52" width="16" height="26" rx="4" fill="#ffffff" opacity="0.9" />
        <polygon points="50,28 53,35 60,35 55,39 57,46 50,42 43,46 45,39 40,35 47,35" fill="#fbbf24" />
      </svg>`,
      staffNavLabel: "Concierge & Hospitality Staff",
      servicesNavLabel: "Suites & Amenities",
      customersNavLabel: "Guests Directory",
      apptsNavLabel: "Reservations",
      todayApptsMetric: "Today's Check-ins",
      totalApptsMetric: "Total Reservations",
      servicesMetric: "Active Suites & Rooms",
      staffMetric: "Active Hospitality Staff",
      servicesTitle: "Suites, Rooms & Experience Packages",
      servicesDesc: "Deluxe suites, dining vouchers, and wellness access",
      addServiceBtn: "+ Add Suite / Experience",
      staffTitle: "Concierge, Host & Management",
      staffDesc: "Floor managers, concierge team, and guest leads",
      addStaffBtn: "+ Add Concierge Member",
      customersTitle: "Guest Profiles & VIP Records",
      customerColumnLabel: "Guest Name",
      apptCustomerColumnLabel: "Guest",
      serviceModalTitle: "Add Suite / Amenity Reservation",
      serviceNamePlaceholder: "e.g. Executive Deluxe Suite (1 Night)",
      staffModalTitle: "Add Concierge / Host",
      staffNamePlaceholder: "e.g. Smita Manager",
      staffRolePlaceholder: "e.g. Head Concierge",
      userShowcaseServices: "Available Suites & Hospitality Experiences",
      userShowcaseStaff: "Concierge & Hospitality Team",
      userHeroDesc: "Reserve luxury rooms, check exclusive amenities, or book with AI assistant."
    };
  }

  // 8. Legal / Law / Consulting / Finance / Real Estate / Agency
  if (cat.includes("law") || cat.includes("legal") || cat.includes("consult") || cat.includes("finance") || cat.includes("account") || cat.includes("agency") || cat.includes("estate")) {
    return {
      type: "consulting",
      badgeText: "Consultancy & Advisory",
      iconClass: "fa-solid fa-briefcase",
      staffIconClass: "fa-solid fa-user-tie",
      serviceIconClass: "fa-solid fa-scale-balanced",
      customerIconClass: "fa-solid fa-handshake",
      colors: {
        primary: "#6366f1",
        secondary: "#4338ca",
        accent: "#818cf8",
        glow: "rgba(99, 102, 241, 0.45)",
        gradient: "linear-gradient(135deg, #6366f1 0%, #3730a3 100%)",
        border: "rgba(99, 102, 241, 0.35)"
      },
      bgBaseColor: "#080c29",
      bgMesh: "radial-gradient(ellipse at 15% 15%, rgba(99, 102, 241, 0.5) 0%, transparent 60%), radial-gradient(ellipse at 85% 20%, rgba(79, 70, 229, 0.45) 0%, transparent 60%), radial-gradient(ellipse at 50% 85%, rgba(59, 130, 246, 0.35) 0%, transparent 60%), linear-gradient(140deg, #080c2b 0%, #131b54 45%, #070924 100%)",
      heroCover: "https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=1600&q=80",
      logoSvg: `<svg viewBox="0 0 100 100" class="hero-biz-logo-svg" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="consultGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#818cf8" />
            <stop offset="100%" stop-color="#4f46e5" />
          </linearGradient>
        </defs>
        <circle cx="50" cy="50" r="46" fill="url(#consultGrad)" opacity="0.2" />
        <rect x="22" y="24" width="56" height="8" rx="4" fill="#ffffff" opacity="0.9" />
        <rect x="28" y="34" width="8" height="34" rx="3" fill="url(#consultGrad)" />
        <rect x="46" y="34" width="8" height="34" rx="3" fill="url(#consultGrad)" />
        <rect x="64" y="34" width="8" height="34" rx="3" fill="url(#consultGrad)" />
        <rect x="18" y="70" width="64" height="10" rx="4" fill="#ffffff" opacity="0.9" />
      </svg>`,
      staffNavLabel: "Attorneys & Advisors",
      servicesNavLabel: "Advisory Services",
      customersNavLabel: "Client Directory",
      apptsNavLabel: "Consultations",
      todayApptsMetric: "Today's Consultations",
      totalApptsMetric: "Total Client Sessions",
      servicesMetric: "Active Advisory Packages",
      staffMetric: "Active Partners / Consultants",
      servicesTitle: "Professional Consulting & Advisory Services",
      servicesDesc: "Legal advice, audit sessions, strategy, and hourly rates",
      addServiceBtn: "+ Add Advisory Service",
      staffTitle: "Partners, Attorneys & Consultants",
      staffDesc: "Consultants, associates, and practice areas",
      addStaffBtn: "+ Add Consultant",
      customersTitle: "Corporate & Individual Client Directory",
      customerColumnLabel: "Client Name",
      apptCustomerColumnLabel: "Client",
      serviceModalTitle: "Add Advisory Consultation",
      serviceNamePlaceholder: "e.g. Legal Contract Review (45 mins)",
      staffModalTitle: "Add Consultant / Attorney",
      staffNamePlaceholder: "e.g. Advocate Sharma",
      staffRolePlaceholder: "e.g. Corporate Law Partner",
      userShowcaseServices: "Available Consultations & Professional Services",
      userShowcaseStaff: "Consultants & Advisory Experts",
      userHeroDesc: "Book your confidential consultation, review specialist availability, or schedule online."
    };
  }

  // 9. General / Professional Services (Default fallback)
  return {
    type: "general",
    badgeText: categoryStr || "Business Portal",
    iconClass: "fa-solid fa-building",
    staffIconClass: "fa-solid fa-user-tie",
    serviceIconClass: "fa-solid fa-concierge-bell",
    customerIconClass: "fa-solid fa-users",
    colors: {
      primary: "#00f2fe",
      secondary: "#3b82f6",
      accent: "#38bdf8",
      glow: "rgba(0, 242, 254, 0.4)",
      gradient: "linear-gradient(135deg, #00f2fe 0%, #3b82f6 100%)",
      border: "rgba(0, 242, 254, 0.3)"
    },
    bgBaseColor: "#051629",
    bgMesh: "radial-gradient(ellipse at 15% 15%, rgba(0, 242, 254, 0.48) 0%, transparent 60%), radial-gradient(ellipse at 85% 20%, rgba(139, 92, 246, 0.45) 0%, transparent 60%), radial-gradient(ellipse at 50% 85%, rgba(236, 72, 153, 0.35) 0%, transparent 60%), linear-gradient(140deg, #05162a 0%, #150f38 45%, #061327 100%)",
    heroCover: "https://images.unsplash.com/photo-1522071820081-009f0129c71c?auto=format&fit=crop&w=1600&q=80",
    logoSvg: `<svg viewBox="0 0 100 100" class="hero-biz-logo-svg" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="genGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#00f2fe" />
          <stop offset="100%" stop-color="#3b82f6" />
        </linearGradient>
      </defs>
      <circle cx="50" cy="50" r="46" fill="url(#genGrad)" opacity="0.2" />
      <polygon points="50,18 78,32 78,68 50,82 22,68 22,32" fill="url(#genGrad)" />
      <circle cx="50" cy="50" r="12" fill="#ffffff" />
    </svg>`,
    staffNavLabel: "Staff & Specialists",
    servicesNavLabel: "Services Catalog",
    customersNavLabel: "Customer Directory",
    apptsNavLabel: "Appointments",
    todayApptsMetric: "Today's Appointments",
    totalApptsMetric: "Total Appointments",
    servicesMetric: "Active Services",
    staffMetric: "Active Staff",
    servicesTitle: "Services Management",
    servicesDesc: "Add, edit or remove business services and pricing",
    addServiceBtn: "+ Add New Service",
    staffTitle: "Staff & Team Management",
    staffDesc: "Configure team members, roles, and duty schedules",
    addStaffBtn: "+ Add Staff Member",
    customersTitle: "Business Customer Directory",
    customerColumnLabel: "Customer Name",
    apptCustomerColumnLabel: "Customer",
    serviceModalTitle: "Add Service",
    serviceNamePlaceholder: "e.g. Premium Service Session",
    staffModalTitle: "Add Staff Member",
    staffNamePlaceholder: "e.g. Alex Taylor",
    staffRolePlaceholder: "e.g. Senior Specialist",
    userShowcaseServices: "Available Business Services",
    userShowcaseStaff: "Available Staff & Specialists",
    userHeroDesc: "Select available dates, pick your service, choose preferred staff, or let AI book for you."
  };
}

function applyBusinessTheme(biz) {
  if (!biz) return;
  const theme = getBusinessTheme(biz.category, biz.name);
  const singleCoverUrl = theme.heroCover;

  // 1. Inject Theme Color Tokens into Root CSS
  if (theme.colors) {
    document.documentElement.style.setProperty("--biz-primary", theme.colors.primary);
    document.documentElement.style.setProperty("--biz-secondary", theme.colors.secondary);
    document.documentElement.style.setProperty("--biz-accent", theme.colors.accent);
    document.documentElement.style.setProperty("--biz-glow", theme.colors.glow);
    document.documentElement.style.setProperty("--biz-gradient", theme.colors.gradient);
    document.documentElement.style.setProperty("--biz-card-border", theme.colors.border);
  }
  if (theme.bgBaseColor) {
    document.documentElement.style.setProperty("--biz-bg-base", theme.bgBaseColor);
  }
  if (theme.bgMesh) {
    document.documentElement.style.setProperty("--biz-bg-mesh", theme.bgMesh);
  }

  // Apply Colorful Theme on body for rich vibrant aesthetics across views
  document.body.classList.add("owner-colorful-theme");

  // Preload and verify image so it is guaranteed to never show pitch black
  if (singleCoverUrl) {
    const probe = new Image();
    probe.src = singleCoverUrl;
    probe.onerror = () => {
      const fallbackUrl = "https://images.unsplash.com/photo-1522071820081-009f0129c71c?auto=format&fit=crop&w=1600&q=80";
      const bgLayer = document.getElementById("webpageBgPhotoLayer") || document.getElementById("ownerBgPhotoLayer");
      const heroBg = document.getElementById("heroCoverBg");
      const ownerBg = document.getElementById("ownerBizHeroBg");
      if (bgLayer) bgLayer.style.backgroundImage = `url('${fallbackUrl}')`;
      if (heroBg) heroBg.style.backgroundImage = `url('${fallbackUrl}')`;
      if (ownerBg) ownerBg.style.backgroundImage = `url('${fallbackUrl}')`;
    };
  }

  // Update Dynamic Ambient Background Elements across the Webpage (ONE full image)
  const webpageBgMesh = document.getElementById("webpageBgGradientMesh") || document.getElementById("ownerBgGradientMesh");
  if (webpageBgMesh && theme.bgMesh) {
    webpageBgMesh.style.background = theme.bgMesh;
  }

  const webpageBgPhoto = document.getElementById("webpageBgPhotoLayer") || document.getElementById("ownerBgPhotoLayer");
  if (webpageBgPhoto && singleCoverUrl) {
    webpageBgPhoto.style.backgroundImage = `url('${singleCoverUrl}')`;
  }

  const webpageBgWatermark = document.getElementById("webpageBgWatermarkLogo") || document.getElementById("ownerBgWatermarkLogo");
  if (webpageBgWatermark && theme.logoSvg) {
    webpageBgWatermark.innerHTML = theme.logoSvg;
  }

  // Update sidebar brand icon with theme gradient & glow
  const brandIcon = document.querySelector(".sidebar .brand-icon");
  if (brandIcon && theme.colors) {
    brandIcon.style.background = theme.colors.gradient;
    brandIcon.style.boxShadow = `0 0 20px ${theme.colors.glow}`;
  }

  // 2. Customer Booking Hub Hero Transformation (Same ONE full image for front)
  const heroCoverBg = document.getElementById("heroCoverBg");
  if (heroCoverBg && singleCoverUrl) {
    heroCoverBg.style.backgroundImage = `url('${singleCoverUrl}')`;
  }

  const heroLogoBadge = document.getElementById("heroBizLogoContainer");
  if (heroLogoBadge && theme.logoSvg) {
    heroLogoBadge.innerHTML = theme.logoSvg;
  }

  const heroCatBadge = document.getElementById("heroBizCategoryBadge");
  if (heroCatBadge) {
    heroCatBadge.innerHTML = `<i class="${theme.iconClass}"></i> ${escapeHtml(biz.category || theme.badgeText)}`;
  }

  const heroName = document.getElementById("heroBizNameHeader");
  if (heroName) heroName.textContent = biz.name;

  const heroTitle = document.getElementById("heroBizTitle");
  if (heroTitle) heroTitle.textContent = biz.name;

  const heroHours = document.getElementById("heroBizHours");
  if (heroHours) heroHours.textContent = biz.operating_hours || '10:00 AM - 08:00 PM';

  const heroLoc = document.getElementById("heroBizLocation");
  if (heroLoc) heroLoc.textContent = biz.location || 'Central Location';

  const heroPhone = document.getElementById("heroBizPhone");
  if (heroPhone) {
    heroPhone.textContent = biz.phone || 'Contact Business';
    heroPhone.href = `tel:${biz.phone || ''}`;
  }

  const heroBizDesc = document.getElementById("heroBizDesc");
  if (heroBizDesc) {
    heroBizDesc.textContent = biz.description || theme.userHeroDesc;
  }

  // 3. Owner Dashboard Overview Hero Transformation
  const ownerBizHeroBg = document.getElementById("ownerBizHeroBg");
  if (ownerBizHeroBg && singleCoverUrl) {
    ownerBizHeroBg.style.backgroundImage = `url('${singleCoverUrl}')`;
  }

  const ownerBizLogo = document.getElementById("ownerBizLogoBadge");
  if (ownerBizLogo && theme.logoSvg) {
    ownerBizLogo.innerHTML = theme.logoSvg;
  }

  const ownerBizCatPill = document.getElementById("ownerBizCategoryPill");
  if (ownerBizCatPill) {
    ownerBizCatPill.innerHTML = `<i class="${theme.iconClass}"></i> ${escapeHtml(biz.category || theme.badgeText)}`;
  }

  const ownerBizName = document.getElementById("ownerBizName");
  if (ownerBizName) ownerBizName.textContent = biz.name;

  const ownerBizSub = document.getElementById("ownerBizSubDetails");
  if (ownerBizSub) {
    ownerBizSub.textContent = `Operating Hours: ${biz.operating_hours || '10:00 AM - 08:00 PM'} • Location: ${biz.location || 'Central Facility'} • Owner: ${biz.owner_name || 'Business Manager'}`;
  }

  // 4. Sidebar Brand Subtitle
  const roleSub = document.getElementById("appRoleSub");
  if (roleSub) {
    roleSub.innerHTML = `<i class="${theme.iconClass}"></i> ${escapeHtml(biz.name)} <span class="badge" style="font-size:10px; padding:2px 6px; margin-left:4px; vertical-align:middle;">${escapeHtml(biz.category || theme.badgeText)}</span>`;
  }

  // 5. Owner Nav Menu Items
  const navStaffText = document.getElementById("ownerNavStaffText");
  const navStaffIcon = document.getElementById("ownerNavStaffIcon");
  if (navStaffText) navStaffText.textContent = theme.staffNavLabel;
  if (navStaffIcon) navStaffIcon.className = theme.staffIconClass;

  const navServicesText = document.getElementById("ownerNavServicesText");
  const navServicesIcon = document.getElementById("ownerNavServicesIcon");
  if (navServicesText) navServicesText.textContent = theme.servicesNavLabel;
  if (navServicesIcon) navServicesIcon.className = theme.serviceIconClass;

  const navCustText = document.getElementById("ownerNavCustomersText");
  const navCustIcon = document.getElementById("ownerNavCustomersIcon");
  if (navCustText) navCustText.textContent = theme.customersNavLabel;
  if (navCustIcon) navCustIcon.className = theme.customerIconClass;

  const navApptsText = document.getElementById("ownerNavApptsText");
  if (navApptsText) navApptsText.textContent = theme.apptsNavLabel;

  // 6. Overview Metric Titles & Icons
  const mToday = document.getElementById("ownerMetricTitleTodayAppts");
  if (mToday) mToday.textContent = theme.todayApptsMetric;

  const mTotal = document.getElementById("ownerMetricTitleTotalAppts");
  if (mTotal) mTotal.textContent = theme.totalApptsMetric;

  const mServices = document.getElementById("ownerMetricTitleServices");
  if (mServices) mServices.textContent = theme.servicesMetric;
  const mServicesIcon = document.getElementById("ownerMetricIconServices");
  if (mServicesIcon) mServicesIcon.className = theme.serviceIconClass;

  const mStaff = document.getElementById("ownerMetricTitleStaff");
  if (mStaff) mStaff.textContent = theme.staffMetric;
  const mStaffIcon = document.getElementById("ownerMetricIconStaff");
  if (mStaffIcon) mStaffIcon.className = theme.staffIconClass;

  // 7. Services Tab
  const sTitle = document.getElementById("ownerServicesHeaderTitle");
  if (sTitle) sTitle.innerHTML = `<i class="${theme.serviceIconClass}"></i> ${theme.servicesTitle}`;
  const sDesc = document.getElementById("ownerServicesHeaderDesc");
  if (sDesc) sDesc.textContent = theme.servicesDesc;
  const sBtnText = document.getElementById("btnOwnerAddServiceText");
  if (sBtnText) sBtnText.textContent = theme.addServiceBtn;

  // 8. Staff Tab
  const stTitle = document.getElementById("ownerStaffHeaderTitle");
  if (stTitle) stTitle.innerHTML = `<i class="${theme.staffIconClass}"></i> ${theme.staffTitle}`;
  const stDesc = document.getElementById("ownerStaffHeaderDesc");
  if (stDesc) stDesc.textContent = theme.staffDesc;
  const stBtnText = document.getElementById("btnOwnerAddStaffText");
  if (stBtnText) stBtnText.textContent = theme.addStaffBtn;

  // 9. Customers Tab
  const cTitle = document.getElementById("ownerCustomersHeaderTitle");
  if (cTitle) cTitle.innerHTML = `<i class="${theme.customerIconClass}"></i> ${theme.customersTitle}`;
  const thCustName = document.getElementById("thOwnerCustName");
  if (thCustName) thCustName.textContent = theme.customerColumnLabel;

  // 10. Appointments Tab
  const thApptCust = document.getElementById("thOwnerApptCustName");
  if (thApptCust) thApptCust.textContent = theme.apptCustomerColumnLabel;

  // 11. Modals
  const svcModalTitle = document.getElementById("serviceModalTitle");
  if (svcModalTitle) svcModalTitle.innerHTML = `<i class="fa-solid fa-plus"></i> ${theme.serviceModalTitle}`;
  const svcNameInput = document.getElementById("svcName");
  if (svcNameInput) svcNameInput.placeholder = theme.serviceNamePlaceholder;

  const staffModalTitle = document.getElementById("staffModalTitle");
  if (staffModalTitle) staffModalTitle.innerHTML = `<i class="fa-solid fa-user-plus"></i> ${theme.staffModalTitle}`;
  const stfNameInput = document.getElementById("stfName");
  if (stfNameInput) stfNameInput.placeholder = theme.staffNamePlaceholder;
  const stfRoleInput = document.getElementById("stfRole");
  if (stfRoleInput) stfRoleInput.placeholder = theme.staffRolePlaceholder;

  // 12. Customer Booking Showcase
  const cSvcShowcase = document.getElementById("customerServicesShowcaseTitle");
  if (cSvcShowcase) cSvcShowcase.innerHTML = `<i class="${theme.serviceIconClass}"></i> ${theme.userShowcaseServices}`;
  const cStfShowcase = document.getElementById("customerStaffShowcaseTitle");
  if (cStfShowcase) cStfShowcase.innerHTML = `<i class="${theme.staffIconClass}"></i> ${theme.userShowcaseStaff}`;
}

/* ==========================================================================
   REMINDERS MANAGEMENT: STATS & BATCH DELETION
   ========================================================================== */
async function loadReminderStats() {
  try {
    const bizId = currentUser?.business_id || selectedBusinessId;
    const url = bizId ? `${API_BASE}/reminders/stats?business_id=${bizId}` : `${API_BASE}/reminders/stats`;
    const res = await fetch(url);
    if (res.ok) {
      const stats = await res.json();
      const sentEl = document.getElementById("ownerReminderSentCount");
      const pendEl = document.getElementById("ownerReminderPendingCount");
      if (sentEl) sentEl.textContent = stats.sent || 0;
      if (pendEl) pendEl.textContent = stats.pending || 0;
    }

    // Check scheduler status
    const statusRes = await fetch(`${API_BASE}/reminders/scheduler-status`);
    if (statusRes.ok) {
      const statusData = await statusRes.json();
      const isActive = statusData.scheduler_active;
      const statusText = document.getElementById("ownerSchedulerStatusText");
      const statusIcon = document.getElementById("ownerSchedulerStatusIcon");
      const btnStop = document.getElementById("btnStopReminders");
      const btnResume = document.getElementById("btnResumeReminders");

      if (statusText) {
        statusText.textContent = isActive ? "Active" : "Stopped";
        statusText.style.color = isActive ? "#10b981" : "#ef4444";
      }
      if (statusIcon) {
        statusIcon.className = isActive ? "fa-solid fa-circle-play" : "fa-solid fa-circle-pause";
        statusIcon.style.color = isActive ? "#10b981" : "#ef4444";
      }
      if (btnStop) btnStop.style.display = isActive ? "inline-flex" : "none";
      if (btnResume) btnResume.style.display = isActive ? "none" : "inline-flex";
    }
  } catch (err) {
    console.error("Load reminder stats error:", err);
  }
}

async function stopOwnerReminders() {
  const bizId = currentUser?.business_id || selectedBusinessId;
  const countPrompt = document.getElementById("ownerReminderPendingCount")?.textContent || "all";
  if (!confirm(`Are you sure you want to STOP the reminder scheduler and delete all pending reminders (${countPrompt} in queue)?\n\nNo automated reminders will be sent until resumed.`)) {
    return;
  }

  const btn = document.getElementById("btnStopReminders");
  const originalHtml = btn ? btn.innerHTML : "";
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Stopping...`;
  }

  try {
    const url = bizId ? `${API_BASE}/reminders/stop?business_id=${bizId}` : `${API_BASE}/reminders/stop`;
    const res = await fetch(url, { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      alert(`🛑 Success: ${data.message || 'Reminder processing stopped and pending reminders cleared.'}`);
      await loadReminderStats();
    } else {
      const err = await res.json();
      alert(`❌ Error stopping reminders: ${err.detail || 'Request failed'}`);
    }
  } catch (e) {
    alert("❌ Error: " + e.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }
  }
}

async function resumeOwnerReminders() {
  const btn = document.getElementById("btnResumeReminders");
  const originalHtml = btn ? btn.innerHTML : "";
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Resuming...`;
  }

  try {
    const res = await fetch(`${API_BASE}/reminders/start`, { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      alert(`✅ ${data.message || 'Reminder processing resumed.'}`);
      await loadReminderStats();
    } else {
      const err = await res.json();
      alert(`❌ Error resuming scheduler: ${err.detail || 'Request failed'}`);
    }
  } catch (e) {
    alert("❌ Error: " + e.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }
  }
}

async function deleteOwnerPendingReminders() {
  const bizId = currentUser?.business_id || selectedBusinessId;
  const countPrompt = document.getElementById("ownerReminderPendingCount")?.textContent || "all";
  if (!confirm(`Are you sure you want to delete all pending reminders (${countPrompt} in queue)?\n\nThis will safely remove all unsent reminders from the scheduling queue.`)) {
    return;
  }

  const btn = document.getElementById("btnDeletePendingReminders");
  const originalHtml = btn ? btn.innerHTML : "";
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Deleting...`;
  }

  try {
    const url = bizId ? `${API_BASE}/reminders/pending?business_id=${bizId}` : `${API_BASE}/reminders/pending`;
    const res = await fetch(url, { method: "DELETE" });
    if (res.ok) {
      const data = await res.json();
      alert(`✅ Success: ${data.message || 'All pending reminders have been deleted.'}`);
      await loadReminderStats();
    } else {
      const err = await res.json();
      alert(`❌ Error deleting reminders: ${err.detail || 'Request failed'}`);
    }
  } catch (e) {
    alert("❌ Error: " + e.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }
  }
}

/* ==========================================================================
   5. OWNER DASHBOARD FUNCTIONALITY & API CALLS
   ========================================================================== */
async function loadOwnerDashboard() {
  if (!currentUser || currentUser.role !== "owner") return;

  try {
    const res = await fetch(`${API_BASE}/owner/dashboard`, { headers: getAuthHeaders() });
    if (!res.ok) {
      openBusinessOnboardModal();
      return;
    }

    const data = await res.json();
    currentUser.business_id = data.business.id;
    selectedBusinessId = data.business.id;

    // Apply dynamic business type theme & terminology!
    applyBusinessTheme(data.business);

    document.getElementById("ownerTodayApptCount").textContent = data.metrics.today_appointments_count;
    document.getElementById("ownerTotalApptCount").textContent = data.metrics.total_appointments;
    document.getElementById("ownerServicesCount").textContent = data.metrics.total_services;
    document.getElementById("ownerStaffCount").textContent = data.metrics.total_staff;

    // Preload customers directory
    loadOwnerCustomers();

    // Load automated reminder stats
    loadReminderStats();

    // Update Public Booking Link & QR Data
    updateOwnerPublicLinkCard(data.business);

    // Populate Today's Appts Table
    const tbody = document.getElementById("ownerTodayApptsTable");
    if (tbody) {
      tbody.innerHTML = data.today_appointments.length === 0
        ? `<tr><td colspan="8" style="text-align:center; padding:20px; color:#94a3b8;">No appointments scheduled for today.</td></tr>`
        : data.today_appointments.map((a) => `
          <tr>
            <td>#${a.id}</td>
            <td><strong>${escapeHtml(a.customer_name)}</strong></td>
            <td>${escapeHtml(a.customer_phone)}</td>
            <td>${escapeHtml(a.event_type)}</td>
            <td>${a.time}</td>
            <td>${escapeHtml(a.venue || '-')}</td>
            <td><span class="status-badge ${a.status.toLowerCase()}">${escapeHtml(a.status)}</span></td>
            <td>
              <button class="btn btn-sm btn-glass" onclick="updateApptStatus(${a.id}, 'completed')"><i class="fa-solid fa-check"></i> Complete</button>
              <button class="btn btn-sm btn-glass" onclick="updateApptStatus(${a.id}, 'cancelled')" style="color:#ef4444;"><i class="fa-solid fa-xmark"></i> Cancel</button>
            </td>
          </tr>
        `).join('');
    }
  } catch (err) {
    console.error("Load owner dashboard error:", err);
  }
}

let ownerCurrentPublicUrl = "";

function updateOwnerPublicLinkCard(biz) {
  if (!biz || !biz.id) return;
  ownerCurrentPublicUrl = `${window.location.origin}/b/${biz.id}`;
  
  const urlSpan = document.getElementById("ownerPublicUrlText");
  if (urlSpan) urlSpan.textContent = ownerCurrentPublicUrl;

  const openBtn = document.getElementById("ownerOpenPublicPageBtn");
  if (openBtn) openBtn.href = ownerCurrentPublicUrl;

  const waBtn = document.getElementById("ownerWhatsAppShareBtn");
  if (waBtn) {
    const text = encodeURIComponent(`Hi! Book your appointments with ${biz.name || 'us'} online: ${ownerCurrentPublicUrl}`);
    waBtn.href = `https://wa.me/?text=${text}`;
  }
}

function copyOwnerPublicLink() {
  if (!ownerCurrentPublicUrl) return;
  navigator.clipboard.writeText(ownerCurrentPublicUrl).then(() => {
    alert("📋 Copied public booking link to clipboard!\n\n" + ownerCurrentPublicUrl);
  }).catch(() => {
    prompt("Copy this public link:", ownerCurrentPublicUrl);
  });
}

function openQrModal() {
  if (!ownerCurrentPublicUrl && selectedBusinessId) {
    ownerCurrentPublicUrl = `${window.location.origin}/b/${selectedBusinessId}`;
  }
  const modal = document.getElementById("ownerQrModal");
  const img = document.getElementById("ownerQrCodeImg");
  if (modal && img) {
    img.src = `https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${encodeURIComponent(ownerCurrentPublicUrl)}`;
    modal.style.display = "flex";
  }
}

function closeQrModal() {
  const modal = document.getElementById("ownerQrModal");
  if (modal) modal.style.display = "none";
}

function printQrCode() {
  const img = document.getElementById("ownerQrCodeImg");
  if (!img) return;
  const printWindow = window.open('', '', 'width=600,height=600');
  printWindow.document.write(`
    <html>
      <head><title>Scan & Book QR Code</title></head>
      <body style="text-align:center; font-family:sans-serif; padding:40px;">
        <h2>Scan to Book an Appointment</h2>
        <p>Powered by Event AI Assistant</p>
        <img src="${img.src}" style="width:280px; height:280px; margin:20px 0;">
        <p style="font-size:14px; color:#555;">${ownerCurrentPublicUrl}</p>
      </body>
    </html>
  `);
  printWindow.document.close();
  printWindow.focus();
  setTimeout(() => { printWindow.print(); printWindow.close(); }, 500);
}

async function loadOwnerBusinessInfo() {
  try {
    const res = await fetch(`${API_BASE}/owner/business`, { headers: getAuthHeaders() });
    if (!res.ok) return;
    const b = await res.json();

    document.getElementById("obName").value = b.name || "";
    document.getElementById("obCategory").value = b.category || "";
    document.getElementById("obDescription").value = b.description || "";
    document.getElementById("obPhone").value = b.phone || "";
    document.getElementById("obLocation").value = b.location || "";
    document.getElementById("obCurrency").value = b.currency || "INR";
    document.getElementById("obTimezone").value = b.timezone || "Asia/Kolkata";
    document.getElementById("obOperatingHours").value = b.operating_hours || "10:00 AM - 08:00 PM";
    updateOwnerPublicLinkCard(b);
  } catch (err) {
    console.error("Load business info error:", err);
  }
}

document.getElementById("ownerBusinessForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    name: document.getElementById("obName").value,
    category: document.getElementById("obCategory").value,
    description: document.getElementById("obDescription").value,
    phone: document.getElementById("obPhone").value,
    location: document.getElementById("obLocation").value,
    currency: document.getElementById("obCurrency").value,
    timezone: document.getElementById("obTimezone").value,
    operating_hours: document.getElementById("obOperatingHours").value
  };

  try {
    const res = await fetch(`${API_BASE}/owner/business`, {
      method: "PUT",
      headers: getAuthHeaders(),
      body: JSON.stringify(body)
    });
    const data = await res.json();
    alert(data.message);
  } catch (err) {
    console.error("Update business error:", err);
  }
});

async function loadOwnerServices() {
  try {
    const res = await fetch(`${API_BASE}/owner/services`, { headers: getAuthHeaders() });
    const list = await res.json();
    const tbody = document.getElementById("ownerServicesTable");
    if (!tbody) return;

    tbody.innerHTML = list.length === 0
      ? `<tr><td colspan="8" style="text-align:center; padding:20px; color:#94a3b8;">No services added yet. Click "+ Add New Service".</td></tr>`
      : list.map((s) => `
        <tr>
          <td>#${s.id}</td>
          <td><strong>${escapeHtml(s.name)}</strong></td>
          <td>${escapeHtml(s.category || '-')}</td>
          <td>${s.duration_minutes} mins</td>
          <td>₹ ${parseFloat(s.price || 0).toFixed(2)}</td>
          <td>${s.deposit_percentage}%</td>
          <td>${escapeHtml(s.required_resource_type || 'None')}</td>
          <td>
            <button class="btn btn-sm btn-glass" onclick="deleteOwnerService(${s.id})" style="color:#ef4444;"><i class="fa-solid fa-trash"></i></button>
          </td>
        </tr>
      `).join('');
  } catch (err) {
    console.error("Load owner services error:", err);
  }
}

async function deleteOwnerService(id) {
  if (confirm("Are you sure you want to delete this service?")) {
    await fetch(`${API_BASE}/owner/services/${id}`, { method: "DELETE", headers: getAuthHeaders() });
    loadOwnerServices();
  }
}

async function loadOwnerStaff() {
  try {
    const res = await fetch(`${API_BASE}/owner/staff`, { headers: getAuthHeaders() });
    const list = await res.json();
    const tbody = document.getElementById("ownerStaffTable");
    if (!tbody) return;

    tbody.innerHTML = list.length === 0
      ? `<tr><td colspan="7" style="text-align:center; padding:20px; color:#94a3b8;">No staff members configured. Click "+ Add Staff/Doctor".</td></tr>`
      : list.map((st) => `
        <tr>
          <td>#${st.id}</td>
          <td><strong>${escapeHtml(st.name)}</strong></td>
          <td>${escapeHtml(st.role || 'Specialist')}</td>
          <td>${escapeHtml(st.working_days || 'Mon-Sat')}</td>
          <td>${st.working_start} - ${st.working_end}</td>
          <td>${st.break_start || '14:00'} - ${st.break_end || '14:30'}</td>
          <td>
            <button class="btn btn-sm btn-glass" onclick="deleteOwnerStaff(${st.id})" style="color:#ef4444;"><i class="fa-solid fa-trash"></i></button>
          </td>
        </tr>
      `).join('');
  } catch (err) {
    console.error("Load owner staff error:", err);
  }
}

async function deleteOwnerStaff(id) {
  if (confirm("Are you sure you want to delete this staff member?")) {
    await fetch(`${API_BASE}/owner/staff/${id}`, { method: "DELETE", headers: getAuthHeaders() });
    loadOwnerStaff();
  }
}

async function loadOwnerRules() {
  try {
    const res = await fetch(`${API_BASE}/owner/rules`, { headers: getAuthHeaders() });
    const data = await res.json();
    const r = data.rules || {};

    document.getElementById("ruleMinNotice").value = r.min_notice_hours || "2";
    document.getElementById("ruleMaxAdvance").value = r.max_advance_days || "30";
    document.getElementById("ruleBuffer").value = r.booking_buffer_mins || "15";
    document.getElementById("ruleMaxGroup").value = r.max_group_size || "10";
    document.getElementById("ruleCancellation").value = r.cancellation_rules || "";
    document.getElementById("ruleReschedule").value = r.rescheduling_rules || "";
    document.getElementById("ruleLateArrival").value = r.late_arrival_rules || "";
  } catch (err) {
    console.error("Load rules error:", err);
  }
}

document.getElementById("ownerRulesForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    min_notice_hours: parseInt(document.getElementById("ruleMinNotice").value),
    max_advance_days: parseInt(document.getElementById("ruleMaxAdvance").value),
    booking_buffer_mins: parseInt(document.getElementById("ruleBuffer").value),
    max_group_size: parseInt(document.getElementById("ruleMaxGroup").value),
    cancellation_rules: document.getElementById("ruleCancellation").value,
    rescheduling_rules: document.getElementById("ruleReschedule").value,
    late_arrival_rules: document.getElementById("ruleLateArrival").value
  };

  try {
    const res = await fetch(`${API_BASE}/owner/rules`, {
      method: "PUT",
      headers: getAuthHeaders(),
      body: JSON.stringify(body)
    });
    const data = await res.json();
    alert(data.message);
  } catch (err) {
    console.error("Update rules error:", err);
  }
});

async function loadOwnerCustomers() {
  try {
    const res = await fetch(`${API_BASE}/owner/customers`, { headers: getAuthHeaders() });
    if (!res.ok) return;
    const list = await res.json();
    const tbody = document.getElementById("ownerCustomersTable");
    if (!tbody) return;

    tbody.innerHTML = list.length === 0
      ? `<tr><td colspan="7" style="text-align:center; padding:20px; color:#94a3b8;">No registered customers or bookings found yet.</td></tr>`
      : list.map((c) => `
        <tr>
          <td>#${c.id}</td>
          <td><strong>${escapeHtml(c.name)}</strong></td>
          <td>${escapeHtml(c.phone)}</td>
          <td>${escapeHtml(c.email || '-')}</td>
          <td><span class="badge" style="background:rgba(56,189,248,0.15); color:#38bdf8; font-weight:700; border:1px solid rgba(56,189,248,0.3);">${c.total_bookings ?? 0}</span></td>
          <td><span style="font-size:12px; color:#cbd5e1;">${escapeHtml(c.last_visit || '-')}</span></td>
          <td>${c.created_at || '-'}</td>
        </tr>
      `).join('');
  } catch (err) {
    console.error("Load owner customers error:", err);
  }
}

async function loadOwnerAppointments() {
  try {
    const res = await fetch(`${API_BASE}/owner/appointments`, { headers: getAuthHeaders() });
    const list = await res.json();
    const tbody = document.getElementById("ownerAllApptsTable");
    if (!tbody) return;

    tbody.innerHTML = list.length === 0
      ? `<tr><td colspan="9" style="text-align:center; padding:20px; color:#94a3b8;">No appointments found.</td></tr>`
      : list.map((a) => `
        <tr>
          <td>#${a.id}</td>
          <td><strong>${escapeHtml(a.customer_name)}</strong></td>
          <td>${escapeHtml(a.customer_phone)}</td>
          <td>${escapeHtml(a.service_name)}</td>
          <td>${escapeHtml(a.staff_name)}</td>
          <td>${a.appointment_date}</td>
          <td>${a.appointment_time}</td>
          <td><span class="status-badge ${a.status.toLowerCase()}">${escapeHtml(a.status)}</span></td>
          <td>
            <button class="btn btn-sm btn-glass" onclick="updateApptStatus(${a.id}, 'confirmed')"><i class="fa-solid fa-check"></i> Confirm</button>
            <button class="btn btn-sm btn-glass" onclick="updateApptStatus(${a.id}, 'completed')">Done</button>
            <button class="btn btn-sm btn-glass" onclick="updateApptStatus(${a.id}, 'cancelled')" style="color:#ef4444;"><i class="fa-solid fa-xmark"></i></button>
          </td>
        </tr>
      `).join('');
  } catch (err) {
    console.error("Load master appts error:", err);
  }
}

async function updateApptStatus(id, newStatus) {
  try {
    const res = await fetch(`${API_BASE}/owner/appointments/${id}/status?status_val=${newStatus}`, {
      method: "PUT",
      headers: getAuthHeaders()
    });
    const data = await res.json();
    alert(data.message);
    loadOwnerDashboard();
    loadOwnerAppointments();
  } catch (err) {
    console.error("Update status error:", err);
  }
}

/* ==========================================================================
   6. OWNER AI CHATBOT HANDLER
   ========================================================================== */
async function sendOwnerChatMessage() {
  const input = document.getElementById("ownerChatInput");
  const messagesDiv = document.getElementById("ownerChatMessages");
  if (!input || !messagesDiv) return;

  const text = input.value.trim();
  if (!text) return;
  input.value = "";

  // User msg
  const uDiv = document.createElement("div");
  uDiv.className = "chat-msg user";
  uDiv.innerHTML = `<div class="msg-bubble">${escapeHtml(text)}</div>`;
  messagesDiv.appendChild(uDiv);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;

  try {
    const res = await fetch(`${API_BASE}/owner/chat`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ message: text })
    });
    const data = await res.json();

    const bDiv = document.createElement("div");
    bDiv.className = "chat-msg bot";
    let formattedReply = escapeHtml(data.reply).replace(/\n/g, "<br>");
    bDiv.innerHTML = `<div class="msg-bubble"><div>${formattedReply}</div></div>`;
    messagesDiv.appendChild(bDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;

    if (data.action_taken && data.action_taken.includes("ADD") || data.action_taken.includes("UPDATE")) {
      loadOwnerServices();
      loadOwnerStaff();
      loadOwnerDashboard();
    }
  } catch (err) {
    console.error("Owner AI chat error:", err);
  }
}

/* ==========================================================================
   7. MODAL DIALOGS & FORMS (ONBOARDING, SERVICE, STAFF, BOOKING)
   ========================================================================== */
function openBusinessOnboardModal() {
  document.getElementById("businessOnboardModal")?.classList.add("open");
}
function closeBusinessOnboardModal() {
  document.getElementById("businessOnboardModal")?.classList.remove("open");
}

document.getElementById("businessOnboardForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    name: document.getElementById("obnName").value.trim(),
    category: document.getElementById("obnCategory").value.trim(),
    description: document.getElementById("obnDescription").value.trim(),
    phone: document.getElementById("obnPhone").value.trim(),
    operating_hours: document.getElementById("obnHours").value.trim(),
    location: document.getElementById("obnLocation").value.trim()
  };

  try {
    const res = await fetch(`${API_BASE}/owner/onboard`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify(body)
    });
    const data = await res.json();
    alert(data.message);
    closeBusinessOnboardModal();
    if (currentUser) currentUser.business_id = data.business_id;
    localStorage.setItem("booking_ai_user", JSON.stringify(currentUser));
    loadOwnerDashboard();
  } catch (err) {
    console.error("Onboard business error:", err);
  }
});

function openAddServiceModal() {
  document.getElementById("serviceModalTitle").innerHTML = '<i class="fa-solid fa-plus"></i> Add Service';
  document.getElementById("serviceForm").reset();
  document.getElementById("svcId").value = "";
  document.getElementById("serviceModal")?.classList.add("open");
}
function closeServiceModal() {
  document.getElementById("serviceModal")?.classList.remove("open");
}

document.getElementById("serviceForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    name: document.getElementById("svcName").value,
    price: parseFloat(document.getElementById("svcPrice").value),
    duration_minutes: parseInt(document.getElementById("svcDuration").value),
    deposit_percentage: parseInt(document.getElementById("svcDeposit").value || "0")
  };

  try {
    const res = await fetch(`${API_BASE}/owner/services`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify(body)
    });
    const data = await res.json();
    alert(data.message);
    closeServiceModal();
    loadOwnerServices();
  } catch (err) {
    console.error("Save service error:", err);
  }
});

function openAddStaffModal() {
  document.getElementById("staffModalTitle").innerHTML = '<i class="fa-solid fa-user-plus"></i> Add Staff / Doctor';
  document.getElementById("staffForm").reset();
  document.getElementById("stfId").value = "";
  document.getElementById("staffModal")?.classList.add("open");
}
function closeStaffModal() {
  document.getElementById("staffModal")?.classList.remove("open");
}

document.getElementById("staffForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    name: document.getElementById("stfName").value,
    role: document.getElementById("stfRole").value,
    working_days: document.getElementById("stfDays").value,
    working_start: document.getElementById("stfStart").value,
    working_end: document.getElementById("stfEnd").value
  };

  try {
    const res = await fetch(`${API_BASE}/owner/staff`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify(body)
    });
    const data = await res.json();
    alert(data.message);
    closeStaffModal();
    loadOwnerStaff();
  } catch (err) {
    console.error("Save staff error:", err);
  }
});

async function openBookModalForUser() {
  const modal = document.getElementById("appointmentModal");
  if (modal) modal.classList.add("open");

  // Ensure minimum date is today
  const dateInput = document.getElementById("appointmentDate");
  if (dateInput) {
    const today = new Date().toISOString().split("T")[0];
    dateInput.min = today;
    if (!dateInput.value) dateInput.value = today;
  }

  // Pre-fill default time slot if empty
  const timeInput = document.getElementById("appointmentTime");
  if (timeInput && !timeInput.value) {
    timeInput.value = "10:00";
  }

  // Pre-fill Name & Phone from currentUser if available
  const nameInput = document.getElementById("appointmentCustName");
  const phoneInput = document.getElementById("appointmentCustPhone");
  if (nameInput && !nameInput.value && currentUser) {
    nameInput.value = currentUser.username || "";
  }
  if (phoneInput && !phoneInput.value && currentUser) {
    phoneInput.value = currentUser.phone || "";
  }

  // Ensure businesses are loaded
  if (!businesses || businesses.length === 0) {
    await loadBusinesses();
  }

  // Business Select Group
  const apptBizSelect = document.getElementById("appointmentBusinessSelect");
  const apptBizGroup = document.getElementById("appointmentBusinessGroup");

  if (currentUser && currentUser.role === "owner") {
    // Owner booking: lock to owner's specific business and hide business selection dropdown
    selectedBusinessId = currentUser.business_id;
    if (apptBizGroup) apptBizGroup.style.display = "none";
    if (apptBizSelect) apptBizSelect.required = false;
  } else {
    // Customer/User booking: show business selection if needed
    if (apptBizGroup) apptBizGroup.style.display = "block";
    if (apptBizSelect) apptBizSelect.required = true;
  }

  if (apptBizSelect) {
    if (apptBizSelect.options.length <= 1 && businesses && businesses.length > 0) {
      apptBizSelect.innerHTML = '<option value="">Select business...</option>';
      businesses.forEach((b) => {
        const opt = document.createElement("option");
        opt.value = b.id;
        opt.textContent = `${b.name} (${b.category})`;
        apptBizSelect.appendChild(opt);
      });
    }

    if (selectedBusinessId) {
      apptBizSelect.value = String(selectedBusinessId);
      await onModalBusinessChange(selectedBusinessId);
    } else if (apptBizSelect.options.length > 1) {
      apptBizSelect.selectedIndex = 1;
      selectedBusinessId = parseInt(apptBizSelect.value);
      await onModalBusinessChange(apptBizSelect.value);
    }
  }
}

async function openBookModalWithService(serviceId) {
  await openBookModalForUser();
  const svcSelect = document.getElementById("appointmentServiceSelect");
  if (svcSelect && serviceId) {
    svcSelect.value = String(serviceId);
  }
}

function closeAppointmentModal() {
  document.getElementById("appointmentModal")?.classList.remove("open");
}

async function onModalBusinessChange(bizId) {
  if (!bizId) return;

  const svcSelect = document.getElementById("appointmentServiceSelect");
  const stfSelect = document.getElementById("appointmentStaffSelect");

  try {
    const sRes = await fetch(`${API_BASE}/businesses/${bizId}/services`);
    const sList = await sRes.json();
    services = sList; // Store in global services array
    if (svcSelect) {
      svcSelect.innerHTML = '<option value="">Select service...</option>';
      sList.forEach((s) => {
        svcSelect.insertAdjacentHTML("beforeend", `<option value="${s.id}">${escapeHtml(s.name)} (₹${s.price || 0})</option>`);
      });
      if (sList.length > 0 && !svcSelect.value) {
        svcSelect.selectedIndex = 1;
      }
    }
  } catch (e) {}

  try {
    const stRes = await fetch(`${API_BASE}/businesses/${bizId}/staff`);
    const stList = await stRes.json();
    if (stfSelect) {
      stfSelect.innerHTML = '<option value="">Any Available Staff</option>';
      stList.forEach((st) => {
        stfSelect.insertAdjacentHTML("beforeend", `<option value="${st.id}">${escapeHtml(st.name)} (${escapeHtml(st.role || 'Staff')})</option>`);
      });
    }
  } catch (e) {}
}

document.getElementById("appointmentForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();

  let bizId = parseInt(document.getElementById("appointmentBusinessSelect")?.value);
  if (!bizId && currentUser && currentUser.role === "owner") {
    bizId = currentUser.business_id;
  }
  if (!bizId && selectedBusinessId) {
    bizId = selectedBusinessId;
  }
  if (!bizId) return alert("Please select a business.");

  const svcId = parseInt(document.getElementById("appointmentServiceSelect").value);
  if (!svcId) return alert("Please select a service.");

  const staffIdVal = document.getElementById("appointmentStaffSelect").value;
  const dateVal = document.getElementById("appointmentDate").value;
  if (!dateVal) return alert("Please select an appointment date.");

  const timeVal = document.getElementById("appointmentTime").value;
  if (!timeVal) return alert("Please select an appointment time slot.");

  const venueVal = document.getElementById("appointmentVenue").value;

  const custName = (document.getElementById("appointmentCustName")?.value || "").trim() || (currentUser ? currentUser.username : "Customer");
  const rawCustPhone = (document.getElementById("appointmentCustPhone")?.value || "").trim() || (currentUser ? currentUser.phone : "");

  if (!custName) return alert("Please enter your full name.");
  if (!rawCustPhone) return alert("Please enter your mobile phone number.");

  // Clean phone input (remove spaces, hyphens, parentheses)
  const custPhone = rawCustPhone.replace(/[\s\-()]/g, "");

  const svcSelect = document.getElementById("appointmentServiceSelect");
  let event_type = "General Appointment";
  if (svcSelect && svcSelect.selectedIndex >= 0) {
    const selectedText = svcSelect.options[svcSelect.selectedIndex].text;
    event_type = selectedText.split(" (")[0] || "General Appointment";
  }

  // Check / resolve customer record by phone
  let customer_id = null;
  try {
    const cRes = await fetch(`${API_BASE}/customers/?phone=${encodeURIComponent(custPhone)}`);
    if (cRes.ok) {
      const cList = await cRes.json();
      if (cList && cList.length > 0) {
        customer_id = cList[0].id;
      }
    }
    
    if (!customer_id) {
      const createRes = await fetch(`${API_BASE}/customers/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          business_id: bizId,
          name: custName,
          phone: custPhone,
          email: (currentUser ? currentUser.email : null)
        })
      });
      if (createRes.ok) {
        const cust = await createRes.json();
        customer_id = cust.id;
      } else {
        const errJson = await createRes.json().catch(() => ({}));
        alert(`❌ Could not register customer profile: ${errJson.detail || "Please check your name and phone number."}`);
        return;
      }
    }
  } catch (e) {
    console.error("Customer resolution error:", e);
  }

  if (!customer_id) {
    alert("❌ Error: Could not verify customer profile with phone " + custPhone);
    return;
  }

  // If user wasn't logged in, save session so they can view history and receive updates
  if (!currentUser) {
    currentUser = { username: custName, phone: custPhone, role: "user" };
    localStorage.setItem("booking_ai_user", JSON.stringify(currentUser));
    checkAuthSession();
  }

  // Format time properly (e.g. HH:MM)
  let formattedTime = timeVal;
  if (formattedTime && formattedTime.length === 5) {
    formattedTime = formattedTime + ":00";
  }

  try {
    const res = await fetch(`${API_BASE}/appointments/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        business_id: bizId,
        service_id: svcId,
        staff_id: staffIdVal ? parseInt(staffIdVal) : null,
        customer_id: customer_id,
        event_type: event_type,
        appointment_date: dateVal,
        appointment_time: formattedTime,
        venue: venueVal || "Main Branch",
        guests: 1
      })
    });

    if (res.ok) {
      const apptData = await res.json();
      alert(`🎉 Success! Appointment #${apptData.id} for "${event_type}" on ${dateVal} at ${timeVal} is confirmed! Instant confirmation pass generated.`);
      closeAppointmentModal();
      if (currentUser && currentUser.role === "owner") {
        if (typeof loadOwnerAppointments === "function") loadOwnerAppointments();
        if (typeof loadOwnerDashboard === "function") loadOwnerDashboard();
      } else {
        openUserProfileModal();
      }
    } else {
      const err = await res.json().catch(() => ({}));
      alert(`❌ Booking failed: ${err.detail || "Slot unavailable"}`);
    }
  } catch (err) {
    console.error("Booking submit error:", err);
    alert("❌ Failed to communicate with server. Please try again.");
  }
});

/* ==========================================================================
   8. CHAT ENGINE & FLOATING WIDGET
   ========================================================================== */
async function sendChatMessage() {
  const chatInput = document.getElementById("chatInput");
  const chatMessages = document.getElementById("chatMessages");
  if (!chatInput || !chatMessages) return;

  const text = chatInput.value.trim();
  if (!text) return;
  chatInput.value = "";

  const uDiv = document.createElement("div");
  uDiv.className = "chat-msg user";
  uDiv.innerHTML = `<div class="msg-bubble">${escapeHtml(text)}</div>`;
  chatMessages.appendChild(uDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        message: text,
        customer_phone: currentUser ? currentUser.phone : null,
        customer_name: currentUser ? currentUser.username : null,
        business_id: selectedBusinessId ? parseInt(selectedBusinessId) : null
      })
    });
    const data = await res.json();

    let formattedReply = escapeHtml(data.reply).replace(/\n/g, "<br>");
    const pdfCardHtml = renderPdfViewerCardHtml(data.pdf_url);
    const optionsHtml = renderOptionsHtml(data.options);

    const bDiv = document.createElement("div");
    bDiv.className = "chat-msg bot";
    bDiv.innerHTML = `
      <div class="msg-bubble">
        <div>${formattedReply}</div>
        ${pdfCardHtml}
        ${optionsHtml}
      </div>
    `;
    chatMessages.appendChild(bDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  } catch (err) {
    console.error("Chat error:", err);
  }
}

function quickPrompt(text) {
  const input = document.getElementById("chatInput");
  if (input) {
    input.value = text;
    sendChatMessage();
  }
}

function renderPdfViewerCardHtml(pdfUrl) {
  if (!pdfUrl) return "";
  const fullPdfUrl = pdfUrl.startsWith("http") ? pdfUrl : `${API_BASE}${pdfUrl}`;
  return `
    <div class="pdf-viewer-card" style="margin-top: 12px; background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(0, 242, 254, 0.4); border-radius: 12px; padding: 12px;">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
        <span style="color:#00f2fe; font-size:12px; font-weight:600;"><i class="fa-solid fa-file-pdf"></i> Official Pass</span>
      </div>
      <iframe src="${fullPdfUrl}#toolbar=0" style="width: 100%; height: 200px; border: none; border-radius: 6px; background:#fff;"></iframe>
      <a href="${fullPdfUrl}" target="_blank" class="btn btn-sm btn-primary" style="margin-top:8px; display:inline-block;">Download Pass PDF</a>
    </div>
  `;
}

function renderOptionsHtml(optionsList) {
  if (!optionsList || optionsList.length === 0) return "";
  let html = '<div style="display:flex; flex-wrap:wrap; gap:6px; margin-top:10px;">';
  optionsList.forEach((opt) => {
    const label = typeof opt === "string" ? opt : (opt.label || opt.text);
    const safeLabel = escapeHtml(label);
    html += `<button type="button" class="chip" style="cursor:pointer; background:rgba(0,242,254,0.15); border:1px solid rgba(0,242,254,0.4); color:#00f2fe;" onclick="quickPrompt('${safeLabel}')">${safeLabel}</button>`;
  });
  html += '</div>';
  return html;
}

/* ==========================================================================
   9. DRAGGABLE CHAT & 3D ROBOT MASCOT
   ========================================================================== */
function setup3DRobotTracking() {
  document.addEventListener("mousemove", (e) => {
    const heroHead = document.getElementById("hero-robot-head");
    const heroEyes = document.getElementById("hero-robot-eyes");
    if (!heroHead || !heroEyes) return;

    const windowWidth = window.innerWidth;
    const windowHeight = window.innerHeight;
    const mouseX = (e.clientX - windowWidth / 2) / (windowWidth / 2);
    const mouseY = (e.clientY - windowHeight / 2) / (windowHeight / 2);

    heroHead.style.transform = `rotateX(${-mouseY * 15}deg) rotateY(${mouseX * 20}deg)`;
    heroEyes.style.transform = `translate(${mouseX * 4}px, ${mouseY * 3}px)`;
  });
}

function setupDraggableChatWidget() {
  const trigger = document.getElementById("floating-robot-trigger");
  const win = document.getElementById("chat-window");
  const header = document.getElementById("chat-header-drag");
  const btnMin = document.getElementById("btn-minimize-chat");

  if (trigger && win) trigger.addEventListener("click", () => win.classList.toggle("open"));
  if (btnMin && win) btnMin.addEventListener("click", () => win.classList.remove("open"));

  let isDragging = false, startX, startY, initLeft, initTop;

  if (header && win) {
    header.addEventListener("mousedown", (e) => {
      if (e.target.closest(".btn-icon")) return;
      isDragging = true;
      startX = e.clientX;
      startY = e.clientY;
      const rect = win.getBoundingClientRect();
      initLeft = rect.left;
      initTop = rect.top;

      win.style.right = "auto";
      win.style.bottom = "auto";
      win.style.left = `${initLeft}px`;
      win.style.top = `${initTop}px`;

      document.addEventListener("mousemove", onDrag);
      document.addEventListener("mouseup", onStop);
    });
  }

  function onDrag(e) {
    if (!isDragging) return;
    win.style.left = `${initLeft + (e.clientX - startX)}px`;
    win.style.top = `${initTop + (e.clientY - startY)}px`;
  }
  function onStop() {
    isDragging = false;
    document.removeEventListener("mousemove", onDrag);
    document.removeEventListener("mouseup", onStop);
  }
}

function setupEventListeners() {
  const mainInput = document.getElementById("chatInput");
  if (mainInput) {
    mainInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        sendChatMessage();
      }
    });
  }

  const ownerInput = document.getElementById("ownerChatInput");
  if (ownerInput) {
    ownerInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        sendOwnerChatMessage();
      }
    });
  }

  const btnBannerUpload = document.getElementById("btnBannerUploadDoc");
  if (btnBannerUpload) {
    btnBannerUpload.addEventListener("click", () => openOwnerDocUploadModal());
  }

  const btnTableUpload = document.getElementById("btnTableUploadDoc");
  if (btnTableUpload) {
    btnTableUpload.addEventListener("click", () => openOwnerDocUploadModal());
  }
}

function escapeHtml(text) {
  if (!text) return "";
  return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

/* ==========================================================================
   DOCUMENT-DRIVEN BUSINESS ONBOARDING & WEEKLY HOURS MANAGEMENT
   ========================================================================== */
let currentWeeklyHours = [];
let setupSelectedFiles = [];
let extractedSetupData = null;

async function loadOwnerWeeklyHours() {
  const container = document.getElementById("weeklyHoursContainer");
  if (!container) return;
  try {
    const res = await fetch(`${API_BASE}/owner/business-hours`, { headers: getAuthHeaders() });
    currentWeeklyHours = await res.json();
    renderWeeklyHoursEditor(currentWeeklyHours, container);
  } catch (err) {
    console.error("Error loading weekly hours:", err);
  }
}

function renderWeeklyHoursEditor(hoursList, container) {
  if (!container) return;
  container.innerHTML = hoursList.map((h, idx) => `
    <div class="hours-day-row" data-day="${h.day}">
      <div class="hours-day-name">${h.day}</div>
      <div class="hours-time-inputs">
        <label style="font-size:12px; color:#94a3b8;">Open:</label>
        <input type="time" id="hours_open_${idx}" value="${h.opening_time || '10:00'}" ${!h.is_open ? 'disabled' : ''}>
        <label style="font-size:12px; color:#94a3b8; margin-left:8px;">Close:</label>
        <input type="time" id="hours_close_${idx}" value="${h.closing_time || '20:00'}" ${!h.is_open ? 'disabled' : ''}>
      </div>
      <div style="display:flex; align-items:center; gap:8px;">
        <span id="hours_status_${idx}" style="font-size:12px; color:${h.is_open ? '#34d399' : '#f87171'}; font-weight:600; min-width:55px;">
          ${h.is_open ? 'OPEN' : 'CLOSED'}
        </span>
        <label class="toggle-switch">
          <input type="checkbox" id="hours_toggle_${idx}" ${h.is_open ? 'checked' : ''} onchange="toggleDayOpen(${idx})">
          <span class="toggle-slider"></span>
        </label>
      </div>
    </div>
  `).join('');
}

function toggleDayOpen(idx) {
  const toggle = document.getElementById(`hours_toggle_${idx}`);
  const openInput = document.getElementById(`hours_open_${idx}`);
  const closeInput = document.getElementById(`hours_close_${idx}`);
  const statusLabel = document.getElementById(`hours_status_${idx}`);

  const isOpen = toggle.checked;
  openInput.disabled = !isOpen;
  closeInput.disabled = !isOpen;
  statusLabel.textContent = isOpen ? 'OPEN' : 'CLOSED';
  statusLabel.style.color = isOpen ? '#34d399' : '#f87171';
}

async function saveOwnerWeeklyHours() {
  const container = document.getElementById("weeklyHoursContainer");
  if (!container) return;

  const rows = container.querySelectorAll(".hours-day-row");
  const payload = [];

  rows.forEach((row, idx) => {
    const day = row.getAttribute("data-day");
    const openVal = document.getElementById(`hours_open_${idx}`)?.value || "10:00";
    const closeVal = document.getElementById(`hours_close_${idx}`)?.value || "20:00";
    const isOpen = document.getElementById(`hours_toggle_${idx}`)?.checked ?? true;

    payload.push({
      day: day,
      opening_time: openVal,
      closing_time: closeVal,
      is_open: isOpen
    });
  });

  try {
    const res = await fetch(`${API_BASE}/owner/business-hours`, {
      method: "PUT",
      headers: getAuthHeaders(),
      body: JSON.stringify({ hours: payload })
    });
    const data = await res.json();
    alert("✅ " + data.message);
  } catch (err) {
    console.error("Save weekly hours error:", err);
    alert("Failed to update operating hours.");
  }
}

// ============================================================================
// OWNER BUSINESS DOCUMENTS MANAGEMENT
// ============================================================================
let ownerDocSelectedFiles = [];

async function loadOwnerDocuments() {
  const tbody = document.getElementById("ownerDocumentsTable");
  if (!tbody) return;
  try {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:24px; color:#94a3b8;"><i class="fa-solid fa-spinner fa-spin" style="margin-right:8px;"></i> Loading business documents...</td></tr>`;
    const res = await fetch(`${API_BASE}/owner/documents`, { headers: getAuthHeaders() });
    if (!res.ok) {
      throw new Error(`Server returned ${res.status}`);
    }
    const docs = await res.json();
    if (!docs || docs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:36px 20px; color:#94a3b8;">
        <i class="fa-solid fa-folder-open" style="font-size:36px; opacity:0.5; display:block; margin-bottom:12px; color:#10b981;"></i>
        <div style="font-size:15px; font-weight:600; color:#f1f5f9; margin-bottom:6px;">No business documents uploaded yet</div>
        <div style="font-size:13px; color:#94a3b8; margin-bottom:18px;">Upload menus, price catalogs, or service brochures to auto-extract knowledge for your AI assistant.</div>
        <button type="button" class="btn btn-primary" onclick="openOwnerDocUploadModal()" style="background:linear-gradient(135deg, #10b981, #059669); font-weight:600; padding:10px 22px; display:inline-flex; align-items:center; gap:8px;">
          <i class="fa-solid fa-file-arrow-up"></i> Upload Document Now
        </button>
      </td></tr>`;
      return;
    }
    tbody.innerHTML = docs.map((d) => {
      const isProcessed = d.processing_status === "processed";
      const isFailed = d.processing_status === "failed";
      const statusBg = isProcessed ? "#10b981" : (isFailed ? "#ef4444" : "#f59e0b");
      const statusIcon = isProcessed ? "fa-circle-check" : (isFailed ? "fa-circle-xmark" : "fa-clock");
      const previewText = d.extracted_text_preview ? escapeHtml(d.extracted_text_preview) : '<span style="color:#64748b; font-style:italic;">No text extracted</span>';
      const sizeKb = (d.file_size / 1024).toFixed(1);
      const safeFilename = escapeHtml(d.original_filename);

      return `
        <tr>
          <td><span style="color:#94a3b8; font-weight:600;">#${d.id}</span></td>
          <td>
            <div style="font-weight:600; color:#f8fafc; max-width:220px; word-break:break-all;">
              <i class="fa-regular fa-file" style="margin-right:6px; color:#94a3b8;"></i>${safeFilename}
            </div>
          </td>
          <td><span class="doc-format-badge" style="font-size:11px; padding:3px 8px; border-radius:6px; font-weight:700;">${(d.file_type || "TXT").toUpperCase()}</span></td>
          <td style="color:#cbd5e1; font-size:13px;">${sizeKb} KB</td>
          <td>
            <span class="badge" style="background:${statusBg}; display:inline-flex; align-items:center; gap:5px; font-size:11px; padding:4px 9px;" title="${escapeHtml(d.error_message || d.processing_status)}">
              <i class="fa-solid ${statusIcon}"></i> ${d.processing_status}
            </span>
          </td>
          <td style="color:#94a3b8; font-size:12px;">${d.uploaded_at || "Recent"}</td>
          <td>
            <div style="max-width:240px; font-size:12px; color:#cbd5e1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; background:rgba(255,255,255,0.03); padding:4px 8px; border-radius:4px; border:1px solid rgba(255,255,255,0.05);" title="${escapeHtml(d.extracted_text_preview || '')}">
              ${previewText}
            </div>
          </td>
          <td style="text-align:center; white-space:nowrap;">
            <div style="display:inline-flex; gap:6px;">
              <button type="button" class="btn btn-sm btn-glass" onclick="syncOwnerDocument(${d.id}, '${safeFilename.replace(/'/g, "\\'")}')" title="Sync extracted knowledge to business & AI agent" style="padding:4px 9px; font-size:12px; color:#fbbf24; border-color:rgba(245,158,11,0.3);">
                <i class="fa-solid fa-rotate"></i> Sync
              </button>
              <button type="button" class="btn btn-sm btn-glass" onclick="viewOwnerDocument(${d.id})" title="View extracted text" style="padding:4px 9px; font-size:12px;">
                <i class="fa-solid fa-eye" style="color:#38bdf8;"></i> View
              </button>
              <button type="button" class="btn btn-sm btn-glass" onclick="deleteOwnerDocument(${d.id}, '${safeFilename.replace(/'/g, "\\'")}')" title="Delete document" style="padding:4px 9px; font-size:12px; color:#f87171; border-color:rgba(239,68,68,0.3);">
                <i class="fa-solid fa-trash-can"></i>
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    console.error("Error loading owner documents:", err);
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:20px; color:#f87171;">Failed to load documents: ${escapeHtml(err.message)}</td></tr>`;
  }
}

function triggerOwnerDocFileInput() {
  const fileInput = document.getElementById("ownerDocFileInput");
  if (fileInput) {
    fileInput.click();
  }
}

function openOwnerDocUploadModal() {
  ownerDocSelectedFiles = [];
  const errBox = document.getElementById("ownerDocUploadError");
  if (errBox) errBox.style.display = "none";
  renderOwnerDocSelectedList();
  const modal = document.getElementById("ownerDocUploadModal");
  if (modal) {
    modal.style.display = "flex";
    modal.style.opacity = "1";
    modal.style.pointerEvents = "all";
    modal.classList.add("open");
  }
  initOwnerDocDropzone();
}

function closeOwnerDocUploadModal() {
  const modal = document.getElementById("ownerDocUploadModal");
  if (modal) {
    modal.classList.remove("open");
    modal.style.display = "none";
    modal.style.opacity = "0";
    modal.style.pointerEvents = "none";
  }
  ownerDocSelectedFiles = [];
}

function initOwnerDocDropzone() {
  const dropzone = document.getElementById("ownerDocDropzone");
  const fileInput = document.getElementById("ownerDocFileInput");
  if (!dropzone || dropzone.getAttribute("data-inited")) return;

  dropzone.setAttribute("data-inited", "true");

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.style.borderColor = "#10b981";
    dropzone.style.background = "rgba(16, 185, 129, 0.1)";
  });

  dropzone.addEventListener("dragleave", (e) => {
    e.preventDefault();
    dropzone.style.borderColor = "";
    dropzone.style.background = "";
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.style.borderColor = "";
    dropzone.style.background = "";
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      addOwnerDocFiles(Array.from(e.dataTransfer.files));
    }
  });
}

function handleOwnerDocFilesSelected(e) {
  if (e.target.files && e.target.files.length > 0) {
    addOwnerDocFiles(Array.from(e.target.files));
    e.target.value = "";
  }
}

function addOwnerDocFiles(files) {
  const allowedExts = [".pdf", ".docx", ".doc", ".txt", ".csv", ".xlsx", ".xls"];
  const errBox = document.getElementById("ownerDocUploadError");
  const errText = document.getElementById("ownerDocUploadErrorText");

  for (const f of files) {
    const ext = "." + f.name.split(".").pop().toLowerCase();
    if (!allowedExts.includes(ext)) {
      if (errBox && errText) {
        errText.textContent = `File "${f.name}" has an unsupported format. Allowed: PDF, DOCX, TXT, CSV, XLSX.`;
        errBox.style.display = "block";
      }
      continue;
    }
    if (f.size === 0) {
      if (errBox && errText) {
        errText.textContent = `File "${f.name}" is empty (0 bytes). Please upload a file with content.`;
        errBox.style.display = "block";
      }
      continue;
    }
    if (f.size > 15 * 1024 * 1024) {
      if (errBox && errText) {
        errText.textContent = `File "${f.name}" exceeds the maximum allowed size of 15MB.`;
        errBox.style.display = "block";
      }
      continue;
    }
    // Avoid duplicate names in same batch
    if (!ownerDocSelectedFiles.some(existing => existing.name === f.name && existing.size === f.size)) {
      ownerDocSelectedFiles.push(f);
      if (errBox) errBox.style.display = "none";
    }
  }
  renderOwnerDocSelectedList();
}

function removeOwnerDocFile(index) {
  ownerDocSelectedFiles.splice(index, 1);
  renderOwnerDocSelectedList();
}

function renderOwnerDocSelectedList() {
  const container = document.getElementById("ownerDocSelectedListContainer");
  const list = document.getElementById("ownerDocSelectedList");
  const countSpan = document.getElementById("ownerDocSelectedCount");
  const submitBtn = document.getElementById("btnOwnerDocUploadSubmit");

  if (!submitBtn) return;

  if (ownerDocSelectedFiles.length === 0) {
    if (container) container.style.display = "none";
    submitBtn.disabled = false;
    submitBtn.innerHTML = `<i class="fa-solid fa-folder-open"></i> Browse Files to Upload`;
    submitBtn.style.background = "linear-gradient(135deg, #10b981, #059669)";
    return;
  }

  if (container) container.style.display = "block";
  if (countSpan) countSpan.textContent = ownerDocSelectedFiles.length;
  submitBtn.disabled = false;
  submitBtn.innerHTML = `<i class="fa-solid fa-cloud-arrow-up"></i> Upload & Extract Text (${ownerDocSelectedFiles.length})`;
  submitBtn.style.background = "linear-gradient(135deg, #10b981, #059669)";

  if (list) {
    list.innerHTML = ownerDocSelectedFiles.map((file, idx) => `
      <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); padding:8px 12px; border-radius:8px;">
        <div style="display:flex; align-items:center; gap:10px; overflow:hidden;">
          <i class="fa-regular fa-file-lines" style="color:#10b981; font-size:16px;"></i>
          <div style="overflow:hidden;">
            <div style="font-size:13px; font-weight:600; color:#f1f5f9; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;">${escapeHtml(file.name)}</div>
            <div style="font-size:11px; color:#94a3b8;">${(file.size / 1024).toFixed(1)} KB</div>
          </div>
        </div>
        <button type="button" class="btn-icon" onclick="removeOwnerDocFile(${idx})" title="Remove" style="color:#ef4444; width:28px; height:28px;">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
    `).join("");
  }
}

async function submitOwnerDocUpload() {
  if (ownerDocSelectedFiles.length === 0) {
    triggerOwnerDocFileInput();
    return;
  }

  const submitBtn = document.getElementById("btnOwnerDocUploadSubmit");
  const errBox = document.getElementById("ownerDocUploadError");
  const errText = document.getElementById("ownerDocUploadErrorText");

  if (errBox) errBox.style.display = "none";

  const originalBtnHtml = submitBtn ? submitBtn.innerHTML : "";
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Uploading & Extracting...`;
  }

  try {
    const formData = new FormData();
    for (const file of ownerDocSelectedFiles) {
      formData.append("files", file);
    }
    const autoSyncEl = document.getElementById("ownerDocAutoSyncCheckbox");
    const syncToSystem = autoSyncEl ? autoSyncEl.checked : true;
    formData.append("sync_to_system", syncToSystem);

    const headers = {};
    if (currentUser) {
      headers["X-User-Phone"] = currentUser.phone;
      headers["X-User-Role"] = currentUser.role || "owner";
    }

    const res = await fetch(`${API_BASE}/owner/documents`, {
      method: "POST",
      headers: headers,
      body: formData
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Failed to upload document(s).");
    }

    closeOwnerDocUploadModal();
    let msg = data.message || "Documents uploaded and extracted successfully!";
    if (data.sync_summary) {
      const s = data.sync_summary;
      const details = [];
      if (s.services_added > 0) details.push(`${s.services_added} services added`);
      if (s.services_updated > 0) details.push(`${s.services_updated} services updated`);
      if (s.hours_updated > 0) details.push(`${s.hours_updated} operating days updated`);
      if (s.rules_updated > 0) details.push(`${s.rules_updated} booking rules configured`);
      if (s.faqs_added > 0) details.push(`${s.faqs_added} FAQs added`);
      if (details.length > 0) {
        msg += `\n\n⚡ Synced to system! ${details.join(', ')}.`;
      }
    }
    alert(`✅ ${msg}`);
    showOwnerTab('ownerDocuments');
    loadOwnerDocuments();
    if (typeof loadOwnerServices === "function") loadOwnerServices();
    if (typeof loadOwnerWeeklyHours === "function") loadOwnerWeeklyHours();
    if (typeof loadOwnerBusinessInfo === "function") loadOwnerBusinessInfo();
  } catch (err) {
    console.error("Document upload error:", err);
    if (errBox && errText) {
      errText.textContent = err.message;
      errBox.style.display = "block";
    } else {
      alert("❌ Upload error: " + err.message);
    }
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      renderOwnerDocSelectedList();
    }
  }
}

async function viewOwnerDocument(docId) {
  try {
    const res = await fetch(`${API_BASE}/owner/documents/${docId}`, { headers: getAuthHeaders() });
    if (!res.ok) {
      throw new Error("Unable to fetch document details.");
    }
    const doc = await res.json();

    const titleEl = document.getElementById("previewDocTitle");
    const metaEl = document.getElementById("previewDocMeta");
    const textEl = document.getElementById("previewDocExtractedText");
    const charEl = document.getElementById("previewDocCharCount");
    const errBanner = document.getElementById("previewDocErrorBanner");
    const errMsg = document.getElementById("previewDocErrorMsg");

    if (titleEl) titleEl.textContent = doc.original_filename;
    if (metaEl) {
      metaEl.innerHTML = `Format: <strong>${(doc.file_type || '').toUpperCase()}</strong> • Size: <strong>${(doc.file_size / 1024).toFixed(1)} KB</strong> • Uploaded: <strong>${doc.uploaded_at || 'N/A'}</strong>`;
    }

    if (doc.processing_status === "failed" && doc.error_message) {
      if (errBanner && errMsg) {
        errMsg.textContent = doc.error_message;
        errBanner.style.display = "block";
      }
    } else if (errBanner) {
      errBanner.style.display = "none";
    }

    const textContent = doc.extracted_text || "(No readable text extracted from this document)";
    if (textEl) textEl.textContent = textContent;
    if (charEl) charEl.textContent = `${textContent.length.toLocaleString()} characters extracted`;

    const modal = document.getElementById("ownerDocPreviewModal");
    if (modal) {
      modal.style.display = "flex";
      modal.classList.add("open");
    }
  } catch (err) {
    alert("❌ Error loading document content: " + err.message);
  }
}

function closeOwnerDocPreviewModal() {
  const modal = document.getElementById("ownerDocPreviewModal");
  if (modal) {
    modal.classList.remove("open");
    modal.style.display = "none";
  }
}

function copyExtractedDocText() {
  const textEl = document.getElementById("previewDocExtractedText");
  if (!textEl || !textEl.textContent) return;
  navigator.clipboard.writeText(textEl.textContent).then(() => {
    alert("📋 Extracted text copied to clipboard!");
  }).catch(() => {
    alert("Unable to copy to clipboard.");
  });
}

async function deleteOwnerDocument(docId, docName) {
  if (!confirm(`Are you sure you want to delete "${docName}"?\n\nThis will remove the document file and its extracted text permanently.`)) {
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/owner/documents/${docId}`, {
      method: "DELETE",
      headers: getAuthHeaders()
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Failed to delete document.");
    }
    alert(`🗑️ ${data.message || "Document deleted successfully."}`);
    loadOwnerDocuments();
  } catch (err) {
    console.error("Delete document error:", err);
    alert("❌ Delete failed: " + err.message);
  }
}

async function syncOwnerDocument(docId, docName) {
  if (!confirm(`Sync "${docName}" with business system?\n\nThis will extract services, hours, policies, and FAQs from this document and apply them to your catalog & AI agent.`)) {
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/owner/documents/${docId}/sync`, {
      method: "POST",
      headers: getAuthHeaders()
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Failed to sync document.");
    }
    let msg = data.message || "Document synced successfully.";
    if (data.sync_summary) {
      const s = data.sync_summary;
      const details = [];
      if (s.services_added > 0) details.push(`${s.services_added} services added`);
      if (s.services_updated > 0) details.push(`${s.services_updated} services updated`);
      if (s.hours_updated > 0) details.push(`${s.hours_updated} days hours updated`);
      if (s.rules_updated > 0) details.push(`${s.rules_updated} policies configured`);
      if (s.faqs_added > 0) details.push(`${s.faqs_added} FAQs configured`);
      if (details.length > 0) {
        msg += `\n\n⚡ ${details.join(', ')}.`;
      }
    }
    alert(`✅ ${msg}`);
    loadOwnerDocuments();
    if (typeof loadOwnerServices === "function") loadOwnerServices();
    if (typeof loadOwnerWeeklyHours === "function") loadOwnerWeeklyHours();
    if (typeof loadOwnerBusinessInfo === "function") loadOwnerBusinessInfo();
  } catch (err) {
    console.error("Sync document error:", err);
    alert("❌ Sync failed: " + err.message);
  }
}

async function syncAllOwnerDocuments() {
  if (!confirm(`⚡ Sync all processed business documents to your system?\n\nThis will re-extract services, weekly operating hours, booking rules, and FAQs from all your uploaded documents and update your catalog & AI agent.`)) {
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/owner/documents/sync-all`, {
      method: "POST",
      headers: getAuthHeaders()
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Failed to sync documents.");
    }
    let msg = data.message || "All documents synced successfully.";
    if (data.sync_summary) {
      const s = data.sync_summary;
      const details = [];
      if (s.services_added > 0) details.push(`${s.services_added} services added`);
      if (s.services_updated > 0) details.push(`${s.services_updated} services updated`);
      if (s.hours_updated > 0) details.push(`${s.hours_updated} days hours updated`);
      if (s.rules_updated > 0) details.push(`${s.rules_updated} policies configured`);
      if (s.faqs_added > 0) details.push(`${s.faqs_added} FAQs configured`);
      if (details.length > 0) {
        msg += `\n\n⚡ Result: ${details.join(', ')}.`;
      }
    }
    alert(`✅ ${msg}`);
    loadOwnerDocuments();
    if (typeof loadOwnerServices === "function") loadOwnerServices();
    if (typeof loadOwnerWeeklyHours === "function") loadOwnerWeeklyHours();
    if (typeof loadOwnerBusinessInfo === "function") loadOwnerBusinessInfo();
  } catch (err) {
    console.error("Sync all documents error:", err);
    alert("❌ Sync all failed: " + err.message);
  }
}

function initDocDropzone() {
  const dropzone = document.getElementById("docDropzone");
  const fileInput = document.getElementById("setupFileInput");
  if (!dropzone || dropzone.getAttribute("data-inited")) return;

  dropzone.setAttribute("data-inited", "true");

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.style.borderColor = "#a855f7";
    dropzone.style.background = "rgba(168, 85, 247, 0.12)";
  });

  dropzone.addEventListener("dragleave", (e) => {
    e.preventDefault();
    dropzone.style.borderColor = "";
    dropzone.style.background = "";
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.style.borderColor = "";
    dropzone.style.background = "";
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setupSelectedFiles = Array.from(e.dataTransfer.files);
      renderSetupFilesList();
    }
  });

  dropzone.addEventListener("click", (e) => {
    if (e.target !== fileInput) {
      fileInput?.click();
    }
  });
}

function openDocumentSetupModal() {
  setupSelectedFiles = [];
  extractedSetupData = null;
  const input = document.getElementById("setupFileInput");
  if (input) input.value = "";
  const listEl = document.getElementById("setupSelectedFilesList");
  if (listEl) {
    listEl.innerHTML = "";
    listEl.style.display = "none";
  }
  const btn = document.getElementById("btnRunExtraction");
  if (btn) {
    btn.disabled = false;
    btn.innerHTML = `<i class="fa-solid fa-folder-open"></i> Browse Files to Analyze`;
  }

  document.getElementById("setupStepUpload").style.display = "block";
  document.getElementById("setupStepLoading").style.display = "none";
  document.getElementById("setupStepReview").style.display = "none";

  initDocDropzone();
  const modal = document.getElementById("documentSetupModal");
  if (modal) {
    modal.style.display = "flex";
    modal.style.opacity = "1";
    modal.style.pointerEvents = "all";
    modal.classList.add("open");
  }
}

function closeDocumentSetupModal() {
  const modal = document.getElementById("documentSetupModal");
  if (modal) {
    modal.classList.remove("open");
    modal.style.display = "none";
    modal.style.opacity = "0";
    modal.style.pointerEvents = "none";
  }
}

function handleSetupFilesSelected(event) {
  const files = Array.from(event.target.files);
  if (!files || files.length === 0) return;

  setupSelectedFiles = files;
  renderSetupFilesList();
}

function renderSetupFilesList() {
  const listEl = document.getElementById("setupSelectedFilesList");
  const btn = document.getElementById("btnRunExtraction");
  if (!btn) return;

  if (setupSelectedFiles.length === 0) {
    if (listEl) {
      listEl.style.display = "none";
      listEl.innerHTML = "";
    }
    btn.disabled = false;
    btn.innerHTML = `<i class="fa-solid fa-folder-open"></i> Browse Files to Analyze`;
    return;
  }

  if (listEl) {
    listEl.style.display = "flex";
    listEl.innerHTML = setupSelectedFiles.map((f, i) => `
      <div class="doc-file-chip">
        <div class="doc-file-chip-info">
          <i class="fa-solid fa-file-lines"></i>
          <div>
            <div style="font-weight:600;">${escapeHtml(f.name)}</div>
            <div class="doc-file-chip-size">${(f.size / 1024).toFixed(1)} KB</div>
          </div>
        </div>
        <button type="button" class="doc-file-remove-btn" onclick="removeSetupFile(${i})">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
    `).join('');
  }

  btn.disabled = false;
  btn.innerHTML = `<i class="fa-solid fa-bolt"></i> Analyze & Extract with AI (${setupSelectedFiles.length})`;
}

function removeSetupFile(index) {
  setupSelectedFiles.splice(index, 1);
  renderSetupFilesList();
}

function backToSetupUploadStep() {
  document.getElementById("setupStepUpload").style.display = "block";
  document.getElementById("setupStepLoading").style.display = "none";
  document.getElementById("setupStepReview").style.display = "none";
}

async function submitDocumentSetupExtraction() {
  if (setupSelectedFiles.length === 0) {
    document.getElementById("setupFileInput")?.click();
    return;
  }

  document.getElementById("setupStepUpload").style.display = "none";
  document.getElementById("setupStepLoading").style.display = "block";
  document.getElementById("setupStepReview").style.display = "none";

  const formData = new FormData();
  for (const file of setupSelectedFiles) {
    formData.append("files", file);
  }

  try {
    const headers = {};
    if (currentUser) {
      headers["X-User-Phone"] = currentUser.phone;
      headers["X-User-Role"] = currentUser.role;
    }

    const res = await fetch(`${API_BASE}/owner/setup/upload-documents`, {
      method: "POST",
      headers: headers,
      body: formData
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Extraction failed");
    }

    extractedSetupData = await res.json();
    renderDocumentExtractionPreview(extractedSetupData);
  } catch (err) {
    alert("❌ Error analyzing documents: " + err.message);
    backToSetupUploadStep();
  }
}

function renderDocumentExtractionPreview(data) {
  document.getElementById("setupStepLoading").style.display = "none";
  document.getElementById("setupStepReview").style.display = "block";

  // Business Profile
  document.getElementById("previewBizName").value = data.business_name || "";
  document.getElementById("previewBizCategory").value = data.category || "General Services";
  document.getElementById("previewBizPhone").value = data.phone || "";
  document.getElementById("previewBizLocation").value = data.location || "";

  // Missing fields alert (No Fabrication Guarantee)
  const missingBox = document.getElementById("setupMissingBox");
  const missingTags = document.getElementById("setupMissingTags");
  if (data.missing_fields && data.missing_fields.length > 0) {
    missingBox.style.display = "block";
    missingTags.innerHTML = data.missing_fields.map(f => `
      <span class="missing-tag"><i class="fa-solid fa-circle-exclamation"></i> ${escapeHtml(f)}</span>
    `).join('');
  } else {
    missingBox.style.display = "none";
  }

  // Multi-document conflict banner
  const conflictBox = document.getElementById("setupConflictBox");
  if (data.conflicts && data.conflicts.length > 0) {
    conflictBox.style.display = "block";
    conflictBox.innerHTML = data.conflicts.map(c => `
      <div class="conflict-card">
        <div class="conflict-card-header">
          <i class="fa-solid fa-triangle-exclamation"></i>
          <span>Multi-Document Discrepancy Detected for "${escapeHtml(c.item_name)}"</span>
        </div>
        <div class="conflict-card-body">
          <div><strong>${escapeHtml(c.source1)}</strong> indicates: <code>${c.value1}</code></div>
          <div><strong>${escapeHtml(c.source2)}</strong> indicates: <code>${c.value2}</code></div>
          <div style="margin-top:6px; color:#fde047; font-size:12px;"><strong>Resolution Suggestion:</strong> ${escapeHtml(c.resolution_suggestion || 'Please verify the final value below.')}</div>
        </div>
      </div>
    `).join('');
  } else {
    conflictBox.style.display = "none";
  }

  // Services table
  renderPreviewServicesTable(data.services || []);

  // Weekly hours preview
  const hoursContainer = document.getElementById("previewHoursContainer");
  const hours = data.business_hours || [];
  hoursContainer.innerHTML = hours.map((h, i) => `
    <div class="hours-day-row" data-preview-day="${h.day}">
      <div class="hours-day-name">${h.day}</div>
      <div class="hours-time-inputs">
        <label style="font-size:11px; color:#94a3b8;">Open:</label>
        <input type="time" id="preview_open_${i}" value="${h.opening_time || '10:00'}" ${!h.is_open ? 'disabled' : ''}>
        <label style="font-size:11px; color:#94a3b8; margin-left:8px;">Close:</label>
        <input type="time" id="preview_close_${i}" value="${h.closing_time || '20:00'}" ${!h.is_open ? 'disabled' : ''}>
      </div>
      <div style="display:flex; align-items:center; gap:8px;">
        <span id="preview_status_${i}" style="font-size:12px; color:${h.is_open ? '#34d399' : '#f87171'}; font-weight:600; min-width:55px;">
          ${h.is_open ? 'OPEN' : 'CLOSED'}
        </span>
        <label class="toggle-switch">
          <input type="checkbox" id="preview_toggle_${i}" ${h.is_open ? 'checked' : ''} onchange="togglePreviewDayOpen(${i})">
          <span class="toggle-slider"></span>
        </label>
      </div>
    </div>
  `).join('');

  // Rules & FAQs preview
  const faqsContainer = document.getElementById("previewFaqsContainer");
  const faqs = data.faqs || [];
  const rules = data.booking_rules || {};
  document.getElementById("previewFaqsCount").textContent = faqs.length;

  let rulesSummary = `<div style="margin-bottom:8px; line-height:1.6;">
    <strong>Notice Period:</strong> ${rules.min_notice_hours || 2}h | 
    <strong>Buffer:</strong> ${rules.booking_buffer_mins || 15}m | 
    <strong>Cancellation:</strong> ${escapeHtml(rules.cancellation_rules || 'Free cancellation up to 2 hours before appointment')}
  </div>`;

  if (faqs.length > 0) {
    rulesSummary += `<div style="display:flex; flex-direction:column; gap:6px; margin-top:8px;">` +
      faqs.map(f => `
        <div style="background:rgba(255,255,255,0.04); padding:8px 12px; border-radius:8px;">
          <strong style="color:#67e8f9;">Q: ${escapeHtml(f.question)}</strong><br>
          <span style="color:#e2e8f0;">A: ${escapeHtml(f.answer)}</span>
        </div>
      `).join('') + `</div>`;
  }
  faqsContainer.innerHTML = rulesSummary;
}

function renderPreviewServicesTable(services) {
  const tbody = document.getElementById("previewServicesTable");
  document.getElementById("previewServicesCount").textContent = services.length;
  tbody.innerHTML = services.map((s, idx) => `
    <tr data-service-idx="${idx}">
      <td><input type="text" class="preview-s-name" value="${escapeHtml(s.name)}" style="width:100%; background:rgba(30,41,59,0.8); border:1px solid rgba(255,255,255,0.1); border-radius:6px; padding:4px 8px; color:white;"></td>
      <td><input type="text" class="preview-s-cat" value="${escapeHtml(s.category || 'General')}" style="width:100%; background:rgba(30,41,59,0.8); border:1px solid rgba(255,255,255,0.1); border-radius:6px; padding:4px 8px; color:white;"></td>
      <td><input type="number" class="preview-s-price" value="${s.price || 0}" style="width:80px; background:rgba(30,41,59,0.8); border:1px solid rgba(255,255,255,0.1); border-radius:6px; padding:4px 8px; color:white;"></td>
      <td><input type="number" class="preview-s-dur" value="${s.duration_minutes || 30}" style="width:70px; background:rgba(30,41,59,0.8); border:1px solid rgba(255,255,255,0.1); border-radius:6px; padding:4px 8px; color:white;"></td>
      <td>
        <button type="button" class="btn btn-sm btn-glass" onclick="removePreviewServiceRow(this)" style="color:#f87171;"><i class="fa-solid fa-trash"></i></button>
      </td>
    </tr>
  `).join('');
}

function addBlankServiceRow() {
  const tbody = document.getElementById("previewServicesTable");
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td><input type="text" class="preview-s-name" placeholder="Service Name" style="width:100%; background:rgba(30,41,59,0.8); border:1px solid rgba(255,255,255,0.1); border-radius:6px; padding:4px 8px; color:white;"></td>
    <td><input type="text" class="preview-s-cat" value="General" style="width:100%; background:rgba(30,41,59,0.8); border:1px solid rgba(255,255,255,0.1); border-radius:6px; padding:4px 8px; color:white;"></td>
    <td><input type="number" class="preview-s-price" value="500" style="width:80px; background:rgba(30,41,59,0.8); border:1px solid rgba(255,255,255,0.1); border-radius:6px; padding:4px 8px; color:white;"></td>
    <td><input type="number" class="preview-s-dur" value="30" style="width:70px; background:rgba(30,41,59,0.8); border:1px solid rgba(255,255,255,0.1); border-radius:6px; padding:4px 8px; color:white;"></td>
    <td>
      <button type="button" class="btn btn-sm btn-glass" onclick="removePreviewServiceRow(this)" style="color:#f87171;"><i class="fa-solid fa-trash"></i></button>
    </td>
  `;
  tbody.appendChild(tr);
  const count = document.getElementById("previewServicesCount");
  count.textContent = parseInt(count.textContent || 0) + 1;
}

function removePreviewServiceRow(btn) {
  btn.closest("tr").remove();
  const count = document.getElementById("previewServicesCount");
  count.textContent = Math.max(0, parseInt(count.textContent || 0) - 1);
}

function togglePreviewDayOpen(idx) {
  const toggle = document.getElementById(`preview_toggle_${idx}`);
  const openInput = document.getElementById(`preview_open_${idx}`);
  const closeInput = document.getElementById(`preview_close_${idx}`);
  const statusLabel = document.getElementById(`preview_status_${idx}`);

  const isOpen = toggle.checked;
  openInput.disabled = !isOpen;
  closeInput.disabled = !isOpen;
  statusLabel.textContent = isOpen ? 'OPEN' : 'CLOSED';
  statusLabel.style.color = isOpen ? '#34d399' : '#f87171';
}

async function confirmBusinessSetup() {
  const name = document.getElementById("previewBizName").value.trim();
  if (!name) {
    alert("Please specify a business name.");
    return;
  }
  const category = document.getElementById("previewBizCategory").value.trim() || "General Services";
  const phone = document.getElementById("previewBizPhone").value.trim();
  const location = document.getElementById("previewBizLocation").value.trim();

  // Harvest services
  const services = [];
  const rows = document.querySelectorAll("#previewServicesTable tr");
  rows.forEach(r => {
    const sName = r.querySelector(".preview-s-name")?.value.trim();
    if (sName) {
      services.push({
        name: sName,
        category: r.querySelector(".preview-s-cat")?.value.trim() || "General",
        price: parseFloat(r.querySelector(".preview-s-price")?.value || 0),
        duration_minutes: parseInt(r.querySelector(".preview-s-dur")?.value || 30),
        description: ""
      });
    }
  });

  // Harvest hours
  const hours = [];
  const hourRows = document.querySelectorAll("#previewHoursContainer .hours-day-row");
  hourRows.forEach((r, i) => {
    hours.push({
      day: r.getAttribute("data-preview-day"),
      opening_time: document.getElementById(`preview_open_${i}`)?.value || "10:00",
      closing_time: document.getElementById(`preview_close_${i}`)?.value || "20:00",
      is_open: document.getElementById(`preview_toggle_${i}`)?.checked ?? true
    });
  });

  const payload = {
    name: name,
    category: category,
    phone: phone,
    description: extractedSetupData?.description || `${name} is a premier ${category} provider.`,
    location: location,
    currency: "INR",
    timezone: "Asia/Kolkata",
    services: services,
    business_hours: hours,
    booking_rules: extractedSetupData?.booking_rules || null,
    faqs: extractedSetupData?.faqs || [],
    document_ids: extractedSetupData?.document_ids || []
  };

  try {
    const res = await fetch(`${API_BASE}/owner/setup/confirm`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Setup confirmation failed");
    }

    const data = await res.json();
    alert("🎉 Success! " + data.message);
    closeDocumentSetupModal();

    // Reload owner dashboard and services
    loadOwnerDashboard();
    loadOwnerBusinessInfo();
    loadOwnerServices();
    loadOwnerWeeklyHours();
    loadOwnerDocuments();
    showOwnerTab("ownerOverview");
  } catch (err) {
    alert("❌ Error saving business setup: " + err.message);
  }
}