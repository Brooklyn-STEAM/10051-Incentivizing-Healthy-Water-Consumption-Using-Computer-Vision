from flask import Flask, render_template, redirect, request, flash, abort # Import necessary functions and classes from the Flask library for web application development, including rendering templates, handling redirects, processing requests, flashing messages, and aborting requests

from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin # Import necessary functions and classes from the Flask-Login library for user authentication and session management

import pymysql # Import the PyMySQL library for MySQL database connection

from dynaconf import Dynaconf # Import the Dynaconf library for configuration management


config = Dynaconf(settings_files=['settings.toml'])

app = Flask(__name__)# Create a Flask application instance

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login" 
app.secret_key = "nchdwnuhwwenedwn"

class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data["ID"]
        self.name = user_data["Name"]
        self.email = user_data["Email"]

config = Dynaconf(settings_file = ["settings.toml"]) # Load the configuration from the settings.toml file

# Define a user loader function for Flask-Login to load a user from the database based on the user ID stored in the session. This function connects to the database, retrieves the user data, and returns a User object if found, or None if not found.
@login_manager.user_loader 
def load_user(user_id):

    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM User WHERE ID = %s", (user_id,))
    user = cursor.fetchone()

    connection.close()

    if user:
        return User(user)

    return None

#connect to database------------------------------------------------------------------------------------------------
def connect_db():
    conn = pymysql.connect(
        host="db.steamcenter.tech",
        user=config.USER,
        password=config.PASSWORD,
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
            return redirect('/browse')
       
        
    return render_template("login.html.jinja")

#for register page------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":
        name = request.form["name"]
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        
        if password != confirm_password:
            flash("Passwords do not match!")
            return render_template("register.html.jinja")

        elif len(password) < 8:
            flash("Password must be at least 8 characters long")
            return render_template("register.html.jinja")
        else:
            connection = connect_db()
            cursor = connection.cursor()
            try: 
                 # Insert new user
                cursor.execute("""
                INSERT INTO User (Name, Email, Password, Username)
                VALUES (%s, %s, %s, %s)
                    """, (name, email, password, username))
                connection.close()

            except pymysql.err.IntegrityError:
                        flash("Email already registered!")
                        connection.close()
                        return render_template("register.html.jinja")
            else:
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

        connection.close()

        return render_template("Wheelofdrinks.html.jinja")


