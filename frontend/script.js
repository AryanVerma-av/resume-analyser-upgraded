// Resume Analyzer UI Script

const SAMPLE_AMAZON_JD = `Amazon - Software Development Engineer I (SDE-I)
Basic Qualifications:
- Experience with at least one general-purpose programming language such as Java, Python, C++, C#, Go, Rust, or TypeScript
- Experience with data structure implementation, basic algorithm development, and/or object-oriented design principles
- Currently has, or in process of obtaining bachelor's degree in CS, Computer Engineering, or related STEM field
- Backend API development, database interaction (SQL/NoSQL), microservices architecture
Preferred Qualifications:
- Experience from previous technical internship(s) or demonstrated project experience
- Experience with cloud platforms (preferably AWS), database systems, version control (Git)
- Basic understanding of software development lifecycle (SDLC)
- Strong problem-solving and analytical skills`;

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("analyze-form");
  const jdInput = document.getElementById("job-description");
  const loadJdBtn = document.getElementById("load-sample-jd");
  const fileInput = document.getElementById("resume-files");
  const fileCountSpan = document.getElementById("selected-files-count");
  const submitBtn = document.getElementById("submit-btn");
  const statusSpinner = document.getElementById("status-spinner");

  const resultsArea = document.getElementById("results-area");
  const passedTableBody = document.getElementById("passed-table-body");
  const filteredTableBody = document.getElementById("filtered-table-body");
  const errorsSection = document.getElementById("errors-section");
  const errorsTableBody = document.getElementById("errors-table-body");

  const passedBadge = document.getElementById("passed-badge");
  const filteredBadge = document.getElementById("filtered-badge");
  const errorsBadge = document.getElementById("errors-badge");

  const modal = document.getElementById("candidate-modal");
  const modalClose = document.getElementById("modal-close");
  const modalCandidateName = document.getElementById("modal-candidate-name");
  const modalBody = document.getElementById("modal-body");

  // Load sample JD by default
  jdInput.value = SAMPLE_AMAZON_JD;

  loadJdBtn.addEventListener("click", () => {
    jdInput.value = SAMPLE_AMAZON_JD;
  });

  // File input change handler
  fileInput.addEventListener("change", () => {
    const count = fileInput.files.length;
    if (count === 0) {
      fileCountSpan.textContent = "No files selected";
    } else if (count === 1) {
      fileCountSpan.textContent = fileInput.files[0].name;
    } else {
      fileCountSpan.textContent = `${count} files selected for batch analysis`;
    }
  });

  // Modal close handlers
  modalClose.addEventListener("click", () => modal.classList.add("hidden"));
  window.addEventListener("click", (e) => {
    if (e.target === modal) modal.classList.add("hidden");
  });

  let currentCandidates = [];

  // Form submit handler
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    if (!fileInput.files || fileInput.files.length === 0) {
      alert("Please select at least one PDF or DOCX resume to analyze.");
      return;
    }

    if (!jdInput.value.trim()) {
      alert("Please provide a job description.");
      return;
    }

    const formData = new FormData(form);

    submitBtn.disabled = true;
    statusSpinner.classList.remove("hidden");
    statusSpinner.textContent = `Analyzing ${fileInput.files.length} resumes... please wait`;

    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server returned status ${response.status}`);
      }

      const data = await response.json();
      currentCandidates = data.candidates || [];
      renderResults(data);
    } catch (err) {
      alert(`Error during analysis: ${err.message}`);
    } finally {
      submitBtn.disabled = false;
      statusSpinner.classList.add("hidden");
    }
  });

  function renderResults(data) {
    resultsArea.classList.remove("hidden");

    passedBadge.textContent = `${data.passed_count} Candidates`;
    filteredBadge.textContent = `${data.filtered_count} Filtered`;
    errorsBadge.textContent = `${data.error_count} Errors`;

    // Clear previous rows
    passedTableBody.innerHTML = "";
    filteredTableBody.innerHTML = "";
    errorsTableBody.innerHTML = "";

    const passedCandidates = data.candidates.filter((c) => c.status === "passed");
    const filteredCandidates = data.candidates.filter((c) => c.status === "filtered");
    const errorCandidates = data.candidates.filter((c) => c.status === "error");

    // Populate Passed Table
    if (passedCandidates.length === 0) {
      passedTableBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No candidates met the requirements for ${data.target_role_display}.</td></tr>`;
    } else {
      passedCandidates.forEach((cand, idx) => {
        const tr = document.createElement("tr");
        const score = cand.match ? Math.round(cand.match.score) : 0;
        const verdict = cand.match ? cand.match.verdict || "Evaluated" : "Evaluated";

        tr.innerHTML = `
          <td><strong>${escapeHtml(cand.name || cand.filename)}</strong><br><small style="color:var(--text-muted)">${escapeHtml(cand.filename)}</small></td>
          <td><span class="badge badge-success">${escapeHtml(cand.screening.role_type || data.target_role)}</span></td>
          <td><span class="badge badge-success score-badge">${score}%</span></td>
          <td style="max-width: 380px;">${escapeHtml(verdict)}</td>
          <td><button type="button" class="btn-secondary" onclick="viewDetails(${idx})">View Details</button></td>
        `;
        passedTableBody.appendChild(tr);
      });
    }

    // Populate Filtered Table
    if (filteredCandidates.length === 0) {
      filteredTableBody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-muted);">No candidates were filtered.</td></tr>`;
    } else {
      filteredCandidates.forEach((cand) => {
        const tr = document.createElement("tr");
        const detected = cand.screening.role_type || "Unknown";

        tr.innerHTML = `
          <td><strong>${escapeHtml(cand.name || cand.filename)}</strong><br><small style="color:var(--text-muted)">${escapeHtml(cand.filename)}</small></td>
          <td><span class="badge badge-danger">${escapeHtml(detected)}</span></td>
          <td style="color: #f85149;">${escapeHtml(cand.screening.reason || "Did not meet criteria")}</td>
        `;
        filteredTableBody.appendChild(tr);
      });
    }

    // Populate Errors Table
    if (errorCandidates.length > 0) {
      errorsSection.classList.remove("hidden");
      errorCandidates.forEach((cand) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${escapeHtml(cand.filename)}</td>
          <td>${escapeHtml(cand.name || "Unknown")}</td>
          <td style="color: #f85149;">${escapeHtml(cand.error || cand.screening.reason || "Processing failed")}</td>
        `;
        errorsTableBody.appendChild(tr);
      });
    } else {
      errorsSection.classList.add("hidden");
    }

    // Scroll smoothly to results
    resultsArea.scrollIntoView({ behavior: "smooth" });
  }

  // Window function for detail modal
  window.viewDetails = function(passedIdx) {
    const passedList = currentCandidates.filter((c) => c.status === "passed");
    const cand = passedList[passedIdx];
    if (!cand) return;

    modalCandidateName.textContent = `Candidate: ${cand.name || cand.filename}`;

    const match = cand.match || {};
    const matchingSkills = match.matching_skills || [];
    const missingSkills = match.missing_skills || [];

    const matchingTags = matchingSkills.length > 0
      ? matchingSkills.map((s) => `<span class="skill-tag">${escapeHtml(s)}</span>`).join("")
      : "<em style='color:var(--text-muted)'>None recorded</em>";

    const missingTags = missingSkills.length > 0
      ? missingSkills.map((s) => `<span class="skill-tag missing">${escapeHtml(s)}</span>`).join("")
      : "<em style='color:var(--text-muted)'>None identified</em>";

    modalBody.innerHTML = `
      <div class="detail-block">
        <div class="detail-label">Role & Match Score</div>
        <p><strong>Role:</strong> ${escapeHtml(cand.screening.role_type || "N/A")}</p>
        <p><strong>Match Score:</strong> <span class="badge badge-success score-badge">${Math.round(match.score || 0)}%</span></p>
      </div>

      <div class="detail-block">
        <div class="detail-label">Matching Skills</div>
        <div class="skill-tags">${matchingTags}</div>
      </div>

      <div class="detail-block">
        <div class="detail-label">Missing Important Skills</div>
        <div class="skill-tags">${missingTags}</div>
      </div>

      <div class="detail-block">
        <div class="detail-label">Experience Requirement</div>
        <p>${match.experience_met ? "Requirement Met" : "Requirement Not Fully Met or Unspecified"}</p>
      </div>

      <div class="detail-block">
        <div class="detail-label">Verdict & Summary</div>
        <p style="line-height: 1.6; color: var(--text-primary);">${escapeHtml(match.verdict || "No detailed verdict available.")}</p>
      </div>
    `;

    modal.classList.remove("hidden");
  };

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});
