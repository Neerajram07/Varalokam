---
description: How to test all Varalokam backend APIs (REST + Socket.IO) using Postman
---

# Varalokam — Complete API Testing Workflow

## Prerequisites

1. **Python environment ready** with all dependencies installed
2. **Postman v10+** installed (Socket.IO support required)
3. Backend server running on `http://localhost:8080`

## Phase 0 — Start the Backend Server

```bash
cd d:\Standalone Project\Varalokam\backend
python -m src.main
```

You should see:
```
============================================================
  🎨  VARALOKAM — Draw & Guess Game Server
============================================================
  Host:   0.0.0.0
  Port:   8080
============================================================
```

> **No .env file needed for basic testing** — all defaults work out of the box.
> Auth is DISABLED by default. No Bearer tokens, no API keys.

---

## Phase 1 — REST API Testing (Standard Postman HTTP Requests)

These are simple GET requests. Create a new Postman **Collection** called `Varalokam` and add these:

### Test 1.1: Health Check

| Field      | Value                          |
|------------|--------------------------------|
| Method     | `GET`                          |
| URL        | `http://localhost:8080/health`  |
| Headers    | None                           |
| Body       | None                           |
| Auth       | None                           |

**Click Send →** Expected `200 OK`:
```json
{
  "status": "healthy",
  "service": "varalokam",
  "rooms": 0,
  "players": 0
}
```

✅ **PASS criteria**: Status is `healthy`, rooms and players are `0` when no one is connected.

---

### Test 1.2: Server Stats

| Field      | Value                          |
|------------|--------------------------------|
| Method     | `GET`                          |
| URL        | `http://localhost:8080/stats`   |
| Headers    | None                           |
| Body       | None                           |
| Auth       | None                           |

**Click Send →** Expected `200 OK`:
```json
{
  "rooms": 0,
  "players": 0,
  "roomList": []
}
```

✅ **PASS criteria**: Returns `0` rooms/players initially. After creating rooms via Socket.IO, this should reflect active rooms.

---

## Phase 2 — Socket.IO Testing Setup in Postman

> ⚠️ **IMPORTANT**: Standard Postman HTTP requests CANNOT test Socket.IO events.
> You MUST use Postman's **Socket.IO client** feature.

### Step-by-step setup:

1. Open Postman
2. Click **New** (top left) → Select **Socket.IO**
3. Set the URL to: `ws://localhost:8080/socket.io/?EIO=4&transport=websocket`
   - Or simply: `http://localhost:8080` and Postman will handle the upgrade
4. In the **Settings** tab next to the URL:
   - Set **Client version** to `v4`
   - Leave **Handshake path** as `/socket.io`
5. Click **Connect**

### Verify Connection:

After connecting, you should automatically receive a `connected` event in the **Messages** panel:

```json
Event: "connected"
{
  "sid": "abc123xyz...",
  "message": "Welcome to Varalokam! 🎨"
}
```

> 📋 **Copy the `sid` value** — you'll need it for some tests later.

### Adding Event Listeners in Postman

Before sending events, set up listeners so you can see server responses. In the **Events** tab at the bottom, add listeners for ALL these events:

```
connected
room_created
room_joined
room_player_joined
room_player_left
room_left
room_error
room_kicked
room_settings_updated
game_error
game_started
game_word_choices
game_choosing_word
game_turn_start
game_timer
game_hint
game_correct_guess
game_turn_end
game_round_change
game_over
game_reset
game_cancelled
draw_stroke
draw_clear
draw_fill
draw_history
chat_message
chat_system
quick_play_joined
quick_play_waiting
quick_play_countdown
quick_play_countdown_cancelled
```

> 💡 **TIP**: In Postman, look for "Listen on event" or similar — add each event name above so you can see responses.

---

## Phase 3 — Full Game Flow Testing (Socket.IO)

You need **2 Postman Socket.IO tabs** (or 1 Postman tab + the `test_client.html` in a browser).

### Tab Setup:
- **Tab 1** = Player 1 (Host) — "Neeraj"
- **Tab 2** = Player 2 (Guesser) — "Kumar"

Connect both tabs to `http://localhost:8080` before proceeding.

---

### Test 3.1: Create a Room (Player 1)

**In Tab 1 (Player 1):**

| Field       | Value          |
|-------------|----------------|
| Event Name  | `room_create`  |
| Message Type | JSON          |

**Payload** (paste in the message box):
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

**Click Send →** You should receive a `room_created` event:
```json
{
  "success": true,
  "room": {
    "code": "A1B2C3",       // ← COPY THIS CODE!
    "hostSid": "<your-sid>",
    "maxPlayers": 8,
    "roundsTotal": 3,
    "turnDuration": 80,
    "status": "waiting",
    "isPublic": false,
    "players": [
      {
        "sid": "<your-sid>",
        "name": "Neeraj",
        "avatar": "😀",
        "score": 0,
        "hasGuessed": false,
        "isConnected": true
      }
    ]
  }
}
```

✅ **PASS criteria**: `success` is `true`, `code` is a 6-character string, status is `"waiting"`.

📋 **ACTION**: Copy the `code` value (e.g., `"A1B2C3"`) — Player 2 needs it to join.

---

### Test 3.2: Join the Room (Player 2)

**In Tab 2 (Player 2):**

| Field       | Value        |
|-------------|--------------|
| Event Name  | `room_join`  |
| Message Type | JSON        |

**Payload** (replace `A1B2C3` with the actual room code from step 3.1):
```json
{
  "roomCode": "A1B2C3",
  "playerName": "Kumar",
  "avatar": "🎨"
}
```

**Click Send →** 

**Tab 2 receives** `room_joined`:
```json
{
  "success": true,
  "room": {
    "code": "A1B2C3",
    "players": [
      { "name": "Neeraj", "avatar": "😀", "score": 0 },
      { "name": "Kumar", "avatar": "🎨", "score": 0 }
    ]
  }
}
```

**Tab 1 also receives** `room_player_joined`:
```json
{
  "player": {
    "sid": "<player2-sid>",
    "name": "Kumar",
    "avatar": "🎨",
    "score": 0
  },
  "playerCount": 2
}
```

✅ **PASS criteria**: Both tabs receive their respective events. Player count = 2.

---

### Test 3.3: Update Room Settings (Player 1 — Optional)

**In Tab 1 (Host only):**

| Field       | Value            |
|-------------|------------------|
| Event Name  | `room_settings`  |
| Message Type | JSON            |

**Payload:**
```json
{
  "maxPlayers": 6,
  "rounds": 2,
  "turnDuration": 60,
  "customWords": ["mango", "umbrella", "elephant"],
  "useCustomWordsOnly": false
}
```

**Both tabs receive** `room_settings_updated`:
```json
{
  "room": { "maxPlayers": 6, "roundsTotal": 2, "turnDuration": 60, ... }
}
```

✅ **PASS criteria**: Settings reflect updated values. `maxPlayers` clamped between 2-12, `rounds` between 1-10, `turnDuration` between 30-180.

**Error test**: Send this from **Tab 2** (non-host) — should receive `room_error`:
```json
{ "message": "Only the host can change settings" }
```

---

### Test 3.4: Start the Game (Player 1)

**In Tab 1 (Host only):**

| Field       | Value         |
|-------------|---------------|
| Event Name  | `game_start`  |
| Message Type | JSON         |

**Payload:**
```json
{}
```

**Both tabs receive** `game_started`:
```json
{
  "round": 1,
  "totalRounds": 3,
  "players": [...]
}
```

**Then immediately, one of the following happens:**

- **The DRAWER** (whichever player is picked first) receives `game_word_choices`:
  ```json
  {
    "words": ["elephant", "bicycle", "lighthouse"],
    "timeout": 15
  }
  ```
- **The OTHER player** receives `game_choosing_word`:
  ```json
  {
    "drawerName": "Neeraj",
    "drawerSid": "<sid>",
    "round": 1,
    "totalRounds": 3
  }
  ```

✅ **PASS criteria**: Game status changes, drawer gets 3 word choices, others know who is drawing.

**Error tests** (each from Tab 2):
- Non-host tries to start → `game_error`: `"Only the host can start the game"`
- Start with only 1 player → `game_error`: `"Need at least 2 players to start"`

---

### Test 3.5: Select a Word (Drawer only)

**In the Drawer's tab:**

| Field       | Value                 |
|-------------|----------------------|
| Event Name  | `game_word_selected`  |
| Message Type | JSON                 |

**Payload** (use one of the words from `game_word_choices`):
```json
{
  "word": "elephant"
}
```

**The Drawer receives** `game_turn_start`:
```json
{
  "isDrawer": true,
  "word": "elephant",
  "wordLength": 8,
  "hint": "_ _ _ _ _ _ _ _",
  "duration": 80,
  "drawerName": "Neeraj",
  "drawerSid": "<sid>",
  "round": 1
}
```

**The Guesser receives** `game_turn_start`:
```json
{
  "isDrawer": false,
  "wordLength": 8,
  "hint": "_ _ _ _ _ _ _ _",
  "duration": 80,
  "drawerName": "Neeraj",
  "drawerSid": "<sid>",
  "round": 1
}
```

✅ **PASS criteria**: Drawer sees the actual word. Guesser does NOT see the word (only hint with underscores).

> ⏱️ **Note**: If you don't select a word within 15 seconds, the server auto-selects one randomly.

---

### Test 3.6: Send Drawing Strokes (Drawer only)

**In the Drawer's tab:**

| Field       | Value          |
|-------------|----------------|
| Event Name  | `draw_stroke`  |
| Message Type | JSON          |

**Payload — Start a stroke:**
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

**Payload — Continue the stroke:**
```json
{
  "x": 0.55,
  "y": 0.35,
  "color": "#FF0000",
  "size": 5,
  "tool": "pen",
  "type": "move"
}
```

**Payload — End the stroke:**
```json
{
  "x": 0.6,
  "y": 0.4,
  "color": "#FF0000",
  "size": 5,
  "tool": "pen",
  "type": "end"
}
```

**Payload — Batch points (alternative):**
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

**The Guesser's tab receives** `draw_stroke` with the same data.

✅ **PASS criteria**: All stroke data is relayed to other players. Drawer does NOT receive their own strokes back.

---

### Test 3.7: Drawing Tools — Clear, Undo, Fill (Drawer only)

#### 3.7a: Clear Canvas

| Event Name | `draw_clear` |
|------------|--------------|
| Payload    | `{}`         |

Others receive `draw_clear` → `{}`

#### 3.7b: Undo Last Stroke

| Event Name | `draw_undo` |
|------------|-------------|
| Payload    | `{}`        |

Others receive `draw_history` → `{ "history": [...remaining strokes...] }`

#### 3.7c: Fill Canvas

| Event Name | `draw_fill`                 |
|------------|-----------------------------|
| Payload    | `{ "color": "#00FF00" }`    |

Others receive `draw_fill` → `{ "color": "#00FF00" }`

---

### Test 3.8: Request Drawing History (Any player)

Useful for reconnection/late joins.

| Field       | Value                     |
|-------------|---------------------------|
| Event Name  | `draw_request_history`    |
| Payload     | `{}`                      |

**The requesting player receives** `draw_history`:
```json
{
  "history": [
    { "x": 0.5, "y": 0.3, "color": "#FF0000", "size": 5, "tool": "pen", "type": "start" },
    ...
  ]
}
```

---

### Test 3.9: Chat / Guess the Word (Guesser)

**In the Guesser's tab:**

| Field       | Value            |
|-------------|------------------|
| Event Name  | `chat_message`   |
| Message Type | JSON            |

#### 3.9a: Normal chat (wrong guess)

**Payload:**
```json
{
  "message": "is it a dog?"
}
```

**Both tabs receive** `chat_message`:
```json
{
  "playerName": "Kumar",
  "message": "is it a dog?",
  "type": "chat",
  "avatar": "🎨"
}
```

#### 3.9b: Close guess

If the word is "elephant" and the guesser types something close:
```json
{
  "message": "elephan"
}
```

**Both tabs receive:**
- `chat_system` → `{ "message": "Kumar is close!", "type": "close_guess" }`
- `chat_message` → `{ "message": "🤔 ...", "type": "close" }`

#### 3.9c: Correct guess!

**Payload:**
```json
{
  "message": "elephant"
}
```

**Both tabs receive:**
- `game_correct_guess`:
  ```json
  {
    "playerName": "Kumar",
    "playerSid": "<sid>",
    "score": 450,
    "totalScore": 450,
    "guessOrder": 1
  }
  ```
- `chat_system`:
  ```json
  {
    "message": "🎉 Kumar guessed the word!",
    "type": "correct_guess"
  }
  ```

✅ **PASS criteria**: Score is calculated (higher for guessing faster), system message confirms the guess.

> **Note**: If ALL guessers guess correctly, the turn ends automatically via `game_turn_end`.

---

### Test 3.10: Turn End & Timer Events

These happen automatically:

- **`game_timer`** — sent every 5 seconds during a turn:
  ```json
  { "remaining": 55, "total": 80 }
  ```

- **`game_hint`** — sent periodically to reveal letters:
  ```json
  { "hint": "e _ _ _ _ _ _ t", "hintsGiven": 1 }
  ```

- **`game_turn_end`** — when timer runs out or all guess:
  ```json
  {
    "word": "elephant",
    "reason": "timeout" | "all_guessed",
    "scoreboard": [...],
    "drawerBonus": 150
  }
  ```

- **`game_round_change`** — between rounds:
  ```json
  { "round": 2, "totalRounds": 3, "scoreboard": [...] }
  ```

- **`game_over`** — when all rounds complete:
  ```json
  {
    "scoreboard": [ { "name": "Kumar", "score": 900 }, ... ],
    "winner": { "name": "Kumar", "score": 900, ... }
  }
  ```

---

### Test 3.11: Play Again (Host only)

**In Tab 1 (Host):**

| Field       | Value              |
|-------------|--------------------------------|
| Event Name  | `game_play_again`  |
| Payload     | `{}`               |

**Both tabs receive** `game_reset`:
```json
{
  "room": {
    "status": "waiting",
    "players": [ ... with scores reset to 0 ... ]
  }
}
```

---

### Test 3.12: Kick a Player (Host only)

**In Tab 1 (Host):**

| Field       | Value        |
|-------------|--------------|
| Event Name  | `room_kick`  |
| Message Type | JSON        |

**Payload** (use Player 2's actual sid):
```json
{
  "targetSid": "<player2-sid>"
}
```

**Tab 2 receives** `room_kicked`:
```json
{ "message": "You were kicked from the room" }
```

**Tab 1 receives** `room_player_left`:
```json
{
  "playerName": "Kumar",
  "playerSid": "<player2-sid>",
  "kicked": true,
  "newHostSid": "<player1-sid>",
  "playerCount": 1,
  "players": [...]
}
```

---

### Test 3.13: Leave the Room

**In any player's tab:**

| Field       | Value         |
|-------------|---------------|
| Event Name  | `room_leave`  |
| Payload     | `{}`          |

**The leaving player receives** `room_left`:
```json
{ "success": true }
```

**Other players receive** `room_player_left`.

---

## Phase 4 — Quick Play / Matchmaking Testing

This is a separate flow from room_create/room_join.

### Test 4.1: Quick Play (Player 1)

**In Tab 1:**

| Field       | Value         |
|-------------|---------------|
| Event Name  | `quick_play`  |
| Message Type | JSON         |

**Payload:**
```json
{
  "playerName": "Neeraj",
  "avatar": "🎮"
}
```

**Tab 1 receives** `quick_play_joined`:
```json
{
  "success": true,
  "isNewRoom": true,
  "room": { "code": "...", "isPublic": true, "autoStart": true, ... },
  "message": "Waiting for players... (1/3 needed to start)"
}
```

### Test 4.2: Quick Play (Player 2)

**In Tab 2:**
```json
{
  "playerName": "Kumar",
  "avatar": "🎨"
}
```

**Tab 2 receives** `quick_play_joined` (auto-joins the same public room).
**Tab 1 receives** `room_player_joined`.

If only 2 players and min is 3, you receive `quick_play_waiting`:
```json
{
  "playerCount": 2,
  "needed": 1,
  "message": "Waiting for 1 more player..."
}
```

### Test 4.3: Quick Play Auto-Start (Player 3)

Open a **Tab 3** and connect, then quick_play:
```json
{
  "playerName": "Ravi",
  "avatar": "🚀"
}
```

When 3+ players join, the server auto-starts a countdown:

1. All receive `quick_play_countdown`:
   ```json
   { "seconds": 10, "message": "Game starting in 10 seconds!" }
   ```
2. Countdown ticks every second
3. After 10 seconds → `game_started` is emitted (auto-started!)
4. The first drawer receives `game_word_choices`

✅ **PASS criteria**: Game auto-starts without anyone clicking "Start".

---

## Phase 5 — Error Testing

Test these scenarios for robustness:

| # | Test | Event | Payload | Expected Error |
|---|------|-------|---------|---------------|
| 1 | Join invalid room code | `room_join` | `{ "roomCode": "XXXXXX", "playerName": "Test", "avatar": "😀" }` | `room_error`: `"Room not found"` |
| 2 | Join without code | `room_join` | `{ "roomCode": "", "playerName": "Test", "avatar": "😀" }` | `room_error`: `"Room code is required"` |
| 3 | Non-host starts game | `game_start` | `{}` (from Tab 2) | `game_error`: `"Only the host can start the game"` |
| 4 | Start with 1 player | `game_start` | `{}` (alone in room) | `game_error`: `"Need at least 2 players to start"` |
| 5 | Start game twice | `game_start` | `{}` (game already running) | `game_error`: `"Game is already in progress"` |
| 6 | Non-host changes settings | `room_settings` | `{ "rounds": 5 }` (from non-host) | `room_error`: `"Only the host can change settings"` |
| 7 | Non-drawer selects word | `game_word_selected` | `{ "word": "test" }` (from non-drawer) | `game_error`: `"You are not the drawer"` |
| 8 | Non-host kicks player | `room_kick` | `{ "targetSid": "..." }` (from non-host) | `room_error`: `"Only the host can kick players"` |
| 9 | Settings during game | `room_settings` | `{ "rounds": 5 }` (game in progress) | `room_error`: `"Cannot change settings during a game"` |
| 10 | Non-host restarts | `game_play_again` | `{}` (from non-host) | `game_error`: `"Only the host can restart"` |

---

## Phase 6 — Disconnection Testing

### Test 6.1: Drawer Disconnects During Turn

1. Start a game, wait for drawing phase
2. **Close Tab 1** (the drawer's tab) entirely — just disconnect
3. **Tab 2 should receive** `room_player_left` (with `disconnected: true`)
4. If 2+ players remain → turn ends via `game_turn_end` with reason `"drawer_left"`
5. If <2 players remain → `game_cancelled` with message `"Not enough players to continue"`

### Test 6.2: Non-Drawer Disconnects

1. During a game, close the guesser's tab
2. Game continues normally for remaining players
3. If all remaining players have guessed → turn ends early

---

## Alternative: Using test_client.html (No Postman Needed)

Your repo has a built-in test client:

1. Open `d:\Standalone Project\Varalokam\backend\test_client.html` in **two browser tabs**
2. Each tab acts as a separate player
3. All Socket.IO events are pre-wired with buttons
4. You can see all incoming events in real-time logs

This is the **fastest way** to test the full game flow without Postman.

---

## Verification Checklist

After running all tests, verify via the `/stats` REST endpoint:

```
GET http://localhost:8080/stats
```

| Check | Expected |
|-------|----------|
| Rooms count matches active rooms | ✅ |
| Players count matches connected players | ✅ |
| `roomList` shows details of each room | ✅ |
| After all disconnect, rooms = 0, players = 0 | ✅ |

---

## Quick Reference — All Events at a Glance

### Client → Server (You Send)

| # | Event | Payload | Who Can Send |
|---|-------|---------|-------------|
| 1 | `room_create` | `{ playerName, avatar, settings }` | Anyone |
| 2 | `room_join` | `{ roomCode, playerName, avatar }` | Anyone |
| 3 | `room_leave` | `{}` | Any player in room |
| 4 | `room_settings` | `{ maxPlayers, rounds, turnDuration, customWords, useCustomWordsOnly }` | Host only |
| 5 | `room_kick` | `{ targetSid }` | Host only |
| 6 | `quick_play` | `{ playerName, avatar }` | Anyone |
| 7 | `game_start` | `{}` | Host only |
| 8 | `game_word_selected` | `{ word }` | Drawer only |
| 9 | `game_play_again` | `{}` | Host only |
| 10 | `draw_stroke` | `{ x, y, color, size, tool, type }` or `{ points, color, size, tool }` | Drawer only |
| 11 | `draw_clear` | `{}` | Drawer only |
| 12 | `draw_undo` | `{}` | Drawer only |
| 13 | `draw_fill` | `{ color }` | Drawer only |
| 14 | `draw_request_history` | `{}` | Any player in room |
| 15 | `chat_message` | `{ message }` | Any player in room |

### Server → Client (You Receive)

| # | Event | When |
|---|-------|------|
| 1 | `connected` | On Socket.IO connection |
| 2 | `room_created` | After room_create |
| 3 | `room_joined` | After room_join (to joiner) |
| 4 | `room_player_joined` | When someone joins your room |
| 5 | `room_player_left` | When someone leaves/disconnects |
| 6 | `room_left` | After room_leave (to you) |
| 7 | `room_kicked` | If you get kicked |
| 8 | `room_error` | Room-related errors |
| 9 | `room_settings_updated` | After settings change |
| 10 | `game_started` | Game begins |
| 11 | `game_word_choices` | Drawer gets 3 words to pick |
| 12 | `game_choosing_word` | Others know who is choosing |
| 13 | `game_turn_start` | Drawing phase begins |
| 14 | `game_timer` | Timer tick every 5 seconds |
| 15 | `game_hint` | Letter hints revealed |
| 16 | `game_correct_guess` | Someone guessed right |
| 17 | `game_turn_end` | Turn finished |
| 18 | `game_round_change` | New round begins |
| 19 | `game_over` | All rounds complete |
| 20 | `game_reset` | After play_again |
| 21 | `game_error` | Game-related errors |
| 22 | `game_cancelled` | Not enough players |
| 23 | `draw_stroke` | Drawing data from drawer |
| 24 | `draw_clear` | Canvas cleared |
| 25 | `draw_fill` | Canvas filled |
| 26 | `draw_history` | Full drawing history |
| 27 | `chat_message` | Chat/guess messages |
| 28 | `chat_system` | System messages |
| 29 | `quick_play_joined` | Matched into a room |
| 30 | `quick_play_waiting` | Waiting for more players |
| 31 | `quick_play_countdown` | Auto-start countdown |
| 32 | `quick_play_countdown_cancelled` | Countdown cancelled |
