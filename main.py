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


@app.route("/camera")
@login_required
def camera():
    return render_template("camera.html.jinja")

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
        INSERT INTO `Water Consumption` (UserID, Points, Cups, Timestamp, Image)
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
import traceback
import random
from flask import Flask, render_template, redirect, request, flash, abort, session, jsonify, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
import pymysql
from dynaconf import Dynaconf
from ai_model import predict_volume
  # keep if used elsewhere

# Load configuration
config = Dynaconf(settings_files=["settings.toml"])

app = Flask(__name__)
app.secret_key = config.get("SECRET_KEY", "replace-me-with-secret")

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

# --- User class --------------------------------------------------------------
class User(UserMixin):
    def __init__(self, id, username=None, email=None):
        self.id = str(id)
        self.username = username
        self.email = email

    def __repr__(self):
        return f"<User id={self.id} username={self.username}>"

# --- Database connection -----------------------------------------------------
def connect_db():
    return pymysql.connect(
        host=config.get("DB_HOST", "db.steamcenter.tech"),
        user=config.USER,
        password=config.PASSWORD,
        database=config.get("DB_NAME", "daily_drip"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False
    )

# --- Flask-Login user loader -------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM `User` WHERE ID = %s", (user_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return User(id=row["ID"], username=row.get("Username"), email=row.get("Email"))
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        conn.close()

# --- Utility: weighted reward picker ----------------------------------------
def pick_weighted_rewards(all_rewards, count):
    """
    all_rewards: list of dicts with at least keys 'ID' and 'Weight'
    count: number of picks
    """
    pool = []
    for r in all_rewards:
        weight = int(r.get("Weight", 1) or 1)
        pool.extend([r] * max(1, weight))
    if not pool:
        return []
    return [random.choice(pool) for _ in range(count)]

# --- Routes ------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("homepage.html.jinja")

# Login route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM User WHERE Username = %s", (username,))
            result = cursor.fetchone()
        finally:
            try:
                cursor.close()
            except Exception:
                pass
            conn.close()

        if result is None:
            flash("Username not registered!")
        elif password != result.get("Password"):
            flash("Incorrect password!")
        else:
            user = User(id=result["ID"], username=result.get("Username"), email=result.get("Email"))
            login_user(user)
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE User SET is_online = 1 WHERE ID = %s",
                (user.id,))
            conn.commit()
            cursor.close()
            conn.close()
            return redirect(url_for("wheelofdrinks"))

    return render_template("login.html.jinja")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if password != confirm_password:
            flash("Passwords do not match!")
            return render_template("register.html.jinja")
        if len(password or "") < 8:
            flash("Password must be at least 8 characters long")
            return render_template("register.html.jinja")

        conn = connect_db()
        try:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO `User` (Name, Email, Password, Username)
                    VALUES (%s, %s, %s, %s)
                """, (name, email, password, username))
                conn.commit()
            except pymysql.err.IntegrityError:
                conn.rollback()
                flash("Email or username already registered!")
                return render_template("register.html.jinja")
        finally:
            try:
                cursor.close()
            except Exception:
                pass
            conn.close()

        flash("Account created successfully!")
        return redirect(url_for("login"))

    return render_template("register.html.jinja")

# Wheel of drinks route
@app.route("/wheelofdrinks")
@login_required
def wheelofdrinks():
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT COALESCE(SUM(Points), 0) AS total_points
            FROM `Water Consumption`
            WHERE UserID = %s
        """, (current_user.id,))
        result = cursor.fetchone()
        points = (result or {}).get("total_points", 0) or 0

        cursor.execute("SELECT * FROM Rewards")
        rewards = cursor.fetchall() or []

        # Fetch user's earned rewards joined with reward metadata (Image, Name, etc.)
        cursor.execute("""
            SELECT ur.ID AS ur_id,
                   ur.UserID,
                   ur.RewardsID,
                   r.ID   AS reward_id,
                   r.Name,
                   r.Image,
                   r.Price,
                   r.Recipe
            FROM `UserRewards` ur
            JOIN `Rewards` r ON ur.RewardsID = r.ID
            WHERE ur.UserID = %s
            ORDER BY ur.ID DESC
        """, (current_user.id,))
        user_rewards = cursor.fetchall() or []

    except Exception:
        app.logger.exception("Error in wheelofdrinks")
        points = 0
        rewards = []
        user_rewards = []
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        conn.close()

    return render_template(
        "wheelofdrinks.html.jinja",
        points=points,
        rewards=rewards,
        user_rewards=user_rewards
    )


# Gacha spin route
@app.route("/gacha_spin", methods=["POST"])
@login_required
def gacha_spin():
    data = request.get_json() or {}
    try:
        plays = int(data.get("plays", 1))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Invalid spin amount"}), 400

    if plays == 1:
        cost = 10
    elif plays == 10:
        cost = 50
    else:
        return jsonify({"success": False, "message": "Invalid spin amount"}), 400

    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT COALESCE(SUM(Points), 0) AS total_points
            FROM `Water Consumption`
            WHERE UserID = %s
        """, (current_user.id,))
        points = (cursor.fetchone() or {}).get("total_points", 0) or 0

        if points < cost:
            return jsonify({"success": False, "message": "Not enough points"}), 400

        # Deduct points; include Oz to satisfy NOT NULL if your schema requires it
        cursor.execute("""
            INSERT INTO `Water Consumption` (UserID, Points, Oz)
            VALUES (%s, %s, %s)
        """, (current_user.id, -cost, 0))

        cursor.execute("SELECT * FROM Rewards")
        all_rewards = cursor.fetchall() or []

        results = pick_weighted_rewards(all_rewards, plays)

        for r in results:
            cursor.execute("""
                INSERT INTO `UserRewards` (UserID, RewardsID)
                VALUES (%s, %s)
            """, (current_user.id, r["ID"]))

        # recompute remaining points
        cursor.execute("""
            SELECT COALESCE(SUM(Points), 0) AS total_points
            FROM `Water Consumption`
            WHERE UserID = %s
        """, (current_user.id,))
        remaining = (cursor.fetchone() or {}).get("total_points", 0) or 0

        conn.commit()

    except Exception:
        traceback.print_exc()
        try:
            conn.rollback()
        except Exception:
            pass
        return jsonify({"success": False, "message": "Server error during gacha spin"}), 500
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        conn.close()

    return jsonify({
        "success": True,
        "rewards": [
            {
                "ID": r["ID"],
                "Name": r.get("Name"),
                "Image": r.get("Image"),
                "Price": float(r["Price"]) if r.get("Price") is not None else None,
                "Recipe": r.get("Recipe"),
                "Weight": r.get("Weight")
            } for r in results
        ],
        "remaining_points": remaining
    })


#for the results page------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route("/reward/<int:reward_id>")
@login_required
def reward_detail(reward_id):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM Rewards
        WHERE ID = %s
    """, (reward_id,))
    reward = cursor.fetchone()
    conn.close()

    if not reward:
        abort(404)



    # optional: map weight → rarity
    weight = reward["Weight"]
    if weight <= 1:
        rarity = "Legendary"
    elif weight <= 3:
        rarity = "Epic"
    elif weight <= 7:
        rarity = "Rare"
    else:
        rarity = "Common"

    return render_template("reward_detail.html.jinja",
                           reward=reward,
                           rarity=rarity)

#for the account page------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route("/Accountpage")
def account_page():

    return render_template("Accountpage.html.jinja")

#for the friends page------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route('/friends')
@login_required
def friends_list():
     connection = connect_db()
     cursor = connection.cursor()
     cursor.execute("""
            SELECT User.ID, User.username, User.is_online
            FROM friendships
            JOIN User 
            ON User.ID = friendships.user_id2
           WHERE friendships.user_id1 = %s;
    """,     (current_user.id,))
     results = cursor.fetchall()
     connection.close()
     return render_template('friends.html.jinja', friends=results)

@app.route("/create_group", methods=["GET", "POST"])
@login_required
def create_group():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        privacy = request.form.get('privacy')

        # Validation
        if not name:
            flash("Group name is required", "error")
            return render_template('create_group.html')

        # Save to database (pseudo)
        # db.create_group(name, description, privacy)

        flash("Group created successfully!", "success")
        return redirect(url_for('create_group'))

    return render_template('create_group.html.jinja')

if __name__ == "__main__":
    app.run(debug=True)


@app.route('/addfriends' , methods=['GET', 'POST']) 
@login_required 
def add_friends(): 
    connection = connect_db() 
    cursor = connection.cursor() 
    cursor.execute(""" SELECT * FROM User """) 
    
    if request.method == "POST": 
        
     user_id2= request.form["user_id2"]
    
     cursor.execute("INSERT INTO friendships(user_id1,user_id2)VALUES(%s,%s)",(current_user.id,user_id2)) 
     connection.commit()
     cursor.close()
     connection.close()
     return redirect('/success') 
    
    results = cursor.fetchall() 
    connection.close() 
    
    
 
    return render_template("addfriends.html.jinja",User=results)

@app.route('/success')
def success():
    return "Friend added successfully!"

if __name__ == '__main__':
    app.run(debug=True)

@app.route('/remove_friend/<int:friend_id>', methods=['POST'])
@login_required
def remove_friend(friend_id):
    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute("""
        DELETE FROM `friendships`
        WHERE `user_id1` = %s AND `user_id2` = %s
    """, (current_user.id, friend_id))

    connection.commit()
    connection.close()

    return redirect('/friends')








#for the logout page------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route("/logout")
@login_required
def logout():
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("UPDATE User SET is_online = 0 WHERE ID = %s", (current_user.id,))
    connection.commit()
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


 
#for the catalog page where users can see the rewards they have earned and how many points they have.------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route("/catalog")
@login_required
def catalog():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            Rewards.ID,
            Rewards.Name,
            Rewards.Image,
            Rewards.Price,
            Rewards.Recipe,
            Rewards.Weight,
            UserRewards.Timestamp
        FROM UserRewards
        JOIN Rewards 
            ON Rewards.ID = UserRewards.RewardsID
        WHERE UserRewards.UserID = %s
        ORDER BY UserRewards.Timestamp DESC
    """, (current_user.id,))

    rewards = cursor.fetchall()
    conn.close()

    return render_template("catalog.html.jinja", rewards=rewards)

