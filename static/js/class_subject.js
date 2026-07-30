// Shared class → subject cascading selects for records/analytics filters
async function wireClassSubjectFilters(classSelectId, subjectSelectId, selectedSubjectId) {
  const classSelect = document.getElementById(classSelectId);
  const subjectSelect = document.getElementById(subjectSelectId);
  if (!classSelect || !subjectSelect) return;

  async function loadSubjects(classId, preferred) {
    subjectSelect.innerHTML = '<option value="">All subjects</option>';
    if (!classId) return;
    const res = await fetch(`/api/classes/${classId}/subjects`);
    const data = await res.json();
    (data.subjects || []).forEach(s => {
      const opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = s.code ? `${s.name} (${s.code})` : s.name;
      if (preferred && String(preferred) === String(s.id)) opt.selected = true;
      subjectSelect.appendChild(opt);
    });
  }

  classSelect.addEventListener("change", () => loadSubjects(classSelect.value, null));
  if (classSelect.value) loadSubjects(classSelect.value, selectedSubjectId);
}
