import sqlite3
import os

from flask import Flask, flash, redirect, render_template, request, session, flash
from flask_session import Session
from flask_mail import Mail, Message
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import login_required, allowed_file
import fitz
from gtts import gTTS
from decouple import config

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Configure sending email to the user
app.config["MAIL_DEFAULT_SENDER"] = config("MAIL_DEFAULT_SENDER")
app.config["MAIL_PASSWORD"] = config("MAIL_PASSWORD")
app.config["MAIL_PORT"] = 465
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_USE_TLS"] = False
app.config["MAIL_USE_SSL"] = True
app.config["MAIL_USERNAME"] = config("MAIL_USERNAME")
mail = Mail(app)


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure uploading of the files
UPLOAD_FOLDER = '/home/ubuntu/project/static/files'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# Configure SQLite database
conn = sqlite3.connect('project.db')
cursor = conn.cursor()


@app.route("/init")
def init():
    """ Initial page that's only purpose is to redirect the user to login or signUp pages """
    return render_template("init.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Register user"""
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            flash("Username is not provided", "warning")
            return redirect(request.url)

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("Password is not provided", "warning")
            return redirect(request.url)

        # Ensure password was confirmed correctly
        elif not request.form.get("confirmation") or request.form.get("password") != request.form.get("confirmation"):
            flash("Password cofirmation failed", "warning")
            return redirect(request.url)

        username = request.form.get("username")
        password = request.form.get("password")

        # Ensure password is at least 8 characters long and contains at least one number and one letter
        if len(password) < 8:
            flash("Password must contain at least 8 characters", "warning")
            return redirect(request.url)

        if not any(char.isdigit() for char in password) or not any(char.isalpha() for char in password):
            flash("Password must contain at least one number and one letter", "warning")
            return redirect(request.url)

        # Check if the user is not registered yet
        cursor.execute("SELECT username FROM users WHERE username = ?", (username,))
        if cursor.fetchone() is not None:
            flash(f"User with this username already exists, please provide unique username, for example {username}1", "warning")
            return redirect(request.url)

        # Insert new user to the database
        cursor.execute("INSERT INTO users (username, hash) VALUES(?, ?)", (username, generate_password_hash(password)))
        flash("Thank you for registration!", "success")

        # Send user an email
        email = request.form.get("email")
        if email:
            message = Message("You are successfully signed up to my project page!", recipients=[email])
            message.body = f"Hello, {username}! Welcome to my project's page where you can upload your PDF files, get text from them and listen to an audio files created for you. Enjoy!"
            mail.send(message)

        # Apply changes in database
        conn.commit()
        return redirect("/login")

    else:
        return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            flash("Username is not provided", "warning")
            return redirect(request.url)

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("Password is not provided", "warning")
            return redirect(request.url)

        username = request.form.get("username")
        password = request.form.get("password")

        # Query database for username
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        rows = cursor.fetchall()

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0][2], password):
            flash("Incorrect username and/or password", "danger")
            return redirect(request.url)

        # Remember which user has logged in
        session["user_id"] = rows[0][0]

        # Redirect user to home page
        return redirect("/")

    else:
        return render_template("login.html")


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """ Here user can select previously uploaded files (if any) and convert them into text or audio """

    session_id = session.get("user_id")

    # Create a list of files uploaded by user
    cursor.execute("SELECT filename FROM files WHERE user_id = ?", (session_id,))
    filenames = cursor.fetchall()

    list1 = []
    for filename in filenames:
        list1.append(filename[0])

    if request.method == "POST":
        # Ensure the user has chosen a file
        if not request.form.get("list1"):
            flash("No file chosen", "warning")
            return redirect(request.url)

        # Take a file selected by user
        filename = request.form.get("list1")
        cursor.execute("SELECT path FROM files WHERE filename = ? AND user_id = ?", (filename, session_id))
        path = cursor.fetchone()[0]

        # Extract the text from PDF file into variable page by page
        full_text = ""
        file = fitz.open(path)
        for page in file.pages():
            text = page.getText()
            full_text += text

        # Each user has ones own folder to avoid conflict between files with the same name uploaded by different users
        audio_path = f"static/audio/{session_id}"

        # Check if user folder in "audio" extsts and if not then create one
        if not os.path.exists(audio_path):
            os.mkdir(audio_path)

        # Check if choden .pdf was not previously transformed to .mp3 to save time for retransformation
        audio_file_name = filename.replace(".pdf", ".mp3")
        if not os.path.exists(f"{audio_path}/{audio_file_name}"):
            # Transforming .pdf to .mp3
            tts = gTTS(full_text, lang='en-uk')
            tts.save(f"{audio_path}/{audio_file_name}")

        flash("Enjoy!", "success")
        return render_template("/index.html", full_text=full_text, list1=list1, audio_file_name=audio_file_name, audio_path=audio_path)

    else:
        return render_template("/index.html", list1=list1)


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to initial page
    return redirect("/init")


@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    """Change users password"""
    session_id = session.get("user_id")

    if request.method == "POST":

        # Ensure old password was submitted
        if not request.form.get("old_pswd"):
            flash("Old password is not provided", "warning")
            return redirect(request.url)

        # Check old password is correct
        cursor.execute("SELECT hash FROM users WHERE id = ?", (session_id,))
        conn.commit()
        old_pswd = cursor.fetchone()[0]
        if not check_password_hash(old_pswd, request.form.get("old_pswd")):
            flash("Incorrect Old Password", "danger")
            return redirect(request.url)

        # Ensure new password was submitted
        elif not request.form.get("new_pswd"):
            flash("New password is not provided", "warning")
            return redirect(request.url)

        # Ensure password was confirmed
        elif not request.form.get("confirmation"):
            flash("New password is not confirmed", "warning")
            return redirect(request.url)

        # Ensure password and confirmation are the same
        elif request.form.get("new_pswd") != request.form.get("confirmation"):
            flash("Password confirmation failed", "danger")
            return redirect(request.url)

        password = request.form.get("new_pswd")
        # Ensure password is at least 8 characters long and contains at least one number and one letter
        if len(password) < 8:
            flash("Password must contain at least 8 characters", "warning")
            return redirect(request.url)

        if not any(char.isdigit() for char in password) or not any(char.isalpha() for char in password):
            flash("Password must contain at least one number and one letter", "warning")
            return redirect(request.url)

        # Update password in the database
        cursor.execute("UPDATE users SET hash = ? WHERE id = ?", (generate_password_hash(request.form.get("new_pswd")), session_id))
        conn.commit()
        flash("Password updated successfully!", "success")

        # Redirect user to home page
        return redirect("/")

    else:
        return render_template("change_password.html")


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    """ Upload PDF file """
    session_id = session.get("user_id")

    if request.method == 'POST':

        # Ensure file was chosen
        if request.files:
            file = request.files["file"]

            if not file:
                flash("No file chosen", "warning")
                return redirect(request.url)

            # Ensure the user is uploading file in .pdf format
            if not allowed_file(file.filename):
                flash("Only .pdf files allowed", "danger")
                return redirect(request.url)

            # Check if current user has a folder for files storage (if not then create one)
            if not os.path.exists(f"{app.config['UPLOAD_FOLDER']}/{session_id}"):
                os.mkdir(f"{app.config['UPLOAD_FOLDER']}/{session_id}")

            # Save file to user's directory
            file_path = os.path.join(f"{app.config['UPLOAD_FOLDER']}/{session_id}", file.filename)
            file.save(file_path)

            # Insert file info into DB
            cursor.execute("INSERT INTO files (user_id, filename, path) VALUES(?, ?, ?)", (session_id, file.filename, file_path))
            conn.commit()
            flash("File successfully uploaded!", "success")

            return redirect(request.url)

        else:
            flash("No file selected", "warning")
            return redirect(request.url)
    else:
        return render_template("upload.html")


@app.route("/remove", methods=["GET", "POST"])
@login_required
def list():
    """Remove chosen file"""
    session_id = session.get("user_id")

    # Create a list of files uploaded by user
    cursor.execute("SELECT filename FROM files WHERE user_id = ?", (session_id,))
    filenames = cursor.fetchall()

    list2 = []
    for filename in filenames:
        list2.append(filename[0])

    if request.method == "POST":
        # Ensure the user has chosen a file
        if not request.form.get("list2"):
            flash("No file chosen", "warning")
            return redirect(request.url)

        # Delete file info from DB and file from user's directory
        filename = request.form.get("list2")
        cursor.execute("DELETE FROM files WHERE filename = ? AND user_id = ?", (filename, session_id))
        conn.commit()

        os.remove(os.path.join(f"{app.config['UPLOAD_FOLDER']}/{session_id}", filename))
        flash("File removed successfully!", "success")
        return redirect(request.url)

    else:
        return render_template("remove.html", list2=list2)
