document.addEventListener("DOMContentLoaded", function () {
  const form = document.getElementById("capture-form");
  const rawInput = document.getElementById("raw-input");
  const resultDiv = document.getElementById("extraction-result");
  const spinner = document.getElementById("extract-spinner");
  const confirmArea = document.getElementById("confirm-area");
  const confirmBtn = document.getElementById("confirm-btn");
  const confirmSpinner = document.getElementById("confirm-spinner");
  const saveSuccess = document.getElementById("save-success");
  const resolutionArea = document.getElementById("resolution-area");

  let currentExtraction = null;
  let currentPersonId = null;

  document.getElementById("dismiss-btn").addEventListener("click", function () {
    resultDiv.classList.add("hidden");
    confirmArea.classList.add("hidden");
    saveSuccess.classList.add("hidden");
    currentExtraction = null;
    currentPersonId = null;
  });

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    const text = rawInput.value.trim();
    if (!text) return;

    spinner.style.display = "inline-block";
    resultDiv.classList.add("hidden");
    saveSuccess.classList.add("hidden");

    try {
      const resp = await fetch("/interactions/text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_input: text }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        alert("Error: " + (data.detail || "Unknown error"));
        return;
      }
      showResult(data);
    } catch (err) {
      alert("Network error: " + err.message);
    } finally {
      spinner.style.display = "none";
    }
  });

  function showResult(data) {
    currentExtraction = data.extraction;
    const res = data.person_resolution;

    document.getElementById("result-person").textContent =
      data.extraction.person_name;
    document.getElementById("result-type").textContent =
      data.extraction.interaction_type;
    document.getElementById("result-summary").textContent =
      data.extraction.summary;

    const factsDiv = document.getElementById("result-facts");
    if (data.extraction.facts.length > 0) {
      factsDiv.innerHTML =
        '<span class="text-gray-500">Facts:</span><ul class="list-disc list-inside mt-1">' +
        data.extraction.facts
          .map(
            (f) =>
              "<li><span class='text-gray-400'>[" +
              escapeHtml(f.category) +
              "]</span> " +
              escapeHtml(f.content) +
              "</li>"
          )
          .join("") +
        "</ul>";
    } else {
      factsDiv.innerHTML = "";
    }

    const tagsDiv = document.getElementById("result-tags");
    if (data.extraction.tags_added.length > 0) {
      tagsDiv.innerHTML =
        '<span class="text-gray-500">Tags:</span> ' +
        data.extraction.tags_added
          .map(
            (t) =>
              '<span class="bg-blue-50 text-blue-700 text-xs px-2 py-0.5 rounded mr-1">' +
              escapeHtml(t) +
              "</span>"
          )
          .join("");
    } else {
      tagsDiv.innerHTML = "";
    }

    const loopsDiv = document.getElementById("result-loops");
    if (data.extraction.loops.length > 0) {
      loopsDiv.innerHTML =
        '<span class="text-gray-500">Loops:</span><ul class="list-disc list-inside mt-1">' +
        data.extraction.loops
          .map(
            (l) =>
              "<li>" +
              escapeHtml(l.description) +
              (l.due_date ? " (due: " + escapeHtml(l.due_date) + ")" : "") +
              "</li>"
          )
          .join("") +
        "</ul>";
    } else {
      loopsDiv.innerHTML = "";
    }

    showResolution(res);
    resultDiv.classList.remove("hidden");
  }

  function showResolution(res) {
    confirmArea.classList.add("hidden");
    currentPersonId = null;

    if (res.status === "matched") {
      currentPersonId = res.matched_person.person_id;
      resolutionArea.innerHTML =
        '<p class="text-sm text-green-700">Matched: <strong>' +
        escapeHtml(res.matched_person.name) +
        "</strong></p>";
      confirmArea.classList.remove("hidden");
    } else if (res.status === "ambiguous") {
      resolutionArea.innerHTML =
        '<p class="text-sm text-yellow-700 mb-2">Multiple matches found. Pick one:</p>' +
        res.candidates
          .map(
            (c) =>
              '<button class="block w-full text-left text-sm bg-yellow-50 border border-yellow-200 rounded p-2 mb-1 hover:bg-yellow-100" data-person-id="' +
              escapeHtml(c.person_id) +
              '">' +
              escapeHtml(c.name) +
              (c.company ? " — " + escapeHtml(c.company) : "") +
              "</button>"
          )
          .join("");
      resolutionArea.querySelectorAll("[data-person-id]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          currentPersonId = this.dataset.personId;
          resolutionArea.innerHTML =
            '<p class="text-sm text-green-700">Selected: <strong>' +
            escapeHtml(this.textContent) +
            "</strong></p>";
          confirmArea.classList.remove("hidden");
        });
      });
    } else {
      resolutionArea.innerHTML =
        '<p class="text-sm text-gray-600 mb-2">Person not found. Create new?</p>' +
        '<form id="create-person-form" class="flex gap-2">' +
        '<input type="text" name="name" placeholder="Full name" value="' +
        escapeHtml(currentExtraction.person_name) +
        '" class="border border-gray-300 rounded px-2 py-1 text-sm flex-1" required>' +
        '<select name="relationship_type" class="border border-gray-300 rounded px-2 py-1 text-sm">' +
        '<option value="colleague">Colleague</option>' +
        '<option value="friend">Friend</option>' +
        '<option value="client">Client</option>' +
        '<option value="investor">Investor</option>' +
        '<option value="founder">Founder</option>' +
        '<option value="prospect">Prospect</option>' +
        '<option value="advisor">Advisor</option>' +
        '<option value="family">Family</option>' +
        '<option value="other">Other</option>' +
        "</select>" +
        '<button type="submit" class="bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700">Create</button>' +
        "</form>";

      document
        .getElementById("create-person-form")
        .addEventListener("submit", async function (e) {
          e.preventDefault();
          const formData = new FormData(this);
          try {
            const resp = await fetch("/people", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                name: formData.get("name"),
                relationship_type: formData.get("relationship_type"),
              }),
            });
            const person = await resp.json();
            if (resp.ok) {
              currentPersonId = person.person_id;
              resolutionArea.innerHTML =
                '<p class="text-sm text-green-700">Created: <strong>' +
                escapeHtml(person.name) +
                "</strong></p>";
              confirmArea.classList.remove("hidden");
            }
          } catch (err) {
            alert("Error creating person: " + err.message);
          }
        });
    }
  }

  confirmBtn.addEventListener("click", async function () {
    if (!currentPersonId || !currentExtraction) return;
    confirmSpinner.style.display = "inline-block";

    try {
      const resp = await fetch("/interactions/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          person_id: currentPersonId,
          extraction: currentExtraction,
        }),
      });
      if (resp.ok) {
        confirmArea.classList.add("hidden");
        saveSuccess.classList.remove("hidden");
        rawInput.value = "";
      } else {
        const data = await resp.json();
        alert("Error: " + (data.detail || "Save failed"));
      }
    } catch (err) {
      alert("Error: " + err.message);
    } finally {
      confirmSpinner.style.display = "none";
    }
  });

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }
});
