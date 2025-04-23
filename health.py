from flask import Flask
import threading

app = Flask(__name__)

@app.route("/")
def index():
    return "OK"

def run_flask():
    app.run(host="0.0.0.0", port=8000)

threading.Thread(target=run_flask).start()
