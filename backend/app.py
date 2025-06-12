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
            app.logger.warning(f"Amap Geocoding Error: {data.get('info')} for address: {address}")
            return None
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Amap Geocoding request failed: {e}")
        return None
    except (ValueError, KeyError) as e:
        app.logger.error(f"Error parsing Amap Geocoding response: {e}")
        return None
    return None

def search_poi(api_key, keywords, city=None, location=None, radius=5000, types=None, limit=20):
    """
    Searches for POIs using Amap Place Text Search API.
    Returns a list of POI dictionaries up to the specified limit, or None.
    """
    if not api_key or not keywords:
        return None

    url = "https://restapi.amap.com/v3/place/text"
    params = {
        "key": api_key,
        "keywords": keywords,
        "offset": limit, # Number of results per page (max 25, controlled by limit)
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
            return pois_data[:limit] # Ensure we don't return more than limit
        else:
            app.logger.warning(f"Amap POI Search Error: {data.get('info')} for keywords: {keywords}")
            return None
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Amap POI Search request failed: {e}")
        return None
    except (ValueError, KeyError) as e:
        app.logger.error(f"Error parsing Amap POI Search response: {e}")
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
            app.logger.warning(f"Amap Public Transit Error: {data.get('info')} from ({origin_lng},{origin_lat}) to ({dest_lng},{dest_lat}) in city {city}")
            return None
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Amap Public Transit request failed: {e}")
        return None
    except (ValueError, KeyError, IndexError) as e:
        app.logger.error(f"Error parsing Amap Public Transit response: {e}")
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
            app.logger.warning(f"Amap Routing Error: {data.get('info')} from ({origin_lng},{origin_lat}) to ({dest_lng},{dest_lat})")
            return None
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Amap Routing request failed: {e}")
        return None
    except (ValueError, KeyError, IndexError) as e: # Added IndexError for path[0]
        app.logger.error(f"Error parsing Amap Routing response: {e}")
        return None
    return None


# --- API Endpoints ---
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        app.logger.warning("Registration attempt with no JSON data.")
        return jsonify({'message': 'No JSON data received'}), 400
        
    username = data.get('username')
    password = data.get('password')
    
    app.logger.info(f"Registration attempt for username: {username}")

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

# --- Route Optimization Logic ---
MAX_SHOPS_FOR_PERMUTATIONS = 6 # Max shops (N) for permutation-based TSP

def _calculate_optimized_route_for_points(api_key, home_point_with_details, shops_with_details_list, mode, city_param, max_shops_limit):
    """
    Internal helper to calculate an optimized route (TSP) for a set of points.
    Returns a tuple: (result_dict, error_tuple).
    result_dict is the successful response. error_tuple is (message, status_code) on error.
    """
    if not api_key:
        return None, ({'message': 'Amap API key not configured on server.'}, 500)

    if len(shops_with_details_list) > max_shops_limit:
        return None, ({'message': f'Too many shops for optimization. Please select {max_shops_limit} or fewer shops.'}, 400)

    all_points_objects = [home_point_with_details] + shops_with_details_list

    all_coords = [(p['latitude'], p['longitude']) for p in all_points_objects]
    num_points = len(all_coords)

    cost_matrix = [[None for _ in range(num_points)] for _ in range(num_points)]

    for i in range(num_points):
        for j in range(i + 1, num_points):
            p1_lat, p1_lon = all_coords[i]
            p2_lat, p2_lon = all_coords[j]

            segment_details = None
            if mode == "public_transit":
                if not city_param:
                    return None, ({'message': 'Missing "city" parameter, required for public transit mode.'}, 400)
                segment_details = get_public_transit_segment_details(api_key, p1_lat, p1_lon, p2_lat, p2_lon, city_param)
            else: # Default to driving
                segment_details = get_driving_route_segment_details(api_key, p1_lat, p1_lon, p2_lat, p2_lon)

            if segment_details is None:
                err_msg = f'Failed to get {mode} route details between {all_points_objects[i]["name"]} and {all_points_objects[j]["name"]}. Cannot optimize.'
                return None, ({'message': err_msg}, 500)

            cost_matrix[i][j] = segment_details
            cost_matrix[j][i] = segment_details # Assuming symmetry for simplicity

    shop_indices = list(range(1, num_points))
    min_total_distance = float('inf')
    best_path_indices = []

    if not shop_indices: # Only home location
        result = {
            'optimized_order': [home_point_with_details],
            'total_distance': 0,
            'total_duration': 0, # home_point_with_details['stay_duration'] is 0
            'route_segments': []
        }
        return result, None

    for p in itertools.permutations(shop_indices):
        current_distance = 0
        current_path_indices = [0] + list(p) + [0] # Home -> Shops -> Home

        valid_permutation = True
        for i_seg in range(len(current_path_indices) - 1):
            u, v = current_path_indices[i_seg], current_path_indices[i_seg+1]
            if cost_matrix[u][v] is None:
                valid_permutation = False
                break
            current_distance += cost_matrix[u][v]['distance']

        if valid_permutation and current_distance < min_total_distance:
            min_total_distance = current_distance
            best_path_indices = current_path_indices

    if not best_path_indices:
        return None, ({'message': 'Could not find an optimal route. Check segment routing.'}, 500)

    optimized_order_objects = [all_points_objects[i] for i in best_path_indices]
    route_segments_details = []
    total_travel_duration = 0
    total_stay_duration = 0

    for i_seg in range(len(best_path_indices) - 1):
        u, v = best_path_indices[i_seg], best_path_indices[i_seg+1]
        segment_info = cost_matrix[u][v]
        route_segments_details.append({
            "from_name": all_points_objects[u]["name"],
            "to_name": all_points_objects[v]["name"],
            "from_id": all_points_objects[u]["id"],
            "to_id": all_points_objects[v]["id"],
            "distance": segment_info['distance'],
            "duration": segment_info['duration'],
            "polyline": segment_info['polyline']
        })
        total_travel_duration += segment_info['duration']

    for shop_idx_in_all_points in best_path_indices[1:-1]:
        total_stay_duration += all_points_objects[shop_idx_in_all_points].get('stay_duration', 0)

    overall_total_duration = total_travel_duration + total_stay_duration

    result = {
        'optimized_order': optimized_order_objects,
        'total_distance': min_total_distance,
        'total_duration': overall_total_duration,
        'route_segments': route_segments_details
    }
    return result, None

# --- API Endpoints ---

@app.route('/api/route/optimize', methods=['POST'])
@login_required
def optimize_route():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Request body must be JSON.'}), 400

    home_location_data = data.get('home_location')
    shops_data = data.get('shops') # This is shops_with_details_list
    mode = data.get('mode', 'driving')
    city_param = data.get('city')

    if not home_location_data or 'latitude' not in home_location_data or 'longitude' not in home_location_data:
        return jsonify({'message': 'Missing or invalid "home_location". It must be an object with "latitude" and "longitude".'}), 400

    if not shops_data or not isinstance(shops_data, list): # Allow empty list for just home
        return jsonify({'message': 'Invalid "shops". It must be a list of shop objects.'}), 400

    # Validate shops_data structure and content
    for shop in shops_data:
        if not all(k in shop for k in ['latitude', 'longitude', 'id', 'name']):
            return jsonify({'message': 'Each shop in "shops" must have "id", "name", "latitude", and "longitude".'}), 400
        if 'stay_duration' in shop:
            if not isinstance(shop['stay_duration'], (int, float)) or shop['stay_duration'] < 0:
                return jsonify({'message': f'Optional "stay_duration" for shop {shop.get("id", "")} must be a non-negative number.'}), 400
        else:
            shop['stay_duration'] = 0 # Default if not provided

    api_key = app.config.get('AMAP_API_KEY')
    # api_key check is inside _calculate_optimized_route_for_points

    home_point = {
        "id": "home",
        "name": "Home",
        "latitude": home_location_data['latitude'],
        "longitude": home_location_data['longitude'],
        "stay_duration": 0
    }

    result, error = _calculate_optimized_route_for_points(
        api_key,
        home_point,
        shops_data, # Already validated and processed
        mode,
        city_param,
        MAX_SHOPS_FOR_PERMUTATIONS
    )

    if error:
        return jsonify(error[0]), error[1]

    return jsonify(result), 200

@app.route('/api/routes/generate_options', methods=['POST'])
@login_required
def generate_route_options():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Request body must be JSON.'}), 400

    home_location = data.get('home_location')
    shop_requests = data.get('shop_requests')
    mode = data.get('mode', 'driving') # Default to driving
    city = data.get('city') # Optional, but required for public_transit

    # Validate home_location
    if not home_location or not isinstance(home_location, dict) or \
       'latitude' not in home_location or 'longitude' not in home_location:
        return jsonify({'message': 'Missing or invalid "home_location". It must be an object with "latitude" and "longitude".'}), 400
    try:
        float(home_location['latitude'])
        float(home_location['longitude'])
    except (ValueError, TypeError):
        return jsonify({'message': 'Invalid coordinates in "home_location". Latitude and longitude must be numbers.'}), 400

    # Validate shop_requests
    if not shop_requests or not isinstance(shop_requests, list):
        return jsonify({'message': 'Missing or invalid "shop_requests". It must be a list.'}), 400

    if not shop_requests: # If list is empty, it's a valid scenario (just go home)
        pass # Or handle as a specific case if needed, e.g. return home location only.

    for i, req in enumerate(shop_requests):
        if not isinstance(req, dict):
            return jsonify({'message': f'Invalid item in "shop_requests" at index {i}. Each item must be an object.'}), 400
        if 'name' not in req or not isinstance(req['name'], str) or not req['name'].strip():
            return jsonify({'message': f'Missing or invalid "name" in shop_requests item at index {i}. Name must be a non-empty string.'}), 400

        # Validate stay_duration_minutes (optional, defaults to 0 if not present)
        stay_duration_minutes = req.get('stay_duration_minutes', 0)
        if not isinstance(stay_duration_minutes, (int, float)) or stay_duration_minutes < 0:
            return jsonify({'message': f'Invalid "stay_duration_minutes" for shop request "{req["name"]}" (index {i}). Must be a non-negative number.'}), 400
        req['stay_duration_seconds'] = stay_duration_minutes * 60 # Convert to seconds for internal use

        # Validate max_candidates (optional, defaults to e.g. 1 or 3 if not present)
        max_candidates = req.get('max_candidates', 3) # Default to 3 candidates
        if not isinstance(max_candidates, int) or max_candidates <= 0:
            return jsonify({'message': f'Invalid "max_candidates" for shop request "{req["name"]}" (index {i}). Must be a positive integer.'}), 400
        req['max_candidates'] = max_candidates # Store validated value

    # Validate mode
    if not isinstance(mode, str) or mode not in ['driving', 'public_transit']: # Add other modes if supported
        return jsonify({'message': 'Invalid "mode". Supported modes are "driving", "public_transit".'}), 400

    # Validate city for public_transit
    if mode == 'public_transit' and (not city or not isinstance(city, str) or not city.strip()):
        return jsonify({'message': 'Missing or invalid "city". City is required for "public_transit" mode.'}), 400

    api_key = app.config.get('AMAP_API_KEY')
    if not api_key:
        return jsonify({'message': 'Amap API key not configured on server.'}), 500

    # Define limits for this endpoint
    MAX_SHOP_NAMES_FOR_OPTIONS = 3
    MAX_TOTAL_COMBINATIONS = 10
    DEFAULT_SEARCH_RADIUS_METERS = 15000

    if len(shop_requests) > MAX_SHOP_NAMES_FOR_OPTIONS:
        return jsonify({'message': f'Too many shop requests. Maximum is {MAX_SHOP_NAMES_FOR_OPTIONS}.'}), 400

    if not shop_requests: # No shops requested, just return home to home.
        home_point_details = {
            "id": "home", "name": "Home",
            "latitude": home_location['latitude'], "longitude": home_location['longitude'],
            "stay_duration": 0
        }
        # Effectively, this is an optimization for zero shops.
        # _calculate_optimized_route_for_points handles this if shops_with_details_list is empty.
        result, error = _calculate_optimized_route_for_points(
            api_key, home_point_details, [], mode, city, MAX_SHOPS_FOR_PERMUTATIONS # MAX_SHOPS_FOR_PERMUTATIONS is for individual TSP
        )
        if error:
            return jsonify(error[0]), error[1]
        return jsonify({'options': [result]}), 200


    # 1. Candidate Fetching
    all_shop_candidates = [] # List of lists, e.g., [[ShopA_Cand1, ShopA_Cand2], [ShopB_Cand1]]
    for i, req in enumerate(shop_requests):
        shop_name_query = req['name']
        limit_candidates = req['max_candidates']
        stay_duration_seconds = req['stay_duration_seconds']

        city_for_search = city # Use main request city if provided
        location_for_search = None
        radius_for_search = DEFAULT_SEARCH_RADIUS_METERS

        if not city_for_search: # If no city in main request, use home location for search context
            location_for_search = f"{home_location['longitude']},{home_location['latitude']}"

        # search_poi(api_key, keywords, city=None, location=None, radius=5000, types=None, limit=20)
        poi_results = search_poi(
            api_key=api_key,
            keywords=shop_name_query,
            city=city_for_search,
            location=location_for_search,
            radius=radius_for_search,
            limit=limit_candidates
        )

        if poi_results is None: # Error during search_poi
            return jsonify({'message': f'Error searching for candidates for "{shop_name_query}".'}), 500
        if not poi_results: # No candidates found
            return jsonify({'message': f'No candidates found for shop request "{shop_name_query}".'}), 404

        current_shop_candidates = []
        for poi in poi_results:
            # Ensure POI has lat/lon, otherwise it's unusable for routing
            if poi.get('latitude') is None or poi.get('longitude') is None:
                app.logger.warning(f"POI candidate {poi.get('name')} for '{shop_name_query}' is missing coordinates, skipping.")
                continue

            candidate = poi.copy() # Copy POI details
            candidate['stay_duration'] = stay_duration_seconds # Add stay_duration from original request
            candidate['original_request_name'] = shop_name_query # For clarity in results
            current_shop_candidates.append(candidate)

        if not current_shop_candidates: # All POIs lacked coordinates
             return jsonify({'message': f'No valid (with coordinates) candidates found for shop request "{shop_name_query}".'}), 404

        all_shop_candidates.append(current_shop_candidates)

    # 2. Generate Combinations
    # Calculate total number of combinations
    num_combinations = 1
    for candidates_list in all_shop_candidates:
        num_combinations *= len(candidates_list)

    if num_combinations == 0: # Should be caught by earlier checks, but as a safeguard
        return jsonify({'message': 'No candidates found for one or more shop requests, cannot generate routes.'}), 404

    if num_combinations > MAX_TOTAL_COMBINATIONS:
        return jsonify({'message': f'Too many potential route combinations ({num_combinations}). Maximum allowed is {MAX_TOTAL_COMBINATIONS}. Please reduce number of shops or candidates per shop.'}), 400

    shop_combinations = list(itertools.product(*all_shop_candidates))

    # 3. Process Combinations
    route_options = []
    home_point_details = {
        "id": "home", "name": "Home",
        "latitude": home_location['latitude'], "longitude": home_location['longitude'],
        "stay_duration": 0
    }

    for combo_shops_list in shop_combinations:
        # combo_shops_list is a tuple of shop candidate dicts, e.g., (cand_A1, cand_B1)
        # Each shop in combo_shops_list already has lat, lon, id, name, stay_duration

        # The _calculate_optimized_route_for_points expects shops_with_details_list
        # which should be a list of dicts. combo_shops_list is already in this format.
        # Ensure that the number of shops in this specific combo does not exceed MAX_SHOPS_FOR_PERMUTATIONS
        # This check is actually inside _calculate_optimized_route_for_points.

        route_result, error_info = _calculate_optimized_route_for_points(
            api_key,
            home_point_details,
            list(combo_shops_list), # Convert tuple to list for the helper
            mode,
            city, # city_param for transit
            MAX_SHOPS_FOR_PERMUTATIONS # max_shops_limit for individual TSP calculation
        )

        if error_info:
            app.logger.warning(f"Skipping a route combination due to error: {error_info[0]['message']}")
            # Optionally, log this error or store it to return partial failures
            continue

        if route_result:
            # Add the specific shops used in this option for clarity in the response
            route_result['shops_in_this_option'] = [
                {
                    "id": shop.get("id"),
                    "name": shop.get("name"),
                    "address": shop.get("address"),
                    "original_request_name": shop.get("original_request_name"),
                    "stay_duration_minutes": shop.get("stay_duration", 0) / 60
                } for shop in combo_shops_list
            ]
            route_options.append(route_result)

    # 4. Sort and Return Results
    if not route_options:
        return jsonify({'message': 'No valid route options could be generated.'}), 404

    # Sort by total_duration, then total_distance
    route_options.sort(key=lambda x: (x.get('total_duration', float('inf')), x.get('total_distance', float('inf'))))

    return jsonify({'options': route_options}), 200

# --- Database Initialization ---
def init_db():
    with app.app_context():
        db.create_all()
    app.logger.info("Database initialized!")

# Initialize database when the app starts
init_db()

if __name__ == '__main__':
    # Consider adding basic logging configuration here if not handled by Flask/Gunicorn in production
    app.run(debug=True, host='0.0.0.0') # In a production environment, use a WSGI server like Gunicorn or uWSGI.
