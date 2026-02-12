from flask import Flask, render_template, redirect

import pymysql

from dynaconf import Dynaconf


app = Flask(__name__)

config = Dynaconf(settings_file = ["settings.toml"])


@app.route("/")
def index():
 return render_template("homepage.html.jinja")


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



@app.route('/register', methods=["POST", "GET"])
def register():
 return render_template("register.html.jinja")
