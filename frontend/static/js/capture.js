document.addEventListener("DOMContentLoaded", function () {
  var form = document.getElementById("capture-form");
  var rawInput = document.getElementById("raw-input");
  var resultDiv = document.getElementById("extraction-result");
  var extractBtn = document.getElementById("extract-btn");
  var extractBtnText = document.getElementById("extract-btn-text");
  var extractSpinner = document.getElementById("extract-spinner");
  var confirmArea = document.getElementById("confirm-area");
  var confirmBtn = document.getElementById("confirm-btn");
  var confirmBtnText = document.getElementById("confirm-btn-text");
  var confirmSpinner = document.getElementById("confirm-spinner");
  var saveSuccess = document.getElementById("save-success");
  var resolutionArea = document.getElementById("resolution-area");

  var currentExtraction = null;
  var currentPersonId = null;
  var currentPersonName = null;

  document.getElementById("dismiss-btn").addEventListener("click", function () {
    resultDiv.classList.add("hidden");
    confirmArea.classList.add("hidden");
    saveSuccess.classList.add("hidden");
    currentExtraction = null;
    currentPersonId = null;
    currentPersonName = null;
  });

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    var text = rawInput.value.trim();
    if (!text) return;

    extractBtn.disabled = true;
    extractBtnText.textContent = "Extracting...";
    extractSpinner.classList.remove("hidden");
    resultDiv.classList.add("hidden");
    saveSuccess.classList.add("hidden");

    try {
      var resp = await fetch("/interactions/text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_input: text }),
      });
      var data = await resp.json();
      if (!resp.ok) {
        showToast("Error: " + (data.detail || "Unknown error"), "error");
        return;
      }
      showResult(data);
    } catch (err) {
      showToast("Network error: " + err.message, "error");
    } finally {
      extractBtn.disabled = false;
      extractBtnText.textContent = "Extract";
      extractSpinner.classList.add("hidden");
    }
  });

  function showResult(data) {
    currentExtraction = data.extraction;
    var res = data.person_resolution;

    document.getElementById("result-person").textContent =
      data.extraction.person_name;
    document.getElementById("result-type").textContent =
      data.extraction.interaction_type;
    document.getElementById("result-summary").textContent =
      data.extraction.summary;

    var factsDiv = document.getElementById("result-facts");
    if (data.extraction.facts.length > 0) {
      factsDiv.innerHTML =
        '<span class="text-gray-500 dark:text-gray-400">Facts:</span>' +
        '<ul class="list-disc list-inside mt-1">' +
        data.extraction.facts
          .map(function (f) {
            return (
              '<li><span class="text-gray-400 dark:text-gray-500">[' +
              escapeHtml(f.category) +
              "]</span> " +
              escapeHtml(f.content) +
              "</li>"
            );
          })
          .join("") +
        "</ul>";
    } else {
      factsDiv.innerHTML = "";
    }

    var tagsDiv = document.getElementById("result-tags");
    if (data.extraction.tags_added.length > 0) {
      tagsDiv.innerHTML =
        '<span class="text-gray-500 dark:text-gray-400">Tags:</span> ' +
        data.extraction.tags_added
          .map(function (t) {
            return (
              '<span class="bg-blue-50 dark:bg-blue-900 text-blue-700 dark:text-blue-300 text-xs px-2 py-0.5 rounded mr-1">' +
              escapeHtml(t) +
              "</span>"
            );
          })
          .join("");
    } else {
      tagsDiv.innerHTML = "";
    }

    var loopsDiv = document.getElementById("result-loops");
    if (data.extraction.loops.length > 0) {
      loopsDiv.innerHTML =
        '<span class="text-gray-500 dark:text-gray-400">Loops:</span>' +
        '<ul class="list-disc list-inside mt-1">' +
        data.extraction.loops
          .map(function (l) {
            return (
              "<li>" +
              escapeHtml(l.description) +
              (l.due_date
                ? ' <span class="text-gray-400 dark:text-gray-500">(due: ' +
                  escapeHtml(l.due_date) +
                  ")</span>"
                : "") +
              "</li>"
            );
          })
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
    saveSuccess.classList.add("hidden");
    currentPersonId = null;
    currentPersonName = null;

    if (res.status === "matched") {
      currentPersonId = res.matched_person.person_id;
      currentPersonName = res.matched_person.name;
      resolutionArea.innerHTML =
        '<p class="text-sm text-green-700 dark:text-green-400">Matched: <strong>' +
        escapeHtml(res.matched_person.name) +
        "</strong></p>";
      confirmArea.classList.remove("hidden");
    } else if (res.status === "ambiguous") {
      resolutionArea.innerHTML =
        '<p class="text-sm text-yellow-700 dark:text-yellow-400 mb-2">Multiple matches found. Pick one:</p>' +
        res.candidates
          .map(function (c) {
            return (
              '<button class="block w-full text-left text-sm bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-700 text-gray-900 dark:text-gray-100 rounded-lg p-2.5 mb-1 hover:bg-yellow-100 dark:hover:bg-yellow-900/50" data-person-id="' +
              escapeHtml(c.person_id) +
              '" data-person-name="' +
              escapeHtml(c.name) +
              '">' +
              escapeHtml(c.name) +
              (c.company
                ? ' <span class="text-gray-500 dark:text-gray-400">— ' +
                  escapeHtml(c.company) +
                  "</span>"
                : "") +
              "</button>"
            );
          })
          .join("");
      resolutionArea
        .querySelectorAll("[data-person-id]")
        .forEach(function (btn) {
          btn.addEventListener("click", function () {
            currentPersonId = this.dataset.personId;
            currentPersonName = this.dataset.personName;
            resolutionArea.innerHTML =
              '<p class="text-sm text-green-700 dark:text-green-400">Selected: <strong>' +
              escapeHtml(currentPersonName) +
              "</strong></p>";
            confirmArea.classList.remove("hidden");
          });
        });
    } else {
      resolutionArea.innerHTML =
        '<p class="text-sm text-gray-600 dark:text-gray-400 mb-2">Person not found. Create new?</p>' +
        '<form id="create-person-form" class="flex gap-2">' +
        '<input type="text" name="name" placeholder="Full name" value="' +
        escapeHtml(currentExtraction.person_name) +
        '" class="border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 rounded-lg px-2.5 py-1.5 text-sm flex-1" required>' +
        '<select name="relationship_type" class="border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 rounded-lg px-2.5 py-1.5 text-sm">' +
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
        '<button type="submit" class="bg-blue-600 text-white px-3 py-1.5 rounded-lg text-sm hover:bg-blue-700">Create</button>' +
        "</form>";

      document
        .getElementById("create-person-form")
        .addEventListener("submit", async function (e) {
          e.preventDefault();
          var formData = new FormData(this);
          try {
            var resp = await fetch("/people", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                name: formData.get("name"),
                relationship_type: formData.get("relationship_type"),
              }),
            });
            var person = await resp.json();
            if (resp.ok) {
              currentPersonId = person.person_id;
              currentPersonName = person.name;
              resolutionArea.innerHTML =
                '<p class="text-sm text-green-700 dark:text-green-400">Created: <strong>' +
                escapeHtml(person.name) +
                "</strong></p>";
              confirmArea.classList.remove("hidden");
            }
          } catch (err) {
            showToast("Error creating person: " + err.message, "error");
          }
        });
    }
  }

  confirmBtn.addEventListener("click", async function () {
    if (!currentPersonId || !currentExtraction) return;
    confirmBtn.disabled = true;
    confirmBtnText.textContent = "Saving...";
    confirmSpinner.classList.remove("hidden");

    try {
      var resp = await fetch("/interactions/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          person_id: currentPersonId,
          extraction: currentExtraction,
        }),
      });
      if (resp.ok) {
        confirmArea.classList.add("hidden");
        var link = document.getElementById("save-success-link");
        link.href = "/app/people/" + currentPersonId;
        link.textContent = "View " + currentPersonName + " →";
        saveSuccess.classList.remove("hidden");
        rawInput.value = "";
        rawInput.style.height = "auto";
        showToast("Interaction saved", "success");
      } else {
        var data = await resp.json();
        showToast("Error: " + (data.detail || "Save failed"), "error");
      }
    } catch (err) {
      showToast("Error: " + err.message, "error");
    } finally {
      confirmBtn.disabled = false;
      confirmBtnText.textContent = "Save";
      confirmSpinner.classList.add("hidden");
    }
  });

  function escapeHtml(text) {
    var div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }
});
