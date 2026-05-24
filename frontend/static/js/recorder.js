document.addEventListener("DOMContentLoaded", function () {
  const recordBtn = document.getElementById("record-btn");
  const recordIcon = document.getElementById("record-icon");
  const recordLabel = document.getElementById("record-label");
  const rawInput = document.getElementById("raw-input");

  if (!recordBtn) return;

  let mediaRecorder = null;
  let audioChunks = [];
  let isRecording = false;

  recordBtn.addEventListener("click", async function () {
    if (isRecording) {
      stopRecording();
    } else {
      await startRecording();
    }
  });

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      audioChunks = [];

      mediaRecorder.ondataavailable = function (e) {
        if (e.data.size > 0) audioChunks.push(e.data);
      };

      mediaRecorder.onstop = async function () {
        stream.getTracks().forEach(function (t) { t.stop(); });
        const blob = new Blob(audioChunks, { type: "audio/webm" });
        await uploadAudio(blob);
      };

      mediaRecorder.start();
      isRecording = true;
      recordIcon.textContent = "⏹";
      recordLabel.textContent = "Stop";
      recordBtn.classList.add("bg-red-100", "text-red-700");
      recordBtn.classList.remove("bg-gray-100", "text-gray-700");
    } catch (err) {
      alert("Microphone access denied or not available.");
    }
  }

  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();
    }
    isRecording = false;
    recordIcon.textContent = "🎤";
    recordLabel.textContent = "Record";
    recordBtn.classList.remove("bg-red-100", "text-red-700");
    recordBtn.classList.add("bg-gray-100", "text-gray-700");
  }

  async function uploadAudio(blob) {
    recordLabel.textContent = "Uploading...";
    const formData = new FormData();
    formData.append("file", blob, "recording.webm");

    try {
      const resp = await fetch("/interactions/audio", {
        method: "POST",
        body: formData,
      });
      const data = await resp.json();
      if (resp.ok) {
        rawInput.value = data.extraction.summary;
        document.getElementById("capture-form").dispatchEvent(
          new Event("submit", { cancelable: true })
        );
        // Re-use the text flow to show results by triggering extraction display
        if (window.showResult) window.showResult(data);
      } else {
        alert("Error: " + (data.detail || "Upload failed"));
      }
    } catch (err) {
      alert("Upload error: " + err.message);
    } finally {
      recordLabel.textContent = "Record";
    }
  }
});
