import os  # lets us work with file paths (to find where to save the database)
import sqlite3  # Python's built-in database tool
from datetime import date  # gives us today's date
from functools import wraps  # helps us build the "login required" check
from flask import Flask, render_template, request, redirect, url_for, session  # Flask tools we need
from werkzeug.security import generate_password_hash, check_password_hash  # tools to scramble and check passwords

app = Flask(__name__)  # creates our web app
app.secret_key = "Shining-in-the-Sand-and-Sun-Like-A-Pearl-Upon-the-Ocean-Come-and-Feel-Me"  # secret text Flask uses to protect login sessions

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # finds the folder where this file is saved
DB = os.path.join(BASE_DIR, "tracker.db")  # database file path: same folder, file named tracker.db


def get_db():  # function that opens a connection to the database
    conn = sqlite3.connect(DB)  # connect to the database file (creates it if missing)
    conn.row_factory = sqlite3.Row  # lets us read columns by name, like row["amount"]
    return conn  # give the connection back to whoever called this function


def init_db():  # function that creates the tables when the app starts
    conn = get_db()  # open the database
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)  # makes the users table: id (auto number), username (no duplicates), scrambled password
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            note TEXT
        )
    """)  # makes the expenses table: user_id says which user owns each expense
    conn.commit()  # saves the changes to the database file
    conn.close()  # closes the connection


init_db()  # runs the function above once, as soon as the app starts


def login_required(f):  # a "checker" we can put on any page that needs login
    @wraps(f)  # keeps the original function's name (Flask needs this)
    def wrapper(*args, **kwargs):  # this runs before the real page function
        if "user_id" not in session:  # if nobody is logged in...
            return redirect(url_for("login"))  # ...send them to the login page
        return f(*args, **kwargs)  # otherwise, run the real page function
    return wrapper  # give back the checked version of the function


@app.route("/register", methods=["GET", "POST"])  # the /register page; GET = open page, POST = submit form
def register():  # function that runs for the register page
    error = None  # no error message yet
    if request.method == "POST":  # true when the user pressed the Register button
        username = request.form["username"].strip()  # read the username box, remove extra spaces
        password = request.form["password"]  # read the password box
        if len(username) < 3 or len(password) < 6:  # check the lengths
            error = "Username needs 3+ characters and password needs 6+."  # message to show
        else:  # lengths are fine
            conn = get_db()  # open the database
            try:  # try to save the new user
                conn.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )  # adds the user; the password is scrambled (hashed) before saving
                conn.commit()  # save the change
                conn.close()  # close the database
                return redirect(url_for("login"))  # success: go to the login page
            except sqlite3.IntegrityError:  # happens if the username already exists
                conn.close()  # close the database
                error = "That username is already taken."  # message to show
    return render_template("register.html", error=error)  # show the register page (with error if any)


@app.route("/login", methods=["GET", "POST"])  # the /login page
def login():  # function that runs for the login page
    error = None  # no error message yet
    if request.method == "POST":  # true when the user pressed the Login button
        username = request.form["username"].strip()  # read the username box
        password = request.form["password"]  # read the password box
        conn = get_db()  # open the database
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()  # look for one user with this username
        conn.close()  # close the database
        if user and check_password_hash(user["password_hash"], password):  # user exists AND password matches
            session["user_id"] = user["id"]  # remember the user's id (this means "logged in")
            session["username"] = user["username"]  # remember the username to show on the page
            return redirect(url_for("index"))  # go to the main page
        error = "Wrong username or password."  # message to show if login failed
    return render_template("login.html", error=error)  # show the login page (with error if any)


@app.route("/logout")  # the /logout page
def logout():  # function that runs when the user logs out
    session.clear()  # forget everything about the user (logs them out)
    return redirect(url_for("login"))  # send them back to the login page


@app.route("/")  # the main page (home)
@login_required  # only logged-in users can open it
def index():  # function that builds the main page
    uid = session["user_id"]  # get the id of the logged-in user
    today = date.today().isoformat()  # today's date as text, like 2026-10-08
    this_month = today[:7]  # first 7 characters = the month, like 2026-10
    conn = get_db()  # open the database

    expenses = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC, id DESC",
        (uid,),
    ).fetchall()  # all of this user's expenses, newest first

    totals = conn.execute(
        "SELECT category, SUM(amount) AS total FROM expenses "
        "WHERE user_id = ? GROUP BY category",
        (uid,),
    ).fetchall()  # total spending for each category (for the pie chart)

    daily = conn.execute(
        "SELECT date, SUM(amount) AS total FROM expenses "
        "WHERE user_id = ? GROUP BY date ORDER BY date DESC LIMIT 30",
        (uid,),
    ).fetchall()  # total spending for each day, newest first, max 30 days

    monthly = conn.execute(
        "SELECT strftime('%Y-%m', date) AS month, SUM(amount) AS total FROM expenses "
        "WHERE user_id = ? GROUP BY month ORDER BY month DESC LIMIT 12",
        (uid,),
    ).fetchall()  # total spending for each month, max 12 months

    today_total = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ? AND date = ?",
        (uid, today),
    ).fetchone()[0]  # total spent today (0 if there are no expenses)

    month_total = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses "
        "WHERE user_id = ? AND strftime('%Y-%m', date) = ?",
        (uid, this_month),
    ).fetchone()[0]  # total spent in the current month

    conn.close()  # close the database

    labels = [row["category"] for row in totals]  # category names (pie chart)
    values = [row["total"] for row in totals]  # category totals (pie chart)

    daily_labels = [row["date"] for row in reversed(daily)]  # day names, oldest first so the chart reads left to right
    daily_values = [row["total"] for row in reversed(daily)]  # day totals in the same order

    monthly_labels = [row["month"] for row in reversed(monthly)]  # month names, oldest first
    monthly_values = [row["total"] for row in reversed(monthly)]  # month totals in the same order

    return render_template(
        "index.html",  # the HTML file to show
        expenses=expenses,  # send the expense list to the page
        labels=labels,  # send the category names to the page
        values=values,  # send the category totals to the page
        grand_total=sum(values),  # send the total of everything
        today=today,  # send today's date
        username=session["username"],  # send the username to show at the top
        daily=daily,  # send the daily rows (for the table)
        monthly=monthly,  # send the monthly rows (for the table)
        daily_labels=daily_labels,  # send day names (for the chart)
        daily_values=daily_values,  # send day totals (for the chart)
        monthly_labels=monthly_labels,  # send month names (for the chart)
        monthly_values=monthly_values,  # send month totals (for the chart)
        today_total=today_total,  # send today's total
        month_total=month_total,  # send this month's total
    )


@app.route("/add", methods=["POST"])  # the /add page; only accepts form submissions
@login_required  # only logged-in users
def add():  # function that adds a new expense
    amount = float(request.form["amount"])  # read the amount and turn it into a number
    if amount <= 0:  # reject zero or negative amounts
        return redirect(url_for("index"))  # go back without saving

    conn = get_db()  # open the database
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, note) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            session["user_id"],  # which user owns this expense
            amount,  # the amount
            request.form["category"],  # the category chosen in the dropdown
            request.form["date"],  # the date chosen
            request.form["note"],  # the note typed
        ),
    )  # saves the new expense
    conn.commit()  # save the change
    conn.close()  # close the database
    return redirect(url_for("index"))  # go back to the main page


@app.route("/delete/<int:expense_id>", methods=["POST"])  # /delete/5 deletes expense number 5
@login_required  # only logged-in users
def delete(expense_id):  # function that deletes an expense
    conn = get_db()  # open the database
    conn.execute(
        "DELETE FROM expenses WHERE id = ? AND user_id = ?",
        (expense_id, session["user_id"]),
    )  # delete it ONLY if it belongs to this user
    conn.commit()  # save the change
    conn.close()  # close the database
    return redirect(url_for("index"))  # go back to the main page


if __name__ == "__main__":  # true only when you run this file directly
    app.run(debug=True)  # starts the app on your laptop (debug=True shows helpful errors)