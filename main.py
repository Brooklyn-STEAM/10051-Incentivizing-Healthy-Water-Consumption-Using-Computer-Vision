from flask import Flask, render_template, redirect, request, flash, abort, jsonify, session # Import necessary functions and classes from the Flask library for web application development, including rendering templates, handling redirects, processing requests, flashing messages, and aborting requests

from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin # Import necessary functions and classes from the Flask-Login library for user authentication and session management

import pymysql # Import the PyMySQL library for MySQL database connection

import base64 # used for images

import os #used to upload files

import math # used for the to do the math for the conversion of ml to fl oz and cups

from dynaconf import Dynaconf # Import the Dynaconf library for configuration management

from datetime import datetime #helps get the date and time for the tracker page

from ai_model import load_model, predict_capacity #for the ai to load and work

model = load_model()





config = Dynaconf(settings_files=['settings.toml'])

app = Flask(__name__)# Create a Flask application instance

tracker_data = {
    "Monday":0,
    "Tuesday":0,
    "Wednesday":0,
    "Thursday":0,
    "Friday":0,
    "Saturday":0,
    "Sunday":0
} #used for the tracker data

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
            return redirect("/Accountpage")
           
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
            return redirect("/healthdata")
        
    return render_template("register.html.jinja")

#for the health data page------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route("/healthdata", methods=["GET", "POST"])
def health_data():
    if request.method == "POST":

        # ✅ GET FORM DATA
        weight = float(request.form["Weight"])
        sex = request.form["Sex"]
        active = request.form["Active level"]
        exercise = request.form["Daily Excersize"]
        climate = request.form["Climate"]
        health = request.form["Health"]

        # ✅ AGE FROM BIRTHDATE
        birthday_str = request.form["Age"]
        birth_date = datetime.strptime(birthday_str, "%Y-%m-%d")
        today = datetime.today()
        age = today.year - birth_date.year - (
            (today.month, today.day) < (birth_date.month, birth_date.day)
        )

        # 💧 DEFAULT VALUES
        sex_oz = 1
        exercise_oz = 0
        climate_oz = 1
        health_mult = 1
        health_bonus = 0

        # 💧 SEX (G)
        if sex == "Female":
            sex_oz = 0.95
        elif sex == "Male":
            sex_oz = 1.05

        # 💧 EXERCISE
        if exercise == "0-30":
            exercise_oz = 12
        elif exercise == "30-60":
            exercise_oz = 24
        elif exercise == "1-2":
            exercise_oz = 36
        elif exercise == "2+":
            exercise_oz = 48

        # 💧 CLIMATE (C)
        if climate == "Cold":
            climate_oz = 0.9
        elif climate == "Mild":
            climate_oz = 1
        elif climate == "Hot":
            climate_oz = 1.2

        # 💧 HEALTH (H + S)
        if health == "Currently sick":
            health_bonus = 16
        elif health == "Kidney problems":
            health_mult = 0.9
        elif health == "Heart condition":
            health_mult = 0.85

        # 💧 FINAL FORMULA
        water_oz = ((weight / 2) + exercise_oz) * health_mult * climate_oz * sex_oz + health_bonus

        # 💧 CONVERT TO CUPS
        import math
        cups = math.ceil(water_oz / 8)

        # ✅ STORE RESULT
        session["cups"] = cups

        return redirect("/tracker")

    return render_template("healthdata.html.jinja")
     


#for account page(second homepage)------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route("/Accountpage")
def account_page():
    return render_template("Accountpage.html.jinja")

#for the friends page------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route('/friends')
def friend_list():
    return render_template("friends.html.jinja")



#for the ai I am not sure if it works yet------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route("/predict", methods=["POST"])
def predict():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]

    # predict_capacity returns ml and fl_oz as separate floats
    predicted_ml, predicted_oz = predict_capacity(file)

    return jsonify({
        "predicted_volume_ml": predicted_ml,
        "predicted_volume_oz": predicted_oz
    })

#for the tracker page(still need to connect to the user input from the photo they take------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route('/tracker')
@login_required
def tracker():
    user_id = current_user.id

    # initialize tracker dictionary
    tracker_data = {day:0 for day in ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]}

    connection = connect_db()
    cursor = connection.cursor(pymysql.cursors.DictCursor)
    try:
        cursor.execute("""
            SELECT Day, SUM(Volume) AS total_volume
            FROM water_log
            WHERE UserID = %s
            GROUP BY Day
        """, (user_id,))
        results = cursor.fetchall()
        for row in results:
            tracker_data[row['Day']] = row['total_volume'] / 20  # convert ml → drops
    except Exception as e:
        print("Error fetching tracker data:", e)
    finally:
        cursor.close()
        connection.close()

    days = list(tracker_data.keys())
    return render_template("tracker.html.jinja", days=days, tracker_data=tracker_data)


@app.route('/capture', methods=['POST'])
@login_required
def capture():
    if "file" not in request.files:
        flash("No file uploaded")
        return redirect("/camera")

    file = request.files["file"]
    if file.filename == "":
        flash("No selected file")
        return redirect("/camera")

    # Save uploaded image
    filename = f"drink_{datetime.now().timestamp()}.jpg"
    filepath = os.path.join("static/user_uploads", filename)
    file.save(filepath)

    # Predict container capacity in mL
    capacity_ml, capacity_oz = predict_capacity(filepath)
    # Convert to cups
    volume_cups = capacity_ml / 240 

    # Save prediction to DB
    connection = connect_db()
    cursor = connection.cursor()
    try:
        cursor.execute("""
        INSERT INTO `Water Consumption` (UserID, Points, Oz, Timestamp, Image)
        VALUES (%s, %s, %s, NOW(), %s)
        """, (current_user.id, 0, volume_cups, filename))
        connection.commit()
    finally:
        cursor.close()
        connection.close()

    flash(f"Drink logged: {volume_cups:.2f} cups")
    return redirect("/tracker")

@app.route('/add_drink', methods=['POST'])
@login_required
def add_drink():
    ounces = request.form.get("ounces", type=float)

    if not ounces or ounces <= 0:
        return {"success": False, "message": "Invalid amount"}

    volume_cups = ounces / 8

    connection = connect_db()
    cursor = connection.cursor()
    try:
        cursor.execute("""
        INSERT INTO `Water Consumption` (UserID, Points, Oz, Timestamp, Image)
        VALUES (%s, %s, %s, NOW(), %s)
        """, (current_user.id, 0, volume_cups, None))
        connection.commit()
    finally:
        cursor.close()
        connection.close()

    flash(f"Drink logged: {ounces} oz ({volume_cups:.2f} cups)")   
    return redirect("/tracker")

# ----------------------------
# TESTING PREDICTION
# ----------------------------
if __name__ == "__main__":
    test_image = "static/user_uploads/drink_1774962039.119192.jpg"

    predicted_ml, predicted_oz = predict_capacity(test_image)

    print(f"Predicted volume: {predicted_ml:.1f} mL / {predicted_oz:.2f} fl oz")
