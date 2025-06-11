import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24) # Replace with a strong secret key in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///travel_planner.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login' # Redirect to login page if user is not authenticated

# --- Database Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Trip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    locations = db.Column(db.Text, nullable=True) # Storing locations as JSON string or simple text

    user = db.relationship('User', backref=db.backref('trips', lazy=True))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- API Endpoints ---
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': 'Username and password are required'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'message': 'Username already exists'}), 409

    new_user = User(username=username)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()

    if user and user.check_password(password):
        login_user(user)
        return jsonify({'message': 'Logged in successfully'}), 200
    return jsonify({'message': 'Invalid username or password'}), 401

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'message': 'Logged out successfully'}), 200

@app.route('/trips', methods=['POST'])
@login_required
def create_trip():
    data = request.get_json()
    name = data.get('name')
    locations = data.get('locations') # This could be a JSON string

    if not name:
        return jsonify({'message': 'Trip name is required'}), 400

    new_trip = Trip(name=name, locations=locations, user_id=current_user.id)
    db.session.add(new_trip)
    db.session.commit()
    return jsonify({'message': 'Trip created successfully', 'trip_id': new_trip.id}), 201

@app.route('/trips', methods=['GET'])
@login_required
def get_trips():
    user_trips = Trip.query.filter_by(user_id=current_user.id).all()
    trips_data = [{'id': trip.id, 'name': trip.name, 'locations': trip.locations} for trip in user_trips]
    return jsonify({'trips': trips_data}), 200

# --- Database Initialization ---
def init_db():
    with app.app_context():
        db.create_all()
    print("Database initialized!")

if __name__ == '__main__':
    # Create database tables if they don't exist
    if not os.path.exists('travel_planner.db'):
        init_db()
    app.run(debug=True) # In a production environment, use a WSGI server like Gunicorn or uWSGI.
