// Local model management panel (Ollama only).
// Lists installed models, pulls new ones with a progress bar, sets the active
// model (hot-swap), and deletes models.

document.addEventListener("DOMContentLoaded", function () {
  var statusEl = document.getElementById("models-status");
  var listEl = document.getElementById("models-list");
  var suggestedEl = document.getElementById("pull-suggested");
  var pullInput = document.getElementById("pull-name");
  var pullBtn = document.getElementById("pull-btn");
  var pullProgress = document.getElementById("pull-progress");
  var pullLabel = document.getElementById("pull-label");
  var pullBar = document.getElementById("pull-bar");
  var refreshBtn = document.getElementById("models-refresh");

  function fmtSize(bytes) {
    if (!bytes) return "";
    var gb = bytes / 1e9;
    if (gb >= 1) return gb.toFixed(1) + " GB";
    return Math.round(bytes / 1e6) + " MB";
  }

  function renderList(data) {
    listEl.innerHTML = "";
    if (!data.installed.length) {
      listEl.innerHTML =
        '<p class="text-sm text-gray-400 dark:text-gray-500">No models installed yet. Install one below.</p>';
    }
    data.installed.forEach(function (m) {
      var isActive = m.name === data.active;
      var row = document.createElement("div");
      row.className =
        "flex items-center justify-between bg-gray-50 dark:bg-gray-900 rounded-md px-3 py-2";

      var left = document.createElement("div");
      left.innerHTML =
        '<span class="font-medium text-sm">' +
        m.name +
        "</span>" +
        (isActive
          ? ' <span class="ml-2 text-xs bg-blue-600 text-white px-2 py-0.5 rounded-full">active</span>'
          : "") +
        '<span class="block text-xs text-gray-400 dark:text-gray-500">' +
        fmtSize(m.size_bytes) +
        "</span>";
      row.appendChild(left);

      var right = document.createElement("div");
      right.className = "flex gap-2";
      if (!isActive) {
        right.appendChild(
          btn("Use", "text-blue-600 dark:text-blue-400", function () {
            activate(m.name);
          })
        );
        right.appendChild(
          btn("Delete", "text-red-600 dark:text-red-400", function () {
            del(m.name);
          })
        );
      }
      row.appendChild(right);
      listEl.appendChild(row);
    });

    suggestedEl.innerHTML = "";
    data.suggested.forEach(function (name) {
      var chip = document.createElement("button");
      chip.className =
        "text-xs bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 px-2 py-1 rounded";
      chip.textContent = name;
      chip.addEventListener("click", function () {
        pullInput.value = name;
      });
      suggestedEl.appendChild(chip);
    });
  }

  function btn(text, color, onClick) {
    var b = document.createElement("button");
    b.className = "text-xs font-medium hover:underline " + color;
    b.textContent = text;
    b.addEventListener("click", onClick);
    return b;
  }

  async function load() {
    statusEl.textContent = "Loading…";
    try {
      var resp = await fetch("/api/models");
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      var data = await resp.json();
      renderList(data);
      statusEl.textContent = data.installed.length + " installed";
    } catch (e) {
      statusEl.textContent = "Could not reach Ollama. Is the container running?";
    }
  }

  async function activate(name) {
    statusEl.textContent = "Switching to " + name + "…";
    var resp = await fetch("/api/models/active", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name }),
    });
    if (resp.ok) {
      await load();
    } else {
      var err = await resp.json().catch(function () {
        return {};
      });
      statusEl.textContent = err.detail || "Failed to switch model.";
    }
  }

  async function del(name) {
    if (!confirm("Delete " + name + "?")) return;
    var resp = await fetch("/api/models/" + encodeURIComponent(name), {
      method: "DELETE",
    });
    if (resp.ok) {
      await load();
    } else {
      var err = await resp.json().catch(function () {
        return {};
      });
      statusEl.textContent = err.detail || "Failed to delete model.";
    }
  }

  var polling = null;

  function pollPull(name) {
    if (polling) clearInterval(polling);
    polling = setInterval(async function () {
      var resp = await fetch(
        "/api/models/pull/status?name=" + encodeURIComponent(name)
      );
      if (!resp.ok) return;
      var p = await resp.json();
      pullLabel.textContent = p.error
        ? "Error: " + p.error
        : p.status + (p.percent ? " — " + p.percent + "%" : "");
      pullBar.style.width = (p.percent || 0) + "%";
      if (p.done || p.error) {
        clearInterval(polling);
        polling = null;
        pullBtn.disabled = false;
        if (!p.error) {
          pullBar.style.width = "100%";
          setTimeout(function () {
            pullProgress.classList.add("hidden");
          }, 1500);
        }
        load();
      }
    }, 1000);
  }

  async function startPull() {
    var name = pullInput.value.trim();
    if (!name) return;
    pullBtn.disabled = true;
    pullProgress.classList.remove("hidden");
    pullLabel.textContent = "Starting…";
    pullBar.style.width = "0%";

    var resp = await fetch("/api/models/pull", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name }),
    });
    if (resp.status === 202) {
      pollPull(name);
    } else {
      var err = await resp.json().catch(function () {
        return {};
      });
      pullLabel.textContent = err.detail || "Failed to start pull.";
      pullBtn.disabled = false;
    }
  }

  pullBtn.addEventListener("click", startPull);
  refreshBtn.addEventListener("click", load);
  load();
});
