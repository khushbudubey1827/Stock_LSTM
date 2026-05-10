# StockSense - Demo Ready Setup

StockSense is a Flask-based stock analytics app with:
- LSTM-based next-day prediction
- EMA trend charts
- Live price snapshot (Yahoo Finance)
- News sentiment summary
- User authentication

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the app:
   ```bash
   python app.py
   ```
4. Open:
   ```
   http://127.0.0.1:5000
   ```

## Demo Notes

- Default database is SQLite at `instance/users.db`.
- If `stock_dl_model.h5` is missing, prediction routes degrade gracefully.
- Optional sentiment API key:
  - Set `GNEWS_API_KEY` in environment to enable GNews headlines.
  - Without it, app falls back to Yahoo Finance news.

## Health Check

Use:
```bash
GET /health
```

Example:
```bash
http://127.0.0.1:5000/health
```

## Optional Environment Variables

- `FLASK_SECRET_KEY`
- `DATABASE_URL`
- `GNEWS_API_KEY`

## Output
<img width="1920" height="1080" alt="Screenshot 2026-03-29 143831" src="https://github.com/user-attachments/assets/d0aad8b4-56f5-4c27-90c0-23342e0b3e4d" />
<img width="1920" height="1080" alt="Screenshot 2026-03-29 143846" src="https://github.com/user-attachments/assets/85e65379-6e15-4632-bacf-37b1d19f4036" />
<img width="1920" height="1080" alt="Screenshot 2026-03-29 143859" src="https://github.com/user-attachments/assets/8af47cb2-f791-4565-b4bd-389a4599bf13" />


