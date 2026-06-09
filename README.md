# 🔐 Messenger – Encrypted Web Messenger with Social Features

A modern, real‑time messenger built with Flask and WebSocket, featuring **end‑to‑end encryption (E2EE)**, two‑factor authentication, a social feed, friend management, and an admin panel.  
Fully containerised with Docker Compose, ready for demonstration or production use.

---

## ✨ Key Features

- **End‑to‑End Encryption (E2EE)**  
  ECDH + AES‑256‑GCM encryption performed entirely in the browser. Private keys are password‑protected and stored in IndexedDB. The server never sees plain‑text messages.

- **Real‑Time Chat**  
  WebSocket communication with typing indicators, read receipts, stickers, file attachments, and reactions.

- **Two‑Factor Authentication (2FA)**  
  TOTP‑based 2FA via apps like Google Authenticator.

- **Social Feed**  
  Create, edit, like, and comment on posts. Only friends see each other’s content.

- **Friend System**  
  Send, accept, reject, and remove friend requests. Chat is only possible between friends.

- **Admin Panel**  
  Manage users, assign roles (owner/admin/moderator), ban/unban, delete users/posts/comments.

- **Email Verification & Password Reset**  
  Account activation and password recovery via SMTP.

- **Dark Theme & Responsive Design**  
  Toggle between light and dark modes, mobile‑friendly interface.

- **Progressive Web App (PWA)**  
  Service worker for offline caching and installability on mobile devices.

- **Docker Support**  
  Quick deployment with PostgreSQL, Redis, and the application bundled in Docker Compose.

## 🎯 Perfect For

- **Startups** needing a secure MVP for private communication
- **Clinics & Law Firms** requiring HIPAA-compliant messaging
- **Educational platforms** wanting built-in chat for students
- **Enterprise teams** looking for a self-hosted Slack alternative
- **Developers** who need a white-label messenger for their clients

## 📸 Screenshots

| Chat with E2EE | Admin Panel | Encrypted DB |
|----------------|-------------|--------------|
| ![chat](screenshots/chat.png) | ![admin](screenshots/admin.png) | ![db](screenshots/db.png) |

Encrypted Web Messenger with E2EE, 2FA, and Social Features

🔐 End-to-end encryption (ECDH + AES-256-GCM)
💬 Real-time chat with file attachments & stickers
👑 Admin panel with role management
🐳 Docker-ready deployment
✅ 30+ automated tests included

Tech: Python/Flask, PostgreSQL, Redis, WebSocket, Docker

---

## 🧰 Technology Stack

| Layer          | Technology                           |
|----------------|--------------------------------------|
| Backend        | Python 3, Flask, Flask‑SocketIO      |
| Database       | PostgreSQL (via SQLAlchemy + Flask‑Migrate) |
| Message Broker | Redis (WebSocket pub/sub)            |
| Security       | Flask‑WTF (CSRF), Flask‑Limiter, PyOTP (2FA), ECDH + AES‑GCM (E2EE) |
| Frontend       | Vanilla JavaScript, Socket.IO client |
| Deployment     | Docker, Docker Compose               |

---


## 📮 Contact / Purchase

Interested in buying this project or have questions?

- **Telegram:** [@Virus_Dev_messege](https://t.me/Virus_Dev_messege)
- **Email:** [virusvirusov22@gmail.com](mailto:virusvirusov22@gmail.com)
- **GitHub:** Private repository access after purchase

---

## 📝 License

This project is licensed under the MIT License.  
Upon purchase, you will receive full source code and a perpetual license to use, modify, and distribute the software.

---

## 💰 How to Purchase

1. **Contact me** via Telegram [@Virus_Dev_messege](https://t.me/Virus_Dev_messege) or email [virusvirusov22@gmail.com](mailto:virusvirusov22@gmail.com)
2. **Agree on price** (starting at $25,000, negotiable based on licensing terms)
3. **Payment via USDT (TRC-20 / ERC-20)** — Bybit or any wallet that supports USDT
   - My Bybit wallet address will be provided upon agreement
   - Alternative: Bank transfer (SWIFT) for US-based buyers
4. **Escrow option:** I support Acquire.com or Flippa escrow for buyer protection (fee covered by buyer or split 50/50)
5. **After payment confirmation,** you receive:
   - Full source code (private Git repository access)
   - Docker Compose configuration
   - Database schemas and migrations
   - 7 days of free technical support

**🚀 Delivery time:** Within 2 hours after payment confirmation

**🔒 Privacy:** No data collection. No tracking. The code is yours forever.

## 💸 Accepted Cryptocurrencies

| Currency | Network | Notes |
|----------|---------|-------|
| **USDT** | TRC-20 / ERC-20 | Recommended (fast & low fees on TRC-20) |
| **USDC** | ERC-20 / BEP-20 | Available upon request |
| **BTC** | - | Higher fees, longer confirmation |

> 💡 **I use Bybit** for all crypto transactions. Escrow available via Acquire.com or Flippa if you prefer traditional payment methods.

**Price: $25,000 (negotiable)**


## 🚀 Quick Start

### 1. Clone and configure

```bash
git clone <your-repo-url>
cd messenger
cp .env.example .env
# Generate a strong secret key:
python3 -c "import secrets; print(secrets.token_hex(32))"
# Insert the generated key into .env as SECRET_KEY=...

2. Start services
bash
docker-compose up -d --build

3. Create the owner account
bash
docker exec -it messenger_app python create_owner.py

Project Structure
text
messenger/
├── app.py                # Main Flask application
├── models.py             # SQLAlchemy models
├── auth.py               # Authentication helpers
├── admin.py              # Admin blueprint
├── create_owner.py       # Owner creation script (interactive)
├── docker-compose.yml    # Docker services
├── requirements.txt      # Python dependencies
├── templates/            # Jinja2 templates (chat, feed, admin, etc.)
├── static/               # CSS, JS, avatars, Service Worker
└── tests/                # Test suite