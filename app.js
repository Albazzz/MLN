/**
 * Quiz MLN – static quiz app
 * Features: random order, wrong-answer bank, tab redo, arrow navigation
 */
(function () {
  "use strict";

  const STORAGE_KEY = "mln-quiz-wrong-ids-v1";
  const LETTERS = ["A", "B", "C", "D"];

  /** @type {Array<{id:number,question:string,options:Object.<string,string>,answer:string}>} */
  const ALL = Array.isArray(window.QUIZ_QUESTIONS) ? window.QUIZ_QUESTIONS : [];

  // —— State ——
  let mode = "all"; // 'all' | 'wrong'
  let queue = []; // question objects currently in play
  let index = 0;
  let answered = false;
  let selectedLetter = null;
  let sessionCorrect = 0;
  let sessionAnswered = 0;
  /** @type {Set<number>} */
  let wrongIds = loadWrongIds();
  /** @type {Map<number, string>} last selected answer per question id (session) */
  let lastChoice = new Map();

  // —— DOM ——
  const $ = (sel) => document.querySelector(sel);
  const el = {
    qIndex: $("#qIndex"),
    qId: $("#qId"),
    questionText: $("#questionText"),
    options: $("#options"),
    feedback: $("#feedback"),
    altPanel: $("#altPanel"),
    quizCard: $("#quizCard"),
    emptyState: $("#emptyState"),
    emptyTitle: $("#emptyTitle"),
    emptyDesc: $("#emptyDesc"),
    btnPrev: $("#btnPrev"),
    btnNext: $("#btnNext"),
    btnJump: $("#btnJump"),
    jumpInput: $("#jumpInput"),
    progressBar: $("#progressBar"),
    statCorrect: $("#statCorrect"),
    statWrong: $("#statWrong"),
    statProgress: $("#statProgress"),
    statTotal: $("#statTotal"),
    badgeAll: $("#badgeAll"),
    badgeWrong: $("#badgeWrong"),
    shuffleToggle: $("#shuffleToggle"),
    btnReshuffle: $("#btnReshuffle"),
    btnResetSession: $("#btnResetSession"),
    btnClearWrong: $("#btnClearWrong"),
    btnGoAll: $("#btnGoAll"),
  };

  /** Correct letter set for a question (supports multi like ABC). */
  function correctLetters(q) {
    if (!q) return [];
    if (Array.isArray(q.answers) && q.answers.length) {
      return q.answers.map(String);
    }
    return q.answer ? [String(q.answer)] : [];
  }

  function isCorrectChoice(q, letter) {
    return correctLetters(q).includes(letter);
  }

  // —— Storage ——
  function loadWrongIds() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return new Set();
      const arr = JSON.parse(raw);
      if (!Array.isArray(arr)) return new Set();
      return new Set(arr.map(Number).filter((n) => Number.isFinite(n)));
    } catch {
      return new Set();
    }
  }

  function saveWrongIds() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify([...wrongIds]));
    } catch {
      /* ignore quota */
    }
  }

  function addWrong(id) {
    wrongIds.add(id);
    saveWrongIds();
    updateBadges();
  }

  function removeWrong(id) {
    if (wrongIds.delete(id)) {
      saveWrongIds();
      updateBadges();
    }
  }

  // —— Utils ——
  function shuffle(arr) {
    const a = arr.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  function getSourceList() {
    if (mode === "wrong") {
      return ALL.filter((q) => wrongIds.has(q.id));
    }
    return ALL.slice();
  }

  function rebuildQueue(keepPositionId) {
    let list = getSourceList();
    if (el.shuffleToggle.checked && list.length > 1) {
      list = shuffle(list);
    }
    queue = list;

    if (keepPositionId != null) {
      const found = queue.findIndex((q) => q.id === keepPositionId);
      index = found >= 0 ? found : 0;
    } else {
      index = 0;
    }

    // Clamp
    if (index >= queue.length) index = Math.max(0, queue.length - 1);

    lastChoice = new Map();
    answered = false;
    selectedLetter = null;
    render();
  }

  function currentQuestion() {
    return queue[index] || null;
  }

  // —— Render ——
  function updateBadges() {
    el.badgeAll.textContent = String(ALL.length);
    el.badgeWrong.textContent = String(wrongIds.size);
    el.statWrong.textContent = String(wrongIds.size);
    el.statCorrect.textContent = String(sessionCorrect);
    el.statTotal.textContent = String(queue.length);
    el.statProgress.textContent = queue.length ? String(index + 1) : "0";

    const pct = queue.length ? ((index + 1) / queue.length) * 100 : 0;
    el.progressBar.style.width = pct + "%";
  }

  function render() {
    updateBadges();

    const q = currentQuestion();
    if (!q) {
      el.quizCard.classList.add("hidden");
      el.emptyState.classList.remove("hidden");
      if (mode === "wrong") {
        el.emptyTitle.textContent = wrongIds.size === 0 ? "Chưa có câu sai 🎉" : "Hết câu trong hàng đợi";
        el.emptyDesc.textContent =
          wrongIds.size === 0
            ? "Khi bạn trả lời sai ở tab Tất cả, câu sẽ được lưu ở đây để làm lại (chế độ ngẫu nhiên)."
            : "Bấm «Xáo lại» hoặc chuyển tab để tiếp tục.";
      } else {
        el.emptyTitle.textContent = "Không có câu hỏi";
        el.emptyDesc.textContent = "File questions.js trống hoặc chưa tải được.";
      }
      el.btnPrev.disabled = true;
      el.btnNext.disabled = true;
      el.jumpInput.max = 1;
      el.jumpInput.value = "";
      return;
    }

    el.emptyState.classList.add("hidden");
    el.quizCard.classList.remove("hidden");

    // Re-trigger card animation
    el.quizCard.style.animation = "none";
    void el.quizCard.offsetWidth;
    el.quizCard.style.animation = "";

    el.qIndex.textContent = `Câu ${index + 1} / ${queue.length}`;
    el.qId.textContent = `#${q.id}` + (wrongIds.has(q.id) ? " · đã sai trước đó" : "");
    el.questionText.textContent = q.question;

    const letters = Object.keys(q.options).sort();
    const prev = lastChoice.get(q.id);
    answered = prev != null;
    selectedLetter = prev || null;
    const corrects = correctLetters(q);

    el.options.innerHTML = "";
    letters.forEach((letter) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "option";
      btn.setAttribute("role", "option");
      btn.dataset.letter = letter;
      btn.innerHTML = `<span class="letter">${letter}</span><span class="opt-text">${escapeHtml(
        q.options[letter]
      )}</span>`;
      btn.addEventListener("click", () => onSelect(letter));
      if (answered) {
        btn.disabled = true;
        applyOptionState(btn, letter, corrects, selectedLetter);
      }
      el.options.appendChild(btn);
    });

    if (answered) {
      showFeedback(isCorrectChoice(q, selectedLetter), q);
      showAltPanel(q);
    } else {
      hideFeedback();
      hideAltPanel();
    }

    el.btnPrev.disabled = index <= 0;
    el.btnNext.disabled = index >= queue.length - 1;
    el.jumpInput.max = queue.length;
    el.jumpInput.value = String(index + 1);
  }

  function applyOptionState(btn, letter, corrects, chosen) {
    const correctSet = Array.isArray(corrects) ? corrects : [corrects];
    if (correctSet.includes(letter)) {
      btn.classList.add("correct");
    } else if (letter === chosen) {
      btn.classList.add("wrong");
    } else {
      btn.classList.add("dimmed");
    }
    if (letter === chosen) btn.classList.add("selected");
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatCorrectAnswer(q) {
    const letters = correctLetters(q);
    const parts = letters.map((L) => {
      const t = (q.options && q.options[L]) || "";
      return t ? `${L}. ${t}` : L;
    });
    return parts.join(" · ");
  }

  function showFeedback(ok, q) {
    el.feedback.classList.remove("hidden", "ok", "err");
    if (ok) {
      el.feedback.classList.add("ok");
      const multi = correctLetters(q).length > 1;
      el.feedback.textContent = multi
        ? `✓ Chính xác! (Đáp án: ${correctLetters(q).join(", ")})`
        : "✓ Chính xác!";
    } else {
      el.feedback.classList.add("err");
      el.feedback.textContent = `✗ Sai. Đáp án đúng: ${formatCorrectAnswer(q)}`;
    }
  }

  function hideFeedback() {
    el.feedback.classList.add("hidden");
    el.feedback.textContent = "";
    el.feedback.classList.remove("ok", "err");
  }

  function hideAltPanel() {
    if (!el.altPanel) return;
    el.altPanel.classList.add("hidden");
    el.altPanel.innerHTML = "";
  }

  /** Show "Kiểu hỏi khác" block(s) with answers after user answered. */
  function showAltPanel(q) {
    if (!el.altPanel) return;
    const alts = (q && q.alternatives) || [];
    if (!alts.length) {
      hideAltPanel();
      return;
    }

    let html = `<div class="alt-panel-title">🔁 Kiểu hỏi khác <span style="font-weight:500;text-transform:none;letter-spacing:0;color:var(--text-muted)">(${alts.length})</span></div>`;

    alts.forEach((alt, idx) => {
      const aq = escapeHtml(alt.question || "Biến thể");
      const opts = alt.options && typeof alt.options === "object" ? alt.options : {};
      const letters = Object.keys(opts).sort();
      const ansLetter = alt.answer || null;
      const ansText = alt.answerText || (ansLetter && opts[ansLetter]) || "";

      html += `<div class="alt-card">`;
      html += `<div class="alt-label">Biến thể ${idx + 1}</div>`;
      html += `<p class="alt-question">${aq}</p>`;

      if (letters.length) {
        html += `<div class="alt-options">`;
        letters.forEach((L) => {
          const isOk = ansLetter && L === ansLetter;
          html += `<div class="alt-opt${isOk ? " is-correct" : ""}">`;
          html += `<span class="alt-letter">${escapeHtml(L)}</span>`;
          html += `<span>${escapeHtml(opts[L] || "")}</span>`;
          html += `</div>`;
        });
        html += `</div>`;
      }

      if (ansLetter || ansText) {
        const label = ansLetter
          ? `Đáp án: ${escapeHtml(ansLetter)}${ansText ? " — " + escapeHtml(ansText) : ""}`
          : `Đáp án: ${escapeHtml(ansText)}`;
        html += `<p class="alt-answer">✓ ${label}</p>`;
      } else {
        html += `<p class="alt-answer" style="background:var(--warn-bg);border-color:rgba(245,158,11,.35);color:var(--warn)">⚠ Chưa có đáp án trong dữ liệu nguồn</p>`;
      }

      html += `</div>`;
    });

    el.altPanel.innerHTML = html;
    el.altPanel.classList.remove("hidden");
  }

  // —— Interactions ——
  function onSelect(letter) {
    const q = currentQuestion();
    if (!q || answered) return;

    answered = true;
    selectedLetter = letter;
    lastChoice.set(q.id, letter);
    sessionAnswered += 1;

    const ok = isCorrectChoice(q, letter);
    if (ok) {
      sessionCorrect += 1;
      // If reviewing wrong tab and get it right, remove from wrong bank
      if (mode === "wrong") {
        removeWrong(q.id);
      }
    } else {
      addWrong(q.id);
    }

    // Update option styles
    const corrects = correctLetters(q);
    const buttons = el.options.querySelectorAll(".option");
    buttons.forEach((btn) => {
      btn.disabled = true;
      applyOptionState(btn, btn.dataset.letter, corrects, letter);
    });

    showFeedback(ok, q);
    showAltPanel(q);
    updateBadges();
  }

  function go(delta) {
    const next = index + delta;
    if (next < 0 || next >= queue.length) return;
    index = next;
    answered = false;
    selectedLetter = null;
    hideAltPanel();
    render();
  }

  function jumpTo(n) {
    const i = Number(n) - 1;
    if (!Number.isFinite(i) || i < 0 || i >= queue.length) return;
    index = i;
    answered = false;
    selectedLetter = null;
    hideAltPanel();
    render();
  }

  function setMode(newMode) {
    if (newMode === mode) return;
    mode = newMode;
    document.querySelectorAll(".tab").forEach((t) => {
      const active = t.dataset.tab === mode;
      t.classList.toggle("active", active);
      t.setAttribute("aria-selected", active ? "true" : "false");
    });
    rebuildQueue(null);
  }

  // —— Events ——
  document.querySelectorAll(".tab").forEach((t) => {
    t.addEventListener("click", () => setMode(t.dataset.tab));
  });

  el.btnPrev.addEventListener("click", () => go(-1));
  el.btnNext.addEventListener("click", () => go(1));

  el.btnJump.addEventListener("click", () => jumpTo(el.jumpInput.value));
  el.jumpInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      jumpTo(el.jumpInput.value);
    }
  });

  el.shuffleToggle.addEventListener("change", () => {
    const cur = currentQuestion();
    rebuildQueue(cur ? cur.id : null);
  });

  el.btnReshuffle.addEventListener("click", () => {
    el.shuffleToggle.checked = true;
    rebuildQueue(null);
  });

  el.btnResetSession.addEventListener("click", () => {
    sessionCorrect = 0;
    sessionAnswered = 0;
    lastChoice = new Map();
    answered = false;
    selectedLetter = null;
    render();
  });

  el.btnClearWrong.addEventListener("click", () => {
    if (wrongIds.size === 0) return;
    if (!confirm(`Xóa ${wrongIds.size} câu sai đã lưu?`)) return;
    wrongIds = new Set();
    saveWrongIds();
    if (mode === "wrong") {
      rebuildQueue(null);
    } else {
      updateBadges();
      render();
    }
  });

  el.btnGoAll.addEventListener("click", () => setMode("all"));

  document.addEventListener("keydown", (e) => {
    // ignore when typing in input
    if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) return;

    if (e.key === "ArrowLeft") {
      e.preventDefault();
      go(-1);
    } else if (e.key === "ArrowRight" || e.key === "Enter") {
      e.preventDefault();
      go(1);
    } else if (e.key >= "1" && e.key <= "4") {
      const q = currentQuestion();
      if (!q || answered) return;
      const letters = Object.keys(q.options).sort();
      const letter = letters[Number(e.key) - 1];
      if (letter) onSelect(letter);
    } else if (e.key === "a" || e.key === "A" || e.key === "b" || e.key === "B" || e.key === "c" || e.key === "C" || e.key === "d" || e.key === "D") {
      const q = currentQuestion();
      if (!q || answered) return;
      const letter = e.key.toUpperCase();
      if (q.options[letter]) onSelect(letter);
    }
  });

  // Swipe on mobile
  let touchStartX = 0;
  document.addEventListener(
    "touchstart",
    (e) => {
      touchStartX = e.changedTouches[0].screenX;
    },
    { passive: true }
  );
  document.addEventListener(
    "touchend",
    (e) => {
      const dx = e.changedTouches[0].screenX - touchStartX;
      if (Math.abs(dx) < 60) return;
      if (dx < 0) go(1);
      else go(-1);
    },
    { passive: true }
  );

  // —— Boot ——
  if (!ALL.length) {
    el.questionText.textContent = "Không tải được câu hỏi. Kiểm tra file questions.js.";
    updateBadges();
    return;
  }

  rebuildQueue(null);
})();
