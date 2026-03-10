# 🕵️ SPY GAME — Railway Deployment Guide

A real-time multiplayer spy party game built with FastAPI + Socket.IO.

---

## 📁 Folder Structure

```
spy-game/
├── server/
│   ├── main.py           ← FastAPI + Socket.IO server
│   ├── game_manager.py   ← Game logic
│   ├── storage.py        ← JSON persistence (/tmp/games.json)
│   ├── games.json        ← Template (runtime data goes to /tmp)
│   └── requirements.txt  ← Python dependencies
└── client/
    ├── index.html        ← Single-page frontend
    ├── style.css         ← Dark cyberpunk UI
    └── app.js            ← Socket.IO client logic
```

---

## 🚀 Deploying to Railway

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "Initial spy game"
git remote add origin https://github.com/YOUR_USER/spy-game.git
git push -u origin main
```

### 2. Create Railway Project

1. Go to [railway.com](https://railway.com) → **New Project**
2. Select **Deploy from GitHub repo**
3. Choose your repository

### 3. Configure the Service

In Railway → your service → **Settings**:

| Setting | Value |
|---------|-------|
| **Root Directory** | `server` |
| **Start Command** | `uvicorn main:socket_app --host 0.0.0.0 --port $PORT` |

### 4. Environment Variables

Railway automatically injects `PORT`. No additional env vars required.

| Variable | Value | Notes |
|----------|-------|-------|
| `PORT`   | (auto) | Set by Railway automatically |

### 5. Generate Domain

In Railway → **Settings → Networking** → **Generate Domain**

Railway provides free HTTPS automatically (e.g. `your-app.up.railway.app`).

---

## 🛠 Running Locally

```bash
cd server
pip install -r requirements.txt

# Start on port 8000
uvicorn main:socket_app --host 0.0.0.0 --port 8000

# Open http://localhost:8000
```

---

## 🎮 How to Play

1. **Host** enters their codename + a secret word → clicks **CREATE GAME**
2. Share the 6-character game code with friends
3. Players enter the code → click **JOIN GAME**
4. Host clicks **START MISSION** (min. 2 players, max 10)
5. One random player becomes **THE SPY** — they don't see the secret word
6. Players discuss and try to identify the spy
7. Host clicks **REVEAL SPY** to end the round
8. Host can start a **NEW ROUND** (same players, new word)

---

## ⚙️ Railway-Specific Notes

- **Port**: Server reads `$PORT` env var (Railway injects this automatically)
- **Socket.IO path**: Client uses relative `/socket.io` — no hardcoded URLs
- **Storage**: Game data saved to `/tmp/games.json` (ephemeral, resets on redeploy)
- **HTTPS**: Provided automatically by Railway — no config needed
- **Static files**: Served by FastAPI from the `client/` directory

---

## 📦 Dependencies

```
fastapi==0.115.5
uvicorn[standard]==0.32.1
python-socketio==5.11.4
python-engineio==4.10.1
aiohttp==3.11.10
```
