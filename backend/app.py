import os
import requests # Added for Amap API calls
import itertools # Added for permutations
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS  # 添加CORS支持
import time
import itertools
import concurrent.futures

# Initialize Flask app
app = Flask(__name__)
CORS(app, supports_credentials=True, resources={
    r"/api/*": {
        "origins": ["http://localhost:8080", "http://127.0.0.1:8080"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})
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

def search_poi(api_key, keywords, city=None, location=None, radius=5000, types=None, max_results=50):
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

        all_pois = []
        page = 1
        offset = 25
        
        while len(all_pois) < max_results:
            params = {
                "key": api_key,
                "keywords": keywords,
                "offset": offset,
                "page": page,
            }
            if data.get("status") == "1" and data.get("pois"):
                current_pois = data["pois"]
                all_pois.extend(current_pois)
                
                # 如果返回的结果少于offset，说明没有更多数据了
                if len(current_pois) < offset:
                    break
                    
                page += 1
            else:
                break
        
        # 移除这行错误的return语句
        # return all_pois[:max_results]  # 限制最终返回数量

        # 处理和转换数据格式
        if all_pois:
            pois_data = []
            for poi in all_pois[:max_results]:  # 限制最终返回数量
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
            print(f"Amap POI Search Error: No POIs found for keywords: {keywords}")
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


def _parse_transit_details(transit_segments):
    """
    Parses transit segments from Amap API response to extract detailed step-by-step instructions.
    """
    detailed_steps = []
    if not transit_segments:
        return detailed_steps

    for segment in transit_segments:
        if segment.get("walking") and isinstance(segment["walking"], dict) and segment["walking"].get("steps"):
            for step in segment["walking"]["steps"]:
                instruction = step.get("instruction", "Walk")
                # Add distance and duration to instruction if available
                distance = step.get("distance", "")
                duration = step.get("duration", "")
                if distance:
                    instruction += f" (Distance: {distance}m"
                if duration:
                    instruction += f", Duration: {duration}s"
                if distance or duration:
                    instruction += ")"
                detailed_steps.append({"type": "walk", "instruction": instruction})

        elif segment.get("bus") and isinstance(segment["bus"], dict) and segment["bus"].get("lines"):
            for bus_line_info in segment["bus"]["lines"]: # A segment can have multiple bus lines (e.g. alternatives)
                line_name = bus_line_info.get("name", "Unknown Bus")
                departure_stop = bus_line_info.get("departure_stop", {}).get("name", "Unknown Stop")
                arrival_stop = bus_line_info.get("arrival_stop", {}).get("name", "Unknown Stop")
                num_stops = len(bus_line_info.get("via_stops", [])) + 1 # departure is not via_stop

                instruction = f"Take {line_name} from {departure_stop} to {arrival_stop} ({num_stops} stop{'s' if num_stops > 1 else ''})."

                # Add via_stops details
                via_stops_details = []
                for via_stop in bus_line_info.get("via_stops", []):
                    via_stops_details.append(via_stop.get("name", "Unknown Intermediate Stop"))
                if via_stops_details:
                    instruction += f" Via: {', '.join(via_stops_details)}."

                detailed_steps.append({"type": "bus", "instruction": instruction})

        elif segment.get("railway") and isinstance(segment["railway"], dict):
            # Railway can have 'alters' for alternative trains, or direct info
            railway_info_to_parse = segment["railway"]
            if segment["railway"].get("alters") and segment["railway"]["alters"]:
                railway_info_to_parse = segment["railway"]["alters"][0] # Take the first alternative

            name = railway_info_to_parse.get("name", "Unknown Line")
            trip = railway_info_to_parse.get("trip", "Unknown Trip") # More specific e.g. G1234
            departure_stop = railway_info_to_parse.get("departure_stop", {}).get("name", "Unknown Station")
            arrival_stop = railway_info_to_parse.get("arrival_stop", {}).get("name", "Unknown Station")
            num_stops = len(railway_info_to_parse.get("via_stops", [])) + 1

            instruction = f"Take {name} ({trip}) from {departure_stop} to {arrival_stop} ({num_stops} stop{'s' if num_stops > 1 else ''})."

            # Add via_stops details for railway
            via_stops_details_rail = []
            for via_stop in railway_info_to_parse.get("via_stops", []):
                 via_stops_details_rail.append(via_stop.get("name", "Unknown Intermediate Station"))
            if via_stops_details_rail:
                instruction += f" Via: {', '.join(via_stops_details_rail)}."

            detailed_steps.append({"type": "railway", "instruction": instruction})

        elif segment.get("taxi") and isinstance(segment["taxi"], dict):
            # Taxi segments usually don't have detailed steps like bus/walk, more like a summary
            distance = segment["taxi"].get("distance")
            duration = segment["taxi"].get("duration")
            instruction = "Take a taxi"
            if distance: instruction += f" (Distance: {distance}m"
            if duration: instruction += f", Duration: {duration}s"
            if distance or duration: instruction += ")"
            detailed_steps.append({"type": "taxi", "instruction": instruction})

        else:
            # Fallback for other types or if structure is unexpected
            # Try to find any instruction-like field if available
            instruction_text = "Transit segment (details not fully parsed)."
            if segment.get("instruction"): # Unlikely top-level, but as a fallback
                instruction_text = segment["instruction"]
            detailed_steps.append({"type": "transit", "instruction": instruction_text})

    return detailed_steps


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
            detailed_steps = _parse_transit_details(transit_path.get("segments"))

            return {
                "distance": int(transit_path.get("distance", 0)), # Overall distance
                "duration": int(transit_path.get("duration", 0)), # Overall duration
                "polyline": full_polyline,
                "steps": detailed_steps
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
    time.sleep(0.05) # 增加50毫秒延迟以避免QPS超限
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
        "extensions": "all", # Request basic route information, "all" for steps and traffic
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
                "polyline": path.get("polyline"), # Polyline for drawing on map
                "steps": path.get("steps", []) # Add steps information
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
    time.sleep(0.05) # 增加50毫秒延迟以避免QPS超限
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
# 定义一个已知的连锁店品牌列表（可以根据需要扩展）
CHAIN_STORE_KEYWORDS = {
    '星巴克', 'starbucks', '肯德基', 'kfc', '麦当劳', 'mcdonald',
    '必胜客', 'pizza hut', '汉堡王', 'burger king', '全家', 'familymart',
    '7-eleven', '711', 'seven-eleven', '罗森', 'lawson', '便利蜂'
}

@app.route('/api/shops/find', methods=['POST'])
def find_shops():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Request body must be JSON.'}), 400

    keywords = data.get('keywords', '').strip()
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    city = data.get('city')
    # 添加新参数来区分搜索意图
    get_details = data.get('get_details', False)  # 是否获取详细分店信息

    if not keywords:
        return jsonify({'message': 'Missing "keywords" in request body.'}), 400

    api_key = app.config.get('AMAP_API_KEY')
    if not api_key:
        return jsonify({'message': 'Amap API key not configured on server.'}), 500

    # 检查是否为连锁店搜索
    is_chain_search = keywords.lower() in CHAIN_STORE_KEYWORDS

    location_str = None
    if latitude is not None and longitude is not None:
        try:
            lat_float = float(latitude)
            lon_float = float(longitude)
            location_str = f"{lon_float},{lat_float}"
        except ValueError:
            return jsonify({'message': 'Invalid latitude or longitude format.'}), 400

    radius = data.get('radius', 10000)

    try:
        results = search_poi(
            api_key=api_key,
            keywords=keywords,
            city=city,
            location=location_str,
            radius=radius if location_str else 5000,
            max_results=50
        )

        if results is None:
            return jsonify({'message': 'Error occurred while searching for shops.'}), 500

        # 修改连锁店处理逻辑：只有在不需要详细信息时才返回汇总
        if is_chain_search and len(results) > 1 and not get_details:
            chain_suggestion = {
                "id": f"chain_{keywords.lower()}",
                "name": keywords,
                "type": "chain",
                "status": "待组合优化",
                "address": f"在 {city or '附近'} 找到 {len(results)} 家分店",
                "count": len(results)
            }
            return jsonify({'shops': [chain_suggestion]}), 200

        if not results:
            return jsonify({'message': 'No shops found matching your query.'}), 404

        return jsonify({'shops': results}), 200

    except Exception as e:
        app.logger.error(f"Failed to search shops. Error: {str(e)}")
        return jsonify({
            'message': 'Failed to search shops due to an internal error.',
            'error': str(e)
        }), 500

# --- Route Optimization Endpoint ---
MAX_SHOPS_FOR_PERMUTATIONS = 6 # Max shops (N) for permutation-based TSP

@app.route('/api/route/optimize', methods=['POST'])
# @login_required  # 移除这行
def optimize_route():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Request body must be JSON.'}), 400

    home_location_data = data.get('home_location')
    shops_data = data.get('shops')
    mode = data.get('mode', 'driving')
    city_param = data.get('city') # City name or adcode, used for public transit
    preferred_shop_ids = data.get('preferred_shop_ids', []) # Added

    if not home_location_data or 'latitude' not in home_location_data or 'longitude' not in home_location_data:
        return jsonify({'message': 'Missing or invalid "home_location". It must be an object with "latitude" and "longitude".'}), 400

    if not shops_data or not isinstance(shops_data, list) or len(shops_data) == 0:
        return jsonify({'message': 'Missing or invalid "shops". It must be a non-empty list of shop objects.'}), 400

    api_key = app.config.get('AMAP_API_KEY')
    if not api_key:
        return jsonify({'message': 'Amap API key not configured on server.'}), 500

    # 处理连锁店汇总信息，展开为具体分店
    expanded_shops = []
    for shop in shops_data:
        # 检查是否为连锁店汇总信息
        if shop.get('type') == 'chain' and shop.get('id', '').startswith('chain_'):
            # 提取连锁店名称
            chain_name = shop.get('name')
            if not chain_name:
                continue
                
            # 重新搜索该连锁店的具体分店
            location_str = None
            if home_location_data.get('latitude') and home_location_data.get('longitude'):
                location_str = f"{home_location_data['longitude']},{home_location_data['latitude']}"
            
            chain_shops = search_poi(
                api_key=api_key,
                keywords=chain_name,
                city=city_param,
                location=location_str,
                radius=20000,  # 20km搜索半径
                max_results=20  # 限制分店数量
            )
            
            if chain_shops:
                # 为每个分店添加连锁店标识和默认停留时间
                for chain_shop in chain_shops:
                    chain_shop['type'] = 'chain'
                    chain_shop['brand'] = chain_name
                    chain_shop['stay_duration'] = shop.get('stay_duration', 30)  # 默认30分钟
                expanded_shops.extend(chain_shops)
            else:
                # 如果搜索失败，返回错误
                return jsonify({'message': f'无法找到 {chain_name} 的具体分店信息'}), 400
        else:
            # 普通店铺直接添加
            expanded_shops.append(shop)
    
    # 更新shops_data为展开后的店铺列表
    shops_data = expanded_shops

    # 验证展开后的店铺数据
    for shop in shops_data:
        if 'latitude' not in shop or 'longitude' not in shop or 'id' not in shop or 'name' not in shop:
            return jsonify({'message': 'Each shop in "shops" must have "id", "name", "latitude", and "longitude".'}), 400
        # Validate stay_duration if provided
        if 'stay_duration' in shop:
            if not isinstance(shop['stay_duration'], (int, float)) or shop['stay_duration'] < 0:
                return jsonify({'message': f'Optional "stay_duration" for shop {shop.get("id", "")} must be a non-negative number.'}), 400
        else:
            shop['stay_duration'] = 0 # Default to 0 if not provided

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

    # Calculate total stay duration once - it's independent of path order
    total_stay_duration_val = 0
    if shop_indices: # Only calculate if there are shops
        for shop_idx_in_all_points in shop_indices: # Iterate through original shop indices
             total_stay_duration_val += all_points_objects[shop_idx_in_all_points].get('stay_duration', 0)

    # Handle case with no shops
    if not shop_indices:
        home_route_segment = {
            "from_name": home_point["name"], "to_name": home_point["name"],
            "from_id": home_point["id"], "to_id": home_point["id"],
            "distance": 0, "duration": 0, "polyline": "", "steps": []
        }
        single_point_route_data = {
            'optimized_order': [home_point],
            'total_distance': 0,
            'total_travel_time': 0,
            'total_stay_time': 0,
            'total_overall_duration': 0,
            'route_segments': [] # No travel segments if only one point
        }
        return jsonify({
            "routes": {
                "shortest_distance": single_point_route_data,
                "fastest_travel_time": single_point_route_data
            },
            "message": "No shops to visit. Only home location provided."
        }), 200

    # --- Optimization Pass 1: Shortest Distance ---
    min_total_distance_val = float('inf')
    best_path_indices_distance = []

    for p in itertools.permutations(shop_indices):
        current_distance_for_perm = 0
        current_path_indices = [0] + list(p) + [0] # Home -> Shops -> Home
        valid_permutation = True
        for i in range(len(current_path_indices) - 1):
            u, v = current_path_indices[i], current_path_indices[i+1]
            if cost_matrix[u][v] is None:
                valid_permutation = False
                break
            current_distance_for_perm += cost_matrix[u][v]['distance']

        if valid_permutation and current_distance_for_perm < min_total_distance_val:
            min_total_distance_val = current_distance_for_perm
            best_path_indices_distance = current_path_indices

    if not best_path_indices_distance:
        return jsonify({'message': 'Could not find an optimal route (distance-based). Check segment routing.'}), 500

    # Construct details for the shortest distance route
    optimized_order_objects_distance = [all_points_objects[i] for i in best_path_indices_distance]
    route_segments_details_distance = []
    total_travel_duration_for_distance_route = 0
    for i in range(len(best_path_indices_distance) - 1):
        u, v = best_path_indices_distance[i], best_path_indices_distance[i+1]
        segment_info = cost_matrix[u][v]
        route_segments_details_distance.append({
            "from_name": all_points_objects[u]["name"], "to_name": all_points_objects[v]["name"],
            "from_id": all_points_objects[u]["id"], "to_id": all_points_objects[v]["id"],
            "distance": segment_info['distance'], "duration": segment_info['duration'],
            "polyline": segment_info['polyline'], "steps": segment_info.get('steps', [])
        })
        total_travel_duration_for_distance_route += segment_info['duration']

    overall_total_duration_distance = total_travel_duration_for_distance_route + total_stay_duration_val

    shortest_distance_route_data = {
        'optimized_order': optimized_order_objects_distance,
        'total_distance': min_total_distance_val,
        'total_travel_time': total_travel_duration_for_distance_route,
        'total_stay_time': total_stay_duration_val,
        'total_overall_duration': overall_total_duration_distance,
        'route_segments': route_segments_details_distance
    }

    # --- Optimization Pass 2: Fastest Travel Time ---
    min_total_travel_duration_val = float('inf')
    best_path_indices_time = []

    for p in itertools.permutations(shop_indices):
        current_travel_duration_for_perm = 0
        current_path_indices = [0] + list(p) + [0] # Home -> Shops -> Home
        valid_permutation = True
        for i in range(len(current_path_indices) - 1):
            u, v = current_path_indices[i], current_path_indices[i+1]
            if cost_matrix[u][v] is None: # This check is crucial
                valid_permutation = False
                break
            current_travel_duration_for_perm += cost_matrix[u][v]['duration']

        if valid_permutation and current_travel_duration_for_perm < min_total_travel_duration_val:
            min_total_travel_duration_val = current_travel_duration_for_perm
            best_path_indices_time = current_path_indices

    fastest_travel_time_route_data = None
    if not best_path_indices_time:
        # This might happen if somehow no valid path for time was found, though unlikely if distance one was.
        # Or if all segments had 0 duration (highly improbable).
        # For now, we'll allow `fastest_travel_time_route_data` to be None if no path is found.
        # The frontend would need to handle this case.
        pass # fastest_travel_time_route_data remains None
    else:
        optimized_order_objects_time = [all_points_objects[i] for i in best_path_indices_time]
        route_segments_details_time = []
        actual_total_distance_for_time_route = 0
        for i in range(len(best_path_indices_time) - 1):
            u, v = best_path_indices_time[i], best_path_indices_time[i+1]
            segment_info = cost_matrix[u][v]
            route_segments_details_time.append({
                "from_name": all_points_objects[u]["name"], "to_name": all_points_objects[v]["name"],
                "from_id": all_points_objects[u]["id"], "to_id": all_points_objects[v]["id"],
                "distance": segment_info['distance'], "duration": segment_info['duration'],
                "polyline": segment_info['polyline'], "steps": segment_info.get('steps', [])
            })
            actual_total_distance_for_time_route += segment_info['distance']

        # total_stay_duration_val is the same as for the distance route
        overall_total_duration_time = min_total_travel_duration_val + total_stay_duration_val

        fastest_travel_time_route_data = {
            'optimized_order': optimized_order_objects_time,
            'total_distance': actual_total_distance_for_time_route,
            'total_travel_time': min_total_travel_duration_val,
            'total_stay_time': total_stay_duration_val, # Same as before
            'total_overall_duration': overall_total_duration_time,
            'route_segments': route_segments_details_time
        }

    # Filter routes based on preferred_shop_ids
    if preferred_shop_ids:
        preferred_shop_ids_set = set(str(shop_id) for shop_id in preferred_shop_ids) # Convert to set of strings

        # Filter shortest_distance_route_data
        if shortest_distance_route_data:
            route_shop_ids_distance = set(
                str(shop['id']) for shop in shortest_distance_route_data['optimized_order'] if str(shop['id']) != 'home'
            )
            if not preferred_shop_ids_set.issubset(route_shop_ids_distance):
                shortest_distance_route_data = None

        # Filter fastest_travel_time_route_data
        if fastest_travel_time_route_data:
            route_shop_ids_time = set(
                str(shop['id']) for shop in fastest_travel_time_route_data['optimized_order'] if str(shop['id']) != 'home'
            )
            if not preferred_shop_ids_set.issubset(route_shop_ids_time):
                fastest_travel_time_route_data = None

    return jsonify({
        "routes": {
            "shortest_distance": shortest_distance_route_data,
            "fastest_travel_time": fastest_travel_time_route_data
        },
        "message": "Successfully generated route options."
    }), 200

@app.route('/api/route/batch-optimize', methods=['POST'])
def batch_optimize_route():
    return jsonify({
        "routes": []
    }), 200

def get_driving_route(origin, destination):
    """一个调用高德API获取驾车路线的辅助函数"""
    api_key = os.getenv('AMAP_API_KEY')
    if not api_key:
        raise ValueError("AMAP_API_KEY is not set in the environment.")
    url = f"https://restapi.amap.com/v3/direction/driving?origin={origin}&destination={destination}&key={api_key}"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    time.sleep(0.05) # 增加50毫秒延迟以避免QPS超限
    if data['status'] == '1' and 'route' in data and 'paths' in data['route'] and len(data['route']['paths']) > 0:
        return data['route']
    else:
        raise Exception(f"Failed to get driving route from AMap API. Info: {data.get('info', 'Unknown error')}")

# --- Database Initialization ---
def init_db():
    with app.app_context():
        db.create_all()
    print("Database initialized!")

# Initialize database when the app starts
init_db()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # Note: Binding to '0.0.0.0' is crucial for Docker
    app.run(host='0.0.0.0', port=5000, debug=True)
