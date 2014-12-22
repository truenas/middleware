__author__ = 'jceel'

from flask import Flask, render_template
from flask_bootstrap import Bootstrap

app = Flask(__name__)
Bootstrap(app)

@app.route('/events')
def events():
    return render_template('events.html')

@app.route('/rpc')
def rpc():
    return render_template('rpc.html')

@app.route('/tasks')
def tasks():
    return render_template('tasks.html')

@app.route('/term')
def term():
    return render_template('term.html')