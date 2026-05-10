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
