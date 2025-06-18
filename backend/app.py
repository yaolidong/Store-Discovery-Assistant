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
import hashlib # Added for route deduplication
import asyncio
from functools import wraps
from concurrent.futures import ThreadPoolExecutor
import logging

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

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AmapAPIManager:
    """高德API管理器，处理QPS限制和重试逻辑"""
    
    def __init__(self, api_key, max_qps=20):
        self.api_key = api_key
        self.max_qps = max_qps
        self.request_times = []
        self.executor = ThreadPoolExecutor(max_workers=5)
    
    def _check_qps_limit(self):
        """检查QPS限制"""
        now = time.time()
        # 清理1秒前的请求记录
        self.request_times = [t for t in self.request_times if now - t < 1.0]
        
        if len(self.request_times) >= self.max_qps:
            sleep_time = 1.0 - (now - self.request_times[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def _record_request(self):
        """记录请求时间"""
        self.request_times.append(time.time())
    
    def with_retry(self, max_retries=3, backoff_factor=1.0):
        """重试装饰器"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                last_exception = None
                for attempt in range(max_retries):
                    try:
                        self._check_qps_limit()
                        result = func(*args, **kwargs)
                        self._record_request()
                        return result
                    except requests.exceptions.RequestException as e:
                        last_exception = e
                        if attempt < max_retries - 1:
                            wait_time = backoff_factor * (2 ** attempt)
                            logger.warning(f"API调用失败，{wait_time}秒后重试: {e}")
                            time.sleep(wait_time)
                        else:
                            logger.error(f"API调用最终失败: {e}")
                    except Exception as e:
                        logger.error(f"非网络错误: {e}")
                        raise e
                raise last_exception
            return wrapper
        return decorator

# 创建全局API管理器实例
amap_manager = AmapAPIManager(app.config.get('AMAP_API_KEY', ''), max_qps=15)

@amap_manager.with_retry(max_retries=3, backoff_factor=0.5)
def geocode_address_safe(api_key, address, city=None):
    """
    安全的地理编码函数，带重试和QPS控制
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
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
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
            logger.warning(f"地理编码失败: {data.get('info')} for address: {address}")
            return None
    except requests.exceptions.Timeout:
        logger.error(f"地理编码请求超时: {address}")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"地理编码请求失败: {e}")
        raise
    except (ValueError, KeyError) as e:
        logger.error(f"地理编码响应解析错误: {e}")
        return None

@amap_manager.with_retry(max_retries=2, backoff_factor=0.3)
def get_driving_route_segment_details_safe(api_key, origin_lat, origin_lng, dest_lat, dest_lng, strategy=5):
    """
    安全的驾车路线查询函数
    """
    if not api_key:
        return None
    url = "https://restapi.amap.com/v3/direction/driving"
    params = {
        "key": api_key,
        "origin": f"{origin_lng},{origin_lat}",
        "destination": f"{dest_lng},{dest_lat}",
        "strategy": str(strategy),
        "extensions": "base",  # 使用base减少响应时间
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "1" and data.get("route") and data["route"].get("paths"):
            path = data["route"]["paths"][0]
            return {
                "distance": int(path.get("distance", 0)),
                "duration": int(path.get("duration", 0)),
                "polyline": path.get("polyline"),
                "steps": path.get("steps", [])
            }
        else:
            error_msg = data.get('info', '未知错误')
            logger.warning(f"路线规划失败: {error_msg}")
            return None
    except requests.exceptions.Timeout:
        logger.error("路线规划请求超时")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"路线规划请求失败: {e}")
        raise
    except (ValueError, KeyError, IndexError) as e:
        logger.error(f"路线规划响应解析错误: {e}")
        return None

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
def optimize_route_enhanced():
    """增强的路线优化接口"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'Request body must be JSON.'}), 400
        # 数据验证
        validation_error = validate_route_request(data)
        if validation_error:
            return jsonify({'message': validation_error}), 400
        home_location_data = data.get('home_location')
        shops_data = data.get('shops')
        mode = data.get('mode', 'driving')
        city_param = data.get('city')
        top_n = data.get('top_n', 10)
        api_key = app.config.get('AMAP_API_KEY')
        if not api_key:
            return jsonify({'message': 'Amap API key not configured on server.'}), 500
        # 检查店铺数量限制
        if len(shops_data) > MAX_SHOPS_FOR_PERMUTATIONS:
            return jsonify({
                'message': f'Too many shops for optimization. Please select {MAX_SHOPS_FOR_PERMUTATIONS} or fewer shops.'
            }), 400
        # 使用线程池处理API调用以提高性能
        with ThreadPoolExecutor(max_workers=3) as executor:
            result = process_route_optimization_threaded(
                executor, api_key, home_location_data, shops_data, mode, city_param, top_n
            )
        return result
    except Exception as e:
        logger.error(f"路线优化处理错误: {str(e)}")
        return jsonify({
            'message': 'Internal server error during route optimization.',
            'error': str(e) if app.debug else 'Contact support'
        }), 500

def validate_route_request(data):
    """验证路线请求数据"""
    home_location_data = data.get('home_location')
    shops_data = data.get('shops')
    if not home_location_data or 'latitude' not in home_location_data or 'longitude' not in home_location_data:
        return 'Missing or invalid "home_location". It must be an object with "latitude" and "longitude".'
    if not shops_data or not isinstance(shops_data, list) or len(shops_data) == 0:
        return 'Missing or invalid "shops". It must be a non-empty list of shop objects.'
    # 验证经纬度格式
    try:
        float(home_location_data['latitude'])
        float(home_location_data['longitude'])
    except (ValueError, TypeError):
        return 'Invalid latitude or longitude format in home_location.'
    # 验证店铺数据
    for i, shop in enumerate(shops_data):
        required_fields = ['id', 'name', 'latitude', 'longitude']
        for field in required_fields:
            if field not in shop:
                return f'Shop {i} missing required field: {field}'
        try:
            float(shop['latitude'])
            float(shop['longitude'])
        except (ValueError, TypeError):
            return f'Invalid latitude or longitude format in shop {i}'
        if 'stay_duration' in shop:
            try:
                duration = float(shop['stay_duration'])
                if duration < 0:
                    return f'stay_duration for shop {i} must be non-negative'
            except (ValueError, TypeError):
                return f'Invalid stay_duration format in shop {i}'
    return None

def process_route_optimization_threaded(executor, api_key, home_location_data, shops_data, mode, city_param, top_n):
    """使用线程池处理路线优化"""
    # 准备点数据
    home_point = {
        "id": "home",
        "name": "Home",
        "latitude": home_location_data['latitude'],
        "longitude": home_location_data['longitude'],
        "stay_duration": 0
    }
    all_points_objects = [home_point] + shops_data
    all_coords = [(p['latitude'], p['longitude']) for p in all_points_objects]
    num_points = len(all_coords)
    # 并发构建距离矩阵
    cost_matrix = [[None for _ in range(num_points)] for _ in range(num_points)]
    # 创建API调用任务
    tasks = []
    for i in range(num_points):
        for j in range(i + 1, num_points):
            p1_lat, p1_lon = all_coords[i]
            p2_lat, p2_lon = all_coords[j]
            if mode == "public_transit":
                task = executor.submit(
                    get_public_transit_segment_details,
                    api_key, p1_lat, p1_lon, p2_lat, p2_lon, city_param
                )
            else:
                task = executor.submit(
                    get_driving_route_segment_details_safe,
                    api_key, p1_lat, p1_lon, p2_lat, p2_lon
                )
            tasks.append((i, j, task))
    # 等待所有任务完成
    for i, j, task in tasks:
        try:
            segment_details = task.result(timeout=30)  # 30秒超时
            if segment_details is None:
                return jsonify({
                    'message': f'Failed to get {mode} route details between {all_points_objects[i]["name"]} and {all_points_objects[j]["name"]}.'
                }), 500
            cost_matrix[i][j] = segment_details
            cost_matrix[j][i] = segment_details
        except Exception as e:
            logger.error(f"API调用失败 {i}->{j}: {e}")
            return jsonify({
                'message': f'Route calculation failed between points {i} and {j}.'
            }), 500
    # 继续TSP计算...
    return complete_tsp_calculation(all_points_objects, cost_matrix, top_n)

def complete_tsp_calculation(all_points_objects, cost_matrix, top_n):
    """完成TSP计算并返回结果"""
    # TSP计算逻辑保持不变
    shop_indices = list(range(1, len(all_points_objects)))
    total_stay_duration_val = sum(all_points_objects[shop_idx].get('stay_duration', 0) for shop_idx in shop_indices)
    if not shop_indices:
        # 处理只有家的情况
        return jsonify({
            "route_candidates": [create_single_point_route(all_points_objects[0])],
            "message": "No shops to visit. Only home location provided."
        }), 200
    # 生成所有排列并计算
    all_route_results = []
    for p in itertools.permutations(shop_indices):
        current_path_indices = [0] + list(p) + [0]
        total_distance = 0
        total_time = 0
        valid_route = True
        route_segments = []
        for i in range(len(current_path_indices) - 1):
            u, v = current_path_indices[i], current_path_indices[i+1]
            if cost_matrix[u][v] is None:
                valid_route = False
                break
            segment_info = cost_matrix[u][v]
            total_distance += segment_info['distance']
            total_time += segment_info['duration']
            route_segments.append({
                "from_name": all_points_objects[u]["name"],
                "to_name": all_points_objects[v]["name"],
                "from_id": all_points_objects[u]["id"],
                "to_id": all_points_objects[v]["id"],
                "distance": segment_info['distance'],
                "duration": segment_info['duration'],
                "polyline": segment_info['polyline'],
                "steps": segment_info.get('steps', [])
            })
        if valid_route:
            optimized_order = [all_points_objects[i] for i in current_path_indices]
            overall_duration = total_time + total_stay_duration_val
            route_data = {
                'optimized_order': optimized_order,
                'total_distance': total_distance,
                'total_travel_time': total_time,
                'total_stay_time': total_stay_duration_val,
                'total_overall_duration': overall_duration,
                'route_segments': route_segments
            }
            all_route_results.append({
                'route_data': route_data,
                'distance_score': total_distance,
                'time_score': total_time,
                'permutation': p
            })
    if not all_route_results:
        return jsonify({'message': 'Could not find any valid routes.'}), 500
    # 生成候选路线
    route_candidates = generate_route_candidates(all_route_results, top_n)
    return jsonify({
        "route_candidates": route_candidates,
        "total_combinations_analyzed": len(all_route_results),
        "message": f"Successfully generated {len(route_candidates)} route candidates."
    }), 200

def generate_route_candidates(all_route_results, top_n):
    """生成候选路线列表"""
    route_candidates = []
    # 按时间排序，取前5个
    routes_by_time = sorted(all_route_results, key=lambda x: x['time_score'])[:5]
    for i, route_result in enumerate(routes_by_time):
        candidate = route_result['route_data'].copy()
        candidate['optimization_type'] = 'time'
        candidate['rank_in_category'] = i + 1
        candidate['time_rank'] = i + 1
        route_candidates.append(candidate)
    # 按距离排序，取前5个（去重）
    routes_by_distance = sorted(all_route_results, key=lambda x: x['distance_score'])[:5]
    existing_permutations = set(route_result['permutation'] for route_result in routes_by_time)
    for i, route_result in enumerate(routes_by_distance):
        if route_result['permutation'] not in existing_permutations:
            candidate = route_result['route_data'].copy()
            candidate['optimization_type'] = 'distance'
            candidate['rank_in_category'] = i + 1
            candidate['distance_rank'] = i + 1
            route_candidates.append(candidate)
            existing_permutations.add(route_result['permutation'])
    return route_candidates[:top_n]

def create_single_point_route(home_point):
    """创建单点路线（只有家）"""
    return {
        'optimized_order': [home_point],
        'total_distance': 0,
        'total_travel_time': 0,
        'total_stay_time': 0,
        'total_overall_duration': 0,
        'route_segments': [],
        'optimization_type': 'time'
    }

# --- New Endpoint for A-to-B Directions ---

def _generate_route_id(transit_path):
    """
    Generates a unique ID for a transit path based on its segments.
    This helps in deduplicating routes that might be returned by different strategies.
    """
    segment_details = []
    if transit_path.get("segments"):
        for segment in transit_path["segments"]:
            if segment.get("walking"):
                segment_details.append(f"walk_{segment['walking'].get('distance')}_{segment['walking'].get('duration')}")
            if segment.get("bus") and segment["bus"].get("lines"):
                for line in segment["bus"]["lines"]:
                    segment_details.append(f"bus_{line.get('name')}_{line.get('departure_stop', {}).get('name')}_{line.get('arrival_stop', {}).get('name')}")
            if segment.get("railway") and segment["railway"].get("name"):
                 segment_details.append(f"rail_{segment['railway'].get('name')}_{segment['railway'].get('departure_stop', {}).get('name')}_{segment['railway'].get('arrival_stop', {}).get('name')}")

    id_string = "".join(segment_details)
    return hashlib.md5(id_string.encode('utf-8')).hexdigest()


def get_public_transit_routes(api_key, origin_lat, origin_lng, dest_lat, dest_lng, city, top_n=5):
    """
    Gets multiple public transit route options from Amap, sorted by duration and distance.
    """
    strategies = [0, 2, 1, 3, 5] # 0:推荐, 2:最少换乘, 1:最少花费, 3:最少步行, 5:不乘地铁
    all_routes = {} # Use dict for deduplication

    for strategy in strategies:
        url = "https://restapi.amap.com/v3/direction/transit/integrated"
        params = {
            "key": api_key,
            "origin": f"{origin_lng},{origin_lat}",
            "destination": f"{dest_lng},{dest_lat}",
            "city": str(city),
            "strategy": str(strategy),
            "extensions": "all",
        }
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "1" and data.get("route") and data["route"].get("transits"):
                for transit_path in data["route"]["transits"]:
                    route_id = _generate_route_id(transit_path)
                    if route_id not in all_routes:
                        full_polyline = _parse_transit_polyline(transit_path)
                        detailed_steps = _parse_transit_details(transit_path.get("segments"))
                        
                        # 为路线摘要创建一个简洁的描述
                        summary = "Unknown Route"
                        if detailed_steps:
                            # 尝试从第一段有效指令开始构建摘要
                            first_step = detailed_steps[0].get('instruction', '...')
                            # 尝试找到关键的公交或地铁线路名
                            main_transit_names = []
                            for segment in transit_path.get("segments", []):
                                if segment.get("bus") and segment["bus"].get("lines"):
                                    main_transit_names.extend([l.get('name', '') for l in segment["bus"]["lines"]])
                                if segment.get("railway") and segment["railway"].get("name"):
                                    main_transit_names.append(segment["railway"]["name"])
                            
                            if main_transit_names:
                                summary = " -> ".join(filter(None, main_transit_names))
                            else:
                                summary = first_step # Fallback to first instruction

                        all_routes[route_id] = {
                            "id": route_id,
                            "summary": summary, # 添加路线摘要
                            "distance": int(transit_path.get("distance", 0)),
                            "duration": int(transit_path.get("duration", 0)),
                            "cost": float(transit_path.get("cost", 0)),
                            "walking_distance": int(transit_path.get("walking_distance", 0)),
                            "polyline": full_polyline,
                            "steps": detailed_steps,
                            "segments": transit_path.get("segments") # Keep original segments for detailed view
                        }
        except requests.exceptions.RequestException as e:
            print(f"Amap Public Transit request failed for strategy {strategy}: {e}")
            continue # Try next strategy
        except (ValueError, KeyError, IndexError) as e:
            print(f"Error parsing Amap Public Transit response for strategy {strategy}: {e}")
            continue
        time.sleep(0.05) # Rate limiting

    if not all_routes:
        return None

    # Sort routes: primary key duration, secondary key distance
    sorted_routes = sorted(all_routes.values(), key=lambda x: (x['duration'], x['distance']))
    
    return sorted_routes[:top_n]

@app.route('/api/route/directions', methods=['POST'])
def get_directions():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Request body must be JSON.'}), 400
    
    origin = data.get('origin')
    destination = data.get('destination')
    mode = data.get('mode', 'public_transit') # 默认公共交通
    city = data.get('city')

    if not origin or 'latitude' not in origin or 'longitude' not in origin:
        return jsonify({'message': 'Missing or invalid "origin". It must be an object with "latitude" and "longitude".'}), 400

    if not destination or 'latitude' not in destination or 'longitude' not in destination:
        return jsonify({'message': 'Missing or invalid "destination". It must be an object with "latitude" and "longitude".'}), 400

    api_key = app.config.get('AMAP_API_KEY')
    if not api_key:
        return jsonify({'message': 'Amap API key not configured on server.'}), 500

    if mode == "public_transit":
        if not city:
            return jsonify({'message': 'Missing "city" parameter, required for public transit mode.'}), 400
        
        routes = get_public_transit_routes(
            api_key, 
            origin['latitude'], origin['longitude'],
            destination['latitude'], destination['longitude'],
            city
        )

        if routes is None or not routes:
            return jsonify({'message': 'Could not find public transit routes.'}), 404
        
        # 返回摘要列表
        route_summaries = [{
            "id": r["id"],
            "summary": r["summary"],
            "duration": r["duration"],
            "distance": r["distance"],
            "cost": r["cost"],
            "walking_distance": r["walking_distance"],
        } for r in routes]

        # 将详细路线信息暂存，以便后续根据ID获取
        # 在实际生产环境中，你可能会使用缓存（如Redis）来存储这些信息
        # 这里为了简化，我们将其存储在全局变量中（注意：这在多线程/多进程环境下不是最佳实践）
        if 'detailed_routes_cache' not in app.config:
            app.config['detailed_routes_cache'] = {}
        
        for r in routes:
            app.config['detailed_routes_cache'][r['id']] = r

        return jsonify(route_summaries)
    
    elif mode == "driving":
        route_details = get_driving_route_segment_details(
            api_key,
            origin['latitude'], origin['longitude'],
            destination['latitude'], destination['longitude']
        )
        if route_details is None:
            return jsonify({'message': 'Could not find driving routes.'}), 404
        # 为了与前端期望的格式统一，包装一下
        route_summary = {
            "id": "driving_route_01", #
            "summary": "推荐驾车路线",
            "duration": route_details.get("duration"),
            "distance": route_details.get("distance"),
        }
        
        if 'detailed_routes_cache' not in app.config:
            app.config['detailed_routes_cache'] = {}
        app.config['detailed_routes_cache'][route_summary['id']] = route_details

        return jsonify([route_summary]) # Return as a list
    
    else:
        return jsonify({'message': f'Unsupported mode: {mode}'}), 400

@app.route('/api/route/directions/<route_id>', methods=['GET'])
def get_direction_details(route_id):
    """
    根据路线ID获取详细的路线信息.
    """
    # 在实际应用中，这里应该从缓存或数据库中获取
    detailed_route = app.config.get('detailed_routes_cache', {}).get(route_id)

    if not detailed_route:
        return jsonify({'message': 'Route details not found or expired.'}), 404
    
    return jsonify(detailed_route)


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
