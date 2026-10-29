    <button>Submit Demo Request</button></form></div>"""
    return page("Withdraw", body)

@app.route("/history")
@login_required
def history():
    with db() as c:
        bets = c.execute("SELECT side,amount,result,profit,created_at FROM bets WHERE user_id=? ORDER BY id DESC LIMIT 100", (session["uid"],)).fetchall()
        reqs = c.execute("SELECT kind,method,amount,status,created_at FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 100", (session["uid"],)).fetchall()
    rows = ''.join(f"<tr><td>{b['side']}</td><td>{b['amount']}</td><td>{b['result']}</td><td>{b['profit']}</td></tr>" for b in bets) or '<tr><td colspan="4">No trades</td></tr>'
    rrows = ''.join(f"<tr><td>{r['kind']}</td><td>{r['method']}</td><td>{r['amount']}</td><td>{r['status']}</td></tr>" for r in reqs) or '<tr><td colspan="4">No requests</td></tr>'
    return page("History", f'<div class="card"><h3>Trades</h3><table><tr><th>Side</th><th>Bet</th><th>Result</th><th>Profit</th></tr>{rows}</table></div><div class="card"><h3>Deposit/withdraw requests</h3><table><tr><th>Type</th><th>Method</th><th>Amount</th><th>Status</th></tr>{rrows}</table></div>')

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if len(username) < 3 or len(username) > 30 or len(password) < 8:
            flash("Username must be 3–30 characters; password at least 8 characters.")
        else:
            try:
                with db() as c:
                    c.execute("INSERT INTO users(username,password_hash,created_at) VALUES(?,?,?)",
                              (username, generate_password_hash(password), datetime.utcnow().isoformat()))
                flash("Account created. Log in to continue.")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("That username is already taken.")
    return page("Register", '<div class="card"><form method="post"><label>Username</label><input name="username" minlength="3" maxlength="30" required><label>Password (8+ characters)</label><input type="password" name="password" minlength="8" required><button>Create account</button></form><p><a href="/login">Already registered? Log in</a></p></div>')

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with db() as c:
            user = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["uid"] = user["id"]
            session["username"] = user["username"]
            session["is_admin"] = bool(ADMIN_PASSWORD and username == ADMIN_USERNAME and check_password_hash(user["password_hash"], ADMIN_PASSWORD))
            return redirect(url_for("admin" if session["is_admin"] else "home"))
        flash("Username or password is incorrect.")
    return page("Login", '<div class="card"><form method="post"><label>Username</label><input name="username" required><label>Password</label><input type="password" name="password" required><button>Log in</button></form><p><a href="/register">Create account</a></p></div>')

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/admin", methods=["GET", "POST"])
@login_required
@admin_required
def admin():
    if request.method == "POST":
        action = request.form.get("action", "")
        with db() as c:
            if action in ("UP", "DOWN", "AUTO"):
                set_setting(c, "direction", action)
                flash("Next round direction updated.")
            elif action.startswith("approve:") or action.startswith("reject:"):
                decision, raw_id = action.split(":", 1)
                try: rid = int(raw_id)
                except ValueError: rid = -1
                req = c.execute("SELECT * FROM requests WHERE id=? AND status='Pending'", (rid,)).fetchone()
                if req:
                    if decision == "approve":
                        if req["kind"] == "Deposit":
                            c.execute("UPDATE users SET balance=balance+? WHERE id=?", (req["amount"], req["user_id"]))
                        c.execute("UPDATE requests SET status='Approved' WHERE id=?", (rid,))
                    else:
                        if req["kind"] == "Withdraw":
                            c.execute("UPDATE users SET balance=balance+? WHERE id=?", (req["amount"], req["user_id"]))
                        c.execute("UPDATE requests SET status='Rejected' WHERE id=?", (rid,))
                    flash("Request updated.")
        return redirect(url_for("admin"))
    with db() as c:
        users = c.execute("SELECT id,username,balance,created_at FROM users ORDER BY id DESC").fetchall()
        requests = c.execute("SELECT requests.*,users.username FROM requests JOIN users ON users.id=requests.user_id ORDER BY requests.id DESC LIMIT 100").fetchall()
        bets = c.execute("SELECT bets.*,users.username FROM bets JOIN users ON users.id=bets.user_id ORDER BY bets.id DESC LIMIT 100").fetchall()
        direction = get_setting(c, "direction", "AUTO")
    urows = ''.join(f"<tr><td>{u['username']}</td><td>{u['balance']}</td></tr>" for u in users)
    qrows = ''.join(f"""<tr><td>{r['username']}</td><td>{r['kind']}</td><td>{r['method']}</td><td>{r['amount']}</td><td>{r['reference']}</td><td>{r['status']}</td><td>{('<form method="post"><button class="smallbtn" name="action" value="approve:'+str(r['id'])+'">Approve</button><button class="smallbtn" name="action" value="reject:'+str(r['id'])+'">Reject</button></form>') if r['status']=='Pending' else ''}</td></tr>""" for r in requests)
    brows = ''.join(f"<tr><td>{b['username']}</td><td>{b['side']}</td><td>{b['amount']}</td><td>{b['result']}</td></tr>" for b in bets)
    body = f"""
    <div class="card"><h3>Next round direction</h3><p>Current setting: <b>{direction}</b></p>
    <form method="post"><div class="grid"><button name="action" value="UP">Next: UP</button><button name="action" value="DOWN">Next: DOWN</button></div><p><button name="action" value="AUTO">Automatic random direction</button></p></form></div>
    <div class="card"><h3>Users and balances</h3><table><tr><th>Username</th><th>Balance</th></tr>{urows}</table></div>
    <div class="card"><h3>Deposit/withdraw requests</h3><table><tr><th>User</th><th>Type</th><th>Method</th><th>Amount</th><th>Reference</th><th>Status</th><th>Action</th></tr>{qrows or '<tr><td colspan="7">No requests</td></tr>'}</table></div>
    <div class="card"><h3>All demo trades</h3><table><tr><th>User</th><th>Side</th><th>Bet</th><th>Result</th></tr>{brows or '<tr><td colspan="4">No trades</td></tr>'}</table></div>
    """
    return page("Admin Panel", body)

@app.errorhandler(403)
def forbidden(error):
    return page("Access denied", "<div class='card'>Admin access only.</div>"), 403

if __name__ == "__main__":
    if not ADMIN_PASSWORD:
        print("WARNING: Set ADMIN_PASSWORD and ADMIN_USERNAME environment variables before deployment.")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)

