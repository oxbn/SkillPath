// Shared by both pages. The theme has already been applied to <html> by the inline script
// in base.html; everything here runs after first paint.

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderMessage(container, text, variant) {
  container.replaceChildren(el("p", `message ${variant}`, text));
}

// Failures carry a "detail" that explains itself far better than the status code — a bad
// title regex, or a paste over the length limit. HTTPException makes it a string, but
// FastAPI's own request validation makes it a list of {msg, loc} objects, so handle both.
function errorMessage(body, status) {
  const detail = body && body.detail;

  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;

  return `Request failed (${status})`;
}

async function requestJSON(url, options) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(errorMessage(body, response.status));
  }

  return body;
}

function initTheme() {
  const toggle = document.getElementById("theme-toggle");
  if (!toggle) return;

  const sync = (theme) => {
    const dark = theme === "dark";
    toggle.setAttribute("aria-pressed", String(dark));
    toggle.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
  };

  sync(document.documentElement.dataset.theme);

  toggle.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("theme", next);
    } catch (error) {
      // Private browsing can refuse writes; the theme still applies for this page.
    }
    sync(next);
  });
}

initTheme();
