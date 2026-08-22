const API = "/api/v1";
let currentUser = null;

const $ = (id) => document.getElementById(id);

const loginPanel = $("login-panel");
const customerPanel = $("customer-panel");
const searchPanel = $("search-panel");
const resultsPanel = $("results-panel");
const listPanel = $("list-panel");
const authBadge = $("auth-badge");
const authUser = $("auth-user");
const resultsOutput = $("results-output");
const customerList = $("customer-list");
const toast = $("toast");

function showToast(message, type = "success") {
  toast.textContent = message;
  toast.className = `toast ${type}`;
  toast.classList.remove("hidden");
  setTimeout(() => toast.classList.add("hidden"), 4000);
}

function showResults(data) {
  resultsPanel.classList.remove("hidden");
  resultsOutput.textContent = JSON.stringify(data, null, 2);
}

function getPersonType() {
  return document.querySelector('input[name="person_type"]:checked').value;
}

function updateDocumentLabel() {
  const isPj = getPersonType() === "PJ";
  $("document-label").textContent = isPj ? "CNPJ" : "CPF";
  $("customer-document").placeholder = isPj ? "04.252.011/0001-10" : "529.982.247-25";
  $("cnpj-actions").classList.toggle("hidden", !isPj);
}

function setAuthenticated(isAuth, username = "") {
  loginPanel.classList.toggle("hidden", isAuth);
  customerPanel.classList.toggle("hidden", !isAuth);
  searchPanel.classList.toggle("hidden", !isAuth);
  listPanel.classList.toggle("hidden", !isAuth);
  authBadge.classList.toggle("hidden", !isAuth);
  authUser.textContent = isAuth ? `Logado: ${username}` : "";
  if (isAuth) loadCustomers();
}

function csrfToken() {
  const entry = document.cookie.split("; ").find((value) => value.startsWith("oficina_csrf="));
  return entry ? decodeURIComponent(entry.substring("oficina_csrf=".length)) : null;
}

let refreshInFlight = null;

// Parallel 401s must share one rotation: two concurrent refreshes send the
// same cookie, and the server reads the second as token reuse and revokes the
// whole session family.
function refreshSession() {
  if (!refreshInFlight) {
    refreshInFlight = api("/auth/refresh", { method: "POST", body: "{}" }, false).finally(
      () => {
        refreshInFlight = null;
      }
    );
  }
  return refreshInFlight;
}

async function api(path, options = {}, allowRefresh = true) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (options.method && !["GET", "HEAD", "OPTIONS"].includes(options.method.toUpperCase())) {
    const csrf = csrfToken();
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }

  const response = await fetch(`${API}${path}`, { ...options, headers, credentials: "include" });
  let body = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    body = await response.json();
  } else if (response.status !== 204) {
    body = await response.text();
  }

  if (response.status === 401 && allowRefresh && path.startsWith("/admin/")) {
    await refreshSession();
    return api(path, options, false);
  }
  if (!response.ok) {
    const detail = body?.detail || `Erro ${response.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return body;
}

function documentBadge(documents) {
  const hasCpf = documents.some((doc) => doc.length === 11);
  const hasCnpj = documents.some((doc) => doc.length === 14);
  if (hasCpf && hasCnpj) return "PF/PJ";
  if (hasCnpj) return "PJ";
  return "PF";
}

function renderCustomers(customers) {
  if (!customers.length) {
    customerList.innerHTML = '<p class="empty-state">Nenhum cliente cadastrado.</p>';
    return;
  }

  customerList.innerHTML = customers
    .map(
      (c) => `
    <article class="customer-item">
      <div>
        <strong>${escapeHtml(c.name)}</strong>
        <span>${escapeHtml(c.email)} · ${escapeHtml(c.phone || "sem telefone")}</span>
        <span>${escapeHtml(c.address)}</span>
      </div>
      <div style="text-align:right">
        <span class="badge badge-${documentBadge(c.documents).toLowerCase()}">${documentBadge(c.documents)}</span>
        <div>${c.documents.map((doc) => `<span>${formatDocument(doc)}</span>`).join("<br>")}</div>
      </div>
    </article>`
    )
    .join("");
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

function formatDocument(doc) {
  if (doc.length === 11) {
    return doc.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, "$1.$2.$3-$4");
  }
  if (doc.length === 14) {
    return doc.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, "$1.$2.$3/$4-$5");
  }
  return doc;
}

async function loadCustomers() {
  try {
    const customers = await api("/admin/customers");
    renderCustomers(customers);
  } catch (err) {
    showToast(err.message, "error");
  }
}

$("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const data = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: $("username").value.trim(),
        password: $("password").value,
      }),
    });
    currentUser = data;
    setAuthenticated(true, data.username);
    showToast("Login realizado com sucesso");
  } catch (err) {
    showToast(err.message, "error");
  }
});

$("logout-btn").addEventListener("click", async () => {
  await api("/auth/logout", { method: "POST", body: "{}" }).catch(() => undefined);
  currentUser = null;
  setAuthenticated(false);
  resultsPanel.classList.add("hidden");
  showToast("Sessão encerrada");
});

document.querySelectorAll('input[name="person_type"]').forEach((radio) => {
  radio.addEventListener("change", updateDocumentLabel);
});

$("validate-cnpj-btn").addEventListener("click", async () => {
  const cnpj = $("customer-document").value.trim();
  if (!cnpj) {
    showToast("Informe o CNPJ", "error");
    return;
  }
  try {
    const result = await api("/admin/customers/validate-cnpj", {
      method: "POST",
      body: JSON.stringify({ document: cnpj.replace(/\D/g, "") }),
    });
    showResults(result);
    showToast(`CNPJ válido: ${result.legal_name || "OK"}`);
  } catch (err) {
    showToast(err.message, "error");
    showResults({ error: err.message });
  }
});

$("customer-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    name: $("customer-name").value.trim(),
    document: $("customer-document").value.trim(),
    email: $("customer-email").value.trim(),
    phone: $("customer-phone").value.trim() || null,
    address: $("customer-address").value.trim(),
  };

  try {
    const customer = await api("/admin/customers", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showResults(customer);
    showToast(`Cliente "${customer.name}" cadastrado`);
    $("customer-form").reset();
    document.querySelector('input[name="person_type"][value="PF"]').checked = true;
    updateDocumentLabel();
    loadCustomers();
  } catch (err) {
    showToast(err.message, "error");
    showResults({ error: err.message });
  }
});

$("search-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const doc = $("search-document").value.trim().replace(/\D/g, "");
  try {
    const customer = await api("/admin/customers/by-document", {
      method: "POST",
      body: JSON.stringify({ document: doc }),
    });
    showResults(customer);
    showToast("Cliente encontrado");
  } catch (err) {
    showToast(err.message, "error");
    showResults({ error: err.message });
  }
});

$("clear-results").addEventListener("click", () => {
  resultsPanel.classList.add("hidden");
  resultsOutput.textContent = "";
});

$("refresh-list").addEventListener("click", loadCustomers);

// Init
updateDocumentLabel();
api("/auth/me")
  .then((user) => {
    currentUser = user;
    setAuthenticated(true, user.username);
  })
  .catch(() => setAuthenticated(false));
