# Cyrus Security Bot

A Telegram group moderation bot for stopping spam, abuse (including Hindi slurs), and more, plus broadcast and admin tools.

## Features

- Automatic message filtering and deletion for abusive or blacklisted words.
- Hindi and English swearing and spam detection.
- Owner/admin commands for managing blocklists, logs, and more.
- Friendly `/help`, `/start`, and welcome messages.
- Daily blacklist auto-backup.
- `/broadcast` command for owner to send messages to all known chats.
- Persisted logs and configs.

## Usage

1. **Clone this repo**

2. **Set up config:**  
   - Owner: edit `BOT_OWNER_ID` in `cyrus_security_bot.py`  
   - Bot token: replace in the same file

3. **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4. **Run the bot**
    ```bash
    python cyrus_security_bot.py
    ```

5. **Add [Cyrus Security Bot](http://t.me/Cyrus_Security_bot) to your group as an admin.**

## Troubleshooting

- Data/log files (`blacklist.txt`, `logs.txt`, `known_chats.json`) are auto-created in the working directory.

---

© Cyrus Security Bot 2024