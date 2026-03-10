from flask import Flask, render_template, redirect, request, flash, abort # Import necessary functions and classes from the Flask library for web application development, including rendering templates, handling redirects, processing requests, flashing messages, and aborting requests

from flask_login import LoginManager, login_user, logout_user, login_required, current_user # Import necessary functions and classes from the Flask-Login library for user authentication and session management

import pymysql # Import the PyMySQL library for MySQL database connection

from dynaconf import Dynaconf # Import the Dynaconf library for configuration management


app = Flask(__name__)# Create a Flask application instance
app.secret_key = "nchdwnuhwwenedwn"

config = Dynaconf(settings_file = ["settings.toml"]) # Load the configuration from the settings.toml file




#connect to database------------------------------------------------------------------------------------------------
def connect_db():
    conn = pymysql.connect(
        host=config.host,
        user=config.username,
        password=config.password,
        database="daily_drip",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor
    )
    return conn

#All of this is connect routes for the website, they will render the html pages that are in the templates folder. 
@app.route("/")
def index():
    return render_template("homepage.html.jinja")

#for login page------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        email = request.form.get('email')
        password = request.form.get('password')

        connection = connect_db()

        cursor = connection.cursor()

        cursor.execute("SELECT * FROM User WHERE Email = %s", (email,))

        print(cursor)

        result = cursor.fetchone()

        connection.close()

        if result is None:
            flash("Email not registered!")
        elif password != result['Password']:
            flash("Incorrect password!")
        else:
            login_user(User(result))
            return redirect('/Accountpage')
       
        
    return render_template("login.html.jinja")

#for register page------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if password != confirm_password:
            flash("Passwords do not match!")
            return render_template("register.html.jinja")

        if len(password) < 8:
            flash("Password must be at least 8 characters long")
            return render_template("register.html.jinja")

        connection = connect_db()
        cursor = connection.cursor()

        # Check if email already exists
        cursor.execute("SELECT * FROM User WHERE Email = %s", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash("Email already registered!")
            connection.close()
            return render_template("register.html.jinja")

        # Insert new user
        cursor.execute("""
            INSERT INTO User (Username, Email, Password)
            VALUES (%s, %s, %s)
        """, (name, email, password))

        connection.close()

        flash("Account created successfully!")
        return redirect("/login")

    return render_template("register.html.jinja")
#for the wheel of drinks page------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route("/Wheelofdrinks")
def wheel():
 #Connect to the database and retrieve all the drink names from the Drink table, then render the Wheelofdrinks.html.jinja template with the retrieved drink names passed as a variable for display on the page.
        connection = connect_db()
        cursor = connection.cursor()
        cursor.execute("SELECT Name FROM Recipe")
        Rewards = cursor.fetchall() 

        return render_template("Wheelofdrinks.html.jinja")
@app.route("/Accountpage")
def account_page():

    return render_template("Accountpage.html.jinja")

@app.route('/friends')
def friend_list():
    
    return render_template("friends.html.jinja")





