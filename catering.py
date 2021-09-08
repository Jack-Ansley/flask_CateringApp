import os
from datetime import datetime

from flask import Flask, request, session, url_for, redirect, render_template, abort, flash

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# from models import db, Owner, Customer, EventRequest, Staffer, Assignment
db = SQLAlchemy()

app = Flask(__name__)

PER_PAGE = 30
DEBUG = True
SECRET_KEY = 'development key'

SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(app.root_path, 'catering.db')

app.config.from_object(__name__)
app.config.from_envvar('MINITWIT_SETTINGS', silent=True)

db.init_app(app)


@app.cli.command('initdb')
def initdb_command():
    try:
        db.drop_all()
        db.create_all()
        db_owner = Owner("owner", generate_password_hash("pass"))
        db.session.add(db_owner)
        db.session.commit()
        print("Database Succesfully Initialized. initdb completed.")
    except Exception as e:
        db.rollback()
        print(e)


@app.route("/")
def default():
    return redirect(url_for("login"))
    # Login page is our landing page. I don't think this breaks the rules


@app.route("/login/", methods=["GET", "POST"])
def login():
    response_txt = ""
    if 'cust_id' in session:
        print("Double Login attemped. Switched to events page")
        return redirect(url_for('events'))
    if 'owner_id' in session:
        print("Double Login attemped. Switched to Manage Page")
        return redirect(url_for('manage'))
    if request.method == "POST":
        if not request.form['username']:
            response_txt = 'Please enter a username'
        elif not request.form['password']:
            response_txt = 'Please enter a password'
        else:
            cust = Customer.query.filter_by(username=request.form['username']).first()
            owner = Owner.query.filter_by(username=request.form['username']).first()
            staff = Staffer.query.filter_by(username=request.form['username']).first()
            if cust is None and owner is None and staff is None:
                response_txt = "Invalid username"
            if cust is not None:
                response_txt = login_cust(cust, request.form["password"])
                if response_txt is None:
                    return redirect(url_for('events'))
            elif owner is not None:
                response_txt = login_owner(owner, request.form["password"])
                if response_txt is None:
                    return redirect(url_for('manage'))
            elif staff is not None:
                response_txt = login_staff(staff, request.form["password"])
                if response_txt is None:
                    return redirect(url_for('staff'))

    return render_template('landingPage.html', error=response_txt)


def login_cust(cust, password):
    if not check_password_hash(cust.pw_hash, password):
        return "Incorrect Password"
    session['cust_id'] = cust.user_id
    return None


def login_staff(instaff, password):
    if not check_password_hash(instaff.pw_hash, password):
        return "Incorrect Password"
    session['staffer_id'] = instaff.staffer_id
    return None


def login_owner(owner, password):
    if not check_password_hash(owner.pw_hash, password):
        return "Incorrect Password"
    session['owner_id'] = owner.owner_id
    return None


@app.route("/staff/", methods=["POST", "GET"])
def staff():
    if "staffer_id" not in session:
        abort(401)
    staff = Staffer.query.filter_by(staffer_id=session["staffer_id"]).first()
    reqs = EventRequest.query.order_by(EventRequest.start_datetime.asc()).all()

    error = None
    try:
        for req in reqs:
            for assignment in req.assignments:
                if staff.staffer_id == assignment.staffer_id:
                    reqs.remove(req)
    except Exception as e:
        db.rollback
        print(e)

    return render_template('staffPage.html', assignments=staff.assignments, requests=reqs, staff=staff, error=error)


@app.route("/register/", methods=["POST", "GET"])
def register():
    error = None
    if request.method == "POST":
        if not request.form['username']:
            error = 'You have to enter a username'
        elif not request.form['password']:
            error = 'You have to enter a password'
        else:
            cust = Customer(request.form['username'], generate_password_hash(request.form['password']))
            # noinspection PyBroadException
            try:
                db.session.add(cust)
                db.session.commit()
                db.session.flush()
            except Exception as error:
                db.rollback()

            flash("Hello " + request.form['username'] + "! ")
            flash("You have been successfully registered!")
            session['cust_id'] = cust.user_id
    return render_template('registrationPage.html', error=error)


@app.route("/logout/", methods=["GET"])
def logout():
    session.pop('owner_id', None)
    session.pop('cust_id', None)
    session.pop('staffer_id', None)
    # session.clear() this makes the flashes weird according to stack overflow.
    return redirect(url_for('login'))


@app.route("/manage/", methods=["POST", "GET"])
def manage():
    error = None
    if "owner_id" not in session:
        abort(401)
    if request.method == "POST":
        error1 = None
        if not request.form["username"]:
            error1 = "Enter a username"
        elif not request.form["password"]:
            error1 = "Enter a password"
        error = error1
        if error is None:
            currstaff = Staffer(request.form["username"], generate_password_hash(request.form["password"]))
            try:
                db.session.add(currstaff)
                db.session.commit()
                flash("Added new staff " + currstaff.username + " successfully!")
            except Exception as e:
                print(e)
    reqs = EventRequest.query.order_by(EventRequest.start_datetime.asc()).all()
    owner = Owner.query.filter_by(owner_id=session["owner_id"]).first()
    staffings = {}
    currstaff = Staffer.query.all()
    return render_template("managerPage.html", requests=reqs, staff=currstaff, staffings=staffings,
                           user_name=owner.username,
                           error=error)


@app.route("/addStaff/", methods=["POST"])
def add_staff():
    if not request.form["request_id"]:
        abort(404)
    if "staffer_id" not in session:
        abort(401)

    Staffer.query.filter_by(staffer_id=session["staffer_id"]).first()
    event_request = EventRequest.query.filter_by(request_id=request.form["request_id"]).first()
    staff = Staffer.query.filter_by(staffer_id=session["staffer_id"]).first()
    if event_request is None or staff is None:  # Make sure both exist in the DB, for FK validation
        abort(404)

    assign = Assignment(event_request.request_id, staff.staffer_id)

    db.session.add(assign)
    db.session.commit()

    flash("Staffer " + staff.username + " assigned to event " + str(event_request) + " successfully!")
    return redirect(url_for('staff'))


@app.route("/events/", methods=["POST", "GET"])
def events():
    error = None
    if 'cust_id' not in session:
        abort(401)
    if request.method == "POST":
        error1 = None
        if not request.form["eventName"]:
            error1 = "Enter the event name"
        elif not request.form["startDate"]:
            error1 = "Enter the start date"
        elif not request.form["endDate"]:
            error1 = "Enter the end date"
        elif not request.form["beginTime"]:
            error1 = "Enter the start time"
        elif not request.form["endTime"]:
            error1 = "Enter the finish time"
        if not error1:
            input_start_datetime = request.form["startDate"] + " " + request.form["beginTime"]
            input_end_datetime = request.form["endDate"] + " " + request.form["endTime"]

            begin_datetime = datetime.strptime(input_start_datetime, '%b %d, %Y %I:%M %p')
            end_datetime = datetime.strptime(input_end_datetime, '%b %d, %Y %I:%M %p')

            if begin_datetime > end_datetime:  # You can't have a begin time LATER than the end time
                error1 = "The start date of '" + str(begin_datetime) + "' is past the end date. invalid! '" + str(
                    end_datetime) + "'"
        error = error1
        if not error:
            if create_event_request(request.form):
                flash("Added '" + request.form["eventName"] + "' event!")
            else:
                error = "Invalid Event Request Time: An existing event already is occuring at the time"
    cust = Customer.query.filter_by(user_id=session['cust_id']).first()
    reqs = EventRequest.query.filter_by(user_id=session['cust_id']).order_by(EventRequest.start_datetime.asc()).all()
    if not cust:
        abort(404)
    return render_template("events.html", error=error, user_name=cust.username, requests=reqs)


@app.route("/deleteEventRequest/<request_id>", methods=["GET"])
def delete_event_request(request_id):
    if 'cust_id' not in session:
        abort(401)  # Not authorized
    req = EventRequest.query.filter_by(request_id=request_id).first()

    try:
        db.session.delete(req)
        db.session.commit()
    except Exception as e:
        db.rollback()
        print(e)

    return redirect(url_for('events'))


def create_event_request(form):
    input_start_datetime = form["startDate"] + " " + form["beginTime"]
    input_end_datetime = form["endDate"] + " " + form["endTime"]

    begin_datetime = datetime.strptime(input_start_datetime, '%b %d, %Y %I:%M %p')
    end_datetime = datetime.strptime(input_end_datetime, '%b %d, %Y %I:%M %p')

    new_req = EventRequest(form["eventName"], begin_datetime, end_datetime, session["cust_id"])
    for req in EventRequest.query.all():
        if new_req.end_datetime.date() >= req.start_datetime.date() and new_req.start_datetime.date() <= req.end_datetime.date():
            return False

    try:
        db.session.add(new_req)
        db.session.commit()
        return True
    except Exception as e:
        db.rollback()
        print(e)


if __name__ == "__main__":
    app.run()


# From Models, but idk how flask is gonna be zipping everything.
class Customer(db.Model):
    # query = None
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    pw_hash = db.Column(db.String(100), nullable=False)

    def __init__(self, username, password):
        self.username = username
        self.pw_hash = password


class Staffer(db.Model):
    # query = None
    staffer_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    pw_hash = db.Column(db.String(100), nullable=False)
    assignments = db.relationship("Assignment")

    def __init__(self, username, pw_hash):
        self.username = username
        self.pw_hash = pw_hash


class Owner(db.Model):
    # query = None
    owner_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    pw_hash = db.Column(db.String(100), nullable=False)

    def __init__(self, username, password):
        self.username = username
        self.pw_hash = password


class Assignment(db.Model):
    request_id = db.Column(db.Integer, db.ForeignKey("eventrequest.request_id"))
    staffer_id = db.Column(db.Integer, db.ForeignKey('staffer.staffer_id'))

    assignment_id = db.Column(db.Integer, primary_key=True)

    staffer = db.relationship("Staffer", back_populates="assignments")
    request = db.relationship("EventRequest", back_populates="assignments")

    def __init__(self, request_id, staffer_id):
        self.request_id = request_id
        self.staffer_id = staffer_id

    def __repr__(self):
        return self.staffer.username + " is working event: " + self.request.name + " | " + self.request.start_datetime.strftime(
            '%d %b, %Y') + " - " + self.request.start_datetime.strftime(
            '%I:%M %p') + " to " + self.request.end_datetime.strftime(
            '%d %b, %Y') + " - " + self.request.end_datetime.strftime('%I:%M %p')


class EventRequest(db.Model):
    # query = None
    __tablename__ = "eventrequest"
    request_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), nullable=False)

    start_datetime = db.Column(db.DateTime(), nullable=False)
    end_datetime = db.Column(db.DateTime(), nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('customer.user_id'), nullable=False)
    assignments = db.relationship("Assignment")

    def __init__(self, name, start_datetime, end_datetime, user_id):
        self.name = name
        self.start_datetime = start_datetime
        self.end_datetime = end_datetime
        self.user_id = user_id

    def __repr__(self):
        return self.name
