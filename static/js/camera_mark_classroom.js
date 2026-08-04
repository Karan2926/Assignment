// camera_mark_classroom.js — Phase 1: requires class_id + subject_id
const classroomPhotoInput = document.getElementById("classroomPhoto");
const analyzeBtn = document.getElementById("analyzeBtn");
const analyzeStatus = document.getElementById("analyzeStatus");
const resultCanvas = document.getElementById("resultCanvas");
const recognizedTableWrap = document.getElementById("recognizedTableWrap");
const recognizedTableBody = document.getElementById("recognizedTableBody");
const confirmBtn = document.getElementById("confirmBtn");
const confirmStatus = document.getElementById("confirmStatus");
const clearBtn = document.getElementById("clearBtn");
const classSelect = document.getElementById("classSelect");
const subjectSelect = document.getElementById("subjectSelect");

let capturedBlobs = [];
let cameraStream = null;
let detectedFaces = [];
let previewFaces = []; // faces from first photo (bboxes match preview canvas)
let previewImage = null;
let activeClassId = null;
let activeSubjectId = null;

const useCameraBtn = document.getElementById("useCameraBtn");
const cameraSection = document.getElementById("cameraSection");
const classroomVideo = document.getElementById("classroomVideo");
const captureBtn = document.getElementById("captureBtn");
const closeCameraBtn = document.getElementById("closeCameraBtn");
const captureCount = document.getElementById("captureCount");

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

classSelect?.addEventListener("change", () => loadSubjects(classSelect.value));

useCameraBtn.addEventListener("click", async () => {
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 } });
    classroomVideo.srcObject = cameraStream;
    await classroomVideo.play();
    cameraSection.style.display = "block";
  } catch (err) {
    alert("Camera error: " + err.message);
  }
});

closeCameraBtn.addEventListener("click", () => {
  if (cameraStream) cameraStream.getTracks().forEach(t => t.stop());
  cameraSection.style.display = "none";
});

captureBtn.addEventListener("click", async () => {
  const canvas = document.createElement("canvas");
  canvas.width = classroomVideo.videoWidth;
  canvas.height = classroomVideo.videoHeight;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(classroomVideo, 0, 0, canvas.width, canvas.height);

  const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", 0.9));
  capturedBlobs.push(blob);
  classroomPhotoInput.value = "";
  captureCount.innerText = `${capturedBlobs.length} photo(s) captured`;
  analyzeStatus.innerText = `${capturedBlobs.length} photo(s) ready. Capture more or click "Analyze Photo".`;
});

clearBtn.addEventListener("click", () => {
  capturedBlobs = [];
  classroomPhotoInput.value = "";
  captureCount.innerText = "";
  detectedFaces = [];
  previewFaces = [];
  previewImage = null;
  activeClassId = null;
  activeSubjectId = null;

  analyzeStatus.innerText = "Cleared. Ready for a new batch.";
  recognizedTableWrap.style.display = "none";
  confirmStatus.innerText = "";
  const summaryCard = document.getElementById("summaryCard");
  if (summaryCard) summaryCard.style.display = "none";

  const ctx = resultCanvas.getContext("2d");
  ctx.clearRect(0, 0, resultCanvas.width, resultCanvas.height);
  resultCanvas.width = 0;
  resultCanvas.height = 0;
});

analyzeBtn.addEventListener("click", async () => {
  if (!classSelect.value || !subjectSelect.value) {
    alert("Select class and subject before analyzing.");
    return;
  }

  const files = capturedBlobs.length > 0
    ? capturedBlobs
    : Array.from(classroomPhotoInput.files);

  if (files.length === 0) {
    alert("Please choose photo(s) or capture with the camera first.");
    return;
  }

  activeClassId = classSelect.value;
  activeSubjectId = subjectSelect.value;

  if (cameraStream) cameraStream.getTracks().forEach(t => t.stop());
  cameraSection.style.display = "none";

  analyzeStatus.innerText = `Analyzing ${files.length} photo(s)... this may take a moment.`;
  recognizedTableWrap.style.display = "none";
  confirmStatus.innerText = "";

  previewImage = new Image();
  previewImage.src = URL.createObjectURL(files[0]);
  await new Promise(resolve => { previewImage.onload = resolve; });

  const mergedByStudent = new Map();
  const unknownFaces = [];
  let anyError = null;
  previewFaces = [];

  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    const fd = new FormData();
    fd.append("image", file, "photo.jpg");
    fd.append("class_id", activeClassId);
    fd.append("subject_id", activeSubjectId);

    try {
      const res = await fetch("/recognize_classroom", { method: "POST", body: fd });
      const data = await res.json();

      if (data.error) { anyError = data.error; continue; }

      const faces = data.faces || [];
      // First photo drives the boxed preview (bbox coords match that image)
      if (i === 0) {
        previewFaces = faces;
      }

      faces.forEach(face => {
        if (face.recognized) {
          const existing = mergedByStudent.get(face.student_id);
          if (!existing || face.confidence > existing.confidence) {
            mergedByStudent.set(face.student_id, face);
          }
        } else {
          unknownFaces.push(face);
        }
      });
    } catch (err) {
      console.error(err);
      anyError = "Network error while analyzing a photo.";
    }
  }

  detectedFaces = [...mergedByStudent.values(), ...unknownFaces];

  if (detectedFaces.length === 0) {
    analyzeStatus.innerText = anyError ? `Error: ${anyError}` : "No faces detected across the photo(s).";
    return;
  }

  analyzeStatus.innerText = `Found ${detectedFaces.length} unique face(s) across ${files.length} photo(s).` + (anyError ? ` (one photo had an issue: ${anyError})` : "");
  drawPreview();
  buildTable();
  recognizedTableWrap.style.display = "block";
});

function faceBoxStyle(face) {
  if (!face.recognized) {
    return { color: "#64748B", label: "Unknown" };
  }
  const review = reviewInfo(face);
  if (face.already_marked) {
    return { color: "#64748B", label: face.name || "Matched" };
  }
  if (review.needsReview) {
    return { color: "#D97706", label: face.name || "Matched" };
  }
  return { color: "#0D9488", label: face.name || "Matched" };
}

function drawFaceBox(ctx, face) {
  const bbox = face.bbox;
  if (!bbox || bbox.length < 4) return;

  const x1 = bbox[0];
  const y1 = bbox[1];
  const x2 = bbox[2];
  const y2 = bbox[3];
  const w = x2 - x1;
  const h = y2 - y1;
  if (w < 2 || h < 2) return;

  const { color, label } = faceBoxStyle(face);
  const lineW = Math.max(2, Math.min(4, Math.round(Math.min(w, h) * 0.02)));

  ctx.strokeStyle = color;
  ctx.lineWidth = lineW;
  ctx.strokeRect(x1, y1, w, h);

  ctx.font = "bold 14px sans-serif";
  const padX = 6;
  const padY = 4;
  const textW = ctx.measureText(label).width;
  const boxH = 22;
  let labelY = y1 - boxH - 2;
  if (labelY < 0) labelY = y1 + 2;

  ctx.fillStyle = color;
  ctx.fillRect(x1, labelY, textW + padX * 2, boxH);
  ctx.fillStyle = "#fff";
  ctx.fillText(label, x1 + padX, labelY + boxH - padY - 2);
}

function drawPreview() {
  resultCanvas.width = previewImage.width;
  resultCanvas.height = previewImage.height;
  const ctx = resultCanvas.getContext("2d");
  ctx.drawImage(previewImage, 0, 0);

  previewFaces.forEach((face) => drawFaceBox(ctx, face));

  const boxed = previewFaces.filter((f) => f.bbox && f.bbox.length >= 4).length;
  ctx.fillStyle = "rgba(16,24,40,0.75)";
  ctx.fillRect(10, 10, 380, 30);
  ctx.fillStyle = "#fff";
  ctx.font = "14px sans-serif";
  ctx.fillText(
    `Preview (first photo) — ${boxed} face box(es)`,
    18,
    30
  );
}

/** Label strength for teachers (does not hide matches). */
const STRONG_MATCH = 0.32;

function reviewInfo(face) {
  if (!face.recognized) {
    return { label: "Unknown — skip", needsReview: true };
  }
  if (face.already_marked) {
    return { label: "Already marked", needsReview: false };
  }
  // Prefer server flag; fall back to local threshold
  const weak =
    face.needs_review === true ||
    (typeof face.needs_review === "undefined" && (face.confidence || 0) < STRONG_MATCH);
  if (weak) {
    return { label: "Needs review", needsReview: true };
  }
  return { label: "Auto-OK", needsReview: false };
}

function buildTable() {
  recognizedTableBody.innerHTML = "";
  let reviewCount = 0;

  detectedFaces.forEach((face) => {
    const review = reviewInfo(face);
    if (review.needsReview && face.recognized && !face.already_marked) {
      reviewCount += 1;
    }

    const tr = document.createElement("tr");
    if (review.label === "Needs review") {
      tr.style.background = "rgba(245, 158, 11, 0.08)";
    }

    const checkTd = document.createElement("td");
    if (face.recognized) {
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      // Always show recognized students as selected (unless already marked)
      // Review column warns about weak matches; teacher can uncheck if wrong
      checkbox.checked = !face.already_marked;
      checkbox.dataset.studentId = face.student_id;
      checkTd.appendChild(checkbox);
    }
    tr.appendChild(checkTd);

    const nameTd = document.createElement("td");
    nameTd.innerText = face.recognized
      ? `${face.name} (Roll: ${face.roll || "-"})`
      : "Unknown";
    tr.appendChild(nameTd);

    const reviewTd = document.createElement("td");
    reviewTd.innerText = review.label;
    if (review.label === "Needs review") {
      reviewTd.style.fontWeight = "600";
      reviewTd.style.color = "var(--amber, #B45309)";
    } else if (review.label === "Auto-OK") {
      reviewTd.style.color = "var(--teal, #0F766E)";
    }
    tr.appendChild(reviewTd);

    const statusTd = document.createElement("td");
    if (!face.recognized) {
      statusTd.innerText = "Not matched";
    } else if (face.already_marked) {
      statusTd.innerText = "Already marked today";
    } else if (review.needsReview) {
      statusTd.innerText = "Selected — double-check name";
    } else {
      statusTd.innerText = "Ready to save";
    }
    tr.appendChild(statusTd);

    recognizedTableBody.appendChild(tr);
  });

  if (reviewCount > 0) {
    analyzeStatus.innerText += ` ${reviewCount} weaker match(es) highlighted — uncheck any wrong name before saving.`;
  }
}

confirmBtn.addEventListener("click", async () => {
  const checkboxes = recognizedTableBody.querySelectorAll('input[type="checkbox"]:checked');
  const studentIds = Array.from(checkboxes).map(cb => parseInt(cb.dataset.studentId));

  const totalFaces = detectedFaces.length;
  const unknownCount = detectedFaces.filter(f => !f.recognized).length;
  const alreadyMarkedCount = detectedFaces.filter(f => f.recognized && f.already_marked).length;

  if (studentIds.length === 0) {
    confirmStatus.innerText = "No students selected to save.";
    return;
  }
  if (!activeClassId || !activeSubjectId) {
    confirmStatus.innerText = "Missing class/subject — analyze again.";
    return;
  }

  confirmStatus.innerText = "Saving...";
  const summaryCard = document.getElementById("summaryCard");
  if (summaryCard) summaryCard.style.display = "none";

  try {
    const res = await fetch("/confirm_classroom_attendance", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        student_ids: studentIds,
        class_id: parseInt(activeClassId),
        subject_id: parseInt(activeSubjectId),
      })
    });
    const data = await res.json();
    confirmStatus.innerText = "";

    if (summaryCard) {
      summaryCard.innerHTML = `
        <div class="card2" style="background:#F7F7F5; border-color:var(--line);">
          <span class="eyebrow">Result</span>
          <div style="display:flex; gap:1.5rem; flex-wrap:wrap; margin-top:0.5rem;">
            <div>
              <div style="font-family:var(--font-display); font-size:1.6rem; font-weight:700; color:var(--teal);">${data.saved}</div>
              <div class="mono" style="font-size:0.75rem; color:var(--ink-soft);">Marked present</div>
            </div>
            <div>
              <div style="font-family:var(--font-display); font-size:1.6rem; font-weight:700; color:var(--indigo);">${alreadyMarkedCount}</div>
              <div class="mono" style="font-size:0.75rem; color:var(--ink-soft);">Already marked today</div>
            </div>
            <div>
              <div style="font-family:var(--font-display); font-size:1.6rem; font-weight:700; color:var(--amber);">${unknownCount}</div>
              <div class="mono" style="font-size:0.75rem; color:var(--ink-soft);">Unknown faces</div>
            </div>
            <div>
              <div style="font-family:var(--font-display); font-size:1.6rem; font-weight:700;">${totalFaces}</div>
              <div class="mono" style="font-size:0.75rem; color:var(--ink-soft);">Total faces found</div>
            </div>
          </div>
        </div>
      `;
      summaryCard.style.display = "block";
    }

    capturedBlobs = [];
    if (captureCount) captureCount.innerText = "";
  } catch (err) {
    console.error(err);
    confirmStatus.innerText = "Error saving attendance.";
  }
});
