import os
import re
import logging
import datetime as dt
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import yfinance as yf
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from keras.models import load_model
from sklearn.preprocessing import MinMaxScaler
from textblob import TextBlob
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from functools import wraps

plt.style.use("fivethirtyeight")

APP_ROOT = Path(__file__).resolve().parent
STATIC_DIR = APP_ROOT / "static"
INSTANCE_DIR = APP_ROOT / "instance"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stocksense")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "stocksense_secret_2026")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", f"sqlite:///{(INSTANCE_DIR / 'users.db').as_posix()}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.permanent_session_lifetime = dt.timedelta(days=7)

db = SQLAlchemy(app)


def load_prediction_model():
    model_candidates = [APP_ROOT / "stock_dl_model.h5", APP_ROOT / "stock_dl_model.keras"]
    for candidate in model_candidates:
        if candidate.exists():
            try:
                logger.info("Loading model: %s", candidate.name)
                return load_model(str(candidate))
            except Exception as exc:
                logger.exception("Failed to load model %s: %s", candidate, exc)
    logger.error("No usable model file found. Prediction features will be disabled.")
    return None


model = load_prediction_model()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fname = db.Column(db.String(50), nullable=False)
    lname = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    password = db.Column(db.String(200), nullable=False)


with app.app_context():
    db.create_all()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated


def sanitize_ticker(raw: str) -> str:
    ticker = (raw or "").strip().upper()
    if not ticker:
        return "POWERGRID.NS"
    if not re.fullmatch(r"[A-Z0-9.\-^=]{1,20}", ticker):
        raise ValueError("Ticker contains unsupported characters.")
    return ticker


def _normalize_download_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if "Close" not in df.columns and "Adj Close" in df.columns:
        df["Close"] = df["Adj Close"]
    if "Close" not in df.columns:
        return pd.DataFrame()
    return df.dropna(subset=["Close"])


def download_stock_data(ticker: str, start=None, end=None, period=None, interval=None) -> pd.DataFrame:
    kwargs = {
        "progress": False,
        "auto_adjust": False,
        "threads": False,
    }
    if period is not None:
        kwargs["period"] = period
    if interval is not None:
        kwargs["interval"] = interval
    if start is not None:
        kwargs["start"] = start
    if end is not None:
        kwargs["end"] = end

    df = yf.download(ticker, **kwargs)
    return _normalize_download_df(df)


def predict_next_day(df: pd.DataFrame, mdl):
    if mdl is None:
        return None
    if df is None or df.empty or len(df) < 100:
        return None

    close_data = df[["Close"]].copy()
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled = scaler.fit_transform(close_data)

    last_100 = scaled[-100:]
    x_input = np.array([last_100]).reshape(1, 100, 1)

    pred_scaled = mdl.predict(x_input, verbose=0)
    pred_price = float(scaler.inverse_transform(pred_scaled)[0][0])

    last_price = float(df["Close"].iloc[-1])
    change = pred_price - last_price
    change_pct = (change / last_price) * 100 if last_price else 0

    return {
        "price": round(pred_price, 2),
        "last_price": round(last_price, 2),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "direction": "UP" if change >= 0 else "DOWN",
        "signal": "BUY" if change_pct > 1 else ("SELL" if change_pct < -1 else "HOLD"),
    }


def _score_text_sentiment(text: str):
    score = TextBlob(text or "").sentiment.polarity
    if score > 0.1:
        return score, "Positive", "green"
    if score < -0.1:
        return score, "Negative", "red"
    return score, "Neutral", "neutral"


def get_sentiment(stock_name: str):
    articles = []
    sentiments = []

    try:
        query = re.sub(r"\.(NS|BO|BSE|NSE)$", "", stock_name, flags=re.IGNORECASE)
        gnews_key = os.getenv("GNEWS_API_KEY", "").strip()

        if gnews_key:
            url = "https://gnews.io/api/v4/search"
            params = {
                "q": f"{query} stock",
                "lang": "en",
                "max": 10,
                "apikey": gnews_key,
            }
            resp = requests.get(url, params=params, timeout=6)
            if resp.ok:
                for item in resp.json().get("articles", [])[:8]:
                    title = item.get("title", "")
                    desc = item.get("description", "") or ""
                    score, label, color = _score_text_sentiment(f"{title} {desc}")
                    sentiments.append(score)
                    articles.append(
                        {
                            "title": title,
                            "url": item.get("url", "#"),
                            "source": item.get("source", {}).get("name", "News"),
                            "time": (item.get("publishedAt", "") or "")[:10],
                            "label": label,
                            "color": color,
                            "score": round(score, 2),
                        }
                    )
    except Exception as exc:
        logger.warning("GNews sentiment fetch failed: %s", exc)

    if not articles:
        try:
            yf_news = yf.Ticker(stock_name).news or []
            for item in yf_news[:8]:
                content = item.get("content", {}) if isinstance(item, dict) else {}
                title = content.get("title") or item.get("title", "")
                if not title:
                    continue
                score, label, color = _score_text_sentiment(title)
                sentiments.append(score)

                pub_date = content.get("pubDate", "") or item.get("providerPublishTime", "")
                time_str = str(pub_date)[:10] if pub_date else dt.datetime.now().strftime("%Y-%m-%d")
                url = content.get("canonicalUrl", {}).get("url", "#") if isinstance(content.get("canonicalUrl", {}), dict) else "#"

                articles.append(
                    {
                        "title": title,
                        "url": url,
                        "source": content.get("provider", {}).get("displayName", "Yahoo Finance"),
                        "time": time_str,
                        "label": label,
                        "color": color,
                        "score": round(score, 2),
                    }
                )
        except Exception as exc:
            logger.warning("Yahoo sentiment fetch failed: %s", exc)

    avg = sum(sentiments) / len(sentiments) if sentiments else 0
    pos = sum(1 for s in sentiments if s > 0.1)
    neg = sum(1 for s in sentiments if s < -0.1)
    neu = max(len(sentiments) - pos - neg, 0)

    if avg > 0.1:
        overall, overall_color = "Bullish", "green"
    elif avg < -0.1:
        overall, overall_color = "Bearish", "red"
    else:
        overall, overall_color = "Neutral", "neutral"

    return {
        "articles": articles,
        "overall": overall,
        "overall_color": overall_color,
        "avg_score": round(avg, 3),
        "positive": pos,
        "negative": neg,
        "neutral": neu,
        "total": len(articles),
    }


def build_dashboard(stock: str, df: pd.DataFrame):
    if model is None:
        raise RuntimeError("Model file is missing or failed to load.")
    if df.empty:
        raise ValueError("No market data found for this ticker.")
    if len(df) < 160:
        raise ValueError("Not enough historical data. Try a ticker with longer history.")

    close_series = df["Close"]
    data_desc = df.describe()

    ema20 = close_series.ewm(span=20, adjust=False).mean()
    ema50 = close_series.ewm(span=50, adjust=False).mean()
    ema100 = close_series.ewm(span=100, adjust=False).mean()
    ema200 = close_series.ewm(span=200, adjust=False).mean()

    split_idx = int(len(df) * 0.70)
    data_training = pd.DataFrame(close_series.iloc[:split_idx])
    data_testing = pd.DataFrame(close_series.iloc[split_idx:])

    scaler = MinMaxScaler(feature_range=(0, 1))
    scaler.fit(data_training)

    past_100_days = data_training.tail(100)
    final_df = pd.concat([past_100_days, data_testing], ignore_index=True)
    input_data = scaler.transform(final_df)

    x_test, y_test = [], []
    for i in range(100, input_data.shape[0]):
        x_test.append(input_data[i - 100 : i])
        y_test.append(input_data[i, 0])
    x_test, y_test = np.array(x_test), np.array(y_test)

    if len(x_test) == 0:
        raise ValueError("Testing window could not be constructed from the available data.")

    y_predicted = model.predict(x_test, verbose=0)
    y_predicted = scaler.inverse_transform(y_predicted).flatten()
    y_test = scaler.inverse_transform(y_test.reshape(-1, 1)).flatten()

    fig1, ax1 = plt.subplots(figsize=(12, 6))
    ax1.plot(close_series, "y", label="Closing Price")
    ax1.plot(ema20, "g", label="EMA 20")
    ax1.plot(ema50, "r", label="EMA 50")
    ax1.set_title("Closing Price vs Time (20 & 50 Days EMA)")
    ax1.set_xlabel("Time")
    ax1.set_ylabel("Price")
    ax1.legend()
    fig1.savefig(STATIC_DIR / "ema_20_50.png")
    plt.close(fig1)

    fig2, ax2 = plt.subplots(figsize=(12, 6))
    ax2.plot(close_series, "y", label="Closing Price")
    ax2.plot(ema100, "g", label="EMA 100")
    ax2.plot(ema200, "r", label="EMA 200")
    ax2.set_title("Closing Price vs Time (100 & 200 Days EMA)")
    ax2.set_xlabel("Time")
    ax2.set_ylabel("Price")
    ax2.legend()
    fig2.savefig(STATIC_DIR / "ema_100_200.png")
    plt.close(fig2)

    fig3, ax3 = plt.subplots(figsize=(12, 6))
    ax3.plot(y_test, "g", label="Original Price", linewidth=1)
    ax3.plot(y_predicted, "r", label="Predicted Price", linewidth=1)
    ax3.set_title("Prediction vs Original Trend")
    ax3.set_xlabel("Time")
    ax3.set_ylabel("Price")
    ax3.legend()
    fig3.savefig(STATIC_DIR / "stock_prediction.png")
    plt.close(fig3)

    dataset_name = secure_filename(f"{stock}_dataset.csv")
    dataset_path = STATIC_DIR / dataset_name
    df.to_csv(dataset_path)

    return {
        "data_desc": data_desc,
        "dataset_link": f"static/{dataset_name}",
    }


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_live_snapshot(ticker: str):
    t = yf.Ticker(ticker)
    info = t.fast_info or {}

    intraday = t.history(period="1d", interval="5m")
    day_hist = t.history(period="1d")
    hist_1y = t.history(period="1y")

    price = _to_float(getattr(info, "last_price", None) if hasattr(info, "last_price") else info.get("last_price"))
    prev = _to_float(getattr(info, "previous_close", None) if hasattr(info, "previous_close") else info.get("previous_close"))

    if price is None and not intraday.empty:
        price = _to_float(intraday["Close"].iloc[-1])
    if prev is None and len(intraday) > 1:
        prev = _to_float(intraday["Close"].iloc[0])

    if price is None:
        raise ValueError("Live price unavailable for this ticker right now.")

    change = round(price - prev, 2) if prev is not None else 0.0
    change_pct = round((change / prev) * 100, 2) if prev not in (None, 0) else 0.0

    open_p = round(float(day_hist["Open"].iloc[-1]), 2) if not day_hist.empty else "--"
    high_p = round(float(day_hist["High"].iloc[-1]), 2) if not day_hist.empty else "--"
    low_p = round(float(day_hist["Low"].iloc[-1]), 2) if not day_hist.empty else "--"

    high_52w = round(float(hist_1y["High"].max()), 2) if not hist_1y.empty else "--"
    low_52w = round(float(hist_1y["Low"].min()), 2) if not hist_1y.empty else "--"

    chart_prices = []
    if not intraday.empty:
        chart_prices = [round(float(x), 2) for x in intraday["Close"].dropna().tail(50).tolist()]

    return {
        "ticker": ticker.upper(),
        "price": round(price, 2),
        "prev_close": round(prev, 2) if prev is not None else "--",
        "change": change,
        "change_pct": change_pct,
        "direction": "up" if change >= 0 else "down",
        "open": open_p,
        "high": high_p,
        "low": low_p,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "chart_prices": chart_prices,
    }


@app.route("/api/live-price/<ticker>")
@login_required
def live_price(ticker):
    try:
        clean_ticker = sanitize_ticker(ticker)
        return jsonify(get_live_snapshot(clean_ticker))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        fname = request.form.get("fname", "").strip()
        lname = request.form.get("lname", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not fname or not lname or not email or not password:
            flash("All required fields must be filled.", "error")
            return render_template("register.html")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            flash("Please enter a valid email address.", "error")
            return render_template("register.html")
        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("register.html")
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("register.html")
        if User.query.filter_by(email=email).first():
            flash("An account with this email already exists.", "error")
            return render_template("register.html")

        new_user = User(
            fname=fname,
            lname=lname,
            email=email,
            phone=phone,
            password=generate_password_hash(password),
        )
        db.session.add(new_user)
        db.session.commit()

        session.permanent = True
        session["user_id"] = new_user.id
        session["user_name"] = new_user.fname
        flash(f"Welcome, {new_user.fname}! Account created successfully.", "success")
        return redirect(url_for("index"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session.permanent = True
            session["user_id"] = user.id
            session["user_name"] = user.fname
            return redirect(url_for("index"))

        flash("Invalid email or password.", "error")
        return render_template("login.html")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    user_name = session.get("user_name") or "User"

    if request.method == "POST":
        try:
            stock = sanitize_ticker(request.form.get("stock", ""))
            start = dt.datetime(2000, 1, 1)
            end = dt.datetime.today() + dt.timedelta(days=1)
            df = download_stock_data(stock, start=start, end=end)

            artifacts = build_dashboard(stock, df)
            next_day = predict_next_day(df, model)
            sentiment = get_sentiment(stock)

            return render_template(
                "index.html",
                plot_path_ema_20_50="static/ema_20_50.png",
                plot_path_ema_100_200="static/ema_100_200.png",
                plot_path_prediction="static/stock_prediction.png",
                data_desc=artifacts["data_desc"].to_html(classes="table table-bordered"),
                dataset_link=artifacts["dataset_link"],
                user_name=user_name,
                stock=stock,
                next_day=next_day,
                sentiment=sentiment,
            )
        except Exception as exc:
            logger.exception("Dashboard generation failed")
            flash(f"Could not process request: {exc}", "error")
            return render_template("index.html", user_name=user_name)

    return render_template("index.html", user_name=user_name)


@app.route("/live-price", methods=["GET", "POST"])
@login_required
def live_price_page():
    user_name = session.get("user_name") or "User"
    live_data = None
    stock = None

    if request.method == "POST":
        try:
            stock = sanitize_ticker(request.form.get("stock", ""))
            live_data = get_live_snapshot(stock)
        except Exception as exc:
            flash(f"Could not fetch data: {exc}", "error")

    return render_template(
        "live_price.html",
        user_name=user_name,
        live_data=live_data,
        stock=stock,
    )


@app.route("/next-day", methods=["GET", "POST"])
@login_required
def next_day_page():
    user_name = session.get("user_name") or "User"
    prediction = None
    stock = None
    history_prices = []

    if request.method == "POST":
        try:
            stock = sanitize_ticker(request.form.get("stock", ""))
            df = download_stock_data(
                stock,
                start=dt.datetime(2000, 1, 1),
                end=dt.datetime.today() + dt.timedelta(days=1),
            )
            if df.empty:
                raise ValueError("No data returned for this ticker.")
            prediction = predict_next_day(df, model)
            if prediction is None:
                raise ValueError("Prediction unavailable. Ensure model exists and enough data is present.")

            last6 = df["Close"].tail(6)
            history_prices = [
                {"day": last6.index[i].strftime("%a"), "price": round(float(last6.iloc[i]), 2)}
                for i in range(len(last6))
            ]
        except Exception as exc:
            flash(f"Prediction failed: {exc}", "error")

    return render_template(
        "next_day_prediction.html",
        user_name=user_name,
        prediction=prediction,
        stock=stock,
        history_prices=history_prices,
    )


@app.route("/sentiment", methods=["GET", "POST"])
@login_required
def sentiment_page():
    user_name = session.get("user_name") or "User"
    sentiment = None
    stock = None

    if request.method == "POST":
        try:
            stock = sanitize_ticker(request.form.get("stock", ""))
            sentiment = get_sentiment(stock)
        except Exception as exc:
            flash(f"Sentiment analysis failed: {exc}", "error")

    return render_template(
        "sentiment_analysis.html",
        user_name=user_name,
        sentiment=sentiment,
        stock=stock,
    )


@app.route("/download/<filename>")
@login_required
def download_file(filename):
    safe_name = secure_filename(filename)
    if not safe_name:
        abort(400)

    target = STATIC_DIR / safe_name
    if not target.exists() or not target.is_file():
        abort(404)

    return send_file(target, as_attachment=True)


@app.route("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "model_loaded": model is not None,
            "database": app.config["SQLALCHEMY_DATABASE_URI"],
            "timestamp": dt.datetime.utcnow().isoformat() + "Z",
        }
    )


if __name__ == "__main__":
    app.run(debug=True)
