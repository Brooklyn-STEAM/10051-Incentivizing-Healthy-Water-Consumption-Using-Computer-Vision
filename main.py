from flask import Flask, render_template, redirect, request, flash, abort, session, jsonify, url_for

from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin # Import necessary functions and classes from the Flask-Login library for user authentication and session management

import pymysql # Import the PyMySQL library for MySQL database connection

import base64 # used for images

import os #used to upload files

import math # used for the to do the math for the conversion of ml to fl oz and cups

from dynaconf import Dynaconf # Import the Dynaconf library for configuration management

from datetime import datetime #helps get the date and time for the tracker page

from ai_model import predict_capacity #for the ai to load and work

import traceback

import random

config = Dynaconf(settings_file = ["settings.toml"])

app = Flask(__name__)

app.secret_key = config.secret_key

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

class User(UserMixin):
    def __init__(self, result):
        self.name = result['Name']
        self.email = result['Email']
        self.id = result['ID']

    def get_id(self):
        return str(self.id)



@login_manager.user_loader
def load_user(user_id):
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM `User` WHERE `ID` = %s", (user_id,))
    result = cursor.fetchone()
    connection.close()

    if result is None:
        return None

    return User(result)

    

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


tracker_data = {
    "Monday":0,
    "Tuesday":0,
    "Wednesday":0,
    "Thursday":0,
    "Friday":0,
    "Saturday":0,
    "Sunday":0
} #used for the tracker data

#All of this is connect routes for the website, they will render the html pages that are in the templates folder. 
@app.route("/")
def index():
    return render_template("homepage.html.jinja")

#for login page------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        connection = connect_db()
        cursor = connection.cursor()

        # Fetch user by username
        cursor.execute("SELECT * FROM `User` WHERE `Username` = %s", (username,))
        result = cursor.fetchone()
        connection.close()

        if result is None:
            flash("Username not found!")
            return render_template("login.html.jinja")

        if password != result["Password"]:
            flash("Username not found!")
            return render_template("login.html.jinja")


        # Mark user online
        connection = connect_db()
        cursor = connection.cursor()
        cursor.execute("UPDATE `User` SET is_online = 1 WHERE ID = %s", (result["ID"],))
        connection.close()

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
                INSERT INTO User (Name, Email, Password, Username, is_online)
                VALUES (%s, %s, %s, %s, %s)
                """, (name, email, password, username, 0))
                connection.close()

            except pymysql.err.IntegrityError:
                        flash("Email already registered!")
                        connection.close()
                        return render_template("register.html.jinja")
            return redirect("/healthdata")
        
    return render_template("register.html.jinja")

#for the health data page------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@app.route("/healthdata", methods=["GET", "POST"])
@login_required
def health_data():
    connection = connect_db()
    cursor = connection.cursor()
    # 🔍 Check if user already has data
    cursor.execute("SELECT * FROM `Health Data` WHERE UserID = %s", (current_user.id,))
    existing_data = cursor.fetchone()

    if request.method == "POST":

        # ✅ GET FORM DATA
        weight = float(request.form["Weight"])
        sex = request.form["Sex"]
        active = request.form["Active"]
        exercise = request.form["Daily Excersize"]
        climate = request.form["Climate"]
        health_list = request.form.getlist("Health")   # gets ALL checked boxes
        health = ",".join(health_list)                # store as "kidney,heart"

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

        if existing_data:
            # ✏️ UPDATE
            cursor.execute("""
                UPDATE `Health Data`
                SET Cups=%s, WaterOz=%s, Weight=%s, Age=%s, Sex=%s,
                    Active=%s, `Daily Excersize`=%s,
                    `Local Weather`=%s, `Health Considerations`=%s
                WHERE UserID=%s
            """, (
                cups, water_oz, weight, age, sex,
                active, exercise, climate, health,
                current_user.id
            ))
        else:
            # ➕ INSERT
            cursor.execute("""
                INSERT INTO `Health Data`
                (UserID, Cups, WaterOz, Weight, Age, Sex, Active,
                 `Daily Excersize`, `Local Weather`, `Health Considerations`)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                current_user.id, cups, water_oz, weight, age, sex,
                active, exercise, climate, health
            ))  

        connection.commit()
        cursor.close()
        connection.close()

        return redirect("/Accountpage")
    cursor.close()
    connection.close() 
    return render_template("healthdata.html.jinja", data=existing_data)
     


#for account page(second homepage)------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
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

@app.route('/addfriends' , methods=['GET', 'POST'])
@login_required
def add_friends():

    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute(""" SELECT * FROM User """)


    if  request.method == "POST":
      user_id2= request.form["user_id2"]


      cursor.execute("INSERT INTO friendships(user_id1,user_id2)VALUES(%s,%s)",(current_user.id,user_id2))
      return redirect('/success')

    results = cursor.fetchall()
    connection.close()



    return render_template("addfriends.html.jinja",User=results)

@app.route('/success')
def success():
    return "Friend added successfully!"

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

if __name__ == "__main__":
    app.run(debug=True)





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

@app.route('/tracker')
@login_required
def tracker():
    try:
        conn = connect_db()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        cursor.execute("""
            SELECT WaterOz 
            FROM `Health Data`
            WHERE UserID = %s
        """, (current_user.id,))

        daily_goal = int((cursor.fetchone() or {}).get("Cups", 0))


        cursor.execute("""
            SELECT COALESCE(SUM(Cups), 0) AS drank_today
            FROM `Water Consumption`
            WHERE UserID = %s AND DATE(Timestamp) = CURDATE()
        """, (current_user.id,))
        result = cursor.fetchone()
        cups_drank = (result or {}).get("drank_today", 0)

        cups_left = max(daily_goal - cups_drank, 0)

        cursor.execute("""
            SELECT 
                DAYNAME(Timestamp) AS day,
                COALESCE(SUM(Cups), 0) AS total_cups
            FROM `Water Consumption`
            WHERE UserID = %s
            GROUP BY DAYNAME(Timestamp)
        """, (current_user.id,))
        weekly_rows = cursor.fetchall()

        tracker_data = {
            "Monday": 0, "Tuesday": 0, "Wednesday": 0,
            "Thursday": 0, "Friday": 0, "Saturday": 0, "Sunday": 0
        }

        for row in weekly_rows:
            tracker_data[row["day"]] = row["total_cups"]

        days = list(tracker_data.keys())

        # ⭐ ADD THIS
        cursor.execute("""
            SELECT COALESCE(SUM(Points), 0) AS total_points
            FROM `Water Consumption`
            WHERE UserID = %s
        """, (current_user.id,))

        points_result = cursor.fetchone()
        total_points = (points_result or {}).get("total_points", 0)

        return render_template(
            "tracker.html.jinja",
            days=days,
            total_points=total_points,   # ⭐ THIS is what your HTML needs
            tracker_data=tracker_data,
            daily_goal=daily_goal,
            cups_drank=cups_drank,
            cups_left=cups_left
        )

    except Exception as e:
        print("ERROR IN TRACKER:", e)
        return str(e)



@app.route("/camera")
def camera():
    return render_template("camera.html.jinja")

@app.route('/capture', methods=['POST'])
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
    volume_cups = round(capacity_ml / 240)
    # Save prediction to DB
    connection = connect_db()
    cursor = connection.cursor()
    try:
        cursor.execute("""
        INSERT INTO `Water Consumption` (UserID, Points, Cups, Timestamp, Image)
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
        flash("Invalid amount")
        return redirect("/tracker")

    volume_cups = ounces / 8

    conn = connect_db()
    cursor = conn.cursor()

    try:
        # 1. Insert the drink------------this stays the same tho----------------------------------------------------------------
        cursor.execute("""
            INSERT INTO `Water Consumption` (UserID, Points, Cups, Timestamp, Image)
            VALUES (%s, %s, %s, NOW(), %s)
        """, (current_user.id, 0, volume_cups, None))

        # 2. Recalculate how much the user drank today-- more math ----------------------------------------------------
        cursor.execute("""
            SELECT COALESCE(SUM(Cups), 0) AS drank_today
            FROM `Water Consumption`
            WHERE UserID = %s AND DATE(Timestamp) = CURDATE()
        """, (current_user.id,))
        result = cursor.fetchone()
        cups_drank = (result or {}).get("drank_today", 0)

        # 3. Get daily goal we got this part done------------------------------------------------------------------------------------------------------------
        cursor.execute("""
            SELECT WaterOz 
            FROM `Health Data`
            WHERE UserID = %s
        """, (current_user.id,))

        daily_goal = int((cursor.fetchone() or {}).get("Cups", 0))
        # 4. If user reached or exceeded goal, award 15 points (only once per day)-----------------------------------------------------------------------------
        if cups_drank >= daily_goal:
            # Check if reward already given today i think? ------------------------------------------------------------------------------------------------------------
            cursor.execute("""
                SELECT COUNT(*) AS reward_count
                FROM `Water Consumption`
                WHERE UserID = %s AND Points = 15 AND DATE(Timestamp) = CURDATE()
            """, (current_user.id,))
            reward_row = cursor.fetchone()
            already_rewarded = reward_row["reward_count"] > 0

            if not already_rewarded:
                cursor.execute("""
                    INSERT INTO `Water Consumption` (UserID, Points, Cups, Timestamp, Image)
                    VALUES (%s, %s, %s, NOW(), %s)
                """, (current_user.id, 15, 0, None))

                flash("🎉 Daily goal reached! You earned +15 points!")

        conn.commit()

    finally:
        cursor.close()
        conn.close()

    flash(f"Drink logged: {ounces} oz ({volume_cups:.2f} cups)")
    return redirect("/tracker")

# ----------------------------
# TESTING PREDICTION
# ----------------------------
if __name__ == "__main__":
    test_image = "static/user_uploads/drink_1774962039.119192.jpg"

    predicted_ml, predicted_oz = predict_capacity(test_image)

    print(f"Predicted volume: {predicted_ml:.1f} mL / {predicted_oz:.2f} fl oz")


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


