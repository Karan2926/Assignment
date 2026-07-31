// camera_add_student.js
const saveInfoBtn = document.getElementById("saveInfoBtn");
const startCaptureBtn = document.getElementById("startCaptureBtn");
const addStudentBtn = document.getElementById("addStudentBtn");
const video = document.getElementById("video");
const captureStatus = document.getElementById("captureStatus");
const progressBar = document.getElementById("progressBar");
const poseInstruction = document.getElementById("poseInstruction");

let student_id = null;
let images = [];
let stream = null;

const POSES = [
  ["Look straight at the camera", 8],
  ["Turn your head slightly LEFT", 8],
  ["Turn your head slightly RIGHT", 8],
  ["Tilt your chin up a little", 8],
  ["Tilt your chin down a little", 8],
  ["Smile naturally", 8],
];
const maxImages = POSES.reduce((sum, p) => sum + p[1], 0);

document.getElementById("studentForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const res = await fetch("/add_student", { method: "POST", body: fd });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    alert(err.error || "Failed to save student info");
    return;
  }
  const j = await res.json();
  student_id = j.student_id;
  alert("Student info saved. Click Start Capture to open the camera.");
  startCaptureBtn.disabled = false;
});

startCaptureBtn.addEventListener("click", async () => {
  startCaptureBtn.disabled = true;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
    video.srcObject = stream;
    await video.play();
    runGuidedCapture();
  } catch (err) {
    alert("Camera access error: " + err.message);
    startCaptureBtn.disabled = false;
  }
});

function setFrameColor(ok) {
  const corners = document.querySelectorAll(".scan-corners span");
  corners.forEach(c => { c.style.borderColor = ok ? "#0EA5A4" : "#EF4444"; });
}

async function captureOneFrame(canvas, ctx) {
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  return await new Promise(res => canvas.toBlob(res, "image/jpeg", 0.9));
}

async function checkFrameQuality(blob) {
  const fd = new FormData();
  fd.append("image", blob, "check.jpg");
  try {
    const res = await fetch("/check_face", { method: "POST", body: fd });
    return await res.json();
  } catch (err) {
    return { ok: false, reason: "network error" };
  }
}

async function runGuidedCapture() {
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth || 640;
  canvas.height = video.videoHeight || 480;
  const ctx = canvas.getContext("2d");

  let totalCaptured = 0;

  for (const [instruction, count] of POSES) {
    poseInstruction.innerText = instruction;
    await new Promise(r => setTimeout(r, 1200));

    let capturedForPose = 0;
    let attempts = 0;
    const maxAttempts = count * 4;

    while (capturedForPose < count && attempts < maxAttempts) {
      attempts++;
      const blob = await captureOneFrame(canvas, ctx);
      const quality = await checkFrameQuality(blob);

      if (quality.ok) {
        images.push(blob);
        capturedForPose++;
        totalCaptured++;
        setFrameColor(true);
        captureStatus.innerText = `Captured ${totalCaptured} / ${maxImages}`;
        progressBar.style.width = `${(totalCaptured / maxImages) * 100}%`;
      } else {
        setFrameColor(false);
        captureStatus.innerText = `${quality.reason || "Adjust position"}... (${totalCaptured} / ${maxImages})`;
      }
      await new Promise(r => setTimeout(r, 350));
    }
  }

  poseInstruction.innerText = "Done!";
  setFrameColor(true);

  const form = new FormData();
  form.append("student_id", student_id);
  images.forEach((b, i) => form.append("images[]", b, `img_${i}.jpg`));
  const resp = await fetch("/upload_face", { method: "POST", body: form });
  if (resp.ok) {
    alert(`Captured and uploaded ${images.length} quality photos across multiple angles.`);
    addStudentBtn.disabled = false;
  } else {
    alert("Upload failed");
  }

  if (stream) stream.getTracks().forEach(t => t.stop());
}

addStudentBtn.addEventListener("click", () => {
  alert("Student record complete. Returning to dashboard.");
  window.location.href = "/";
});
