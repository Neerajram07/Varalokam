# Varalokam Backend

A Python-based real-time multiplayer drawing and guessing game server (like Skribbl.io).

---

## Tech Stack

| Technology | Purpose |
|------------|---------|
| **Python 3.12+** + `aiohttp` | Async HTTP server |
| **python-socketio** | Real-time WebSocket communication (Socket.IO protocol) |
| **Redis** | Ephemeral game state — rooms, players, turns(optional for single-server) |
| **DynamoDB** | Persistent data — user profiles, leaderboards (optional for MVP) |
| **Nginx** | Reverse proxy with WebSocket support |
| **Let's Encrypt** | Free SSL certificates |

---

## How It Works (Architecture)

```
┌─────────────────────┐         ┌──────────────────────────────┐
│   YOUR FRONTEND     │         │   EC2 INSTANCE (Backend)     │
│  (hosted anywhere)  │         │                              │
│                     │  wss:// │  ┌────────┐   ┌───────────┐  │
│  socket.io-client ──┼────────►│  │ Nginx  │──►│ aiohttp + │  │
│                     │         │  │ :443   │   │ socketio  │  │
│  HTML/CSS/JS        │         │  └────────┘   │ :8080     │  │
│  Canvas Drawing     │         │               └─────┬─────┘  │
│  Chat UI            │         │                     │        │
└─────────────────────┘         │               ┌─────▼─────┐  │
                                │               │   Redis   │  │
  Frontend can be hosted on:    │               │ (on same  │  │
  • Netlify                     │               │  server)  │  │
  • Vercel                      │               └───────────┘  │
  • S3 + CloudFront             └──────────────────────────────┘
  • GitHub Pages
  • Your own server
  • Even local files!
```

**Key Point:** Your frontend and backend are completely separate. Deploy the backend → get a URL → plug it into your frontend. That's it.

---

## Quick Start (Local Development)

### Option 1: Docker Compose (Recommended)
```bash
docker-compose up --build
```
Server starts at `http://localhost:8080`

### Option 2: Manual Setup (Windows)
```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy and edit environment file
copy .env.example .env

# 4. Run the server (Redis is optional for local dev)
python -m src.main
```

### Option 3: Manual Setup (Linux/Mac)
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m src.main
```

### Verify It's Working
```bash
# Health check
curl http://localhost:8080/health
# Should return: {"status": "healthy", "service": "varalokam", "rooms": 0, "players": 0}

# Server stats
curl http://localhost:8080/stats
```

---

## 🔌 Connecting Your Frontend (Step-by-Step)

This is the most important section. After you deploy the backend, here's exactly how to connect your frontend.

### Step 1: Add Socket.IO Client Library

Add this script tag in your HTML `<head>` or before `</body>`:

```html
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
```

Or if you're using npm:
```bash
npm install socket.io-client
```
```javascript
import { io } from "socket.io-client";
```

### Step 2: Connect to Your Server

```javascript
// ═══════════════════════════════════════════════════════════
//  Replace this URL with your actual deployed server URL
// ═══════════════════════════════════════════════════════════

// Local development:
const socket = io("http://localhost:8080");

// After deploying to EC2 (replace with your actual URL):
// const socket = io("https://yourdomain.com");
// OR if using IP directly:
// const socket = io("http://YOUR_EC2_PUBLIC_IP:8080");

// ── Connection events ────────────────────────────────────
socket.on("connect", () => {
    console.log("✅ Connected to server! SID:", socket.id);
});

socket.on("disconnect", (reason) => {
    console.log("❌ Disconnected:", reason);
});

socket.on("connect_error", (err) => {
    console.log("❌ Connection failed:", err.message);
});

// Welcome message from server
socket.on("connected", (data) => {
    console.log(data.message); // "Welcome to Varalokam! 🎨"
});
```

### Step 3: Room Management

```javascript
// ═══════════════════════════════════════════════════════════
//  CREATE a room (you become the host)
// ═══════════════════════════════════════════════════════════
function createRoom(playerName) {
    socket.emit("room_create", {
        playerName: playerName,      // Your display name
        avatar: "😀",                // Emoji avatar
        settings: {
            maxPlayers: 8,           // 2-12 players
            rounds: 3,              // 1-10 rounds
            turnDuration: 80,       // 30-180 seconds per turn
            customWords: [],        // Optional custom words
            useCustomWordsOnly: false
        }
    });
}

// Listen for room creation response
socket.on("room_created", (data) => {
    if (data.success) {
        const roomCode = data.room.code;  // e.g., "ABC123"
        console.log("Room created! Code:", roomCode);
        console.log("Share this code with friends!");

        // data.room contains:
        // {
        //   code: "ABC123",
        //   hostSid: "your-socket-id",
        //   maxPlayers: 8,
        //   roundsTotal: 3,
        //   turnDuration: 80,
        //   status: "waiting",
        //   players: [ { sid, name, avatar, score, hasGuessed, isConnected } ],
        //   scoreboard: [ { name, score, avatar, sid } ]
        // }
    }
});

// ═══════════════════════════════════════════════════════════
//  JOIN a room using a code
// ═══════════════════════════════════════════════════════════
function joinRoom(roomCode, playerName) {
    socket.emit("room_join", {
        roomCode: roomCode,          // "ABC123"
        playerName: playerName,
        avatar: "🎮"
    });
}

socket.on("room_joined", (data) => {
    if (data.success) {
        console.log("Joined room:", data.room.code);
        console.log("Players:", data.room.players);
    }
});

// ═══════════════════════════════════════════════════════════
//  LEAVE a room
// ═══════════════════════════════════════════════════════════
function leaveRoom() {
    socket.emit("room_leave");
}

// ═══════════════════════════════════════════════════════════
//  Listen for other players joining/leaving
// ═══════════════════════════════════════════════════════════
socket.on("room_player_joined", (data) => {
    console.log(`${data.player.name} joined! (${data.playerCount} players)`);
    // Update your player list UI
});

socket.on("room_player_left", (data) => {
    console.log(`${data.playerName} left! (${data.playerCount} players)`);
    // data.players has the updated player list
    // data.newHostSid tells you who the new host is
});

socket.on("room_error", (data) => {
    alert(data.message);
    // Possible errors: "Room not found", "Room is full",
    // "Game already in progress", "Name already taken in this room"
});

// ═══════════════════════════════════════════════════════════
//  UPDATE room settings (host only)
// ═══════════════════════════════════════════════════════════
function updateSettings(settings) {
    socket.emit("room_settings", {
        maxPlayers: 8,
        rounds: 3,
        turnDuration: 80
    });
}

socket.on("room_settings_updated", (data) => {
    console.log("Settings updated:", data.room);
});

// ═══════════════════════════════════════════════════════════
//  KICK a player (host only)
// ═══════════════════════════════════════════════════════════
function kickPlayer(targetSid) {
    socket.emit("room_kick", { targetSid: targetSid });
}

socket.on("room_kicked", (data) => {
    alert(data.message); // "You were kicked from the room"
});
```

### Step 4: Game Flow

```javascript
// ═══════════════════════════════════════════════════════════
//  START the game (host only, minimum 2 players)
// ═══════════════════════════════════════════════════════════
function startGame() {
    socket.emit("game_start");
}

socket.on("game_started", (data) => {
    console.log(`Game started! Round ${data.round}/${data.totalRounds}`);
    console.log("Players:", data.players);
    // Switch your UI from lobby → game screen
});

socket.on("game_error", (data) => {
    alert(data.message);
    // "Only the host can start the game"
    // "Need at least 2 players to start"
});

// ═══════════════════════════════════════════════════════════
//  WORD SELECTION — drawer chooses a word
// ═══════════════════════════════════════════════════════════

// This event is sent ONLY to the current drawer
socket.on("game_word_choices", (data) => {
    console.log("Choose a word:", data.words);  // ["cat", "rocket", "butterfly"]
    console.log("You have", data.timeout, "seconds to choose");

    // Show 3 word buttons in your UI
    // If the drawer doesn't choose in time, server auto-picks one
});

// This is sent to everyone EXCEPT the drawer
socket.on("game_choosing_word", (data) => {
    console.log(`${data.drawerName} is choosing a word...`);
    // Show a waiting screen: "Alice is choosing a word..."
});

function selectWord(word) {
    socket.emit("game_word_selected", { word: word });
}

// ═══════════════════════════════════════════════════════════
//  TURN START — drawing begins!
// ═══════════════════════════════════════════════════════════
socket.on("game_turn_start", (data) => {
    if (data.isDrawer) {
        // YOU are drawing
        console.log("Your turn! Draw:", data.word);    // "cat"
        // Show the canvas with drawing tools
        // Enable drawing on the canvas
    } else {
        // YOU are guessing
        console.log(`${data.drawerName} is drawing!`);
        console.log("Word length:", data.wordLength);   // 3
        console.log("Hint:", data.hint);                 // "_ _ _"
        // Show the canvas (view only)
        // Show the chat input for guessing
    }

    console.log("Time:", data.duration, "seconds");
    console.log("Round:", data.round);
});

// ═══════════════════════════════════════════════════════════
//  TIMER — countdown updates (every 5 seconds)
// ═══════════════════════════════════════════════════════════
socket.on("game_timer", (data) => {
    console.log(`⏱️ ${data.remaining}s / ${data.total}s`);
    // Update your timer UI
});

// ═══════════════════════════════════════════════════════════
//  HINTS — progressive letter reveals
// ═══════════════════════════════════════════════════════════
socket.on("game_hint", (data) => {
    console.log("Hint:", data.hint);  // "c _ _" → "c a _"
    // Update the hint display in your UI
});

// ═══════════════════════════════════════════════════════════
//  CORRECT GUESS — someone guessed it!
// ═══════════════════════════════════════════════════════════
socket.on("game_correct_guess", (data) => {
    console.log(`🎉 ${data.playerName} guessed it! +${data.score}pts`);
    console.log(`Total score: ${data.totalScore}`);
    // Show a celebration animation
    // Update the scoreboard
});

// ═══════════════════════════════════════════════════════════
//  TURN END — word is revealed
// ═══════════════════════════════════════════════════════════
socket.on("game_turn_end", (data) => {
    console.log(`Turn over! The word was: "${data.word}"`);
    console.log("Reason:", data.reason);  // "timeout" | "all_guessed" | "drawer_left"
    console.log("Scoreboard:", data.scoreboard);
    // [{ name: "Alice", score: 450, avatar: "😀" }, ...]
    // Show the word reveal screen for 5 seconds
});

// ═══════════════════════════════════════════════════════════
//  ROUND CHANGE
// ═══════════════════════════════════════════════════════════
socket.on("game_round_change", (data) => {
    console.log(`Round ${data.round}/${data.totalRounds}`);
    // Show a round transition screen
});

// ═══════════════════════════════════════════════════════════
//  GAME OVER — show final results!
// ═══════════════════════════════════════════════════════════
socket.on("game_over", (data) => {
    console.log("🏆 GAME OVER!");
    console.log("Winner:", data.winner);        // { name: "Alice", score: 1250, ... }
    console.log("Scoreboard:", data.scoreboard);
    // Show the final scoreboard with winner animation
});

// ═══════════════════════════════════════════════════════════
//  PLAY AGAIN (host only — resets to lobby)
// ═══════════════════════════════════════════════════════════
function playAgain() {
    socket.emit("game_play_again");
}

socket.on("game_reset", (data) => {
    console.log("Game reset! Back to lobby");
    // Switch UI back to lobby
});

socket.on("game_cancelled", (data) => {
    console.log("Game cancelled:", data.message);
    // "Not enough players to continue"
});
```

### Step 5: Drawing (Canvas)

```javascript
// ═══════════════════════════════════════════════════════════
//  SEND drawing strokes to the server
//  (Only works if you are the current drawer)
//
//  IMPORTANT: Normalize coordinates to 0-1 range
//  so the drawing looks the same on all screen sizes!
// ═══════════════════════════════════════════════════════════

// Example: Hook into your canvas mouse events
const canvas = document.getElementById("drawingCanvas");
const ctx = canvas.getContext("2d");
let isDrawing = false;

canvas.addEventListener("mousedown", (e) => {
    isDrawing = true;
    const x = e.offsetX / canvas.width;   // Normalize to 0-1
    const y = e.offsetY / canvas.height;  // Normalize to 0-1

    socket.emit("draw_stroke", {
        x: x,
        y: y,
        color: "#FF0000",      // Current brush color
        size: 5,               // Brush size (1-50)
        tool: "pen",           // "pen" | "eraser"
        type: "start"          // "start" = beginning of a stroke
    });
});

canvas.addEventListener("mousemove", (e) => {
    if (!isDrawing) return;
    const x = e.offsetX / canvas.width;
    const y = e.offsetY / canvas.height;

    socket.emit("draw_stroke", {
        x: x,
        y: y,
        color: "#FF0000",
        size: 5,
        tool: "pen",
        type: "move"           // "move" = continuing the stroke
    });
});

canvas.addEventListener("mouseup", () => {
    isDrawing = false;
    socket.emit("draw_stroke", { type: "end" });
});

// ═══════════════════════════════════════════════════════════
//  RECEIVE drawing strokes from the server
//  (Render other player's drawings on your canvas)
// ═══════════════════════════════════════════════════════════
socket.on("draw_stroke", (data) => {
    // Convert normalized coordinates back to canvas pixels
    const x = data.x * canvas.width;
    const y = data.y * canvas.height;

    if (data.type === "start") {
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.strokeStyle = data.color;
        ctx.lineWidth = data.size;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
    } else if (data.type === "move") {
        ctx.lineTo(x, y);
        ctx.stroke();
    } else if (data.type === "end") {
        ctx.closePath();
    }
});

// ═══════════════════════════════════════════════════════════
//  CLEAR canvas / UNDO / FILL
// ═══════════════════════════════════════════════════════════
function clearCanvas() {
    socket.emit("draw_clear");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
}

function undoStroke() {
    socket.emit("draw_undo");
}

function fillCanvas(color) {
    socket.emit("draw_fill", { color: color });
}

// Other players receive these:
socket.on("draw_clear", () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
});

socket.on("draw_fill", (data) => {
    ctx.fillStyle = data.color;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
});

socket.on("draw_history", (data) => {
    // Re-render the entire drawing history
    // Used after undo or when a player joins mid-game
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    data.history.forEach((stroke) => {
        // Re-render each stroke...
    });
});
```

### Step 6: Chat & Guessing

```javascript
// ═══════════════════════════════════════════════════════════
//  SEND a chat message (also used for guessing!)
//  The server automatically checks if your message
//  matches the current word.
// ═══════════════════════════════════════════════════════════
const chatInput = document.getElementById("chatInput");

chatInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
        socket.emit("chat_message", {
            message: chatInput.value
        });
        chatInput.value = "";
    }
});

// ═══════════════════════════════════════════════════════════
//  RECEIVE chat messages
// ═══════════════════════════════════════════════════════════
socket.on("chat_message", (data) => {
    // data.type can be:
    //   "chat"         → normal chat message
    //   "close"        → player's guess was close (censored)
    //   "guessed_chat" → chat from a player who already guessed

    const chatBox = document.getElementById("chatBox");
    chatBox.innerHTML += `
        <div class="chat-msg">
            <span class="avatar">${data.avatar}</span>
            <strong>${data.playerName}:</strong> ${data.message}
        </div>
    `;
});

// System messages (correct guess announcements, etc.)
socket.on("chat_system", (data) => {
    // data.type can be:
    //   "correct_guess" → "🎉 Alice guessed the word!"
    //   "close_guess"   → "Alice is close!"

    const chatBox = document.getElementById("chatBox");
    chatBox.innerHTML += `
        <div class="chat-system">${data.message}</div>
    `;
});
```

---

## Complete Socket.IO Events Reference

### Room Events

| Direction | Event | Payload | Description |
|-----------|-------|---------|-------------|
| Client → Server | `room_create` | `{playerName, avatar, settings: {maxPlayers, rounds, turnDuration, customWords, useCustomWordsOnly}}` | Create a new room |
| Client → Server | `room_join` | `{roomCode, playerName, avatar}` | Join a room by code |
| Client → Server | `room_leave` | — | Leave current room |
| Client → Server | `room_settings` | `{maxPlayers?, rounds?, turnDuration?, customWords?, useCustomWordsOnly?}` | Update settings (host only) |
| Client → Server | `room_kick` | `{targetSid}` | Kick a player (host only) |
| Server → Client | `room_created` | `{success, room}` | Room created successfully |
| Server → Client | `room_joined` | `{success, room}` | Joined room successfully |
| Server → Client | `room_player_joined` | `{player, playerCount}` | A new player joined |
| Server → Client | `room_player_left` | `{playerName, playerSid, newHostSid, playerCount, players, disconnected?, kicked?}` | A player left |
| Server → Client | `room_settings_updated` | `{room}` | Settings were changed |
| Server → Client | `room_error` | `{message}` | Error message |
| Server → Client | `room_kicked` | `{message}` | You were kicked |
| Server → Client | `room_left` | `{success}` | You left the room |

### Game Events

| Direction | Event | Payload | Description |
|-----------|-------|---------|-------------|
| Client → Server | `game_start` | — | Start game (host only) |
| Client → Server | `game_word_selected` | `{word}` | Drawer picks a word |
| Client → Server | `game_play_again` | — | Restart (host only) |
| Server → Client | `game_started` | `{round, totalRounds, players}` | Game started |
| Server → Client | `game_word_choices` | `{words: [str, str, str], timeout}` | Word options (drawer only) |
| Server → Client | `game_choosing_word` | `{drawerName, drawerSid, round, totalRounds}` | Drawer is picking |
| Server → Client | `game_turn_start` | `{isDrawer, word?, wordLength, hint, duration, drawerName, drawerSid, round}` | Turn begins (`word` only sent to drawer) |
| Server → Client | `game_timer` | `{remaining, total}` | Timer tick (every 5 seconds) |
| Server → Client | `game_hint` | `{hint, hintsGiven}` | Hint letter revealed |
| Server → Client | `game_correct_guess` | `{playerName, playerSid, score, totalScore, guessOrder}` | Someone guessed correctly |
| Server → Client | `game_turn_end` | `{word, reason, scoreboard, drawerBonus}` | Turn ended |
| Server → Client | `game_round_change` | `{round, totalRounds, scoreboard}` | New round starting |
| Server → Client | `game_over` | `{scoreboard, winner}` | Game finished |
| Server → Client | `game_reset` | `{room}` | Game reset to lobby |
| Server → Client | `game_cancelled` | `{message}` | Game cancelled (not enough players) |
| Server → Client | `game_error` | `{message}` | Game error |

### Drawing Events

| Direction | Event | Payload | Description |
|-----------|-------|---------|-------------|
| Client → Server | `draw_stroke` | `{x, y, color, size, tool, type}` | Drawing data (high frequency) |
| Client → Server | `draw_clear` | — | Clear canvas |
| Client → Server | `draw_undo` | — | Undo last stroke |
| Client → Server | `draw_fill` | `{color}` | Fill canvas with color |
| Client → Server | `draw_request_history` | — | Request drawing history (reconnection) |
| Server → Client | `draw_stroke` | `{x, y, color, size, tool, type}` | Receive drawing data |
| Server → Client | `draw_clear` | `{}` | Canvas was cleared |
| Server → Client | `draw_fill` | `{color}` | Canvas was filled |
| Server → Client | `draw_history` | `{history: [...strokes]}` | Full drawing history |

### Chat Events

| Direction | Event | Payload | Description |
|-----------|-------|---------|-------------|
| Client → Server | `chat_message` | `{message}` | Send chat / guess |
| Server → Client | `chat_message` | `{playerName, message, type, avatar}` | Chat message (`type`: "chat", "close", "guessed_chat") |
| Server → Client | `chat_system` | `{message, type}` | System message (`type`: "correct_guess", "close_guess") |

### Connection Events

| Direction | Event | Payload | Description |
|-----------|-------|---------|-------------|
| Server → Client | `connected` | `{sid, message}` | Welcome message |

---

## Game Flow Diagram

```
 ┌──────────────────────────────────────────────────┐
 │                    LOBBY                          │
 │  • Players join with room code                   │
 │  • Host configures settings                      │
 │  • Host clicks "Start" (min 2 players)           │
 └────────────────────┬─────────────────────────────┘
                      │ game_start
                      ▼
 ┌──────────────────────────────────────────────────┐
 │              WORD SELECTION (15s)                 │
 │  • Drawer sees 3 word choices                    │
 │  • Others see "Player is choosing a word..."     │
 │  • Auto-picks if timeout                         │
 └────────────────────┬─────────────────────────────┘
                      │ game_word_selected
                      ▼
 ┌──────────────────────────────────────────────────┐
 │              DRAWING PHASE (80s)                  │
 │  • Drawer draws on canvas → strokes broadcast   │
 │  • Guessers type in chat → auto-checked         │
 │  • Hints revealed progressively                  │
 │  • Timer counts down                             │
 │  • Early end if all players guess correctly      │
 └──────────┬──────────────────┬────────────────────┘
            │ timer expires    │ all guessed
            ▼                  ▼
 ┌──────────────────────────────────────────────────┐
 │              TURN REVEAL (5s)                     │
 │  • Word is revealed to everyone                  │
 │  • Scores shown                                  │
 └────────────────────┬─────────────────────────────┘
                      │
          ┌───────────┴───────────┐
          │                       │
    More players            All players
    to draw?                have drawn?
          │                       │
          ▼                       ▼
   Back to WORD            ┌────────────────┐
   SELECTION               │   ROUND END    │
                           └───────┬────────┘
                                   │
                         ┌─────────┴─────────┐
                         │                   │
                    More rounds?        Final round?
                         │                   │
                         ▼                   ▼
                  Back to WORD        ┌──────────────┐
                  SELECTION           │  GAME OVER   │
                                      │  🏆 Winner!  │
                                      └──────────────┘
```

## Scoring System

| Who | How | Points |
|-----|-----|--------|
| **Guesser** | Based on speed (faster = more) | 100-500 pts |
| **Guesser** | First guess bonus | +50 pts |
| **Guesser** | Second guess bonus | +30 pts |
| **Guesser** | Third guess bonus | +10 pts |
| **Drawer** | Per correct guesser | +50 pts each |
| **Drawer** | Everyone guessed bonus | +100 pts |
| **Drawer** | Majority bonus (>50% guessed) | 1.2x multiplier |
| **Drawer** | Maximum cap | 500 pts max |

---

## 🚀 Deployment to AWS EC2 (Complete Guide)

### Prerequisites
- An AWS account (free tier eligible)
- A GitHub repository with your backend code (or you'll SCP the files)

---

### Step 1: AWS Account Setup (Do This First!)

```
1. Log into AWS Console: https://console.aws.amazon.com

2. SET UP BILLING ALERTS (very important!):
   → Go to "Billing and Cost Management"
   → Click "Budgets" in the left sidebar
   → Create a budget:
     • Budget type: Cost budget
     • Budget amount: $5 (or whatever you're comfortable with)
     • Alert at: 80% ($4)
     • Email: your email
   
3. ENABLE MFA on your root account:
   → Go to IAM
   → Click your account name → Security credentials
   → Set up MFA (use Google Authenticator)
```

---

### Step 2: Launch an EC2 Instance

```
1. Go to EC2 Dashboard → "Launch Instance"

2. Configuration:
   • Name: "varalokam-server"
   • AMI: Ubuntu Server 22.04 LTS (Free Tier eligible)
   • Instance type: t2.micro (Free Tier) or t3.micro
   • Key pair: Create a new key pair
     → Name: "varalokam-key"
     → Type: RSA
     → Format: .pem
     → DOWNLOAD AND SAVE THIS FILE! You cannot download it again.
   
3. Network settings → Click "Edit":
   • Auto-assign public IP: Enable
   • Security Group: Create new
     → Name: "varalokam-sg"
     → Add these rules:
     
     ┌──────────┬──────────┬─────────────────┬─────────────────┐
     │ Type     │ Port     │ Source          │ Purpose         │
     ├──────────┼──────────┼─────────────────┼─────────────────┤
     │ SSH      │ 22       │ My IP           │ Your SSH access │
     │ HTTP     │ 80       │ 0.0.0.0/0       │ Web traffic     │
     │ HTTPS    │ 443      │ 0.0.0.0/0       │ SSL traffic     │
     │ Custom   │ 8080     │ 0.0.0.0/0       │ Direct access   │
     └──────────┴──────────┴─────────────────┴─────────────────┘

4. Storage: 8 GB gp3 (Free Tier gives up to 30GB)

5. Click "Launch Instance"

6. Note your PUBLIC IP ADDRESS from the instance details page.
   Example: 13.235.xx.xx
```

---

### Step 3: Connect to Your EC2 Instance via SSH

```bash
# On Windows (PowerShell):
ssh -i "C:\path\to\varalokam-key.pem" ubuntu@YOUR_EC2_PUBLIC_IP

# On Mac/Linux:
chmod 400 varalokam-key.pem
ssh -i varalokam-key.pem ubuntu@YOUR_EC2_PUBLIC_IP

# If you get "UNPROTECTED PRIVATE KEY FILE" error on Windows:
# Right-click the .pem file → Properties → Security → Advanced
# Remove all users except your own. Set your permission to "Full Control".
```

---

### Step 4: Install Everything on EC2

Run these commands one by one after SSHing in:

```bash
# ── 1. Update system ─────────────────────────────────────
sudo apt update && sudo apt upgrade -y

# ── 2. Install Python 3.12 ──────────────────────────────
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev python3-pip git

# ── 3. Install Redis ────────────────────────────────────
sudo apt install -y redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
redis-cli ping
# Should print: PONG

# ── 4. Install Nginx ────────────────────────────────────
sudo apt install -y nginx
sudo systemctl enable nginx

# ── 5. Install Certbot (for free SSL) ───────────────────
sudo apt install -y certbot python3-certbot-nginx
```

---

### Step 5: Upload Your Backend Code

**Option A: Using Git (recommended)**
```bash
cd /opt
sudo mkdir varalokam
sudo chown ubuntu:ubuntu varalokam
cd varalokam

# Clone your repo
git clone https://github.com/YOUR_USERNAME/varalokam.git .
# OR just the backend:
# git clone https://github.com/YOUR_USERNAME/varalokam.git
```

**Option B: Using SCP (copy files from your PC)**
```bash
# Run this on YOUR PC (not on EC2):
scp -i "varalokam-key.pem" -r "D:\Standalone Project\Varalokam\backend" ubuntu@YOUR_EC2_IP:/opt/varalokam/backend
```

---

### Step 6: Set Up the Application

```bash
cd /opt/varalokam/backend

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file
cp .env.example .env
nano .env
```

**Edit the .env file with these values:**
```bash
HOST=0.0.0.0
PORT=8080
DEBUG=false
CORS_ORIGINS=https://your-frontend-url.com,http://your-frontend-url.com

REDIS_URL=redis://localhost:6379/0

# Leave these empty for now (MVP without persistent storage)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AUTH_ENABLED=false
```

**Quick test — make sure it starts:**
```bash
python -m src.main
# You should see:
# ════════════════════════════════════════════════════════
#   🎨  VARALOKAM — Draw & Guess Game Server
# ════════════════════════════════════════════════════════
#   Host:   0.0.0.0
#   Port:   8080

# Press Ctrl+C to stop the test
```

---

### Step 7: Create a Systemd Service (Auto-start on Boot)

```bash
sudo nano /etc/systemd/system/varalokam.service
```

Paste this content:
```ini
[Unit]
Description=Varalokam Game Server
After=network.target redis-server.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/varalokam/backend
Environment=PATH=/opt/varalokam/backend/venv/bin:/usr/bin
ExecStart=/opt/varalokam/backend/venv/bin/python -m src.main
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable varalokam
sudo systemctl start varalokam

# Check if it's running
sudo systemctl status varalokam
# Should show: "active (running)"

# View live logs
sudo journalctl -u varalokam -f
# Press Ctrl+C to exit logs
```

---

### Step 8: Configure Nginx (Reverse Proxy)

```bash
sudo nano /etc/nginx/sites-available/varalokam
```

Paste this content:
```nginx
# Rate limiting
limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;

upstream varalokam_backend {
    server 127.0.0.1:8080;
    keepalive 64;
}

server {
    listen 80;
    server_name YOUR_DOMAIN_OR_IP;  # Replace with your domain or EC2 IP

    # WebSocket / Socket.IO
    location /socket.io/ {
        proxy_pass http://varalokam_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
        proxy_buffering off;
    }

    # Health check
    location /health {
        proxy_pass http://varalokam_backend;
        proxy_set_header Host $host;
        limit_req zone=api burst=5 nodelay;
    }

    # Stats
    location /stats {
        proxy_pass http://varalokam_backend;
        proxy_set_header Host $host;
        limit_req zone=api burst=5 nodelay;
    }

    # Default
    location / {
        proxy_pass http://varalokam_backend;
        proxy_set_header Host $host;
    }

    gzip on;
    gzip_types text/plain text/css application/json application/javascript;
}
```

```bash
# Enable the site
sudo ln -sf /etc/nginx/sites-available/varalokam /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test config
sudo nginx -t
# Should say: "syntax is ok" and "test is successful"

# Restart Nginx
sudo systemctl restart nginx
```

---

### Step 9: Test Your Deployment

```bash
# From your PC, test the health endpoint:
curl http://YOUR_EC2_PUBLIC_IP/health

# Expected:
# {"status": "healthy", "service": "varalokam", "rooms": 0, "players": 0}
```

🎉 **If you see that response, your backend is live!**

Now in your frontend, connect to it:
```javascript
const socket = io("http://YOUR_EC2_PUBLIC_IP");
```

---

### Step 10: Set Up SSL with Free Certificate (Optional but Recommended)

If you have a domain name:
```bash
# Point your domain's DNS A record to your EC2 public IP first!
# Then run:
sudo certbot --nginx -d yourdomain.com

# Follow the prompts:
# - Enter your email
# - Accept the terms
# - Choose to redirect HTTP to HTTPS (recommended)

# Certbot auto-renews. Test it:
sudo certbot renew --dry-run
```

After SSL, your frontend connects via:
```javascript
const socket = io("https://yourdomain.com");
```

If you don't have a domain, you can still use HTTP with the IP address.

---

### Step 11: Set Up CORS for Your Frontend

Edit the .env on EC2 to allow your frontend's URL:
```bash
sudo nano /opt/varalokam/backend/.env
```

```bash
# If your frontend is on Netlify:
CORS_ORIGINS=https://your-app.netlify.app

# If on Vercel:
CORS_ORIGINS=https://your-app.vercel.app

# Multiple origins (comma-separated):
CORS_ORIGINS=https://your-app.netlify.app,http://localhost:3000

# Allow everything (development only, NOT for production):
# Set DEBUG=true in .env
```

```bash
# Restart after changing .env
sudo systemctl restart varalokam
```

---

## Useful Commands (After Deployment)

```bash
# ── Server Management ────────────────────────────────────
sudo systemctl status varalokam     # Check if running
sudo systemctl restart varalokam    # Restart server
sudo systemctl stop varalokam       # Stop server
sudo journalctl -u varalokam -f     # Live logs
sudo journalctl -u varalokam -n 50  # Last 50 log lines

# ── Nginx ─────────────────────────────────────────────────
sudo systemctl restart nginx        # Restart Nginx
sudo nginx -t                       # Test config
sudo tail -f /var/log/nginx/error.log   # Nginx error logs

# ── Redis ─────────────────────────────────────────────────
redis-cli ping                      # Test Redis
redis-cli monitor                   # Watch all Redis commands

# ── Update Code ──────────────────────────────────────────
cd /opt/varalokam/backend
git pull                            # Pull latest code
sudo systemctl restart varalokam    # Restart
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **Can't connect from frontend** | Check CORS_ORIGINS in `.env`, restart server |
| **WebSocket connection fails** | Make sure Nginx config has the `proxy_set_header Upgrade` lines |
| **"502 Bad Gateway"** | Python server crashed. Check: `sudo journalctl -u varalokam -n 20` |
| **Server won't start** | Check .env file. Try manually: `cd /opt/varalokam/backend && source venv/bin/activate && python -m src.main` |
| **"Room not found"** | Room codes expire when server restarts. Rooms only exist in memory. |
| **High latency** | Make sure your EC2 region is close to your users (ap-south-1 for India) |
| **Billed unexpectedly** | Check for running instances in ALL regions. Set up billing alerts! |

---

## Project Structure

```
backend/
├── src/
│   ├── main.py              # Server entry point (aiohttp + Socket.IO)
│   ├── config.py            # Environment configuration
│   ├── models/
│   │   ├── player.py        # Player data model
│   │   ├── room.py          # Room data model (players, state, serialization)
│   │   └── game.py          # Game state machine (transitions)
│   ├── services/
│   │   ├── room_manager.py  # In-memory room CRUD singleton
│   │   ├── word_service.py  # Word bank, hints, guess checking
│   │   ├── score_service.py # Time-based score calculations
│   │   └── dynamo_service.py# Optional DynamoDB persistence
│   ├── socket_handlers/
│   │   ├── room_handler.py  # Room create/join/leave/kick events
│   │   ├── game_handler.py  # Full game loop (timers, turns, rounds)
│   │   ├── draw_handler.py  # High-frequency drawing relay
│   │   └── chat_handler.py  # Chat messages + guess checking
│   └── data/
│       └── wordbank.json    # 300+ words (easy/medium/hard)
├── deploy/
│   ├── setup-ec2.sh         # EC2 provisioning script
│   └── nginx.conf           # Nginx reverse proxy config
├── test_client.html          # Interactive browser test tool
├── requirements.txt          # Python dependencies
├── Dockerfile                # Docker image
├── docker-compose.yml        # Docker Compose (local dev)
├── .env.example              # Environment variable template
└── README.md                 # This file
```

---

## Cost Estimate (AWS Free Tier)

| Service | Configuration | Monthly Cost |
|---------|--------------|-------------|
| EC2 | t2.micro (750 hrs/mo free for 12 months) | **$0** |
| Redis | Installed on EC2 (no ElastiCache) | **$0** |
| EBS | 8 GB gp3 (30 GB free) | **$0** |
| Data Transfer | Up to 100 GB/mo free | **$0** |
| **Total (Year 1)** | | **$0/month** |

After the free tier expires (Year 2+):
| Service | Cost |
|---------|------|
| EC2 t3.micro | ~$8/month |
| EBS 8 GB | ~$0.64/month |
| **Total** | **~$9/month** |

---

## License

MIT
