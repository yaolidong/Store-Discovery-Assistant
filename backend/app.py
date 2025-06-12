import os
import requests # Added for Amap API calls
import itertools # Added for permutations
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import time

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24) # Replace with a strong secret key in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///travel_planner.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['AMAP_API_KEY'] = '68778fb7fc7baf898edd94a8fc683768' # Added Amap API Key

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login' # Redirect to login page if user is not authenticated

# --- Database Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    home_address = db.Column(db.String(255), nullable=True)
    home_latitude = db.Column(db.Float, nullable=True)
    home_longitude = db.Column(db.Float, nullable=True)

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

# --- Amap API Utility Functions ---
def geocode_address(api_key, address, city=None):
    """
    Geocodes an address using Amap Web Service API.
    Returns {'latitude': lat, 'longitude': lng, 'formatted_address': formatted_address} or None.
    """
    if not api_key or not address:
        return None

    url = "https://restapi.amap.com/v3/geocode/geo"
    params = {
        "key": api_key,
        "address": address,
    }
    if city:
        params["city"] = city

    try:
        response = requests.get(url, params=params, timeout=5) # 5 seconds timeout
        response.raise_for_status()  # Raise an exception for HTTP errors
        data = response.json()

        if data.get("status") == "1" and data.get("geocodes"):
            geocode_info = data["geocodes"][0]
            location_str = geocode_info.get("location")
            if location_str:
                lon, lat = map(float, location_str.split(','))
                return {
                    "latitude": lat,
                    "longitude": lon,
                    "formatted_address": geocode_info.get("formatted_address")
                }
        else:
            print(f"Amap Geocoding Error: {data.get('info')} for address: {address}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Amap Geocoding request failed: {e}")
        return None
    except (ValueError, KeyError) as e:
        print(f"Error parsing Amap Geocoding response: {e}")
        return None
    return None

def search_poi(api_key, keywords, city=None, location=None, radius=5000, types=None):
    """
    Searches for POIs using Amap Place Text Search API.
    Returns a list of POI dictionaries or None.
    """
    if not api_key or not keywords:
        return None

    url = "https://restapi.amap.com/v3/place/text"
    params = {
        "key": api_key,
        "keywords": keywords,
        "offset": 20, # Number of results per page (max 25)
        "page": 1,
    }
    if city:
        params["city"] = city
    if location: # "longitude,latitude"
        params["location"] = location
        params["radius"] = radius # Search radius in meters
    if types: # POI type codes
        params["types"] = types

    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "1" and data.get("pois"):
            pois_data = []
            for poi in data["pois"]:
                lon, lat = None, None
                if poi.get("location"):
                    try:
                        lon, lat = map(float, poi["location"].split(','))
                    except ValueError:
                        pass # Could not parse location

                pois_data.append({
                    "id": poi.get("id"),
                    "name": poi.get("name"),
                    "type": poi.get("type"),
                    "typecode": poi.get("typecode"),
                    "address": poi.get("address"),
                    "latitude": lat,
                    "longitude": lon,
                    "tel": poi.get("tel"),
                    "distance": poi.get("distance") # if location is provided
                })
            return pois_data
        else:
            print(f"Amap POI Search Error: {data.get('info')} for keywords: {keywords}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Amap POI Search request failed: {e}")
        return None
    except (ValueError, KeyError) as e:
        print(f"Error parsing Amap POI Search response: {e}")
        return None
    return None

def _parse_transit_polyline(transit_details):
    """
    Helper to extract a representative polyline from Amap transit segments.
    For simplicity, this might concatenate polylines of walking and transit segments.
    Amap returns segments, each with its own polyline.
    """
    polylines = []
    if transit_details and transit_details.get("segments"):
        for segment in transit_details["segments"]:
            # Each segment (walking, bus, subway) can have a polyline
            if segment.get("walking") and segment["walking"].get("polyline"):
                polylines.append(segment["walking"]["polyline"])
            if segment.get("bus") and segment["bus"].get("polylines"):
                 for pl_bus in segment["bus"]["polylines"]: # Bus might have multiple polylines
                    if pl_bus.get("polyline"):
                        polylines.append(pl_bus.get("polyline"))
            if segment.get("railway") and segment["railway"].get("polyline"): # For subway/train
                 polylines.append(segment["railway"]["polyline"])
            # Other transit types like "taxi" might not have polylines or are handled differently.
    return ";".join(filter(None, polylines)) if polylines else None


def get_public_transit_segment_details(api_key, origin_lat, origin_lng, dest_lat, dest_lng, city, strategy=0):
    """
    Gets public transit route details using Amap Integrated Directions API.
    `city` is the origin city code or name.
    Strategy: 0 for recommended, other values for different preferences (e.g., less walking).
    Returns a dictionary like {"distance": meters, "duration": seconds, "polyline": "concatenated_polyline_string"} or None.
    Distance for transit is often walking distance + transit line distance, can be complex. Amap returns 'distance' field for the whole transit path.
    """
    if not api_key:
        return None

    url = "https://restapi.amap.com/v3/direction/transit/integrated"
    params = {
        "key": api_key,
        "origin": f"{origin_lng},{origin_lat}",
        "destination": f"{dest_lng},{dest_lat}",
        "city": str(city), # City code or name for origin city
        # "cityd": str(city), # Optionally, destination city if different, but often same for intra-city
        "strategy": str(strategy),
        "extensions": "all", # Request "all" to get polyline details for segments
    }

    try:
        response = requests.get(url, params=params, timeout=15) # Transit can take longer
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "1" and data.get("route") and data["route"].get("transits"):
            transit_path = data["route"]["transits"][0] # Take the first recommended transit path

            # The 'polyline' for the entire transit path is not directly provided in 'transits' object usually.
            # It's often part of individual segments (walking, bus, subway lines).
            # We need to concatenate them or use a primary segment's polyline.
            # For simplicity, _parse_transit_polyline will try to build one.
            # Amap's total 'distance' for transit includes walking and in-vehicle. 'duration' is total time.

            full_polyline = _parse_transit_polyline(transit_path)

            return {
                "distance": int(transit_path.get("distance", 0)), # Overall distance
                "duration": int(transit_path.get("duration", 0)), # Overall duration
                "polyline": full_polyline
            }
        else:
            print(f"Amap Public Transit Error: {data.get('info')} from ({origin_lng},{origin_lat}) to ({dest_lng},{dest_lat}) in city {city}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Amap Public Transit request failed: {e}")
        return None
    except (ValueError, KeyError, IndexError) as e:
        print(f"Error parsing Amap Public Transit response: {e}")
        return None
    return None


def get_driving_route_segment_details(api_key, origin_lat, origin_lng, dest_lat, dest_lng, strategy=5):
    """
    Gets driving route details (distance, duration, polyline) between two points using Amap API.
    Renamed from get_route_segment_details to be specific.
    Strategy: Amap routing strategy, 5 is default (recommended).
    Returns a dictionary like {"distance": meters, "duration": seconds, "polyline": "encoded_polyline_string"} or None.
    """
    if not api_key:
        return None

    url = "https://restapi.amap.com/v3/direction/driving"
    params = {
        "key": api_key,
        "origin": f"{origin_lng},{origin_lat}",
        "destination": f"{dest_lng},{dest_lat}",
        "strategy": str(strategy),
        "extensions": "base", # Request basic route information, "all" for steps and traffic
    }

    try:
        response = requests.get(url, params=params, timeout=10) # Increased timeout for routing
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "1" and data.get("route") and data["route"].get("paths"):
            path = data["route"]["paths"][0] # Take the first path
            # Amap returns distance in meters and duration in seconds directly in path object
            return {
                "distance": int(path.get("distance", 0)),
                "duration": int(path.get("duration", 0)), # duration is 'duration' not 'duration_seconds'
                "polyline": path.get("polyline") # Polyline for drawing on map
            }
        else:
            print(f"Amap Routing Error: {data.get('info')} from ({origin_lng},{origin_lat}) to ({dest_lng},{dest_lat})")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Amap Routing request failed: {e}")
        return None
    except (ValueError, KeyError, IndexError) as e: # Added IndexError for path[0]
        print(f"Error parsing Amap Routing response: {e}")
        return None
    return None


# --- API Endpoints ---
@app.route('/api/register', methods=['POST'])
def register():
    print("Received registration request")
    print("Request headers:", dict(request.headers))
    print("Request data:", request.get_data())
    print("Request JSON:", request.get_json())
    print("Request form:", request.form)
    print("Request args:", request.args)
    
    data = request.get_json()
    if not data:
        print("No JSON data received")
        return jsonify({'message': 'No JSON data received'}), 400
        
    username = data.get('username')
    password = data.get('password')
    
    print("Extracted username:", username)
    print("Extracted password:", password)

    if not username or not password:
        return jsonify({'message': 'Username and password are required'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'message': 'Username already exists'}), 409

    new_user = User(username=username)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()

    if user and user.check_password(password):
        login_user(user)
        return jsonify({'message': 'Logged in successfully'}), 200
    return jsonify({'message': 'Invalid username or password'}), 401

@app.route('/api/logout', methods=['POST'])
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

# --- User Home Location Endpoints ---
@app.route('/api/user/home', methods=['POST'])
@login_required
def update_home_location():
    data = request.get_json()
    address = data.get('address')
    latitude = data.get('latitude')
    longitude = data.get('longitude')

    # If address is provided but latitude/longitude are missing, geocode the address
    if address and (latitude is None or longitude is None):
        api_key = app.config.get('AMAP_API_KEY')
        if not api_key:
            return jsonify({'message': 'Amap API key not configured on server.'}), 500

        geocoded_location = geocode_address(api_key, address)
        if geocoded_location:
            latitude = geocoded_location['latitude']
            longitude = geocoded_location['longitude']
            # Optionally, you might want to use geocoded_location['formatted_address']
            # if you prefer the address returned by Amap. For now, use user's input address.
        else:
            # Address provided but geocoding failed
            return jsonify({'message': 'Could not geocode address. Please provide coordinates or check address.'}), 400
    elif not address and (latitude is None or longitude is None):
        # Clear home location
        current_user.home_address = None
        current_user.home_latitude = None
        current_user.home_longitude = None
        db.session.commit()
        return jsonify({'message': 'Home location cleared.'}), 200

    current_user.home_address = address
    current_user.home_latitude = latitude
    current_user.home_longitude = longitude
    db.session.commit()
    return jsonify({'message': 'Home location updated successfully'}), 200

@app.route('/api/user/home', methods=['GET'])
@login_required
def get_home_location():
    return jsonify({
        'home_address': current_user.home_address,
        'home_latitude': current_user.home_latitude,
        'home_longitude': current_user.home_longitude
    }), 200

# --- Shop Search Endpoint ---
@app.route('/api/shops/find', methods=['POST'])
def find_shops():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Request body must be JSON.'}), 400

    keywords = data.get('keywords')
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    city = data.get('city')

    if not keywords:
        return jsonify({'message': 'Missing "keywords" in request body.'}), 400

    api_key = app.config.get('AMAP_API_KEY')
    if not api_key:
        return jsonify({'message': 'Amap API key not configured on server.'}), 500

    location_str = None
    if latitude is not None and longitude is not None:
        try:
            # Ensure lat/lon can be converted to float before using them
            lat_float = float(latitude)
            lon_float = float(longitude)
            location_str = f"{lon_float},{lat_float}"
        except ValueError:
            return jsonify({'message': 'Invalid latitude or longitude format.'}), 400

    # Default radius for location-based search (e.g., 10km)
    radius = data.get('radius', 10000)

    # 添加重试机制
    max_retries = 3
    retry_count = 0
    last_error = None

    while retry_count < max_retries:
        try:
            # Call the search_poi utility function
            results = search_poi(
                api_key=api_key,
                keywords=keywords,
                city=city,
                location=location_str,
                radius=radius if location_str else 5000 # Default radius if location is used
            )

            if results is None:
                # This case implies an error occurred during the API call in search_poi
                # search_poi function already prints errors, so here we return a generic server error
                return jsonify({'message': 'Error occurred while searching for shops.'}), 500

            if not results: # Empty list means no POIs found
                return jsonify({'message': 'No shops found matching your query.'}), 404

            return jsonify({'shops': results}), 200

        except Exception as e:
            last_error = str(e)
            retry_count += 1
            if retry_count < max_retries:
                time.sleep(1)  # 等待1秒后重试
                continue
            else:
                app.logger.error(f"Failed to search shops after {max_retries} retries. Last error: {last_error}")
                return jsonify({
                    'message': 'Failed to search shops after multiple attempts.',
                    'error': last_error
                }), 500

# --- Route Optimization Endpoint ---
MAX_SHOPS_FOR_PERMUTATIONS = 6 # Max shops (N) for permutation-based TSP

@app.route('/api/route/optimize', methods=['POST'])
@login_required
def optimize_route():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Request body must be JSON.'}), 400

    home_location_data = data.get('home_location')
    shops_data = data.get('shops')
    mode = data.get('mode', 'driving')
    city_param = data.get('city') # City name or adcode, used for public transit

    if not home_location_data or 'latitude' not in home_location_data or 'longitude' not in home_location_data:
        return jsonify({'message': 'Missing or invalid "home_location". It must be an object with "latitude" and "longitude".'}), 400

    if not shops_data or not isinstance(shops_data, list) or len(shops_data) == 0:
        return jsonify({'message': 'Missing or invalid "shops". It must be a non-empty list of shop objects.'}), 400

    for shop in shops_data:
        if 'latitude' not in shop or 'longitude' not in shop or 'id' not in shop or 'name' not in shop:
            return jsonify({'message': 'Each shop in "shops" must have "id", "name", "latitude", and "longitude".'}), 400
        # Validate stay_duration if provided
        if 'stay_duration' in shop:
            if not isinstance(shop['stay_duration'], (int, float)) or shop['stay_duration'] < 0:
                return jsonify({'message': f'Optional "stay_duration" for shop {shop.get("id", "")} must be a non-negative number.'}), 400
        else:
            shop['stay_duration'] = 0 # Default to 0 if not provided

    api_key = app.config.get('AMAP_API_KEY')
    if not api_key:
        return jsonify({'message': 'Amap API key not configured on server.'}), 500

    if len(shops_data) > MAX_SHOPS_FOR_PERMUTATIONS:
        return jsonify({'message': f'Too many shops for optimization. Please select {MAX_SHOPS_FOR_PERMUTATIONS} or fewer shops.'}), 400

    # Prepare points: Home is point 0, shops are 1 to N
    # Keep original shop data to return in optimized_order
    home_point = {
        "id": "home",
        "name": "Home",
        "latitude": home_location_data['latitude'],
        "longitude": home_location_data['longitude'],
        "stay_duration": 0 # Home has no stay duration in this context
    }
    # Ensure shops_data now contains validated/defaulted stay_duration
    all_points_objects = [home_point] + shops_data # Store full objects for reference

    # Create a list of (lat, lon) for distance matrix calculation
    all_coords = [(p['latitude'], p['longitude']) for p in all_points_objects]
    num_points = len(all_coords)

    # Build distance matrix: cost_matrix[i][j] stores {'distance': d, 'duration': t, 'polyline': pl}
    cost_matrix = [[None for _ in range(num_points)] for _ in range(num_points)]

    for i in range(num_points):
        for j in range(i + 1, num_points):
            p1_lat, p1_lon = all_coords[i]
            p2_lat, p2_lon = all_coords[j]

            segment_details = None
            if mode == "public_transit":
                if not city_param: # City is crucial for public transit
                    return jsonify({'message': 'Missing "city" parameter in request body, required for public transit mode.'}), 400
                segment_details = get_public_transit_segment_details(api_key, p1_lat, p1_lon, p2_lat, p2_lon, city_param)
            else: # Default to driving
                segment_details = get_driving_route_segment_details(api_key, p1_lat, p1_lon, p2_lat, p2_lon)

            if segment_details is None:
                return jsonify({'message': f'Failed to get {mode} route details between {all_points_objects[i]["name"]} and {all_points_objects[j]["name"]}. Cannot optimize.'}), 500

            cost_matrix[i][j] = segment_details
            # For public transit, cost might not be symmetric, but for permutation TSP, we often assume it or build full matrix.
            # For simplicity here, if we need symmetric for TSP algo, we might need to call API twice or use this value.
            # However, Amap's transit duration can vary significantly based on direction due to one-way lines etc.
            # For a more accurate TSP with public transit, matrix might need cost_matrix[j][i] fetched separately.
            # For now, assume symmetry for simplicity of TSP distance calc, but this is a known limitation.
            cost_matrix[j][i] = segment_details

    # TSP using permutations for shops (points 1 to num_points-1)
    shop_indices = list(range(1, num_points)) # Indices of shops in all_coords/all_points_objects

    min_total_distance = float('inf')
    best_path_indices = [] # Stores indices relative to all_coords

    if not shop_indices: # Only home location, no shops
        return jsonify({
            'optimized_order': [home_point],
            'total_distance': 0,
            'total_duration': 0,
            'route_segments': []
        }), 200

    for p in itertools.permutations(shop_indices):
        current_distance = 0
        current_path_indices = [0] + list(p) + [0] # Home -> Shops -> Home

        valid_permutation = True
        for i in range(len(current_path_indices) - 1):
            u, v = current_path_indices[i], current_path_indices[i+1]
            if cost_matrix[u][v] is None: # Should have been caught earlier, but as a safeguard
                valid_permutation = False
                break
            current_distance += cost_matrix[u][v]['distance']

        if valid_permutation and current_distance < min_total_distance:
            min_total_distance = current_distance
            best_path_indices = current_path_indices

    if not best_path_indices:
        return jsonify({'message': 'Could not find an optimal route. Check segment routing.'}), 500

    # Construct final response with full segment details for the best path
    optimized_order_objects = [all_points_objects[i] for i in best_path_indices]
    route_segments_details = []
    total_travel_duration = 0
    total_stay_duration = 0

    # Calculate total travel duration from segments
    for i in range(len(best_path_indices) - 1):
        u, v = best_path_indices[i], best_path_indices[i+1]
        segment_info = cost_matrix[u][v] # Already fetched, includes polyline
        route_segments_details.append({
            "from_name": all_points_objects[u]["name"],
            "to_name": all_points_objects[v]["name"],
            "from_id": all_points_objects[u]["id"],
            "to_id": all_points_objects[v]["id"],
            "distance": segment_info['distance'],
            "duration": segment_info['duration'], # This is travel time for the segment
            "polyline": segment_info['polyline']
        })
        total_travel_duration += segment_info['duration']

    # Calculate total stay duration for shops in the chosen path
    # The first and last points in best_path_indices are 'home', which has stay_duration 0.
    # Shops are all_points_objects[idx] where idx is in best_path_indices[1:-1]
    for shop_idx_in_all_points in best_path_indices[1:-1]: # Exclude home at start and end
        # all_points_objects already has stay_duration (either provided or defaulted to 0)
        total_stay_duration += all_points_objects[shop_idx_in_all_points].get('stay_duration', 0)

    overall_total_duration = total_travel_duration + total_stay_duration

    return jsonify({
        'optimized_order': optimized_order_objects,
        'total_distance': min_total_distance, # This is purely travel distance
        'total_duration': overall_total_duration, # Travel time + Stay time
        'route_segments': route_segments_details # Segments only show travel time
    }), 200


# --- Database Initialization ---
def init_db():
    with app.app_context():
        db.create_all()
    print("Database initialized!")

# Initialize database when the app starts
init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0') # In a production environment, use a WSGI server like Gunicorn or uWSGI.
