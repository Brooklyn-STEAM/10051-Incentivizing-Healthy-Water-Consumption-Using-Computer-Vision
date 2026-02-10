from flask import Flask, render_template, redirect

import pymysql

from dynaconf import Dynaconf


app = Flask(__name__)

config = Dynaconf(settings_file = ["settings.toml"])

@app.route("/")
def index():
    return render_template("homepage.html.jinja")