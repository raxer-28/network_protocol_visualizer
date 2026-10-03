# Network Protocol Visualizer

A dual-panel web dashboard that lets you perform **Browsing, Mail, and Streaming** activities while simultaneously visualizing the underlying protocol exchanges step-by-step.

Built with **Python (FastAPI) + HTML/CSS/Vanilla JS** for the Computer Networks assignments.
Supports both **Application Layer (Assignment 1)** and **Transport Layer (Assignment 2)** visualizations.

---

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.10 or newer
- `pip` (or `pip3`)

### 2. Install Dependencies

```bash
cd network_protocol_visualizer
pip install -r requirements.txt
```

### 3. Configure Email (for real SMTP sending)

```bash
# Copy the template
copy .env.example .env
```

Edit `.env` with your details:
```
SENDER_EMAIL=your_gmail@gmail.com
SENDER_PASSWORD=your_16_char_app_password
```

> **How to get a Gmail App Password:**
> 1. Go to [myaccount.google.com](https://myaccount.google.com) → Security
> 2. Enable **2-Step Verification** (required)
> 3. Search "App Passwords" → Select app: **Mail** → Device: **Windows Computer**
> 4. Copy the 16-character password (no spaces) into `.env`

> **Without credentials:** The Mail tab still works — it shows a complete **simulated** SMTP conversation in the right panel (all correct protocol behavior, just no actual email sent).

### 4. Run the Server

```bash
# From the project root directory
uvicorn backend.main:app --reload --port 8000
```

### 5. Open the Dashboard

Open your browser and go to: **[http://localhost:8000](http://localhost:8000)**

---

## 📋 Features

### 🌐 Browsing Tab
- Enter any URL in the address bar and click **Visit**
- The page loads in a proxy iframe on the left
- Right panel shows: **DNS A record lookup → TCP handshake → TLS handshake → HTTP GET request → HTTP response** with all headers

### ✉️ Mail Tab
- Fill in **To**, **Subject**, and **Body**
- Click **Send Email** to send a real email via Gmail SMTP
- Right panel shows the full **SMTP conversation**: DNS MX lookup → TCP → STARTTLS → EHLO → AUTH → MAIL FROM → RCPT TO → DATA → 250 OK → QUIT

### ▶️ Streaming Tab
- Paste any public `.mp4` or `.m3u8` video URL (or use the default Big Buck Bunny URL)
- Click **Load** — the video plays in the left panel
- Right panel shows: **DNS → TCP → TLS → HTTP HEAD → HTTP GET (byte-range chunks or HLS segments)**

### 📡 Protocol Visualizer (Right Panel)
- **Layer Tabs**: Switch between **Application Layer** (DNS, HTTP, SMTP) and **Transport Layer** (TCP, UDP) views.
- **Detailed Transport Layer**: Shows precise TCP handshakes (SYN, SYN-ACK, ACK), teardowns (FIN), flags, sequence numbers, acknowledgement numbers, and window sizes. 
- **Directional Alignment**: Client requests (`Client --> Server`) align left, while server responses (`Client <-- Server`) align right for easy readability.
- **Step-by-step animation** with configurable speed (0.5×, 1×, 2×, 5×)
- **Playback controls**: ⏮ First · ⏪ Back · ▶/⏸ Play/Pause · ⏩ Next · ⏭ Last · 🔁 Replay
- **Phase badges**: DNS · TCP · UDP · TLS · HTTP · SMTP (color-coded)
- **Click any step** to expand and see the full raw message with highlighted key fields
- **Progress bar** showing current position in the protocol sequence

---

## 📁 Project Structure

```
network_protocol_visualizer/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── models.py                # Pydantic data models
│   ├── routers/
│   │   ├── browse.py            # /api/browse + /proxy
│   │   ├── mail.py              # /api/mail
│   │   └── stream.py            # /api/stream
│   └── services/
│       ├── dns_service.py       # Real DNS A/MX lookups (dnspython)
│       ├── http_service.py      # Real HTTP requests (httpx)
│       ├── smtp_service.py      # Real SMTP send (smtplib)
│       └── stream_service.py    # HLS/MP4 stream analysis
├── frontend/
│   ├── index.html               # Main two-panel shell
│   ├── css/styles.css           # Design system (dark mode, glassmorphism)
│   └── js/
│       ├── app.js               # Tab switching, toast notifications
│       ├── visualizer.js        # Protocol step renderer + playback engine
│       ├── browse.js            # Browsing activity logic
│       ├── mail.js              # Mail compose + send logic
│       └── stream.js            # Video stream loader + controls
├── .env.example                 # Email credentials template
├── requirements.txt
└── README.md
```

---

## 🔌 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/browse` | DNS + HTTP fetch for a URL |
| `GET`  | `/proxy?url=` | Proxy-serves a web page in the iframe |
| `POST` | `/api/mail` | DNS MX lookup + SMTP send |
| `POST` | `/api/stream` | DNS + HTTP stream analysis |
| `GET`  | `/health` | Health check |

---

## 🚀 How to Run (Without the Agent)

If you want to run this project manually from your terminal, follow these steps:

1. **Activate your Python environment** (if you use one).
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Start the FastAPI server**:
   ```bash
   uvicorn backend.main:app --reload --port 8000
   ```
   *Alternatively, you can just run `python backend/main.py`!*
4. **Open your browser** and navigate to: [http://localhost:8000](http://localhost:8000)

---

## 🎓 Assignment Notes

- **Platform used**: Google Antigravity (with Claude/Gemini models)
- **Assignment 1 (Application Layer)**: Complete. Includes HTTP, SMTP (with Simulation Mode), and DNS visualization.
- **Assignment 2 (Transport Layer)**: Complete. Implements dual-tab views for Application/Transport, RTL server message layout, precise sequence/ack/win numbers, and explicit `Client --> Server` formatting for TCP/UDP datagrams.
- **Protocol accuracy**: DNS uses real `dnspython` resolution; HTTP uses real `httpx` requests; SMTP uses real `smtplib` STARTTLS; Transport layer overlays realistic sequence/flags/timing over the actual data flows.
- **AI Evidence**: Full conversation logs, tool calls, and implementation artifacts are available in the Antigravity session.

---

## ⚠️ Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| Email auth failed (535) | Check App Password in `.env`, ensure 2FA is enabled on Gmail |
| iframe shows "blocked" page | Site uses X-Frame-Options — protocol steps are still accurate |
| Port 8000 in use | Add `--port 8001` to the uvicorn command |
