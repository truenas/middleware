from .proxy import ReverseProxied
from flask import Flask, render_template

app = Flask(__name__)
app.wsgi_app = ReverseProxied(app.wsgi_app)


@app.route('/')
def main():
    return render_template('websocket.html')
