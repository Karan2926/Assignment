// camera_mark.js — Phase 1: requires class_id + subject_id
const startMarkBtn = document.getElementById("startMarkBtn");
const stopMarkBtn = document.getElementById("stopMarkBtn");
const markVideo = document.getElementById("markVideo");
const markOverlay = document.getElementById("markOverlay");
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
  clearOverlay();
});

function clearOverlay() {
  if (!markOverlay) return;
  const ctx = markOverlay.getContext("2d");
  ctx.clearRect(0, 0, markOverlay.width, markOverlay.height);
}

/** Map image-pixel bbox onto overlay for object-fit: cover video. */
function mapBboxCover(bbox, srcW, srcH, destW, destH) {
  const scale = Math.max(destW / srcW, destH / srcH);
  const drawnW = srcW * scale;
  const drawnH = srcH * scale;
  const offX = (destW - drawnW) / 2;
  const offY = (destH - drawnH) / 2;
  return [
    bbox[0] * scale + offX,
    bbox[1] * scale + offY,
    bbox[2] * scale + offX,
    bbox[3] * scale + offY,
  ];
}

function drawLiveBox(result) {
  if (!markOverlay || !markVideo) return;

  const destW = markVideo.clientWidth || markOverlay.clientWidth;
  const destH = markVideo.clientHeight || markOverlay.clientHeight;
  if (!destW || !destH) return;

  if (markOverlay.width !== destW || markOverlay.height !== destH) {
    markOverlay.width = destW;
    markOverlay.height = destH;
  }

  const ctx = markOverlay.getContext("2d");
  ctx.clearRect(0, 0, destW, destH);

  const bbox = result && result.bbox;
  if (!bbox || bbox.length < 4) return;

  const srcW = result.image_width || markVideo.videoWidth || 640;
  const srcH = result.image_height || markVideo.videoHeight || 480;
  const [x1, y1, x2, y2] = mapBboxCover(bbox, srcW, srcH, destW, destH);
  const w = x2 - x1;
  const h = y2 - y1;
  if (w < 2 || h < 2) return;

  let color = "#94A3B8";
  let label = result.label || "Unknown";
  if (result.recognized) {
    color = result.already_marked ? "#64748B" : "#0D9488";
    label = result.name || label;
  } else if (result.error === "no face detected") {
    return;
  } else {
    label = "Unknown";
  }

  ctx.strokeStyle = color;
  ctx.lineWidth = 3;
  ctx.strokeRect(x1, y1, w, h);

  ctx.font = "bold 14px sans-serif";
  const padX = 6;
  const boxH = 22;
  const textW = ctx.measureText(label).width;
  let labelY = y1 - boxH - 2;
  if (labelY < 0) labelY = y1 + 2;
  ctx.fillStyle = color;
  ctx.fillRect(x1, labelY, textW + padX * 2, boxH);
  ctx.fillStyle = "#fff";
  ctx.fillText(label, x1 + padX, labelY + boxH - 6);
}

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
    clearOverlay();
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
  clearOverlay();
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
    drawLiveBox(j);
    if (j.recognized) {
      const note = j.already_marked ? "already marked today" : "attendance saved";
      // No raw confidence % — clearer teacher-facing status
      markStatus.innerText = `Matched: ${j.name} — ${note}`;
      if (!recognizedIds.has(j.student_id)) {
        recognizedIds.add(j.student_id);
        const li = document.createElement("li");
        li.style.cssText = "padding:0.7rem 0.85rem;border:1px solid var(--line);border-radius:10px;background:rgba(255,255,255,0.75);";
        li.innerText = `${j.name} — ${new Date().toLocaleTimeString()}`;
        recognizedList.prepend(li);
      }
    } else {
      if (j.error) markStatus.innerText = `Not recognized: ${j.error}`;
      else markStatus.innerText = `Not recognized — ask student to face the camera`;
      if (j.error === "no face detected") clearOverlay();
    }
  } catch (err) {
    console.error(err);
  }
}
