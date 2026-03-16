from flask import Flask, render_template, redirect, request, flash, abort, session, jsonify # Import necessary functions and classes from the Flask library for web application development, including rendering templates, handling redirects, processing requests, flashing messages, aborting requests, managing sessions, and returning JSON responses

from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin # Import necessary functions and classes from the Flask-Login library for user authentication and session management

import pymysql # Import the PyMySQL library for MySQL database connection

from dynaconf import Dynaconf # Import the Dynaconf library for configuration management

from ai_model import predict_volume  # import the AI function


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



# Define a route for the homepage of the web application, which renders the "homepage.html.jinja" template when accessed.
@app.route("/")
def index():
    return render_template("homepage.html.jinja")

#for login page------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        username = request.form.get('username')
        password = request.form.get('password')

        connection = connect_db()
        cursor = connection.cursor()

        cursor.execute("SELECT * FROM User WHERE Username = %s", (username,))
        result = cursor.fetchone()

        connection.close()

        if result is None:
            flash("Username not registered!")
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
@app.route("/wheelofdrinks")
@login_required
def wheelofdrinks():

    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT SUM(Points) AS total_points
        FROM `Water Consumption`
        WHERE UserID = %s
    """, (current_user.id,))

    result = cursor.fetchone()
    points = result["total_points"] if result["total_points"] else 0

    connection.close()

    return render_template(
        "wheelofdrinks.html.jinja",
        coins=points
    )

#for the gacha spin page------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route("/gacha_spin", methods=["POST"])
@login_required
def gacha_spin():

    data = request.json
    plays = int(data["plays"])

    cost = plays * 10

    connection = connect_db()
    cursor = connection.cursor()

    # get user's points
    cursor.execute("""
        SELECT SUM(Points) AS total_points
        FROM `Water Consumption`
        WHERE UserID = %s
    """, (current_user.id,))

    result = cursor.fetchone()
    points = result["total_points"] if result["total_points"] else 0


    # THIS IS THE IF STATEMENT THAT CHECKS IF THE USER HAS ENOUGH POINTS TO PLAY THE GACHA SPIN. IF THE USER DOES NOT HAVE ENOUGH POINTS, IT CLOSES THE DATABASE CONNECTION AND RETURNS A JSON RESPONSE INDICATING FAILURE AND A MESSAGE STATING "Not enough points".
    if points < cost:
        connection.close()
        return jsonify({
            "success": False,
            "message": "Not enough points"
        })


    # get rewards from Rewards table 
    cursor.execute("""
        SELECT ID, Name, Image
        FROM Rewards
        ORDER BY RAND()
        LIMIT %s
    """, (plays,))

    rewards = cursor.fetchall()

    # save rewards to UserRewards
    for reward in rewards:

        cursor.execute("""
        INSERT INTO UserRewards (UserID, RewardsID)
        VALUES (%s, %s)
        """, (current_user.id, reward["ID"]))


    session["rewards"] = rewards

    connection.close()

    return jsonify({"success": True})

#for the results page------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route("/results")
@login_required
def results():

    rewards = session.get("rewards", [])

    return render_template(
        "results.html.jinja",
        rewards=rewards
    )
#for the account page------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route("/Accountpage")
def account_page():

    return render_template("Accountpage.html.jinja")

#for the friends page------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route('/friends')
def friend_list():
    
    return render_template("friends.html.jinja")


#for the logout page------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/")
#for the ai I am not sure if it works yet------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route("/predict", methods=["POST"])
def predict():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    predicted_volume = predict_volume(file)
    return jsonify({"predicted_volume": predicted_volume})

#for the tracker page(still need to connect to the user input from the photo they take------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route("/tracker")  
def tracker():
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    tracker_data = {
        "Monday": 2,
        "Tuesday": 5,
        "Wednesday": 2,
        "Thursday": 0,
        "Friday": 0,
        "Saturday": 0,
        "Sunday": 0
    }
    return render_template("tracker.html.jinja", days=days, tracker_data=tracker_data)
#for the camera (incomplete) ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route("/camera")
def camera():
    return render_template("camera.html.jinja")

#for the health data page where users can input their health data and it will be saved to the database.----------------------------------------------------------------------------------------------------------------------
@app.route("/healthdata", methods=["GET", "POST"])
@login_required
def healthdata():

    if request.method == "POST":

        age = request.form.get("age")
        weight = request.form.get("weight")
        sex = request.form.get("sex")
        exercise = request.form.get("exercise")
        climate = request.form.get("climate")

        health = request.form.getlist("health")
        health_string = ", ".join(health)

        connection = connect_db()
        cursor = connection.cursor()

        cursor.execute("""
        INSERT INTO `Health Data`
        (UserID, Weight, Sex, `Daily Exercise`, `Local Weather`, `Health Considerations`)
        VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            current_user.id,
            weight,
            sex,
            exercise,
            climate,
            health_string
        ))

        connection.close()

        flash("Health data saved!")
        return redirect("/Accountpage")

    return render_template("healthdata.html.jinja")


