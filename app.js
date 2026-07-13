/**
 * Quiz MLN – static quiz app
 * Multi-select for multi-answer questions, search, wrong bank, navigation
 */
(function () {
  "use strict";

  const STORAGE_KEY = "mln-quiz-wrong-ids-v1";

  /** @type {Array<{id:number,question:string,options:Object.<string,string>,answer:string,answers?:string[]}>} */
  const ALL = Array.isArray(window.QUIZ_QUESTIONS) ? window.QUIZ_QUESTIONS : [];

  // —— State ——
  let mode = "all"; // 'all' | 'wrong'
  let queue = [];
  let index = 0;
  let answered = false;
  /** @type {string[]} pending multi-select or single choice before submit */
  let selectedLetters = [];
  let sessionCorrect = 0;
  let sessionAnswered = 0;
  /** @type {Set<number>} */
  let wrongIds = loadWrongIds();
  /**
   * lastChoice: id -> string[] of chosen letters
   * @type {Map<number, string[]>}
   */
  let lastChoice = new Map();
  let searchQuery = "";

  // —— DOM ——
  const $ = (sel) => document.querySelector(sel);
  const el = {
    qIndex: $("#qIndex"),
    qId: $("#qId"),
    questionText: $("#questionText"),
    multiHint: $("#multiHint"),
    options: $("#options"),
    submitRow: $("#submitRow"),
    btnSubmit: $("#btnSubmit"),
    submitCount: $("#submitCount"),
    feedback: $("#feedback"),
    explainPanel: $("#explainPanel"),
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
    searchInput: $("#searchInput"),
    searchResults: $("#searchResults"),
    btnClearSearch: $("#btnClearSearch"),
  };

  function correctLetters(q) {
    if (!q) return [];
    if (Array.isArray(q.answers) && q.answers.length) {
      return q.answers.map(String).sort();
    }
    return q.answer ? [String(q.answer)] : [];
  }

  function isMulti(q) {
    return correctLetters(q).length > 1;
  }

  function setsEqual(a, b) {
    if (a.length !== b.length) return false;
    const sa = a.slice().sort().join(",");
    const sb = b.slice().sort().join(",");
    return sa === sb;
  }

  function isCorrectSelection(q, chosen) {
    return setsEqual(correctLetters(q), chosen || []);
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
      /* ignore */
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

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
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
    if (index >= queue.length) index = Math.max(0, queue.length - 1);

    lastChoice = new Map();
    answered = false;
    selectedLetters = [];
    render();
  }

  function currentQuestion() {
    return queue[index] || null;
  }

  function goToQuestionId(id) {
    // Prefer current queue; if not found, switch to all + unshuffle order by id
    let found = queue.findIndex((q) => q.id === id);
    if (found < 0) {
      mode = "all";
      document.querySelectorAll(".tab").forEach((t) => {
        const active = t.dataset.tab === "all";
        t.classList.toggle("active", active);
        t.setAttribute("aria-selected", active ? "true" : "false");
      });
      el.shuffleToggle.checked = false;
      queue = ALL.slice();
      found = queue.findIndex((q) => q.id === id);
    }
    if (found < 0) return;
    index = found;
    answered = false;
    selectedLetters = [];
    hideSearchResults();
    if (el.searchInput) el.searchInput.value = "";
    searchQuery = "";
    if (el.btnClearSearch) el.btnClearSearch.classList.add("hidden");
    render();
    el.quizCard?.scrollIntoView({ behavior: "smooth", block: "start" });
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

  function updateSubmitUI(q) {
    if (!el.submitRow || !el.btnSubmit) return;
    if (!q || answered || !isMulti(q)) {
      el.submitRow.classList.add("hidden");
      return;
    }
    el.submitRow.classList.remove("hidden");
    el.btnSubmit.disabled = selectedLetters.length === 0;
    if (el.submitCount) {
      el.submitCount.textContent =
        selectedLetters.length === 0
          ? "Chưa chọn"
          : `Đã chọn ${selectedLetters.length}: ${selectedLetters.slice().sort().join(", ")}`;
    }
  }

  function render() {
    updateBadges();

    const q = currentQuestion();
    if (!q) {
      el.quizCard.classList.add("hidden");
      el.emptyState.classList.remove("hidden");
      if (mode === "wrong") {
        el.emptyTitle.textContent = wrongIds.size === 0 ? "Chưa có câu sai" : "Hết câu trong hàng đợi";
        el.emptyDesc.textContent =
          wrongIds.size === 0
            ? "Khi bạn trả lời sai ở tab Tất cả, câu sẽ được lưu ở đây để làm lại."
            : "Bấm «Xáo lại» hoặc chuyển tab để tiếp tục.";
      } else {
        el.emptyTitle.textContent = "Không có câu hỏi";
        el.emptyDesc.textContent = "File questions.js trống hoặc chưa tải được.";
      }
      el.btnPrev.disabled = true;
      el.btnNext.disabled = true;
      el.jumpInput.max = 1;
      el.jumpInput.value = "";
      if (el.submitRow) el.submitRow.classList.add("hidden");
      if (el.multiHint) el.multiHint.classList.add("hidden");
      return;
    }

    el.emptyState.classList.add("hidden");
    el.quizCard.classList.remove("hidden");

    el.quizCard.style.animation = "none";
    void el.quizCard.offsetWidth;
    el.quizCard.style.animation = "";

    el.qIndex.innerHTML = `<i class="fa-solid fa-circle-question"></i> Câu ${index + 1} / ${queue.length}`;
    el.qId.textContent = `#${q.id}` + (wrongIds.has(q.id) ? " · đã sai trước đó" : "");
    el.questionText.textContent = q.question;

    const multi = isMulti(q);
    if (el.multiHint) {
      el.multiHint.classList.toggle("hidden", !multi || answered);
    }

    const prev = lastChoice.get(q.id);
    answered = prev != null;
    selectedLetters = answered ? prev.slice() : [];
    const corrects = correctLetters(q);
    const letters = Object.keys(q.options).sort();

    el.options.innerHTML = "";
    letters.forEach((letter) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "option" + (multi ? " option-multi" : "");
      btn.setAttribute("role", "option");
      btn.dataset.letter = letter;
      const mark = multi
        ? `<span class="check-mark"><i class="fa-regular fa-square"></i></span>`
        : `<span class="letter">${letter}</span>`;
      btn.innerHTML = `${mark}<span class="opt-text"><span class="opt-letter-inline">${letter}.</span> ${escapeHtml(
        q.options[letter]
      )}</span>`;
      btn.addEventListener("click", () => onToggle(letter));
      if (answered) {
        btn.disabled = true;
        applyOptionState(btn, letter, corrects, selectedLetters);
      } else if (selectedLetters.includes(letter)) {
        btn.classList.add("picked");
        if (multi) {
          btn.querySelector(".check-mark i")?.classList.replace("fa-regular", "fa-solid");
          btn.querySelector(".check-mark i")?.classList.replace("fa-square", "fa-square-check");
        }
      }
      el.options.appendChild(btn);
    });

    if (answered) {
      showFeedback(isCorrectSelection(q, selectedLetters), q);
      showExplainPanel(q);
      showAltPanel(q);
      if (el.submitRow) el.submitRow.classList.add("hidden");
    } else {
      hideFeedback();
      hideExplainPanel();
      hideAltPanel();
      updateSubmitUI(q);
    }

    el.btnPrev.disabled = index <= 0;
    el.btnNext.disabled = index >= queue.length - 1;
    el.jumpInput.max = queue.length;
    el.jumpInput.value = String(index + 1);
  }

  /**
   * @param {HTMLElement} btn
   * @param {string} letter
   * @param {string[]} corrects
   * @param {string[]} chosen
   */
  function applyOptionState(btn, letter, corrects, chosen) {
    const correctSet = corrects || [];
    const chosenSet = chosen || [];
    const isCorrect = correctSet.includes(letter);
    const isChosen = chosenSet.includes(letter);

    if (isCorrect) {
      btn.classList.add("correct");
    } else if (isChosen) {
      btn.classList.add("wrong");
    } else {
      btn.classList.add("dimmed");
    }
    if (isChosen) btn.classList.add("selected");

    // multi checkbox icons
    const icon = btn.querySelector(".check-mark i");
    if (icon) {
      icon.className = isCorrect
        ? "fa-solid fa-square-check"
        : isChosen
          ? "fa-solid fa-square-xmark"
          : "fa-regular fa-square";
    }
  }

  function formatCorrectAnswer(q) {
    const letters = correctLetters(q);
    return letters
      .map((L) => {
        const t = (q.options && q.options[L]) || "";
        return t ? `${L}. ${t}` : L;
      })
      .join(" · ");
  }

  function showFeedback(ok, q) {
    el.feedback.classList.remove("hidden", "ok", "err");
    if (ok) {
      el.feedback.classList.add("ok");
      const multi = isMulti(q);
      const msg = multi
        ? `Chính xác! (Đáp án: ${correctLetters(q).join(", ")})`
        : "Chính xác!";
      el.feedback.innerHTML = `<i class="fa-solid fa-circle-check"></i><span>${escapeHtml(msg)}</span>`;
    } else {
      el.feedback.classList.add("err");
      el.feedback.innerHTML = `<i class="fa-solid fa-circle-xmark"></i><span>Sai. Đáp án đúng: ${escapeHtml(
        formatCorrectAnswer(q)
      )}</span>`;
    }
  }

  function hideFeedback() {
    el.feedback.classList.add("hidden");
    el.feedback.innerHTML = "";
    el.feedback.classList.remove("ok", "err");
  }

  function hideAltPanel() {
    if (!el.altPanel) return;
    el.altPanel.classList.add("hidden");
    el.altPanel.innerHTML = "";
  }

  function hideExplainPanel() {
    if (!el.explainPanel) return;
    el.explainPanel.classList.add("hidden");
    el.explainPanel.innerHTML = "";
  }

  function showExplainPanel(q) {
    if (!el.explainPanel) return;
    const exp = q && q.explanation;
    if (!exp || (!exp.whyCorrect && !exp.whyWrong)) {
      hideExplainPanel();
      return;
    }

    const corrects = correctLetters(q);
    let html = `<div class="explain-title"><i class="fa-solid fa-lightbulb"></i> Giải thích</div>`;

    if (exp.whyCorrect) {
      html += `<div class="explain-block explain-ok">
        <div class="explain-label"><i class="fa-solid fa-circle-check"></i> Vì sao đúng</div>
        <p>${escapeHtml(exp.whyCorrect)}</p>
      </div>`;
    }

    const wrong = exp.whyWrong || {};
    const wrongKeys = Object.keys(wrong).sort();
    if (wrongKeys.length) {
      html += `<div class="explain-block explain-bad">
        <div class="explain-label"><i class="fa-solid fa-circle-xmark"></i> Vì sao các lựa chọn còn lại sai</div>
        <ul class="explain-list">`;
      wrongKeys.forEach((L) => {
        const optText = (q.options && q.options[L]) || "";
        html += `<li><strong>${escapeHtml(L)}${optText ? ". " + escapeHtml(optText) : ""}</strong>
          <span>${escapeHtml(wrong[L])}</span></li>`;
      });
      html += `</ul></div>`;
    }

    // also list correct options clearly for multi
    if (corrects.length > 1) {
      html += `<div class="explain-block explain-keys">
        <div class="explain-label"><i class="fa-solid fa-list-check"></i> Các đáp án đúng</div>
        <ul class="explain-list">`;
      corrects.forEach((L) => {
        html += `<li><strong>${escapeHtml(L)}. ${escapeHtml((q.options && q.options[L]) || "")}</strong></li>`;
      });
      html += `</ul></div>`;
    }

    el.explainPanel.innerHTML = html;
    el.explainPanel.classList.remove("hidden");
  }

  function showAltPanel(q) {
    if (!el.altPanel) return;
    const alts = (q && q.alternatives) || [];
    if (!alts.length) {
      hideAltPanel();
      return;
    }

    let html = `<div class="alt-panel-title"><i class="fa-solid fa-retweet"></i> Kiểu hỏi khác <span style="font-weight:600;text-transform:none;letter-spacing:0;color:var(--muted)">(${alts.length})</span></div>`;

    alts.forEach((alt, idx) => {
      const aq = escapeHtml(alt.question || "Biến thể");
      const opts = alt.options && typeof alt.options === "object" ? alt.options : {};
      const letters = Object.keys(opts).sort();
      const ansLetter = alt.answer || null;
      const ansText = alt.answerText || (ansLetter && opts[ansLetter]) || "";

      html += `<div class="alt-card">`;
      html += `<div class="alt-label"><i class="fa-solid fa-clone"></i> Biến thể ${idx + 1}</div>`;
      html += `<p class="alt-question">${aq}</p>`;

      if (letters.length) {
        html += `<div class="alt-options">`;
        letters.forEach((L) => {
          const isOk = ansLetter && String(ansLetter).includes(L);
          html += `<div class="alt-opt${isOk ? " is-correct" : ""}">`;
          html += `<span class="alt-letter">${escapeHtml(L)}</span>`;
          html += `<span>${escapeHtml(opts[L] || "")}</span>`;
          html += `</div>`;
        });
        html += `</div>`;
      }

      if (ansLetter || ansText) {
        const label = ansLetter
          ? `Đáp án: ${escapeHtml(String(ansLetter))}${ansText ? " — " + escapeHtml(ansText) : ""}`
          : `Đáp án: ${escapeHtml(ansText)}`;
        html += `<p class="alt-answer"><i class="fa-solid fa-check"></i><span>${label}</span></p>`;
      } else {
        html += `<p class="alt-answer warn"><i class="fa-solid fa-triangle-exclamation"></i><span>Chưa có đáp án trong dữ liệu nguồn</span></p>`;
      }
      if (alt.explanation && alt.explanation.whyCorrect) {
        html += `<p class="alt-explain"><i class="fa-solid fa-lightbulb"></i> ${escapeHtml(alt.explanation.whyCorrect)}</p>`;
      }
      html += `</div>`;
    });

    el.altPanel.innerHTML = html;
    el.altPanel.classList.remove("hidden");
  }

  // —— Selection ——
  function onToggle(letter) {
    const q = currentQuestion();
    if (!q || answered) return;

    if (!isMulti(q)) {
      // single choice — submit immediately
      commitAnswer(q, [letter]);
      return;
    }

    // multi: toggle
    const i = selectedLetters.indexOf(letter);
    if (i >= 0) selectedLetters.splice(i, 1);
    else selectedLetters.push(letter);

    // refresh picked UI without full re-render of feedback
    el.options.querySelectorAll(".option").forEach((btn) => {
      const L = btn.dataset.letter;
      const on = selectedLetters.includes(L);
      btn.classList.toggle("picked", on);
      const icon = btn.querySelector(".check-mark i");
      if (icon) {
        icon.className = on ? "fa-solid fa-square-check" : "fa-regular fa-square";
      }
    });
    updateSubmitUI(q);
  }

  function commitAnswer(q, chosen) {
    if (!q || answered) return;
    answered = true;
    selectedLetters = chosen.slice().sort();
    lastChoice.set(q.id, selectedLetters.slice());
    sessionAnswered += 1;

    const ok = isCorrectSelection(q, selectedLetters);
    if (ok) {
      sessionCorrect += 1;
      if (mode === "wrong") removeWrong(q.id);
    } else {
      addWrong(q.id);
    }

    const corrects = correctLetters(q);
    el.options.querySelectorAll(".option").forEach((btn) => {
      btn.disabled = true;
      applyOptionState(btn, btn.dataset.letter, corrects, selectedLetters);
    });

    if (el.multiHint) el.multiHint.classList.add("hidden");
    if (el.submitRow) el.submitRow.classList.add("hidden");

    showFeedback(ok, q);
    showExplainPanel(q);
    showAltPanel(q);
    updateBadges();
  }

  function submitMulti() {
    const q = currentQuestion();
    if (!q || answered || !isMulti(q) || selectedLetters.length === 0) return;
    commitAnswer(q, selectedLetters);
  }

  function go(delta) {
    const next = index + delta;
    if (next < 0 || next >= queue.length) return;
    index = next;
    answered = false;
    selectedLetters = [];
    hideExplainPanel();
    hideAltPanel();
    render();
  }

  function jumpTo(n) {
    const i = Number(n) - 1;
    if (!Number.isFinite(i) || i < 0 || i >= queue.length) return;
    index = i;
    answered = false;
    selectedLetters = [];
    hideExplainPanel();
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

  // —— Search ——
  function hideSearchResults() {
    if (!el.searchResults) return;
    el.searchResults.classList.add("hidden");
    el.searchResults.innerHTML = "";
  }

  function runSearch(q) {
    searchQuery = (q || "").trim();
    if (el.btnClearSearch) {
      el.btnClearSearch.classList.toggle("hidden", !searchQuery);
    }
    if (!searchQuery) {
      hideSearchResults();
      return;
    }
    const tokens = searchQuery
      .toLowerCase()
      .split(/\s+/)
      .filter(Boolean);
    if (!tokens.length) {
      hideSearchResults();
      return;
    }

    const pool = mode === "wrong" ? ALL.filter((x) => wrongIds.has(x.id)) : ALL;
    const hits = [];
    for (const item of pool) {
      const hay = (
        item.question +
        " " +
        Object.values(item.options || {}).join(" ")
      ).toLowerCase();
      if (tokens.every((t) => hay.includes(t))) {
        hits.push(item);
        if (hits.length >= 40) break;
      }
    }

    if (!hits.length) {
      el.searchResults.innerHTML = `<div class="search-empty"><i class="fa-solid fa-magnifying-glass"></i> Không tìm thấy câu nào</div>`;
      el.searchResults.classList.remove("hidden");
      return;
    }

    el.searchResults.innerHTML = hits
      .map((item) => {
        const snippet = escapeHtml(item.question.length > 120 ? item.question.slice(0, 120) + "…" : item.question);
        return `<button type="button" class="search-item" data-id="${item.id}" role="option">
          <span class="search-item-id">#${item.id}</span>
          <span class="search-item-text">${snippet}</span>
        </button>`;
      })
      .join("");
    el.searchResults.classList.remove("hidden");

    el.searchResults.querySelectorAll(".search-item").forEach((btn) => {
      btn.addEventListener("click", () => {
        goToQuestionId(Number(btn.dataset.id));
      });
    });
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

  if (el.btnSubmit) {
    el.btnSubmit.addEventListener("click", submitMulti);
  }

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
    selectedLetters = [];
    render();
  });

  el.btnClearWrong.addEventListener("click", () => {
    if (wrongIds.size === 0) return;
    if (!confirm(`Xóa ${wrongIds.size} câu sai đã lưu?`)) return;
    wrongIds = new Set();
    saveWrongIds();
    if (mode === "wrong") rebuildQueue(null);
    else {
      updateBadges();
      render();
    }
  });

  el.btnGoAll.addEventListener("click", () => setMode("all"));

  if (el.searchInput) {
    let searchTimer = null;
    el.searchInput.addEventListener("input", () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => runSearch(el.searchInput.value), 180);
    });
    el.searchInput.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        el.searchInput.value = "";
        runSearch("");
        el.searchInput.blur();
      }
    });
  }
  if (el.btnClearSearch) {
    el.btnClearSearch.addEventListener("click", () => {
      if (el.searchInput) el.searchInput.value = "";
      runSearch("");
      el.searchInput?.focus();
    });
  }

  // click outside search closes results
  document.addEventListener("click", (e) => {
    if (!el.searchResults || el.searchResults.classList.contains("hidden")) return;
    const t = e.target;
    if (el.searchResults.contains(t) || el.searchInput?.contains(t) || el.btnClearSearch?.contains(t)) return;
    // keep results visible while typing; only hide when clicking far? better keep until clear
  });

  document.addEventListener("keydown", (e) => {
    if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) {
      // allow Enter on multi submit when not in jump/search? skip
      return;
    }

    if (e.key === "ArrowLeft") {
      e.preventDefault();
      go(-1);
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      go(1);
    } else if (e.key === "Enter") {
      const q = currentQuestion();
      if (q && !answered && isMulti(q) && selectedLetters.length) {
        e.preventDefault();
        submitMulti();
      } else if (!answered) {
        // don't auto next on enter for single
      } else {
        e.preventDefault();
        go(1);
      }
    } else if (e.key >= "1" && e.key <= "5") {
      const q = currentQuestion();
      if (!q || answered) return;
      const letters = Object.keys(q.options).sort();
      const letter = letters[Number(e.key) - 1];
      if (letter) onToggle(letter);
    } else if (/^[a-eA-E]$/.test(e.key)) {
      const q = currentQuestion();
      if (!q || answered) return;
      const letter = e.key.toUpperCase();
      if (q.options[letter]) onToggle(letter);
    }
  });

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
