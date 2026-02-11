from flask import Flask, render_template, redirect

import pymysql

from dynaconf import Dynaconf


app = Flask(__name__)

config = Dynaconf(settings_file = ["settings.toml"])

login_manager = LoginManager( app )

@app.route("/")
def index():
    return render_template("homepage.html.jinja")

login_manager.login_view = '/login'
class User:
    is_authenticated = True
    is_active = True
    is_anonymous = False

    def __init__(self, result):
        self.name = result['Name']
        self.email = result['Email']
        self.username = result['Username']
        self.id = result['ID']

@app.route("/login", methods = ["POST", "GET"])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        connection = connect_db()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM `User` WHERE `Username` = %s" , (username) )
        result = cursor.fetchone()
        connection.close()
        if result is None:
            flash("No user found")
        elif password != result["Password"]:
            flash("Incorrect password")
        else:
            login_user(User(result))
            return redirect('/browse')
    return render_template("login.html.jinja")

@app.route("/logout",  methods = ["POST", "GET"])
@login_required
def logout():
    logout_user()
    flash("You Have Been Logged Out! Thanks For Shopping")
    return redirect("/login")