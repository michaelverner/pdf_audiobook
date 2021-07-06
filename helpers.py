from flask import redirect, session
from functools import wraps


def login_required(f):
    """ Decorate routes to require login. """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/init")
        return f(*args, **kwargs)
    return decorated_function


# List of allowed extensions of the files
ALLOWED_EXTENSIONS = {'pdf'}

# Check if the file's extension is allowed
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
