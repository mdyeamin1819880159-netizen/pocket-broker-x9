 import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask, request, redirect, url_for,
    session, flash, render_template_string
)
from werkzeug.security import (
    generate_password_hash, check_password_hash
)

app = Flask(__name__)
app.secret_key = os.environ.get(
    "APP_SECRET_KEY", "change-this-demo-secret"
)

DB_PATH = os.environ.get("DB_PATH", "pocket_broker.db")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "uid" not in session:
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper

def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return "Admin access only", 403
        return func(*args, **kwargs)
    return wrapper
def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            balance REAL NOT NULL DEFAULT 1000,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            side TEXT NOT NULL,
            amount REAL NOT NULL,
            result TEXT NOT NULL DEFAULT 'Pending',
            profit REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            method TEXT NOT NULL,
            amount REAL NOT NULL,
            reference TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """)

def set_setting(c, key, value):
    c.execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value))
    )

def get_setting(c, key, default="AUTO"):
    row = c.execute(
        "SELECT value FROM settings WHERE key=?",
        (key,)
    ).fetchone()
    return row["value"] if row else default

init_db()

def page(title, body):
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport"
              content="width=device-width, initial-scale=1">
        <title>{{ title }} - Pocket Broker X9</title>
        <style>
            body {
                margin: 0;
                padding: 16px;
                background: #101827;
                color: #ffffff;
                font-family: Arial, sans-serif;
            }
            .container {
                max-width: 500px;
                margin: 20px auto;
            }
            .card {
                background: #1e2b40;
                padding: 20px;
                margin-bottom: 16px;
                border-radius: 14px;
            }
            h1, h2 {
                color: #ffd54a;
            }
            input, select, button {
                box-sizing: border-box;
                width: 100%;
                padding: 12px;
                margin: 8px 0;
                border-radius: 8px;
                border: 0;
                font-size: 16px;
            }
            button {
                background: #ffd54a;
                color: #101827;
                font-weight: bold;
            }
            a {
                color: #ffd54a;
                margin-right: 10px;
            }
            .notice {
                color: #9ee7b0;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <h1>Pocket Broker X9</h1>
                <p>Virtual demo only — no real money.</p>
                <a href="{{ url_for('home') }}">Home</a>
                <a href="{{ url_for('history') }}">History</a>
                {% if session.get('uid') %}
                    <a href="{{ url_for('logout') }}">Logout</a>
                {% else %}
                    <a href="{{ url_for('login') }}">Login</a>
                    <a href="{{ url_for('register') }}">Register</a>
                {% endif %}
            </div>
            {{ body|safe }}
        </div>
    </body>
    </html>
    """, title=title, body=body)


@app.route("/")
def home():
    if "uid" not in session:
        body = """
        <div class="card">
            <h2>Welcome!</h2>
            <p>Create an account or log in to try the demo.</p>
            <a href="/register">Create Account</a>
            <a href="/login">Login</a>
        </div>
        """
        return page("Home", body)

    with db() as c:
        user = c.execute(
            "SELECT username, balance FROM users WHERE id=?",
            (session["uid"],)
        ).fetchone()

    if user is None:
        session.clear()
        return redirect(url_for("login"))

    body = f"""
    <div class="card">
        <h2>Welcome, {user['username']}!</h2>
        <h2>Balance: {user['balance']:.2f} Demo Credits</h2>
        <p class="notice">These credits have no real-money value.</p>
        <a href="/deposit">Demo Deposit</a>
        <a href="/withdraw">Demo Withdraw</a>
    </div>
    """
    return page("Home", body)

@app.route("/register", methods=["GET", "POST"])
def register():
    message = ""

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if len(username) < 3 or len(password) < 6:
            message = "Username needs 3 characters and password needs 6."
        else:
            try:
                with db() as c:
                    c.execute(
                        """INSERT INTO users
                        (username, password_hash, balance, created_at)
                        VALUES (?, ?, ?, ?)""",
                        (
                            username,
                            generate_password_hash(password),
                            1000,
                            datetime.now().isoformat(timespec="seconds")
                        )
                    )
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                message = "That username is already taken."

    body = """
    <div class="card">
        <h2>Create Account</h2>
        <p>{{ message }}</p>
        <form method="post">
            <input name="username" placeholder="Username"
                   minlength="3" required>
            <input name="password" type="password"
                   placeholder="Password (6+ characters)"
                   minlength="6" required>
            <button type="submit">Register</button>
        </form>
    </div>
    """
    return render_template_string(
        page("Register", body), message=message
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    message = ""

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        with db() as c:
            user = c.execute(
                "SELECT * FROM users WHERE username=?",
                (username,)
            ).fetchone()

        if user and check_password_hash(
            user["password_hash"], password
        ):
            session.clear()
            session["uid"] = user["id"]
            return redirect(url_for("home"))

        message = "Incorrect username or password."

    body = """
    <div class="card">
        <h2>Login</h2>
        <p>{{ message }}</p>
        <form method="post">
            <input name="username" placeholder="Username" required>
            <input name="password" type="password"
                   placeholder="Password" required>
            <button type="submit">Login</button>
        </form>
    </div>
    """
    return render_template_string(
        page("Login", body), message=message
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/history")
@login_required
def history():
    with db() as c:
        requests_list = c.execute(
            """SELECT kind, method, amount, status, created_at
            FROM requests WHERE user_id=?
            ORDER BY id DESC LIMIT 50""",
            (session["uid"],)
        ).fetchall()

        bets_list = c.execute(
            """SELECT side, amount, result, profit, created_at
            FROM bets WHERE user_id=?
            ORDER BY id DESC LIMIT 50""",
            (session["uid"],)
        ).fetchall()

    body = """
    <div class="card">
        <h2>Demo Request History</h2>
        {% for r in requests_list %}
            <p>{{ r['kind'] }} — {{ r['amount'] }} credits
            — {{ r['status'] }} — {{ r['created_at'] }}</p>
        {% else %}
            <p>No demo requests yet.</p>
        {% endfor %}
    </div>
    <div class="card">
        <h2>Demo Trade History</h2>
        {% for b in bets_list %}
            <p>{{ b['side'] }} — {{ b['amount'] }} credits
            — {{ b['result'] }} — {{ b['created_at'] }}</p>
        {% else %}
            <p>No demo trades yet.</p>
        {% endfor %}
    </div>
    """
    return render_template_string(
        page("History", body),
        requests_list=requests_list,
        bets_list=bets_list
    )

@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    message = ""

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", "0"))
        except ValueError:
            amount = 0

        if not 1 <= amount <= 10000:
            message = "Enter an amount from 1 to 10000 demo credits."
        else:
            with db() as c:
                c.execute(
                    """INSERT INTO requests
                    (user_id, kind, method, amount, reference,
                     status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        session["uid"],
                        "Demo Deposit",
                        "Virtual",
                        amount,
                        "",
                        "Pending",
                        datetime.now().isoformat(timespec="seconds")
                    )
                )
            message = "Demo deposit request submitted for admin review."

    body = """
    <div class="card">
        <h2>Demo Deposit</h2>
        <p>{{ message }}</p>
        <p>Virtual credits only. No real payment is accepted.</p>
        <form method="post">
            <input type="number" name="amount"
                   min="1" max="10000" step="1"
                   placeholder="Demo credits" required>
            <button type="submit">Submit Demo Request</button>
        </form>
    </div>
    """
    return render_template_string(
        page("Demo Deposit", body), message=message
    )


@app.route("/withdraw", methods=["GET", "POST"])
@login_required
def withdraw():
    message = ""

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", "0"))
        except ValueError:
            amount = 0

        if not 1 <= amount <= 10000:
            message = "Enter an amount from 1 to 10000 demo credits."
        else:
            with db() as c:
                user = c.execute(
                    "SELECT balance FROM users WHERE id=?",
                    (session["uid"],)
                ).fetchone()

                pending = c.execute(
                    """SELECT COALESCE(SUM(amount), 0) AS total
                    FROM requests
                    WHERE user_id=? AND kind='Demo Withdraw'
                    AND status='Pending'""",
                    (session["uid"],)
                ).fetchone()["total"]

                if user is None:
                    session.clear()
                    return redirect(url_for("login"))

                available = user["balance"] - pending

                if amount > available:
                    message = "Not enough available demo credits."
                else:
                    c.execute(
                        """INSERT INTO requests
                        (user_id, kind, method, amount, reference,
                         status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            session["uid"],
                            "Demo Withdraw",
                            "Virtual",
                            amount,
                            "",
                            "Pending",
                            datetime.now().isoformat(timespec="seconds")
                        )
                    )
                    message = "Demo withdrawal request submitted."

    body = """
    <div class="card">
        <h2>Demo Withdraw</h2>
        <p>{{ message }}</p>
        <p>Virtual credits only. No real money will be sent.</p>
        <form method="post">
            <input type="number" name="amount"
                   min="1" max="10000" step="1"
                   placeholder="Demo credits" required>
            <button type="submit">Submit Demo Request</button>
        </form>
    </div>
    """
    return render_template_string(
        page("Demo Withdraw", body), message=message
    )

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    message = ""

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if (
            ADMIN_PASSWORD
            and username == ADMIN_USERNAME
            and password == ADMIN_PASSWORD
        ):
            session.clear()
            session["is_admin"] = True
            return redirect(url_for("admin"))

        message = "Invalid admin login. Check Render environment settings."

    body = render_template_string("""
    <div class="card">
        <h2>Admin Login</h2>
        <p>{{ message }}</p>
        <form method="post">
            <input name="username" placeholder="Admin username" required>
            <input name="password" type="password"
                   placeholder="Admin password" required>
            <button type="submit">Admin Login</button>
        </form>
    </div>
    """, message=message)

    return page("Admin Login", body)


@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():
    message = ""

    if request.method == "POST":
        request_id = request.form.get("request_id", type=int)
        action = request.form.get("action", "")

        if not request_id or action not in ("approve", "reject"):
            message = "Invalid request."
        else:
            with db() as c:
                item = c.execute(
                    """SELECT * FROM requests
                    WHERE id=? AND status='Pending'""",
                    (request_id,)
                ).fetchone()

                if item is None:
                    message = "Request not found or already processed."
                elif action == "reject":
                    c.execute(
                        "UPDATE requests SET status='Rejected' "
                        "WHERE id=? AND status='Pending'",
                        (request_id,)
                    )
                    message = "Request rejected."
                else:
                    user = c.execute(
                        "SELECT balance FROM users WHERE id=?",
                        (item["user_id"],)
                    ).fetchone()

                    if item["kind"] == "Demo Deposit":
                        c.execute(
                            "UPDATE users SET balance=balance+? WHERE id=?",
                            (item["amount"], item["user_id"])
                        )
                        c.execute(
                            "UPDATE requests SET status='Approved' "
                            "WHERE id=? AND status='Pending'",
                            (request_id,)
                        )
                        message = "Demo credits added."
                    elif item["kind"] == "Demo Withdraw":
                        pending = c.execute(
                            """SELECT COALESCE(SUM(amount), 0) AS total
                            FROM requests
                            WHERE user_id=? AND kind='Demo Withdraw'
                            AND status='Pending' AND id<>?""",
                            (item["user_id"], request_id)
                        ).fetchone()["total"]

                        if (
                            user is None
                            or user["balance"] < item["amount"]
                            or user["balance"] - pending < item["amount"]
                        ):
                            message = "Insufficient demo balance; reject this request."
                        else:
                            c.execute(
                                "UPDATE users SET balance=balance-? WHERE id=?",
                                (item["amount"], item["user_id"])
                            )
                            c.execute(
                                "UPDATE requests SET status='Approved' "
                                "WHERE id=? AND status='Pending'",
                                (request_id,)
                            )
                            message = "Demo credits deducted."
                    else:
                        message = "Unknown request type."

    with db() as c:
        requests_list = c.execute(
            """SELECT requests.*, users.username
            FROM requests
            JOIN users ON users.id=requests.user_id
            ORDER BY requests.id DESC LIMIT 100"""
        ).fetchall()

    body = render_template_string("""
    <div class="card">
        <h2>Admin Panel</h2>
        <p>{{ message }}</p>
        <p>Demo credits only. No real-money payments.</p>
        <a href="/logout">Admin Logout</a>
    </div>

    {% for r in requests_list %}
    <div class="card">
        <p><b>Request #{{ r['id'] }}</b></p>
        <p>User: {{ r['username'] }}</p>
        <p>Type: {{ r['kind'] }}</p>
        <p>Amount: {{ r['amount'] }} demo credits</p>
        <p>Status: {{ r['status'] }}</p>

        {% if r['status'] == 'Pending' %}
        <form method="post">
            <input type="hidden" name="request_id"
                   value="{{ r['id'] }}">
            <button name="action" value="approve">
                Approve Demo Request
            </button>
            <button name="action" value="reject">
                Reject Request
            </button>
        </form>
        {% endif %}
    </div>
    {% else %}
    <div class="card"><p>No requests found.</p></div>
    {% endfor %}
    """, message=message, requests_list=requests_list)

    return page("Admin Panel", body)

@app.errorhandler(404)
def not_found(error):
    return page(
        "Not Found",
        '<div class="card"><h2>Page not found</h2>'
        '<a href="/">Go Home</a></div>'
    ), 404


@app.errorhandler(500)
def server_error(error):
    return page(
        "Server Error",
        '<div class="card"><h2>Something went wrong.</h2>'
        '<a href="/">Go Home</a></div>'
    ), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
