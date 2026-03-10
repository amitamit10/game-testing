/* ══════════════════════════════════════════════════════════════
   SPY GAME — CLIENT
   Real-time multiplayer via Socket.IO (relative URL for Railway)
══════════════════════════════════════════════════════════════ */

"use strict";

// ── State ─────────────────────────────────────────────────────────────────────
let socket = null;
let gameState = null;   // current game view
let mySocketId = null;  // our socket id
let currentGameId = null;
let isHost = false;

// ── Socket.IO Init ────────────────────────────────────────────────────────────
// Use relative path — no hardcoded host/port. Works on Railway automatically.
function initSocket() {
  socket = io({
    path: "/socket.io",
    transports: ["websocket", "polling"],
    reconnectionAttempts: 5,
    reconnectionDelay: 1500,
  });

  socket.on("connect", () => {
    mySocketId = socket.id;
    hideConnecting();
    clearError("home");
    console.log("[socket] Connected:", mySocketId);
  });

  socket.on("disconnect", () => {
    console.warn("[socket] Disconnected");
  });

  socket.on("connect_error", (err) => {
    hideConnecting();
    showError("home", "Connection failed. Retrying…");
    console.error("[socket] Error:", err);
  });

  // ── Game Events ──────────────────────────────────────────────────────────

  socket.on("game_created", (data) => {
    gameState = data;
    currentGameId = data.id;
    isHost = true;
    showLobby(data);
  });

  socket.on("game_joined", (data) => {
    gameState = data;
    currentGameId = data.id;
    isHost = data.is_host;
    showLobby(data);
  });

  socket.on("lobby_update", (data) => {
    // Sync player list while in lobby (or update lobby when host is on playing screen)
    if (gameState) {
      gameState.players = data.players;
      gameState.status = data.status;
      gameState.round = data.round;
    }
    if (isOnScreen("lobby")) {
      renderLobbyPlayers(data.players, data.game_id);
    }
  });

  socket.on("game_state", (data) => {
    gameState = data;
    currentGameId = data.id;
    isHost = data.is_host;

    switch (data.status) {
      case "lobby":
        showLobby(data);
        break;
      case "playing":
        showPlaying(data);
        break;
      case "reveal":
        showReveal(data);
        break;
    }
  });

  socket.on("game_deleted", (data) => {
    alert(data.message || "The game has ended.");
    resetToHome();
  });

  socket.on("error", (data) => {
    const screens = ["home", "lobby", "playing", "reveal", "modal"];
    // Show on the currently visible screen
    const current = getCurrentScreen();
    showError(current || "home", data.message || "An error occurred.");
    hideConnecting();
  });
}

// ── Screen Management ─────────────────────────────────────────────────────────
function showScreen(id) {
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  const el = document.getElementById("screen-" + id);
  if (el) el.classList.add("active");
}

function isOnScreen(id) {
  const el = document.getElementById("screen-" + id);
  return el && el.classList.contains("active");
}

function getCurrentScreen() {
  const screens = ["home", "lobby", "playing", "reveal"];
  for (const s of screens) {
    if (isOnScreen(s)) return s;
  }
  return "home";
}

// ── Error Handling ────────────────────────────────────────────────────────────
function showError(screen, message) {
  const id = screen === "modal" ? "error-modal" : `error-${screen}`;
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = "⚠ " + message;
  el.classList.add("visible");
  setTimeout(() => el.classList.remove("visible"), 5000);
}

function clearError(screen) {
  const el = document.getElementById(`error-${screen}`);
  if (el) el.classList.remove("visible");
}

// ── Connecting Indicator ──────────────────────────────────────────────────────
function showConnecting() {
  const el = document.getElementById("connecting-msg");
  if (el) el.style.display = "block";
}
function hideConnecting() {
  const el = document.getElementById("connecting-msg");
  if (el) el.style.display = "none";
}

// ── Tab Switcher ──────────────────────────────────────────────────────────────
function switchTab(tab) {
  document.getElementById("tab-host").classList.toggle("active", tab === "host");
  document.getElementById("tab-join").classList.toggle("active", tab === "join");
  document.getElementById("form-host").style.display = tab === "host" ? "block" : "none";
  document.getElementById("form-join").style.display = tab === "join" ? "block" : "none";
  clearError("home");
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function avatarLetter(name) {
  return (name || "?")[0].toUpperCase();
}

function renderPlayerItem(player, myId, showSpyStatus, revealMode) {
  const isMe = player.id === myId;
  const isSpy = player.is_spy && (showSpyStatus || revealMode);

  let badge = "";
  if (player.is_host) {
    badge = `<span class="player-badge badge-host">HOST</span>`;
  }
  if (revealMode) {
    if (isSpy) {
      badge += `<span class="player-badge badge-spy">SPY</span>`;
    } else {
      badge += `<span class="player-badge badge-safe">SAFE</span>`;
    }
  }

  const classes = [
    "player-item",
    isMe ? "is-me" : "",
    isSpy && revealMode ? "is-spy-revealed" : "",
  ].filter(Boolean).join(" ");

  return `
    <div class="${classes}">
      <div class="player-avatar">${avatarLetter(player.name)}</div>
      <div class="player-name${isMe ? " me-label" : ""}">${escHtml(player.name)}</div>
      ${badge}
    </div>
  `;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── Lobby Screen ──────────────────────────────────────────────────────────────
function showLobby(data) {
  showScreen("lobby");
  document.getElementById("lobby-code").textContent = data.id || currentGameId || "------";
  renderLobbyPlayers(data.players, data.id);

  const hostControls = document.getElementById("lobby-host-controls");
  const waitingMsg   = document.getElementById("lobby-waiting-msg");
  const waitingPlrs  = document.getElementById("waiting-players");
  const btnStart     = document.getElementById("btn-start-game");

  if (data.is_host) {
    hostControls.style.display = "block";
    waitingMsg.style.display = "none";
    const canStart = data.players.length >= 2;
    btnStart.disabled = !canStart;
    waitingPlrs.style.display = canStart ? "none" : "block";
  } else {
    hostControls.style.display = "none";
    waitingMsg.style.display = "block";
  }
}

function renderLobbyPlayers(players, gameId) {
  const list = document.getElementById("lobby-player-list");
  const count = document.getElementById("lobby-count");
  if (!list) return;

  list.innerHTML = players.map(p =>
    renderPlayerItem(p, mySocketId, false, false)
  ).join("");
  if (count) count.textContent = players.length;

  // Update start button
  const btnStart = document.getElementById("btn-start-game");
  if (btnStart) btnStart.disabled = players.length < 2;
  const waitingPlrs = document.getElementById("waiting-players");
  if (waitingPlrs) waitingPlrs.style.display = players.length < 2 ? "block" : "none";
}

// ── Playing Screen ────────────────────────────────────────────────────────────
function showPlaying(data) {
  showScreen("playing");
  closeNewRoundModal();

  // Round badge
  document.getElementById("playing-round-badge").textContent = `Round ${data.round || 1}`;
  document.getElementById("playing-player-count").textContent =
    `${data.players.length} operative${data.players.length !== 1 ? "s" : ""}`;

  // Role cards
  const cardSpy   = document.getElementById("role-card-spy");
  const cardAgent = document.getElementById("role-card-agent");
  cardSpy.style.display   = data.is_spy ? "block" : "none";
  cardAgent.style.display = data.is_spy ? "none"  : "block";

  // Secret word
  const wordDisplay = document.getElementById("word-display");
  const wordValue   = document.getElementById("playing-word");
  if (data.secret_word) {
    wordDisplay.style.display = "block";
    wordValue.textContent = data.secret_word.toUpperCase();
  } else {
    wordDisplay.style.display = "none";
  }

  // Players
  const list = document.getElementById("playing-player-list");
  list.innerHTML = data.players.map(p =>
    renderPlayerItem(p, mySocketId, data.is_spy, false)
  ).join("");

  // Host controls
  const hostCtrl = document.getElementById("playing-host-controls");
  if (data.is_host) {
    hostCtrl.style.display = "block";
    hostCtrl.style.width = "100%";
  } else {
    hostCtrl.style.display = "none";
  }
}

// ── Reveal Screen ─────────────────────────────────────────────────────────────
function showReveal(data) {
  showScreen("reveal");
  closeNewRoundModal();

  document.getElementById("reveal-spy-name").textContent =
    (data.spy_name || "Unknown").toUpperCase();
  document.getElementById("reveal-secret-word").textContent =
    data.secret_word ? data.secret_word.toUpperCase() : "—";

  const list = document.getElementById("reveal-player-list");
  list.innerHTML = data.players.map(p =>
    renderPlayerItem(p, mySocketId, true, true)
  ).join("");

  const hostCtrl = document.getElementById("reveal-host-controls");
  if (data.is_host) {
    hostCtrl.style.display = "block";
  } else {
    hostCtrl.style.display = "none";
  }
}

// ── Actions ───────────────────────────────────────────────────────────────────
function handleCreateGame() {
  clearError("home");
  const hostName   = document.getElementById("host-name").value.trim();
  const secretWord = document.getElementById("secret-word").value.trim();

  if (!hostName)   { showError("home", "Please enter your codename."); return; }
  if (!secretWord) { showError("home", "Please enter a secret word."); return; }
  if (!socket || !socket.connected) {
    showError("home", "Not connected to server. Please wait…");
    return;
  }

  showConnecting();
  socket.emit("create_game", { host_name: hostName, secret_word: secretWord });
}

function handleJoinGame() {
  clearError("home");
  const playerName = document.getElementById("join-name").value.trim();
  const gameCode   = document.getElementById("join-code").value.trim().toUpperCase();

  if (!playerName) { showError("home", "Please enter your codename."); return; }
  if (!gameCode)   { showError("home", "Please enter a game code."); return; }
  if (!socket || !socket.connected) {
    showError("home", "Not connected to server. Please wait…");
    return;
  }

  showConnecting();
  socket.emit("join_game", { game_id: gameCode, player_name: playerName });
}

function handleStartGame() {
  if (!currentGameId) return;
  socket.emit("start_game", { game_id: currentGameId });
}

function handleReveal() {
  if (!currentGameId) return;
  socket.emit("reveal", { game_id: currentGameId });
}

function openNewRoundModal() {
  document.getElementById("modal-new-round").classList.add("visible");
  document.getElementById("new-secret-word").value = "";
  clearError("modal");
  setTimeout(() => document.getElementById("new-secret-word").focus(), 100);
}

function closeNewRoundModal() {
  document.getElementById("modal-new-round").classList.remove("visible");
}

function handleNewRound() {
  const word = document.getElementById("new-secret-word").value.trim();
  if (!word) {
    showError("modal", "Please enter a secret word for the new round.");
    return;
  }
  if (!currentGameId) return;
  socket.emit("new_round", { game_id: currentGameId, secret_word: word });
  closeNewRoundModal();
}

function handleLeaveGame() {
  resetToHome();
}

function resetToHome() {
  gameState = null;
  currentGameId = null;
  isHost = false;
  showScreen("home");
  closeNewRoundModal();
  // Reconnect socket if needed
  if (socket && !socket.connected) {
    socket.connect();
  }
}

// ── Keyboard shortcuts ────────────────────────────────────────────────────────
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    closeNewRoundModal();
  }
  if (e.key === "Enter") {
    if (isOnScreen("home")) {
      const activeTab = document.getElementById("tab-host").classList.contains("active");
      if (activeTab) handleCreateGame();
      else handleJoinGame();
    }
    if (document.getElementById("modal-new-round").classList.contains("visible")) {
      handleNewRound();
    }
  }
});

// Close modal on backdrop click
document.getElementById("modal-new-round").addEventListener("click", (e) => {
  if (e.target === e.currentTarget) closeNewRoundModal();
});

// Input uppercase for join code
document.getElementById("join-code").addEventListener("input", function () {
  const pos = this.selectionStart;
  this.value = this.value.toUpperCase();
  this.setSelectionRange(pos, pos);
});

// ── Bootstrap ─────────────────────────────────────────────────────────────────
initSocket();
