from flask import Flask, redirect, render_template

import pymysql

app = Flask(__name__)

config = Dynaconf(settings_file = ["settings.toml"])

@app.route("/")
def index():
    return render_template("homepage.html.jinja")