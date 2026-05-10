# StockSense (Stock_LSTM) Installation and Run Guide

## 1. Prerequisites
Before you begin, ensure you have the following installed on your system:
- **Python**: Version 3.8 or above is recommended.
- **Git**: Optional, if you need to clone the repository.

## 2. Setup and Installation

### Step 2.1: Open Terminal or Command Prompt
Navigate to the project directory where your files are located:
```bash
cd path\to\Stock_LSTM
```

### Step 2.2: Create a Virtual Environment
It is highly recommended to use a virtual environment to avoid dependency conflicts. Run the following command:
```bash
python -m venv venv
```

### Step 2.3: Activate the Virtual Environment
Depending on your operating system, run the activation command:
- **Windows**:
  ```bash
  .\venv\Scripts\activate
  ```
- **macOS/Linux**:
  ```bash
  source venv/bin/activate
  ```

### Step 2.4: Install Dependencies
Install all required libraries using the `requirements.txt` file:
```bash
pip install -r requirements.txt
```
> Note: This will install required packages like `Flask`, `TensorFlow`, `scikit-learn`, `yfinance`, etc.

## 3. Running the Application

### Step 3.1: Start the Server
Once the dependencies are installed, start the Flask web application by running:
```bash
python app.py
```

### Step 3.2: Access the Application
Open your web browser and navigate to the following URL:
```
http://127.0.0.1:5000
```

## 4. Optional Configuration
The application can work without API keys by degrading gracefully to fallbacks, but you can configure the following environment variables if needed:
- **`GNEWS_API_KEY`**: Use an API key from GNews to fetch live headlines instead of falling back to Yahoo Finance.
- **`FLASK_SECRET_KEY`**: Used for securing the session in user authentication.
- **`DATABASE_URL`**: Custom database URI (by default it uses SQLite).

## 5. Troubleshooting
- **Database errors**: The project defaults to SQLite and creates the database `instance/users.db` automatically. Ensure you have proper permissions if it fails to create.
- **Health Check**: You can verify the app status by visiting `http://127.0.0.1:5000/health` in your browser.
