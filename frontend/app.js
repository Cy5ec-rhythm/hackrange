// This file talks to the backend API and builds the lab cards on the page.
// If you're new to JS: this runs entirely in the browser, after the page loads.

const BACKEND_URL = "http://localhost:5000";

async function loadLabs() {
  const container = document.getElementById("lab-list");

  try {
    const res = await fetch(`${BACKEND_URL}/api/labs`, {
      credentials: "include", // sends the session cookie so progress is remembered
    });
    const labs = await res.json();

    container.innerHTML = ""; // clear "Loading labs..." message

    labs.forEach((lab) => {
      container.appendChild(buildLabCard(lab));
    });
  } catch (err) {
    container.innerHTML = `<p style="color:#ff7b72">
      Could not reach the backend at ${BACKEND_URL}. Is it running?
    </p>`;
    console.error(err);
  }
}

function getCookie(name) {
  const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
  return match ? match[2] : null;
}

function setCookie(name, value, days) {
  const expires = new Date(Date.now() + days * 24 * 60 * 60 * 1000).toUTCString();
  document.cookie = `${name}=${value}; expires=${expires}; path=/; SameSite=Lax`;
}

function getSessionId() {
  // Two storage locations, since either one can independently get wiped
  // (browser cleanup, private windows, extensions, etc.) — if one is
  // gone, we recover from the other instead of silently starting over.
  let sid = localStorage.getItem("lab_session_id") || getCookie("lab_session_id");

  if (!sid) {
    sid = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2);
  }

  // Keep both in sync every time, so either one being cleared later can
  // still be restored from the other.
  localStorage.setItem("lab_session_id", sid);
  setCookie("lab_session_id", sid, 365);

  return sid;
}

function buildLabCard(lab) {
  const card = document.createElement("div");
  card.className = "lab-card";

  card.innerHTML = `
    <div class="top-row">
      <h2>${lab.title}</h2>
      <span class="tag ${lab.solved ? "solved" : ""}">
        ${lab.solved ? "Solved" : lab.difficulty}
      </span>
    </div>
    <p class="desc">${lab.description}</p>
    <div class="lab-actions">
      <button class="launch" data-lab-id="${lab.id}">Launch lab</button>
      <button class="stop" data-lab-id="${lab.id}" style="display:none">Stop lab</button>
      <input type="text" placeholder="Paste flag here" data-lab-id="${lab.id}">
      <button class="submit-flag" data-lab-id="${lab.id}">Submit</button>
    </div>
    <div class="flag-result" data-result-for="${lab.id}"></div>
    <div class="hints-section">
      <button class="hint-btn" data-lab-id="${lab.id}">Show hint (1/${lab.hints.length})</button>
      <ul class="hint-list" data-hints-for="${lab.id}"></ul>
    </div>
  `;

  const launchButton = card.querySelector("button.launch");
  const stopButton = card.querySelector("button.stop");
  launchButton.addEventListener("click", () => launchLab(lab.id, launchButton, stopButton));
  stopButton.addEventListener("click", () => stopLab(lab.id, launchButton, stopButton));

  const submitButton = card.querySelector("button.submit-flag");
  submitButton.addEventListener("click", () => submitFlag(lab.id, card));

  const hintButton = card.querySelector("button.hint-btn");
  let hintsRevealed = 0;
  hintButton.addEventListener("click", () => {
    const hintList = card.querySelector(`[data-hints-for="${lab.id}"]`);
    if (hintsRevealed < lab.hints.length) {
      const li = document.createElement("li");
      li.textContent = lab.hints[hintsRevealed];
      hintList.appendChild(li);
      hintsRevealed++;
    }
    if (hintsRevealed >= lab.hints.length) {
      hintButton.disabled = true;
      hintButton.textContent = "No more hints";
    } else {
      hintButton.textContent = `Show hint (${hintsRevealed + 1}/${lab.hints.length})`;
    }
  });

  return card;
}

async function launchLab(labId, launchBtn, stopBtn) {
  // Every click asks the backend for THIS visitor's own private container
  // instead of opening a fixed, shared URL.
  const originalText = launchBtn.textContent;
  launchBtn.textContent = "Starting...";
  launchBtn.disabled = true;

  try {
    const res = await fetch(`${BACKEND_URL}/api/labs/${labId}/launch`, {
      method: "POST",
      credentials: "include",
    });
    const data = await res.json();

    if (data.url) {
      window.open(data.url, "_blank", "noopener");
      // Now that a container is running, show the Stop button so the
      // user can clean it up manually instead of waiting on the timeout.
      stopBtn.style.display = "inline-block";
    } else {
      alert(data.error || "Could not start the lab. Try again in a moment.");
    }
  } catch (err) {
    alert("Could not reach the backend to launch the lab.");
    console.error(err);
  } finally {
    launchBtn.textContent = originalText;
    launchBtn.disabled = false;
  }
}

async function stopLab(labId, launchBtn, stopBtn) {
  const originalText = stopBtn.textContent;
  stopBtn.textContent = "Stopping...";
  stopBtn.disabled = true;

  try {
    await fetch(`${BACKEND_URL}/api/labs/${labId}/stop`, {
      method: "POST",
      credentials: "include",
    });
  } catch (err) {
    console.error(err);
  } finally {
    stopBtn.style.display = "none";
    stopBtn.textContent = originalText;
    stopBtn.disabled = false;
  }
}

async function submitFlag(labId, card) {
  const input = card.querySelector(`input[data-lab-id="${labId}"]`);
  const resultBox = card.querySelector(`[data-result-for="${labId}"]`);
  const flag = input.value.trim();

  if (!flag) return;

  try {
    const res = await fetch(`${BACKEND_URL}/api/check-flag`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lab_id: labId, flag }),
    });
    const data = await res.json();

    if (data.correct) {
      resultBox.textContent = "Correct! Lab solved.";
      resultBox.className = "flag-result correct";
      // Update just this card's badge in place, instead of re-rendering
      // the whole list (which was wiping out the message immediately).
      const badge = card.querySelector(".tag");
      badge.textContent = "Solved";
      badge.classList.add("solved");
    } else {
      resultBox.textContent = "Not quite — keep trying.";
      resultBox.className = "flag-result wrong";
    }
  } catch (err) {
    resultBox.textContent = "Error contacting backend.";
    resultBox.className = "flag-result wrong";
    console.error(err);
  }
}

loadLabs();
