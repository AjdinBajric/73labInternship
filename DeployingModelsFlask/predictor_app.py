import flask
from flask import request
from predictor_api import concat_pages

# Initialize the app
app = flask.Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def predict():
    print(request.args)
    if request.args:
        text = \
            concat_pages(request.args['chat_in'])
        print(text)

        return flask.render_template('predictor.html', chat_in=x_input, text=text)
