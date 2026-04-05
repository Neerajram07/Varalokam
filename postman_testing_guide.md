# Varalokam — Postman Testing Guide

## 🔐 Authentication Status

> [!IMPORTANT]
> **NO Bearer Token is used.** The auth system is completely **disabled** by default.
> 
> In [config.py](file:///d:/Standalone%20Project/Varalokam/backend/src/config.py#L36), `AUTH_ENABLED` defaults to `"false"`. The JWT validation code in `main.py` (lines 69-73) is **commented out**. There is **no middleware** checking for tokens on any endpoint.
> 
> **You do NOT need to set any Authorization header, Bearer token, or API key.**

---

## 📡 Two Types of Endpoints

Your backend has:

| Type | Protocol | Can Test in Postman? |
|------|----------|---------------------|
| **REST API** (2 endpoints) | HTTP GET | ✅ Yes, directly |
| **Socket.IO Events** (14 events) | WebSocket (Socket.IO) | ⚠️ Requires Postman's **Socket.IO** feature or a separate tool |

> [!WARNING]
> Postman's standard HTTP request builder **cannot** test Socket.IO events. You need to use **Postman's Socket.IO client** (available in newer versions) or use the `test_client.html` file already in your repo, or a tool like [Hoppscotch](https://hoppscotch.io) or the [Socket.IO Admin UI](https://admin.socket.io/).

---

## Part 1: REST API Endpoints (Test with standard Postman HTTP requests)

### Base URL
```
http://localhost:8080
```

---

### 1️⃣ Health Check

| Field | Value |
|-------|-------|
| **Method** | `GET` |
| **URL** | `http://localhost:8080/health` |
| **Headers** | None required |
| **Body** | None |
| **Auth** | None |

**Expected Response** (`200 OK`):
```json
{
  "status": "healthy",
  "service": "varalokam",
  "rooms": 0,
  "players": 0
}
```

---

### 2️⃣ Server Stats

| Field | Value |
|-------|-------|
| **Method** | `GET` |
| **URL** | `http://localhost:8080/stats` |
| **Headers** | None required |
| **Body** | None |
| **Auth** | None |

**Expected Response** (`200 OK`):
```json
{
  "rooms": 0,
  "players": 0,
  "roomList": []
}
```

---

## Part 2: Socket.IO Events (Test with Postman Socket.IO or test_client.html)

### How to Set Up in Postman (Socket.IO)

1. Open Postman → Click **New** → Select **Socket.IO**
2. Set the URL to: `http://localhost:8080`
3. Click **Connect**
4. You should receive a `connected` event with your `sid`

> [!NOTE]
> When you connect, the server auto-emits this to you:
> ```json
> Event: "connected"
> {
>   "sid": "<your-socket-id>",
>   "message": "Welcome to Varalokam! 🎨"
> }
> ```

---

## 🔢 Execution Order for Full Game Flow Testing

Follow this exact order to test a complete game flow. You need **2 connected clients** (2 Postman Socket.IO tabs or the test_client.html for the 2nd player).

```
Step 1:  Connect Player 1          (auto - just connect)
Step 2:  Connect Player 2          (auto - just connect in 2nd tab)
Step 3:  room_create               (Player 1 creates room)
Step 4:  room_join                  (Player 2 joins with room code)
Step 5:  room_settings             (Optional - Player 1 updates settings)
Step 6:  game_start                (Player 1 starts the game)
Step 7:  game_word_selected        (Drawer picks a word)
Step 8:  draw_stroke               (Drawer sends drawing data)
Step 9:  chat_message              (Player 2 guesses the word)
Step 10: game_play_again           (Player 1 restarts — optional)
Step 11: room_leave                (Any player leaves)
```

---

## All Socket.IO Events — Detailed

### 📌 Step 3: `room_create` — Create a Room

| Field | Value |
|-------|-------|
| **Event Name** | `room_create` |
| **Sender** | Player 1 |

**Payload:**
```json
{
  "playerName": "Neeraj",
  "avatar": "😀",
  "settings": {
    "maxPlayers": 8,
    "rounds": 3,
    "turnDuration": 80,
    "customWords": [],
    "useCustomWordsOnly": false
  }
}
```

**Server Response Event:** `room_created`
```json
{
  "success": true,
  "room": {
    "code": "A1B2C3",
    "hostSid": "<player1-sid>",
    "maxPlayers": 8,
    "roundsTotal": 3,
    "turnDuration": 80,
    "status": "waiting",
    "isPublic": false,
    "autoStart": false,
    "currentRound": 0,
    "currentDrawerSid": null,
    "currentDrawerName": null,
    "hintRevealed": "",
    "wordLength": 0,
    "turnStartTime": 0,
    "players": [
      {
        "sid": "<player1-sid>",
        "name": "Neeraj",
        "avatar": "😀",
        "score": 0,
        "hasGuessed": false,
        "isConnected": true
      }
    ],
    "scoreboard": [...]
  }
}
```

> [!TIP]
> **Save the `code` from the response** (e.g., `"A1B2C3"`). Player 2 needs it to join.

---

### 📌 Step 4: `room_join` — Join a Room

| Field | Value |
|-------|-------|
| **Event Name** | `room_join` |
| **Sender** | Player 2 |

**Payload:**
```json
{
  "roomCode": "A1B2C3",
  "playerName": "Kumar",
  "avatar": "🎨"
}
```

**Server Response Events:**
- To Player 2 → `room_joined` (full room state)
- To Player 1 → `room_player_joined` (new player info)

**Error Response** (if invalid code): `room_error`
```json
{
  "message": "Room not found"
}
```

---

### 📌 Step 5 (Optional): `room_settings` — Update Room Settings

| Field | Value |
|-------|-------|
| **Event Name** | `room_settings` |
| **Sender** | Player 1 (Host only) |

**Payload:**
```json
{
  "maxPlayers": 6,
  "rounds": 5,
  "turnDuration": 60,
  "customWords": ["mango", "umbrella", "elephant"],
  "useCustomWordsOnly": false
}
```

**Server Response Event:** `room_settings_updated` (to all players in room)

---

### 📌 Step 6: `game_start` — Start the Game

| Field | Value |
|-------|-------|
| **Event Name** | `game_start` |
| **Sender** | Player 1 (Host only) |

**Payload:**
```json
{}
```
*(No payload needed, can also send `null`)*

**Server Response Events:**
- To all → `game_started`
```json
{
  "round": 1,
  "totalRounds": 3,
  "players": [...]
}
```
- To drawer → `game_word_choices` (3 word options)
- To others → `game_choosing_word` (who is choosing)

**Error Cases:**
```json
{"message": "Only the host can start the game"}
{"message": "Need at least 2 players to start"}
{"message": "Game is already in progress"}
```

---

### 📌 Step 7: `game_word_selected` — Drawer Picks a Word

| Field | Value |
|-------|-------|
| **Event Name** | `game_word_selected` |
| **Sender** | Current drawer only |

**Payload:**
```json
{
  "word": "elephant"
}
```
*(Must be one of the words from `game_word_choices`)*

**Server Response Events:**
- To drawer → `game_turn_start` with `isDrawer: true` and actual `word`
- To guessers → `game_turn_start` with `isDrawer: false` and `hint` (underscores)

> [!NOTE]
> If the drawer doesn't pick within **15 seconds**, the server auto-selects a random word.

---

### 📌 Step 8: `draw_stroke` — Send Drawing Data

| Field | Value |
|-------|-------|
| **Event Name** | `draw_stroke` |
| **Sender** | Current drawer only |

**Payload (single point):**
```json
{
  "x": 0.5,
  "y": 0.3,
  "color": "#FF0000",
  "size": 5,
  "tool": "pen",
  "type": "start"
}
```

**Payload (batch points):**
```json
{
  "points": [
    {"x": 0.5, "y": 0.3},
    {"x": 0.55, "y": 0.35},
    {"x": 0.6, "y": 0.4}
  ],
  "color": "#FF0000",
  "size": 5,
  "tool": "pen"
}
```

**`type` values:** `"start"` | `"move"` | `"end"`
**`tool` values:** `"pen"` | `"eraser"`

Server broadcasts `draw_stroke` to all other players.

---

### 📌 Step 9: `chat_message` — Send Chat / Guess

| Field | Value |
|-------|-------|
| **Event Name** | `chat_message` |
| **Sender** | Any player (guessers) |

**Payload:**
```json
{
  "message": "elephant"
}
```

**Possible Server Responses:**

| Scenario | Event Emitted |
|----------|--------------|
| Normal chat (no game) | `chat_message` with `type: "chat"` |
| Correct guess | `game_correct_guess` + `chat_system` |
| Close guess | `chat_system` with `type: "close_guess"` |
| Already guessed player | `chat_message` with `type: "guessed_chat"` (only visible to other guessed players + drawer) |

---

### 📌 Other Drawing Events

#### `draw_clear` — Clear Canvas
```json
// Event: draw_clear
// Payload: {} or null
// Sender: Drawer only
```

#### `draw_undo` — Undo Last Stroke
```json
// Event: draw_undo
// Payload: {} or null
// Sender: Drawer only
```

#### `draw_fill` — Fill Canvas
```json
// Event: draw_fill
{
  "color": "#FFFFFF"
}
// Sender: Drawer only
```

#### `draw_request_history` — Get Drawing History
```json
// Event: draw_request_history
// Payload: {} or null
// Sender: Any player (useful for reconnection)
```

---

### 📌 Step 10: `game_play_again` — Restart Game

| Field | Value |
|-------|-------|
| **Event Name** | `game_play_again` |
| **Sender** | Player 1 (Host only) |

**Payload:**
```json
{}
```

**Server Response:** `game_reset` with full room state

---

### 📌 Step 11: `room_leave` — Leave Room

| Field | Value |
|-------|-------|
| **Event Name** | `room_leave` |
| **Sender** | Any player |

**Payload:**
```json
{}
```

**Server Response Events:**
- To leaving player → `room_left`
- To remaining players → `room_player_left`

---

### 📌 `room_kick` — Kick a Player (Host Only)

| Field | Value |
|-------|-------|
| **Event Name** | `room_kick` |
| **Sender** | Host only |

**Payload:**
```json
{
  "targetSid": "<player-sid-to-kick>"
}
```

---

### 📌 `quick_play` — Quick Play / Matchmaking

| Field | Value |
|-------|-------|
| **Event Name** | `quick_play` |
| **Sender** | Any player |

**Payload:**
```json
{
  "playerName": "Neeraj",
  "avatar": "🎮"
}
```

**Server Response:** `quick_play_joined` with room state. Game auto-starts when 3+ players join.

---

## 📋 Complete Event Summary Table

| # | Event Name | Direction | Payload Required | Who Can Send |
|---|-----------|-----------|-----------------|-------------|
| 1 | `room_create` | Client → Server | ✅ | Any connected player |
| 2 | `room_join` | Client → Server | ✅ | Any connected player |
| 3 | `room_leave` | Client → Server | ❌ | Any player in a room |
| 4 | `room_settings` | Client → Server | ✅ | Host only |
| 5 | `room_kick` | Client → Server | ✅ | Host only |
| 6 | `quick_play` | Client → Server | ✅ | Any connected player |
| 7 | `game_start` | Client → Server | ❌ | Host only |
| 8 | `game_word_selected` | Client → Server | ✅ | Current drawer only |
| 9 | `game_play_again` | Client → Server | ❌ | Host only |
| 10 | `draw_stroke` | Client → Server | ✅ | Current drawer only |
| 11 | `draw_clear` | Client → Server | ❌ | Current drawer only |
| 12 | `draw_undo` | Client → Server | ❌ | Current drawer only |
| 13 | `draw_fill` | Client → Server | ✅ | Current drawer only |
| 14 | `draw_request_history` | Client → Server | ❌ | Any player in a room |
| 15 | `chat_message` | Client → Server | ✅ | Any player in a room |

---

## 🧪 Quick Alternative: Use test_client.html

Your repo already has a test client at [test_client.html](file:///d:/Standalone%20Project/Varalokam/backend/test_client.html). You can open it in a browser to test all Socket.IO events interactively without Postman.
