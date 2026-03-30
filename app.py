# app.py
import traceback
import random
from flask import Flask, render_template, redirect, request, flash, abort, session, jsonify, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
import pymysql
from dynaconf import Dynaconf
from ai_model import predict_volume  # keep if used elsewhere

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
            cursor.execute("SELECT * FROM `User` WHERE Username = %s", (username,))
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
            return redirect(url_for("wheelofdrinks"))
        cursor.execute("UPDATE User SET is_online = 1 WHERE ID = %s", (current_user.id,))
    return render_template("login.html.jinja")

# Register route
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

@app.route('/addfriends' , methods=['GET', 'POST'])
@login_required
def add_friends():
    
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute(""" SELECT * FROM `User` """)
     

    if  request.method == "POST":
      user_id2= request.form["user_id2"]
     
     
      cursor.execute("INSERT INTO `friendships`(`user_id1`,`user_id2`)VALUES(%s,%s)",(current_user.id,user_id2))
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
    logout_user()
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("UPDATE User SET is_online = 0 WHERE ID = %s", (current_user.id,))
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
