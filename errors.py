from run import app
from flask import json
from werkzeug.exceptions import HTTPException, InternalServerError


@app.errorhandler(HTTPException)
def handle_400(e):
	"""Return JSON instead of HTML for HTTP errors."""

	response = e.get_response()
	# replace the body with JSON
	response.data = json.dumps({
		"code": e.code,
		"name": e.name,
		"description": e.description,
	})
	response.content_type = "application/json"
	return response


@app.errorhandler(InternalServerError)
def handle_500(e):
	pass


app.register_error_handler(400, handle_400)
app.register_error_handler(500, handle_500)
