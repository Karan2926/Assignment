// camera_mark.js — Phase 1: requires class_id + subject_id
const startMarkBtn = document.getElementById("startMarkBtn");
const stopMarkBtn = document.getElementById("stopMarkBtn");
const markVideo = document.getElementById("markVideo");
const markStatus = document.getElementById("markStatus");
const recognizedList = document.getElementById("recognizedList");
const classSelect = document.getElementById("classSelect");
const subjectSelect = document.getElementById("subjectSelect");

let markStream = null;
let markInterval = null;
let recognizedIds = new Set();

async function loadSubjects(classId) {
  subjectSelect.innerHTML = '<option value="">Select subject</option>';
  if (!classId) return;
  const res = await fetch(`/api/classes/${classId}/subjects`);
  const data = await res.json();
  (data.subjects || []).forEach(s => {
    const opt = document.createElement("option");
    opt.value = s.id;
    opt.textContent = s.code ? `${s.name} (${s.code})` : s.name;
    subjectSelect.appendChild(opt);
  });
}

classSelect?.addEventListener("change", () => {
  loadSubjects(classSelect.value);
  recognizedIds.clear();
  recognizedList.innerHTML = "";
});

startMarkBtn.addEventListener("click", async () => {
  if (!classSelect.value || !subjectSelect.value) {
    alert("Select class and subject before starting.");
    return;
  }
  startMarkBtn.disabled = true;
  stopMarkBtn.disabled = false;
  classSelect.disabled = true;
  subjectSelect.disabled = true;
  try {
    markStream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
    markVideo.srcObject = markStream;
    await markVideo.play();
    markStatus.innerText = "Scanning...";
    markInterval = setInterval(captureAndRecognize, 1200);
  } catch (err) {
    alert("Camera error: " + err.message);
    startMarkBtn.disabled = false;
    stopMarkBtn.disabled = true;
    classSelect.disabled = false;
    subjectSelect.disabled = false;
  }
});

stopMarkBtn.addEventListener("click", () => {
  if (markInterval) clearInterval(markInterval);
  if (markStream) markStream.getTracks().forEach(t => t.stop());
  startMarkBtn.disabled = false;
  stopMarkBtn.disabled = true;
  classSelect.disabled = false;
  subjectSelect.disabled = false;
  markStatus.innerText = "Stopped";
});

async function captureAndRecognize() {
  const canvas = document.createElement("canvas");
  canvas.width = markVideo.videoWidth || 640;
  canvas.height = markVideo.videoHeight || 480;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(markVideo, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise(r => canvas.toBlob(r, "image/jpeg", 0.85));
  const fd = new FormData();
  fd.append("image", blob, "snap.jpg");
  fd.append("class_id", classSelect.value);
  fd.append("subject_id", subjectSelect.value);
  try {
    const res = await fetch("/recognize_face", { method: "POST", body: fd });
    const j = await res.json();
    if (j.recognized) {
      const note = j.already_marked ? "already marked" : "saved";
      markStatus.innerText = `Recognized: ${j.name} (conf ${Math.round(j.confidence * 100)}%) — ${note}`;
      if (!recognizedIds.has(j.student_id)) {
        recognizedIds.add(j.student_id);
        const li = document.createElement("li");
        li.style.cssText = "padding:0.7rem 0.85rem;border:1px solid var(--line);border-radius:10px;background:rgba(255,255,255,0.75);";
        li.innerText = `${j.name} — ${new Date().toLocaleTimeString()}`;
        recognizedList.prepend(li);
      }
    } else {
      if (j.error) markStatus.innerText = `Not recognized: ${j.error}`;
      else markStatus.innerText = `Not recognized`;
    }
  } catch (err) {
    console.error(err);
  }
}
