from api.app import app

app.run(host="localhost", port=5000, debug=True, processes=1)
