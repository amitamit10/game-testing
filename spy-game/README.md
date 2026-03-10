# 🕵️ COVERT — Spy Social Deduction Game

A browser-based multiplayer spy game with a futuristic cyberpunk UI.
Built with **Python + Flask-SocketIO** backend and vanilla **HTML/CSS/JS** frontend.

---

## 📁 File Structure

```
spy-game/
├── server.py          # Flask + SocketIO backend
├── requirements.txt   # Python dependencies
├── games.json         # Auto-created on first run
└── client/
    └── index.html     # Full frontend (HTML + CSS + JS)
```

---

## ⚙️ Requirements

- **Python 3.8+**
- pip

---

## 🚀 Quick Start

### 1. Clone / download the project
```bash
cd spy-game
```

### 2. (Recommended) Create a virtual environment
```bash
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the server
```bash
python server.py
```

### 5. Open the game
Visit **http://localhost:5050** in your browser.

---

## 🎮 How to Play

### Setup
1. One player opens the site and clicks **Create New Game**
2. A 6-character **Game ID** appears — share it with friends
3. Other players enter their name + the Game ID and click **Join Game**
4. All players appear in the lobby in real-time (min 3, max 10)

### Starting a Round
1. The **Host** sees the control panel
2. Host selects a **Spy** from the dropdown
3. Host types a **Secret Word** (e.g. "Pizza")
4. Host clicks **Start Round**

### Roles
- **Agents** see: their secret word glowing on screen
- **The Spy** sees: "You are the spy." — they don't know the word

### In Real Life (no app needed)
- Everyone says one word or phrase that hints at the secret word (without saying it)
- Players vote on who they think the spy is
- The spy tries to blend in without knowing the word

### New Round
- Host clicks **New Round** to reset
- Same players stay — choose a new spy and word

---

## 🌐 Multiplayer on a Local Network

To let other devices on your WiFi join:

1. Find your local IP:
   - macOS/Linux: `ifconfig | grep "inet "`
   - Windows: `ipconfig`
2. Share: `http://YOUR_LOCAL_IP:5050`
3. Other devices on the same network can join

---

## 🔧 Dependencies

| Package         | Version  | Purpose                        |
|----------------|----------|--------------------------------|
| flask           | ≥3.0.0   | Web framework                  |
| flask-socketio  | ≥5.3.6   | WebSocket / real-time events   |
| eventlet        | ≥0.35.2  | Async server for SocketIO      |

---

## 🎨 Tech Stack

| Layer     | Tech                        |
|-----------|-----------------------------|
| Backend   | Python · Flask · Flask-SocketIO |
| Frontend  | HTML · CSS · Vanilla JS     |
| Storage   | JSON file (games.json)      |
| Real-time | WebSockets via Socket.IO    |
| Fonts     | Orbitron · Share Tech Mono · Exo 2 |

---

## 💡 Notes

- No database needed — all state lives in `games.json`
- If the host disconnects, the next player becomes host automatically
- Empty rooms are cleaned up automatically on disconnect
- Works on mobile browsers — fully responsive
