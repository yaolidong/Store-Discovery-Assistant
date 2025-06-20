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
import json # Added for distance cache
from datetime import datetime, timedelta # Added for cache expiry
import random # Added for genetic algorithm
import numpy as np # Added for advanced algorithms
try:
    from ortools.constraint_solver import pywrapcp
    from ortools.constraint_solver import routing_enums_pb2
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False
    print("Or-Tools not available, using fallback algorithms")

# 常量定义
MAX_SHOPS_FOR_OPTIMIZATION = 10  # 最大优化店铺数量
MAX_CHAIN_BRANCHES_PER_BRAND = 5  # 每个品牌最大搜索分店数量，降低算法复杂度

# Initialize Flask app
app = Flask(__name__)
CORS(app, supports_credentials=True, resources={
    r"/api/*": {
        "origins": [
            "http://localhost:8080", "http://127.0.0.1:8080",
            "http://localhost:3000", "http://127.0.0.1:3000",
            "http://localhost:3001", "http://127.0.0.1:3001", 
            "http://localhost:3002", "http://127.0.0.1:3002",
            "http://localhost:3003", "http://127.0.0.1:3003"
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
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

@login_manager.unauthorized_handler
def unauthorized_handler():
    """自定义未授权处理，API请求返回JSON，非API请求可以重定向（如果需要）"""
    # 检查请求路径是否以/api/开头
    if request.path.startswith('/api/'):
        return jsonify({'message': 'Authorization required. Please log in.'}), 401
    # 对于非API请求，可以保留重定向到登录页的行为
    # 这里我们假设所有需要登录的都是API，所以直接返回401
    return jsonify({'message': 'Authorization required.'}), 401

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def amap_api_handler(api_name="Unknown API"):
    """通用的高德API错误处理装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except requests.exceptions.Timeout:
                logger.error(f"{api_name}请求超时")
                return None
            except requests.exceptions.RequestException as e:
                logger.error(f"{api_name}请求失败: {e}")
                return None
            except (ValueError, KeyError, IndexError) as e:
                logger.error(f"{api_name}响应解析错误: {e}")
                return None
            except Exception as e:
                logger.error(f"{api_name}未知错误: {e}")
                return None
        return wrapper
    return decorator

class AmapAPIManager:
    """高德API管理器，处理QPS限制和重试逻辑"""
    
    def __init__(self, api_key, max_qps=20):
        self.api_key = api_key
        self.max_qps = max_qps
        self.request_times = []
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.session = requests.Session()  # 创建持久连接会话
    
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
    
    def apply_rate_limit(self):
        """应用速率限制 - 统一的延迟管理"""
        self._check_qps_limit()
        self._record_request()
        time.sleep(0.15)  # 增加基础延迟，防止QPS超限
    
    def with_retry(self, max_retries=5, backoff_factor=1.5):
        """重试装饰器 - 增强版本，特别处理QPS和SSL错误"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                last_exception = None
                for attempt in range(max_retries):
                    try:
                        self.apply_rate_limit()
                        result = func(*args, **kwargs)
                        return result
                    except requests.exceptions.SSLError as e:
                        last_exception = e
                        if attempt < max_retries - 1:
                            wait_time = backoff_factor * (2 ** attempt) + 1  # SSL错误额外等待
                            logger.warning(f"SSL连接失败，{wait_time}秒后重试: {e}")
                            time.sleep(wait_time)
                        else:
                            logger.error(f"SSL连接最终失败: {e}")
                    except requests.exceptions.HTTPError as e:
                        last_exception = e
                        # 检查是否是QPS限制错误
                        if hasattr(e, 'response') and e.response is not None:
                            try:
                                error_text = e.response.text
                                if 'CUQPS_HAS_EXCEEDED_THE_LIMIT' in error_text:
                                    if attempt < max_retries - 1:
                                        wait_time = backoff_factor * (3 ** attempt) + 2  # QPS错误更长等待
                                        logger.warning(f"QPS限制错误，{wait_time}秒后重试")
                                        time.sleep(wait_time)
                                        continue
                            except:
                                pass
                        if attempt < max_retries - 1:
                            wait_time = backoff_factor * (2 ** attempt)
                            logger.warning(f"HTTP错误，{wait_time}秒后重试: {e}")
                            time.sleep(wait_time)
                        else:
                            logger.error(f"HTTP错误最终失败: {e}")
                    except requests.exceptions.RequestException as e:
                        last_exception = e
                        if attempt < max_retries - 1:
                            wait_time = backoff_factor * (2 ** attempt)
                            logger.warning(f"网络请求失败，{wait_time}秒后重试: {e}")
                            time.sleep(wait_time)
                        else:
                            logger.error(f"网络请求最终失败: {e}")
                    except Exception as e:
                        logger.error(f"非网络错误: {e}")
                        raise e
                raise last_exception
            return wrapper
        return decorator
    
    def safe_request(self, url, params=None, timeout=30):
        """统一的安全API请求方法"""
        try:
            response = self.session.get(
                url, 
                params=params, 
                timeout=(10, timeout),  # (连接超时, 读取超时)
                verify=True
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {url}, 错误: {e}")
            raise

class DistanceCache:
    """距离缓存管理器，用于缓存API调用结果以提高性能，支持持久化存储"""
    
    def __init__(self, cache_duration_hours=24, persistent_cache=False, cache_file_path=None):
        self.cache = {}  # 内存缓存
        self.cache_duration = timedelta(hours=cache_duration_hours)
        self.hit_count = 0
        self.miss_count = 0
        self.persistent_cache = persistent_cache
        self.cache_file_path = cache_file_path or 'distance_cache.json'
        
        # 如果启用持久化缓存，尝试加载现有缓存
        if self.persistent_cache:
            self._load_cache_from_file()
        
    def _load_cache_from_file(self):
        """从文件加载缓存数据"""
        try:
            if os.path.exists(self.cache_file_path):
                with open(self.cache_file_path, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
                    
                # 转换时间戳字符串回datetime对象
                for key, value in file_data.items():
                    if 'timestamp' in value:
                        value['timestamp'] = datetime.fromisoformat(value['timestamp'])
                
                self.cache = file_data
                logger.info(f"从文件加载了 {len(self.cache)} 个缓存条目")
        except Exception as e:
            logger.warning(f"加载缓存文件失败: {e}")
            self.cache = {}
    
    def _save_cache_to_file(self):
        """将缓存数据保存到文件"""
        if not self.persistent_cache:
            return
            
        try:
            # 创建文件副本用于序列化
            serializable_cache = {}
            for key, value in self.cache.items():
                serializable_value = value.copy()
                if 'timestamp' in serializable_value:
                    serializable_value['timestamp'] = serializable_value['timestamp'].isoformat()
                serializable_cache[key] = serializable_value
            
            # 使用临时文件确保原子性写入
            temp_file = self.cache_file_path + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(serializable_cache, f, ensure_ascii=False, indent=2)
            
            # 原子性替换
            os.replace(temp_file, self.cache_file_path)
            logger.debug(f"缓存已保存到文件: {len(self.cache)} 个条目")
        except Exception as e:
            logger.error(f"保存缓存文件失败: {e}")
        
    def _generate_cache_key(self, lat1, lng1, lat2, lng2, mode='driving', city=None):
        """生成缓存键，考虑地理位置的对称性"""
        # 确保坐标顺序一致（小坐标在前）
        if (lat1, lng1) > (lat2, lng2):
            lat1, lng1, lat2, lng2 = lat2, lng2, lat1, lng1
            
        # 创建缓存键，使用更精确的坐标精度
        key_data = {
            'coords': f"{lat1:.8f},{lng1:.8f}-{lat2:.8f},{lng2:.8f}",
            'mode': mode,
            'city': city
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode('utf-8')).hexdigest()
    
    def get(self, lat1, lng1, lat2, lng2, mode='driving', city=None):
        """从缓存获取距离信息"""
        cache_key = self._generate_cache_key(lat1, lng1, lat2, lng2, mode, city)
        
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            # 检查缓存是否过期
            if datetime.now() - cached_data['timestamp'] < self.cache_duration:
                self.hit_count += 1
                logger.debug(f"缓存命中: {cache_key[:8]}...")
                return cached_data['data']
            else:
                # 缓存过期，删除
                del self.cache[cache_key]
                
        self.miss_count += 1
        return None
    
    def set(self, lat1, lng1, lat2, lng2, data, mode='driving', city=None):
        """将距离信息存入缓存"""
        cache_key = self._generate_cache_key(lat1, lng1, lat2, lng2, mode, city)
        self.cache[cache_key] = {
            'data': data,
            'timestamp': datetime.now()
        }
        logger.debug(f"缓存存储: {cache_key[:8]}...")
        
        # 定期保存到文件（每10次写入保存一次）
        if self.persistent_cache and len(self.cache) % 10 == 0:
            self._save_cache_to_file()
    
    def get_cache_stats(self):
        """获取缓存统计信息"""
        total_requests = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total_requests * 100) if total_requests > 0 else 0
        
        # 计算缓存大小
        cache_size_bytes = 0
        try:
            cache_size_bytes = len(json.dumps(self.cache, default=str).encode('utf-8'))
        except:
            pass
        
        return {
            'total_entries': len(self.cache),
            'hit_count': self.hit_count,
            'miss_count': self.miss_count,
            'hit_rate': f"{hit_rate:.1f}%",
            'cache_size_mb': f"{cache_size_bytes / 1024 / 1024:.2f}",
            'persistent_cache_enabled': self.persistent_cache,
            'cache_file_path': self.cache_file_path if self.persistent_cache else None
        }
    
    def clear_expired(self):
        """清理过期的缓存条目"""
        now = datetime.now()
        expired_keys = []
        for key, value in self.cache.items():
            if now - value['timestamp'] >= self.cache_duration:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.info(f"清理了 {len(expired_keys)} 个过期缓存条目")
            # 保存到文件
            if self.persistent_cache:
                self._save_cache_to_file()
        
        return len(expired_keys)
    
    def optimize_cache(self):
        """优化缓存：清理过期条目，压缩存储"""
        expired_count = self.clear_expired()
        
        # 如果缓存过大，删除最旧的条目
        max_entries = 10000  # 最大缓存条目数
        entries_to_remove = 0
        if len(self.cache) > max_entries:
            # 按时间戳排序，删除最旧的条目
            sorted_entries = sorted(self.cache.items(), key=lambda x: x[1]['timestamp'])
            entries_to_remove = len(self.cache) - max_entries
            
            for i in range(entries_to_remove):
                del self.cache[sorted_entries[i][0]]
            
            logger.info(f"缓存优化: 删除了 {entries_to_remove} 个最旧的条目")
        
        # 保存到文件
        if self.persistent_cache:
            self._save_cache_to_file()
        
        return {
            'expired_removed': expired_count,
            'old_entries_removed': entries_to_remove,
            'current_size': len(self.cache)
        }
        
    def __del__(self):
        """析构函数，确保缓存在对象销毁时保存"""
        if self.persistent_cache and hasattr(self, 'cache'):
            self._save_cache_to_file()

# 初始化全局缓存管理器
distance_cache = DistanceCache(cache_duration_hours=24, persistent_cache=True, cache_file_path="./instance/distance_cache.json")
amap_manager = AmapAPIManager(app.config.get('AMAP_API_KEY', ''), max_qps=8)  # 降低QPS限制

class TSPWithCategoriesOptimizer:
    """
    TSP with Categories 优化器
    解决从每个类别（连锁店品牌）中选择恰好一个节点以最小化总行程长度的问题
    """
    
    def __init__(self, home_location, chain_categories, private_shops=None, api_key=None, city=None):
        """
        初始化优化器
        
        Args:
            home_location: 用户家的位置 {'latitude': float, 'longitude': float}
            chain_categories: 连锁店类别字典 {'brand_name': [shop1, shop2, ...]}
            private_shops: 私人店铺列表（可选）
            api_key: 高德API密钥
            city: 城市名称
        """
        self.home_location = home_location
        self.chain_categories = chain_categories
        self.private_shops = private_shops or []
        self.api_key = api_key
        self.city = city
        
        # 创建所有点的索引映射
        self.all_points = []
        self.point_to_category = {}  # 点索引 -> 类别名称的映射
        self.category_points = {}    # 类别名称 -> 点索引列表的映射
        
        self._build_point_mappings()
        
    def _build_point_mappings(self):
        """构建点的索引映射"""
        # 添加家的位置（索引0）
        self.all_points.append({
            'id': 'home',
            'name': 'Home',
            'latitude': self.home_location['latitude'],
            'longitude': self.home_location['longitude'],
            'type': 'home'
        })
        
        # 添加私人店铺
        for shop in self.private_shops:
            self.all_points.append(shop)
            
        # 添加连锁店分店
        for brand_name, shops in self.chain_categories.items():
            category_indices = []
            for shop in shops:
                shop_with_brand = shop.copy()
                shop_with_brand['brand'] = brand_name
                shop_with_brand['type'] = 'chain'
                
                point_index = len(self.all_points)
                self.all_points.append(shop_with_brand)
                self.point_to_category[point_index] = brand_name
                category_indices.append(point_index)
                
            self.category_points[brand_name] = category_indices
            
    async def optimize(self, travel_mode='driving', max_time_seconds=30):
        """
        执行TSP with Categories优化
        
        Args:
            travel_mode: 出行方式 ('driving' 或 'public_transit')
            max_time_seconds: 最大计算时间
            
        Returns:
            dict: 包含最优路线的结果
        """
        try:
            logger.info(f"开始TSP with Categories优化: {len(self.chain_categories)}个品牌, {len(self.all_points)}个总点数")
            
            # 构建距离矩阵
            cost_matrix = await self._build_cost_matrix(travel_mode)
            
            # 执行优化算法
            if len(self.chain_categories) <= 3 and all(len(shops) <= 5 for shops in self.chain_categories.values()):
                # 小规模问题：使用精确算法
                logger.info(f"使用精确算法: {len(self.chain_categories)} 个品牌")
                result = await self._exact_optimization(cost_matrix)
            else:
                # 大规模问题：使用启发式算法
                logger.info(f"使用启发式算法: {len(self.chain_categories)} 个品牌")
                result = await self._heuristic_optimization(cost_matrix, max_time_seconds)
                
            if result is None:
                logger.warning("优化算法返回None，使用后备结果")
                return self._create_fallback_result()
                
            return self._format_result(result, cost_matrix)
            
        except Exception as e:
            logger.error(f"TSP with Categories优化失败: {str(e)}", exc_info=True)
            return self._create_fallback_result()
            
    async def _build_cost_matrix(self, travel_mode):
        """构建距离矩阵"""
        n_points = len(self.all_points)
        cost_matrix = [[None for _ in range(n_points)] for _ in range(n_points)]
        
        # 并行构建距离矩阵
        tasks = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            for i in range(n_points):
                for j in range(i + 1, n_points):
                    p1 = self.all_points[i]
                    p2 = self.all_points[j]
                    
                    # 检查缓存
                    cache_key = travel_mode if travel_mode != 'public_transit' else f'public_transit_{self.city}'
                    cached_result = distance_cache.get(
                        p1['latitude'], p1['longitude'], 
                        p2['latitude'], p2['longitude'], 
                        cache_key, self.city
                    )
                    
                    if cached_result:
                        cost_matrix[i][j] = cached_result
                        cost_matrix[j][i] = cached_result
                    else:
                        # 需要API调用
                        if travel_mode == 'public_transit':
                            task = executor.submit(
                                get_public_transit_segment_details,
                                self.api_key, p1['latitude'], p1['longitude'],
                                p2['latitude'], p2['longitude'], self.city
                            )
                        else:
                            task = executor.submit(
                                get_driving_route_segment_details,
                                self.api_key, p1['latitude'], p1['longitude'],
                                p2['latitude'], p2['longitude']
                            )
                        tasks.append((i, j, task))
            
            # 等待所有API调用完成
            for i, j, task in tasks:
                try:
                    result = task.result(timeout=30)
                    if result:
                        cost_matrix[i][j] = result
                        cost_matrix[j][i] = result
                        
                        # 缓存结果
                        cache_key = travel_mode if travel_mode != 'public_transit' else f'public_transit_{self.city}'
                        distance_cache.set(
                            self.all_points[i]['latitude'], self.all_points[i]['longitude'],
                            self.all_points[j]['latitude'], self.all_points[j]['longitude'],
                            result, cache_key, self.city
                        )
                    else:
                        # 使用直线距离作为备选
                        distance = calculate_haversine_distance(
                            self.all_points[i]['latitude'], self.all_points[i]['longitude'],
                            self.all_points[j]['latitude'], self.all_points[j]['longitude']
                        )
                        fallback_result = {
                            'distance': int(distance),
                            'duration': max(300, int((distance/1000)/(40/3.6))),  # 最少5分钟
                            'polyline': '',
                            'steps': []
                        }
                        cost_matrix[i][j] = fallback_result
                        cost_matrix[j][i] = fallback_result
                        
                except Exception as e:
                    logger.warning(f"获取路线信息失败 ({i},{j}): {str(e)}")
                    # 使用直线距离作为备选
                    distance = calculate_haversine_distance(
                        self.all_points[i]['latitude'], self.all_points[i]['longitude'],
                        self.all_points[j]['latitude'], self.all_points[j]['longitude']
                    )
                    fallback_result = {
                        'distance': int(distance),
                        'duration': max(300, int((distance/1000)/(40/3.6))),
                        'polyline': '',
                        'steps': []
                    }
                    cost_matrix[i][j] = fallback_result
                    cost_matrix[j][i] = fallback_result
                    
        return cost_matrix
        
    async def _exact_optimization(self, cost_matrix):
        """精确优化算法（适用于小规模问题）- 改进版本，生成更多候选路线"""
        logger.info("使用精确算法进行TSP with Categories优化")
        
        # 生成所有有效的类别组合
        category_combinations = self._generate_category_combinations()
        
        all_candidates = []
        
        for combination in category_combinations:
            # 添加家和私人店铺
            route_points = [0]  # 从家开始
            route_points.extend(range(1, len(self.private_shops) + 1))  # 私人店铺
            route_points.extend(combination)  # 选择的连锁店分店
            
            # 对这个组合进行TSP优化
            optimizer = TSPOptimizer(cost_matrix, [self.all_points[i] for i in route_points], route_points)
            optimized_routes, optimized_costs = optimizer.hybrid_optimize()
            
            # 调试日志
            logger.debug(f"组合 {combination}: route_points={route_points}, points数量={len(route_points)}")
            
            if optimized_routes:
                # 处理时间最优的路线
                if 'time' in optimized_routes and optimized_routes['time']:
                    time_costs = optimized_costs.get('time', []) if optimized_costs else []
                    for i, route in enumerate(optimized_routes['time']):
                        if route:
                            # TSPOptimizer返回的索引是内部索引，需要映射回全局索引
                            try:
                                # TSPOptimizer返回的路线索引对应传入的points顺序
                                # route中的每个索引j对应route_points[j]
                                if all(0 <= j < len(route_points) for j in route):
                                    # 直接将内部索引映射回全局索引
                                    mapped_route = [route_points[j] for j in route]
                                    
                                    # 安全获取成本
                                    if i < len(time_costs):
                                        time_cost = time_costs[i]
                                    else:
                                        time_cost = self._calculate_route_time(mapped_route, cost_matrix)
                                    
                                    all_candidates.append({
                                        'route_indices': mapped_route,
                                        'selected_shops': combination,
                                        'total_time_cost': time_cost,
                                        'total_distance_cost': self._calculate_route_distance(mapped_route, cost_matrix),
                                        'optimization_type': 'time',
                                        'combination_id': tuple(sorted(combination))
                                    })
                                else:
                                    # 处理异常路线：可能存在超出范围的索引
                                    logger.warning(f"跳过异常时间路线: route={route}, route_points={route_points}")
                                    continue
                            except (IndexError, ValueError) as e:
                                logger.error(f"处理时间路线异常: {e}, route={route}")
                                continue
                
                # 处理距离最优的路线
                if 'distance' in optimized_routes and optimized_routes['distance']:
                    distance_costs = optimized_costs.get('distance', []) if optimized_costs else []
                    for i, route in enumerate(optimized_routes['distance']):
                        if route:
                            # TSPOptimizer返回的索引是内部索引，需要映射回全局索引
                            try:
                                # TSPOptimizer返回的路线索引对应传入的points顺序
                                # route中的每个索引j对应route_points[j]
                                if all(0 <= j < len(route_points) for j in route):
                                    # 直接将内部索引映射回全局索引
                                    mapped_route = [route_points[j] for j in route]
                                    
                                    # 安全获取成本
                                    if i < len(distance_costs):
                                        distance_cost = distance_costs[i]
                                    else:
                                        distance_cost = self._calculate_route_distance(mapped_route, cost_matrix)
                                    
                                    all_candidates.append({
                                        'route_indices': mapped_route,
                                        'selected_shops': combination,
                                        'total_time_cost': self._calculate_route_time(mapped_route, cost_matrix),
                                        'total_distance_cost': distance_cost,
                                        'optimization_type': 'distance',
                                        'combination_id': tuple(sorted(combination))
                                    })
                                else:
                                    # 处理异常路线：可能存在超出范围的索引
                                    logger.warning(f"跳过异常距离路线: route={route}, route_points={route_points}")
                                    continue
                            except (IndexError, ValueError) as e:
                                logger.error(f"处理距离路线异常: {e}, route={route}")
                                continue
        
        # 去重并按时间和距离分别排序
        return self._select_top_candidates(all_candidates)
        
    async def _heuristic_optimization(self, cost_matrix, max_time_seconds):
        """启发式优化算法（适用于大规模问题）- 改进版本，生成更多候选路线"""
        logger.info("使用启发式算法进行TSP with Categories优化")
        
        start_time = time.time()
        all_candidates = []
        
        # 策略1: 基于距离的贪心选择 - 生成多个候选
        candidates_from_distance = self._distance_based_selection(cost_matrix, max_time_seconds * 0.3)
        all_candidates.extend(candidates_from_distance)
        
        # 策略2: 随机重启优化 - 生成更多候选
        remaining_time = max_time_seconds - (time.time() - start_time)
        if remaining_time > 0:
            candidates_from_random = self._enhanced_random_restart_optimization(cost_matrix, remaining_time * 0.5)
            all_candidates.extend(candidates_from_random)
        
        # 策略3: 最近邻启发式的多种变体
        remaining_time = max_time_seconds - (time.time() - start_time)
        if remaining_time > 0:
            candidates_from_nearest = self._multi_nearest_neighbor_optimization(cost_matrix, remaining_time)
            all_candidates.extend(candidates_from_nearest)
        
        return self._select_top_candidates(all_candidates)
    
    def _distance_based_selection(self, cost_matrix, time_limit):
        """基于距离的贪心选择策略 - 生成多个候选"""
        candidates = []
        
        # 为每个连锁店品牌按照距离家的远近排序
        brand_distance_rankings = {}
        home_idx = 0
        
        for brand_name, point_indices in self.category_points.items():
            distances = []
            for point_idx in point_indices:
                if cost_matrix[home_idx][point_idx]:
                    distance = cost_matrix[home_idx][point_idx]['distance']
                    distances.append((distance, point_idx))
            
            distances.sort(key=lambda x: x[0])  # 按距离排序
            brand_distance_rankings[brand_name] = distances
        
        # 生成不同的分店组合：最近、次近、混合等
        combinations_to_try = []
        
        if len(self.category_points) == 2:
            # 两个品牌的情况：生成更多组合
            brands = list(self.category_points.keys())
            brand1_shops = brand_distance_rankings[brands[0]]
            brand2_shops = brand_distance_rankings[brands[1]]
            
            # 各种组合策略
            for i in range(min(3, len(brand1_shops))):
                for j in range(min(3, len(brand2_shops))):
                    combination = [brand1_shops[i][1], brand2_shops[j][1]]
                    combinations_to_try.append(combination)
        else:
            # 多品牌的组合策略 
            import itertools
            brand_choices = []
            for brand_name in self.category_points.keys():
                # 每个品牌选择前3个最近的店铺
                top_shops = brand_distance_rankings[brand_name][:3]
                brand_choices.append([shop[1] for shop in top_shops])
            
            # 生成笛卡尔积的前20个组合
            for combination in itertools.product(*brand_choices):
                combinations_to_try.append(list(combination))
                if len(combinations_to_try) >= 20:
                    break
        
        # 对每个组合进行TSP优化
        for combination in combinations_to_try:
            route_points = [0] + list(range(1, len(self.private_shops) + 1)) + combination
            optimizer = TSPOptimizer(cost_matrix, [self.all_points[i] for i in route_points], route_points)
            
            # 使用快速启发式算法
            result = optimizer.nearest_neighbor_heuristic()
            if result:
                improved_route, improved_cost = optimizer.two_opt_improve(result, 'duration')
                time_cost = improved_cost
                distance_cost = self._calculate_route_distance(improved_route, cost_matrix)
                
                candidates.append({
                    'route_indices': improved_route,
                    'selected_shops': combination,
                    'total_time_cost': time_cost,
                    'total_distance_cost': distance_cost,
                    'combination_id': tuple(sorted(combination)),
                    'strategy': 'distance_based'
                })
        
        return candidates
    
    def _enhanced_random_restart_optimization(self, cost_matrix, time_limit):
        """增强的随机重启优化策略"""
        candidates = []
        start_time = time.time()
        restart_count = 0
        max_restarts = min(50, int(time_limit * 3))
        
        while restart_count < max_restarts and (time.time() - start_time) < time_limit:
            # 随机选择每个类别中的店铺
            combination = []
            for brand_name, point_indices in self.category_points.items():
                if point_indices:
                    combination.append(random.choice(point_indices))
            
            if combination:
                route_points = [0] + list(range(1, len(self.private_shops) + 1)) + combination
                optimizer = TSPOptimizer(cost_matrix, [self.all_points[i] for i in route_points], route_points)
                
                # 轮换使用不同的优化方法
                if restart_count % 3 == 0:
                    result = optimizer.nearest_neighbor_heuristic()
                    if result:
                        improved_route, improved_cost = optimizer.two_opt_improve(result, 'duration')
                elif restart_count % 3 == 1:
                    result = optimizer.nearest_neighbor_heuristic()
                    if result:
                        improved_route, improved_cost = optimizer.two_opt_improve(result, 'distance')
                else:
                    # 使用遗传算法的快速版本
                    if len(route_points) <= 10:
                        genetic_result, _ = optimizer.genetic_algorithm_solve(population_size=15, generations=20)
                        if genetic_result and 'time' in genetic_result and genetic_result['time']:
                            improved_route = genetic_result['time']
                            improved_cost = optimizer.calculate_route_cost(improved_route, 'duration')
                        else:
                            continue
                    else:
                        continue
                
                if 'improved_route' in locals() and improved_route:
                    time_cost = improved_cost if restart_count % 3 == 0 else optimizer.calculate_route_cost(improved_route, 'duration')
                    distance_cost = optimizer.calculate_route_cost(improved_route, 'distance')
                    
                    candidates.append({
                        'route_indices': improved_route,
                        'selected_shops': combination,
                        'total_time_cost': time_cost,
                        'total_distance_cost': distance_cost,
                        'combination_id': tuple(sorted(combination)),
                        'strategy': 'random_restart'
                    })
            
            restart_count += 1
        
        logger.info(f"随机重启优化完成: {restart_count}次重启，生成{len(candidates)}个候选")
        return candidates
    
    def _multi_nearest_neighbor_optimization(self, cost_matrix, time_limit):
        """多起点最近邻优化策略"""
        candidates = []
        start_time = time.time()
        
        # 尝试不同的起始策略
        strategies = [
            'closest_to_home',      # 选择离家最近的店铺
            'farthest_from_home',   # 选择离家最远的店铺  
            'balanced_distance',    # 平衡距离选择
            'random_selection'      # 随机选择
        ]
        
        for strategy in strategies:
            if (time.time() - start_time) > time_limit:
                break
                
            # 根据策略选择每个品牌的店铺
            combinations = self._generate_combinations_by_strategy(strategy, cost_matrix)
            
            for combination in combinations[:5]:  # 每种策略最多5个组合
                route_points = [0] + list(range(1, len(self.private_shops) + 1)) + combination
                optimizer = TSPOptimizer(cost_matrix, [self.all_points[i] for i in route_points], route_points)
                
                # 多起点最近邻
                best_route = None
                best_cost = float('inf')
                
                for start_point in [0] + combination[:3]:  # 尝试不同起点
                    result = optimizer.nearest_neighbor_heuristic(start_point)
                    if result:
                        # 调整路线确保从家开始
                        if result[0] != 0:
                            home_idx = result.index(0)
                            adjusted_route = result[home_idx:] + result[1:home_idx] + [0]
                        else:
                            adjusted_route = result
                        
                        improved_route, improved_cost = optimizer.two_opt_improve(adjusted_route, 'duration')
                        if improved_cost < best_cost:
                            best_cost = improved_cost
                            best_route = improved_route
                
                if best_route:
                    distance_cost = optimizer.calculate_route_cost(best_route, 'distance')
                    candidates.append({
                        'route_indices': best_route,
                        'selected_shops': combination,
                        'total_time_cost': best_cost,
                        'total_distance_cost': distance_cost,
                        'combination_id': tuple(sorted(combination)),
                        'strategy': f'multi_nearest_{strategy}'
                    })
        
        return candidates
    
    def _generate_combinations_by_strategy(self, strategy, cost_matrix):
        """根据策略生成分店组合"""
        combinations = []
        home_idx = 0
        
        if strategy == 'closest_to_home':
            # 每个品牌选择离家最近的店铺
            combination = []
            for brand_name, point_indices in self.category_points.items():
                best_distance = float('inf')
                best_shop = None
                for point_idx in point_indices:
                    if cost_matrix[home_idx][point_idx]:
                        distance = cost_matrix[home_idx][point_idx]['distance']
                        if distance < best_distance:
                            best_distance = distance
                            best_shop = point_idx
                if best_shop is not None:
                    combination.append(best_shop)
            if combination:
                combinations.append(combination)
                
        elif strategy == 'farthest_from_home':
            # 每个品牌选择离家最远的店铺
            combination = []
            for brand_name, point_indices in self.category_points.items():
                best_distance = 0
                best_shop = None
                for point_idx in point_indices:
                    if cost_matrix[home_idx][point_idx]:
                        distance = cost_matrix[home_idx][point_idx]['distance']
                        if distance > best_distance:
                            best_distance = distance
                            best_shop = point_idx
                if best_shop is not None:
                    combination.append(best_shop)
            if combination:
                combinations.append(combination)
                
        elif strategy == 'balanced_distance':
            # 尝试平衡的距离组合
            for brand_name, point_indices in self.category_points.items():
                # 按距离排序，选择中等距离的店铺
                distances = []
                for point_idx in point_indices:
                    if cost_matrix[home_idx][point_idx]:
                        distance = cost_matrix[home_idx][point_idx]['distance']
                        distances.append((distance, point_idx))
                
                distances.sort(key=lambda x: x[0])
                # 选择中位数位置的店铺
                if distances:
                    mid_idx = len(distances) // 2
                    combinations.append([distances[mid_idx][1]])
                    
        elif strategy == 'random_selection':
            # 随机选择策略，生成多个组合
            for _ in range(3):
                combination = []
                for brand_name, point_indices in self.category_points.items():
                    if point_indices:
                        combination.append(random.choice(point_indices))
                if combination:
                    combinations.append(combination)
        
        return combinations
    
    def _calculate_route_time(self, route_indices, cost_matrix):
        """计算路线的总时间"""
        total_time = 0
        for i in range(len(route_indices) - 1):
            u, v = route_indices[i], route_indices[i + 1]
            if cost_matrix[u][v]:
                total_time += cost_matrix[u][v]['duration']
        return total_time
    
    def _calculate_route_distance(self, route_indices, cost_matrix):
        """计算路线的总距离"""
        total_distance = 0
        for i in range(len(route_indices) - 1):
            u, v = route_indices[i], route_indices[i + 1]
            if cost_matrix[u][v]:
                total_distance += cost_matrix[u][v]['distance']
        return total_distance
    
    def _select_top_candidates(self, all_candidates):
        """从所有候选中选择最佳的路线"""
        if not all_candidates:
            return None
            
        # 去重：基于分店组合
        unique_candidates = {}
        for candidate in all_candidates:
            combination_id = candidate['combination_id']
            if combination_id not in unique_candidates:
                unique_candidates[combination_id] = candidate
            else:
                # 如果已存在相同组合，保留更优的
                existing = unique_candidates[combination_id]
                if candidate['total_time_cost'] < existing['total_time_cost']:
                    unique_candidates[combination_id] = candidate
        
        unique_list = list(unique_candidates.values())
        
        if not unique_list:
            return None
        
        # 按时间排序，选择前5个
        time_sorted = sorted(unique_list, key=lambda x: x['total_time_cost'])[:5]
        
        # 按距离排序，选择前5个（避免重复）
        distance_sorted = sorted(unique_list, key=lambda x: x['total_distance_cost'])[:5]
        
        # 合并并去重
        selected_candidates = []
        seen_combinations = set()
        
        # 添加时间最优的候选
        for candidate in time_sorted:
            if candidate['combination_id'] not in seen_combinations:
                candidate['optimization_priority'] = 'time'
                selected_candidates.append(candidate)
                seen_combinations.add(candidate['combination_id'])
        
        # 添加距离最优的候选（如果还没有）
        for candidate in distance_sorted:
            if candidate['combination_id'] not in seen_combinations and len(selected_candidates) < 5:
                candidate['optimization_priority'] = 'distance'
                selected_candidates.append(candidate)
                seen_combinations.add(candidate['combination_id'])
        
        logger.info(f"最终选择了 {len(selected_candidates)} 个不同的路线候选")
        return selected_candidates
    
    def _generate_category_combinations(self):
        """生成所有有效的类别组合（笛卡尔积）"""
        if not self.chain_categories:
            return [[]]
            
        category_lists = list(self.category_points.values())
        combinations = []
        
        def generate_recursive(current_combination, category_index):
            if category_index == len(category_lists):
                combinations.append(current_combination[:])
                return
                
            for point_index in category_lists[category_index]:
                current_combination.append(point_index)
                generate_recursive(current_combination, category_index + 1)
                current_combination.pop()
        
        generate_recursive([], 0)
        return combinations
        

        
    def _format_result(self, selected_candidates, cost_matrix):
        """格式化优化结果 - 支持多个候选路线"""
        if not selected_candidates:
            return self._create_fallback_result()
        
        # 构建多个候选路线
        route_candidates = []
        
        for rank, candidate in enumerate(selected_candidates, 1):
            route_indices = candidate['route_indices']
            
            # 构建路线详情
            route_details = []
            total_distance = 0
            total_duration = 0
            
            for i in range(len(route_indices) - 1):
                from_idx = route_indices[i]
                to_idx = route_indices[i + 1]
                
                segment = cost_matrix[from_idx][to_idx]
                if segment:
                    route_details.append({
                        'from': self.all_points[from_idx],
                        'to': self.all_points[to_idx],
                        'distance': segment.get('distance', 0),
                        'duration': segment.get('duration', 0),
                        'polyline': segment.get('polyline', ''),
                        'steps': segment.get('steps', [])
                    })
                    total_distance += segment.get('distance', 0)
                    total_duration += segment.get('duration', 0)
            
            # 添加返回家的路径
            if len(route_indices) > 1:
                last_idx = route_indices[-1]
                home_idx = 0
                segment = cost_matrix[last_idx][home_idx]
                if segment:
                    route_details.append({
                        'from': self.all_points[last_idx],
                        'to': self.all_points[home_idx],
                        'distance': segment.get('distance', 0),
                        'duration': segment.get('duration', 0),
                        'polyline': segment.get('polyline', ''),
                        'steps': segment.get('steps', [])
                    })
                    total_distance += segment.get('distance', 0)
                    total_duration += segment.get('duration', 0)
            
            # 构建选中的店铺信息
            selected_chain_shops = []
            for shop_idx in candidate['selected_shops']:
                shop = self.all_points[shop_idx]
                selected_chain_shops.append({
                    'id': shop['id'],
                    'name': shop['name'],
                    'brand': shop.get('brand', ''),
                    'latitude': shop['latitude'],
                    'longitude': shop['longitude'],
                    'address': shop.get('address', ''),
                    'type': 'chain'
                })
            
            # 构建候选路线数据
            route_candidate = {
                'rank': rank,
                'optimization_priority': candidate.get('optimization_priority', 'time'),
                'route_points': [self.all_points[i] for i in route_indices],
                'route_details': route_details,
                'selected_chain_shops': selected_chain_shops,
                'private_shops': self.private_shops,
                'total_distance': total_distance,
                'total_duration': total_duration,
                'total_time_cost': candidate['total_time_cost'],
                'total_distance_cost': candidate['total_distance_cost'],
                'strategy': candidate.get('strategy', 'unknown'),
                'shop_combination_summary': self._get_combination_summary(candidate['selected_shops'])
            }
            
            route_candidates.append(route_candidate)
        
        # 按时间和距离分别排序，生成分类的候选
        time_ranked = sorted(route_candidates, key=lambda x: x.get('total_time_cost', float('inf')))
        distance_ranked = sorted(route_candidates, key=lambda x: x.get('total_distance_cost', float('inf')))
        
        return {
            'success': True,
            'total_candidates': len(route_candidates),
            'route_candidates': {
                'by_time': time_ranked,
                'by_distance': distance_ranked,
                'all': route_candidates
            },
            'optimization_method': 'TSP_with_Categories_Enhanced',
            'summary': {
                'fastest_route': {
                    'duration': time_ranked[0]['total_duration'] if time_ranked else 0,
                    'combination': time_ranked[0]['shop_combination_summary'] if time_ranked else {}
                },
                'shortest_route': {
                    'distance': distance_ranked[0]['total_distance'] if distance_ranked else 0,
                    'combination': distance_ranked[0]['shop_combination_summary'] if distance_ranked else {}
                }
            }
        }
        
    def _get_combination_summary(self, selected_shops):
        """获取选中分店组合的摘要"""
        summary = {}
        for shop_idx in selected_shops:
            shop = self.all_points[shop_idx]
            brand = shop.get('brand', shop.get('name', 'Unknown'))
            summary[brand] = shop.get('name', 'Unknown Shop')
        return summary
        
    def _create_fallback_result(self):
        """创建后备结果"""
        logger.warning("创建TSP with Categories的后备结果")
        
        # 简单选择每个类别中的第一个店铺
        selected_shops = []
        for brand_name, point_indices in self.category_points.items():
            if point_indices:
                selected_shops.append(self.all_points[point_indices[0]])
        
        # 简单的路线：家 -> 私人店铺 -> 连锁店铺 -> 家
        route_points = [self.all_points[0]]  # 家
        route_points.extend(self.private_shops)  # 私人店铺
        route_points.extend(selected_shops)  # 连锁店铺
        route_points.append(self.all_points[0])  # 返回家
        
        return {
            'success': True,
            'optimized_route': {
                'route_points': route_points,
                'route_details': [],
                'selected_chain_shops': selected_shops,
                'private_shops': self.private_shops,
                'total_distance': 0,
                'total_duration': 0,
                'optimization_method': 'Fallback'
            },
            'alternatives': [],
            'warning': '优化失败，使用简单路线规划'
        }

def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    """
    使用哈弗辛公式计算两点间的球面距离（公里）
    """
    import math
    
    # 转换为弧度
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # 哈弗辛公式
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # 地球半径（公里）
    r = 6371
    
    return c * r

class TSPOptimizer:
    """TSP优化器，实现多种算法"""
    
    def __init__(self, cost_matrix, points_objects, route_points=None):
        self.cost_matrix = cost_matrix
        self.points_objects = points_objects
        self.route_points = route_points if route_points is not None else list(range(len(points_objects)))
        self.num_points = len(points_objects)  # 修复：使用实际传入的点数量
    
    def calculate_route_cost(self, route_indices, cost_type='duration'):
        """计算路线的总成本（距离或时间）"""
        total_cost = 0
        for i in range(len(route_indices) - 1):
            # 将内部索引映射到全局索引
            u_global = self.route_points[route_indices[i]]
            v_global = self.route_points[route_indices[i + 1]]
            
            if self.cost_matrix[u_global][v_global] is None:
                return float('inf')
            if cost_type == 'duration':
                total_cost += self.cost_matrix[u_global][v_global]['duration']
            else:  # distance
                total_cost += self.cost_matrix[u_global][v_global]['distance']
        return total_cost
    
    def two_opt_improve(self, route_indices, cost_type='duration'):
        """
        2-opt局部搜索算法优化路线
        route_indices: 包含起点和终点的完整路线索引 [0, 1, 2, 3, 0]
        """
        improved = True
        best_route = route_indices[:]
        best_cost = self.calculate_route_cost(best_route, cost_type)
        
        iteration_count = 0
        max_iterations = 100  # 防止无限循环
        
        while improved and iteration_count < max_iterations:
            improved = False
            iteration_count += 1
            
            # 对于路线中的每对边进行2-opt交换
            # 注意：我们排除起点和终点，只交换中间的店铺顺序
            for i in range(1, len(route_indices) - 2):
                for j in range(i + 1, len(route_indices) - 1):
                    # 创建新的路线：反转i到j之间的顺序
                    new_route = route_indices[:]
                    new_route[i:j+1] = reversed(new_route[i:j+1])
                    
                    new_cost = self.calculate_route_cost(new_route, cost_type)
                    
                    if new_cost < best_cost:
                        best_route = new_route
                        best_cost = new_cost
                        improved = True
                        logger.debug(f"2-opt改进: 第{iteration_count}轮, 成本从{best_cost:.0f}降至{new_cost:.0f}")
        
        logger.info(f"2-opt优化完成: {iteration_count}轮迭代, 最终成本: {best_cost:.0f}")
        return best_route, best_cost
    
    def nearest_neighbor_heuristic(self, start_index=0):
        """最近邻启发式算法生成初始解"""
        unvisited = set(range(self.num_points))
        unvisited.remove(start_index)
        
        route = [start_index]
        current = start_index
        
        while unvisited:
            # 将内部索引映射到全局索引进行比较
            current_global = self.route_points[current]
            nearest = min(unvisited, 
                         key=lambda x: self.cost_matrix[current_global][self.route_points[x]]['duration'] 
                         if self.cost_matrix[current_global][self.route_points[x]] else float('inf'))
            route.append(nearest)
            unvisited.remove(nearest)
            current = nearest
        
        route.append(start_index)  # 回到起点
        return route
    
    def hybrid_optimize(self, use_exact_for_small=True):
        """
        混合优化策略：
        - 小规模问题使用精确算法
        - 大规模问题使用启发式+2-opt
        返回格式: (best_routes, best_costs)
        """
        shop_indices = list(range(1, self.num_points))  # 排除家（索引0）
        
        if len(shop_indices) <= 6 and use_exact_for_small:
            # 小规模使用精确算法
            return self._exact_tsp_solution(shop_indices)
        else:
            # 大规模使用启发式+2-opt
            return self._heuristic_tsp_solution(shop_indices)
    
    def _exact_tsp_solution(self, shop_indices):
        """精确TSP解（暴力枚举）- 生成前5名候选路线"""
        logger.info(f"使用精确算法求解{len(shop_indices)}个店铺的TSP问题，生成前5名候选")
        
        # 存储所有路线候选
        all_routes = []
        
        for perm in itertools.permutations(shop_indices):
            route_indices = [0] + list(perm) + [0]
            
            # 计算时间和距离成本
            time_cost = self.calculate_route_cost(route_indices, 'duration')
            distance_cost = self.calculate_route_cost(route_indices, 'distance')
            
            if time_cost != float('inf') and distance_cost != float('inf'):
                all_routes.append({
                    'route': route_indices,
                    'time_cost': time_cost,
                    'distance_cost': distance_cost,
                    'permutation': perm
                })
        
        if not all_routes:
            return {'time': [], 'distance': []}, {'time': [], 'distance': []}
        
        # 按时间排序，取前5名
        time_sorted = sorted(all_routes, key=lambda x: x['time_cost'])[:5]
        
        # 按距离排序，取前5名
        distance_sorted = sorted(all_routes, key=lambda x: x['distance_cost'])[:5]
        
        # 构建返回结果
        best_routes = {
            'time': [route['route'] for route in time_sorted],
            'distance': [route['route'] for route in distance_sorted]
        }
        
        best_costs = {
            'time': [route['time_cost'] for route in time_sorted],
            'distance': [route['distance_cost'] for route in distance_sorted]
        }
        
        logger.info(f"精确算法生成了 {len(time_sorted)} 个时间候选和 {len(distance_sorted)} 个距离候选")
        return best_routes, best_costs
    
    def _heuristic_tsp_solution(self, shop_indices):
        """启发式TSP解（最近邻+2-opt）- 生成多个候选路线"""
        logger.info(f"使用启发式算法求解{len(shop_indices)}个店铺的TSP问题，生成多个候选")
        
        # 存储所有候选路线
        all_candidates = []
        
        # 策略1：多起始点最近邻算法
        start_points = [0] + shop_indices[:min(5, len(shop_indices))]  # 尝试更多起始点
        
        for start_point in start_points:
            initial_route = self.nearest_neighbor_heuristic(start_point)
            
            # 如果起点不是家，需要调整路线
            if start_point != 0:
                home_idx = initial_route.index(0)
                adjusted_route = initial_route[home_idx:] + initial_route[1:home_idx] + [0]
                initial_route = adjusted_route
            
            # 对每种成本类型进行2-opt优化
            for cost_type in ['duration', 'distance']:
                improved_route, improved_cost = self.two_opt_improve(initial_route, cost_type)
                
                all_candidates.append({
                    'route': improved_route,
                    'time_cost': self.calculate_route_cost(improved_route, 'duration'),
                    'distance_cost': self.calculate_route_cost(improved_route, 'distance'),
                    'strategy': f'nearest_neighbor_start_{start_point}_{cost_type}'
                })
        
        # 策略2：随机重启优化（生成更多候选）
        for _ in range(min(10, len(shop_indices) * 2)):  # 根据店铺数量调整重启次数
            # 随机打乱店铺顺序
            shuffled_shops = shop_indices.copy()
            random.shuffle(shuffled_shops)
            initial_route = [0] + shuffled_shops + [0]
            
            # 对随机路线进行2-opt优化
            for cost_type in ['duration', 'distance']:
                improved_route, improved_cost = self.two_opt_improve(initial_route, cost_type)
                
                all_candidates.append({
                    'route': improved_route,
                    'time_cost': self.calculate_route_cost(improved_route, 'duration'),
                    'distance_cost': self.calculate_route_cost(improved_route, 'distance'),
                    'strategy': f'random_restart_{cost_type}'
                })
        
        # 去重：基于路线的店铺访问顺序
        unique_candidates = []
        seen_permutations = set()
        
        for candidate in all_candidates:
            if candidate['time_cost'] == float('inf') or candidate['distance_cost'] == float('inf'):
                continue
                
            # 提取店铺访问顺序（排除起点和终点的家）
            route_shops = tuple(candidate['route'][1:-1])
            
            if route_shops not in seen_permutations:
                seen_permutations.add(route_shops)
                unique_candidates.append(candidate)
        
        if not unique_candidates:
            return {'time': [], 'distance': []}, {'time': [], 'distance': []}
        
        # 按时间排序，取前5名
        time_sorted = sorted(unique_candidates, key=lambda x: x['time_cost'])[:5]
        
        # 按距离排序，取前5名（避免重复）
        distance_sorted = sorted(unique_candidates, key=lambda x: x['distance_cost'])[:5]
        
        # 构建返回结果
        best_routes = {
            'time': [candidate['route'] for candidate in time_sorted],
            'distance': [candidate['route'] for candidate in distance_sorted]
        }
        
        best_costs = {
            'time': [candidate['time_cost'] for candidate in time_sorted],
            'distance': [candidate['distance_cost'] for candidate in distance_sorted]
        }
        
        logger.info(f"启发式算法从 {len(all_candidates)} 个候选中筛选出 {len(time_sorted)} 个时间候选和 {len(distance_sorted)} 个距离候选")
        return best_routes, best_costs
    
    def ortools_solve(self, max_time_seconds=30):
        """使用Or-Tools求解TSP问题"""
        if not ORTOOLS_AVAILABLE:
            logger.warning("Or-Tools不可用，回退到启发式算法")
            return self._heuristic_tsp_solution(list(range(1, self.num_points)))
        
        logger.info(f"使用Or-Tools求解{self.num_points}个点的TSP问题")
        
        try:
            # 创建路由模型
            manager = pywrapcp.RoutingIndexManager(self.num_points, 1, 0)
            routing = pywrapcp.RoutingModel(manager)
            
            def distance_callback(from_index, to_index):
                from_node = manager.IndexToNode(from_index)
                to_node = manager.IndexToNode(to_index)
                if self.cost_matrix[from_node][to_node] is None:
                    return 999999
                return int(self.cost_matrix[from_node][to_node]['duration'])
            
            transit_callback_index = routing.RegisterTransitCallback(distance_callback)
            routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
            
            search_parameters = pywrapcp.DefaultRoutingSearchParameters()
            search_parameters.first_solution_strategy = (
                routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
            search_parameters.local_search_metaheuristic = (
                routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
            search_parameters.time_limit.seconds = max_time_seconds
            
            solution = routing.SolveWithParameters(search_parameters)
            
            if solution:
                route_indices = []
                index = routing.Start(0)
                while not routing.IsEnd(index):
                    route_indices.append(manager.IndexToNode(index))
                    index = solution.Value(routing.NextVar(index))
                route_indices.append(0)
                
                return {'time': route_indices, 'distance': route_indices.copy()}, None
            else:
                return self._heuristic_tsp_solution(list(range(1, self.num_points)))
                
        except Exception as e:
            logger.error(f"Or-Tools求解失败: {e}")
            return self._heuristic_tsp_solution(list(range(1, self.num_points)))
    
    def genetic_algorithm_solve(self, population_size=50, generations=100):
        """遗传算法求解TSP"""
        logger.info(f"使用遗传算法求解{self.num_points}个点的TSP问题")
        
        shop_indices = list(range(1, self.num_points))
        if len(shop_indices) < 2:
            return self._exact_tsp_solution(shop_indices)
        
        def create_individual():
            route = shop_indices.copy()
            random.shuffle(route)
            return route
        
        def calculate_fitness(individual):
            route_indices = [0] + individual + [0]
            cost = self.calculate_route_cost(route_indices, 'duration')
            return 1.0 / (cost + 1) if cost != float('inf') else 0
        
        def crossover(parent1, parent2):
            size = len(parent1)
            start, end = sorted(random.sample(range(size), 2))
            child = [-1] * size
            child[start:end+1] = parent1[start:end+1]
            
            pointer = 0
            for item in parent2:
                if item not in child:
                    while child[pointer] != -1:
                        pointer += 1
                    child[pointer] = item
            return child
        
        def mutate(individual, mutation_rate=0.1):
            if random.random() < mutation_rate:
                idx1, idx2 = random.sample(range(len(individual)), 2)
                individual[idx1], individual[idx2] = individual[idx2], individual[idx1]
            return individual
        
        population = [create_individual() for _ in range(population_size)]
        best_individual = None
        best_fitness = 0
        
        for generation in range(generations):
            fitness_scores = [calculate_fitness(ind) for ind in population]
            max_fitness_idx = np.argmax(fitness_scores)
            
            if fitness_scores[max_fitness_idx] > best_fitness:
                best_fitness = fitness_scores[max_fitness_idx]
                best_individual = population[max_fitness_idx].copy()
            
            total_fitness = sum(fitness_scores)
            if total_fitness == 0:
                break
                
            probabilities = [f/total_fitness for f in fitness_scores]
            new_population = []
            
            for _ in range(population_size):
                parent1 = population[np.random.choice(len(population), p=probabilities)]
                parent2 = population[np.random.choice(len(population), p=probabilities)]
                child = crossover(parent1, parent2)
                child = mutate(child)
                new_population.append(child)
            
            population = new_population
        
        if best_individual:
            best_route = [0] + best_individual + [0]
            return {'time': best_route, 'distance': best_route.copy()}, None
        else:
            return self._heuristic_tsp_solution(shop_indices)
    
    def adaptive_solve(self, max_time_seconds=30):
        """自适应算法选择"""
        num_shops = self.num_points - 1
        
        if num_shops <= 6:
            logger.info("使用精确算法（≤6个店铺）")
            return self._exact_tsp_solution(list(range(1, self.num_points)))
        elif num_shops <= 15 and ORTOOLS_AVAILABLE:
            logger.info("使用Or-Tools算法（7-15个店铺）")
            return self.ortools_solve(max_time_seconds)
        elif num_shops <= 25:
            logger.info("使用遗传算法（16-25个店铺）")
            return self.genetic_algorithm_solve(population_size=30, generations=50)
        else:
            logger.info("使用启发式+2-opt算法（>25个店铺）")
            return self._heuristic_tsp_solution(list(range(1, self.num_points)))

@amap_api_handler("geocode_address")
def geocode_address(api_key, address, city=None):
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
        response = amap_manager.safe_request(url, params=params, timeout=15)
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

@amap_api_handler("get_driving_route_segment_details")
def get_driving_route_segment_details(api_key, origin_lat, origin_lng, dest_lat, dest_lng, strategy=5, departure_time=None):
    """
    安全的驾车路线查询函数，支持缓存和实时路况
    """
    if not api_key:
        return None
    
    # 生成缓存键时考虑出发时间（实时路况）
    cache_key_suffix = f"_{departure_time}" if departure_time else ""
    cached_result = distance_cache.get(origin_lat, origin_lng, dest_lat, dest_lng, f'driving{cache_key_suffix}')
    if cached_result:
        return cached_result
    
    # 缓存未命中，调用API
    @amap_api_handler("get_public_transit_segment_details")
    def _api_call():
        url = "https://restapi.amap.com/v3/direction/driving"
        params = {
            "key": api_key,
            "origin": f"{origin_lng},{origin_lat}",
            "destination": f"{dest_lng},{dest_lat}",
            "strategy": str(strategy),
            "extensions": "all",  # 修复：使用"all"获取详细的路线指导信息
            "waypoints": "",  # 空的途经点
        }
        
        # 添加实时路况支持
        if departure_time:
            # departure_time 格式: 'YYYY-MM-DD HH:MM:SS' 或时间戳
            if isinstance(departure_time, str):
                try:
                    departure_dt = datetime.strptime(departure_time, '%Y-%m-%d %H:%M:%S')
                    params["departure_time"] = int(departure_dt.timestamp())
                except ValueError:
                    try:
                        params["departure_time"] = int(departure_time)
                    except ValueError:
                        logger.warning(f"无效的出发时间格式: {departure_time}")
            else:
                params["departure_time"] = int(departure_time)
        
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            if data.get("status") == "1" and data.get("route") and data["route"].get("paths"):
                path = data["route"]["paths"][0]
                
                # 处理驾车详细步骤
                driving_steps = []
                if path.get("steps"):
                    for step in path["steps"]:
                        instruction = step.get("instruction", "")
                        road_name = step.get("road", "")
                        distance = step.get("distance", "")
                        duration = step.get("duration", "")
                        action = step.get("action", "")
                        
                        # 构建更详细的指导文本
                        if instruction and road_name:
                            detailed_instruction = f"{instruction}，沿{road_name}行驶"
                        elif instruction:
                            detailed_instruction = instruction
                        elif road_name:
                            detailed_instruction = f"沿{road_name}行驶"
                        else:
                            detailed_instruction = action or "继续行驶"
                        
                        # 添加距离和时间信息
                        if distance:
                            detailed_instruction += f"（{distance}米"
                            if duration:
                                detailed_instruction += f"，约{int(float(duration)/60)}分钟"
                            detailed_instruction += "）"
                        
                        driving_steps.append({
                            "type": "driving",
                            "instruction": detailed_instruction,
                            "action": action,
                            "road": road_name,
                            "distance": distance,
                            "duration": duration
                        })
                
                result = {
                    "distance": int(path.get("distance", 0)),
                    "duration": int(path.get("duration", 0)),
                    "polyline": path.get("polyline", ""),
                    "steps": driving_steps,  # 使用处理后的详细步骤
                    "traffic_lights": path.get("traffic_lights", 0),  # 红绿灯数量
                    "restriction": path.get("restriction", 0),  # 限行信息
                    "has_real_time": departure_time is not None,  # 是否使用实时路况
                    "tolls": path.get("tolls", 0),  # 过路费
                    "toll_distance": path.get("toll_distance", 0),  # 收费路段距离
                    "restrictions": path.get("restrictions", [])  # 限行信息
                }
                
                # 将结果存入缓存（实时路况的缓存时间较短）
                cache_mode = f'driving{cache_key_suffix}'
                distance_cache.set(origin_lat, origin_lng, dest_lat, dest_lng, result, cache_mode)
                return result
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
    
    return _api_call()

# --- Database Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    home_address = db.Column(db.String(255), nullable=True)
    home_latitude = db.Column(db.Float, nullable=True)
    home_longitude = db.Column(db.Float, nullable=True)
    preferred_province = db.Column(db.String(100), nullable=True)  # 用户偏好省份
    preferred_city = db.Column(db.String(100), nullable=True)      # 用户偏好城市

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
# geocode_address function has been replaced with the safe version above

@amap_api_handler("search_poi")
def search_poi(api_key, keywords, city=None, location=None, radius=5000, types=None, max_results=25):
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

        # 处理和转换数据格式 - 修复逻辑
        if data.get("status") == "1" and data.get("pois"):
            all_pois = data["pois"]
            offset = 20  # 默认每页20个结果
            
            # 如果需要更多结果且当前结果数量达到了offset限制，尝试获取更多页面
            if len(all_pois) >= offset and len(all_pois) < max_results:
                page = 2
                while len(all_pois) < max_results and page <= 5:  # 最多获取5页避免无限循环
                    try:
                        paginated_params = params.copy()
                        paginated_params['page'] = page
                        paginated_response = requests.get(url, params=paginated_params, timeout=5)
                        paginated_response.raise_for_status()
                        paginated_data = paginated_response.json()
                        
                        if paginated_data.get("status") == "1" and paginated_data.get("pois"):
                            current_pois = paginated_data["pois"]
                            all_pois.extend(current_pois)
                            
                            # 如果返回的结果少于offset，说明没有更多数据了
                            if len(current_pois) < offset:
                                break
                        else:
                            break
                        page += 1
                        time.sleep(0.05)  # 分页请求间隔
                    except requests.exceptions.RequestException:
                        break  # 分页请求失败，使用已获取的结果
            
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
                        "distance": poi.get("distance"), # if location is provided
                        "business_area": poi.get("business_area"),  # 商圈信息
                        "province": poi.get("province"),  # 省份
                        "city": poi.get("city"),  # 城市
                        "district": poi.get("district"),  # 区县
                        "adname": poi.get("adname"),  # 行政区名称
                        "rating": poi.get("rating"),  # 评分
                        "cost": poi.get("cost"),  # 人均消费
                        "indoor_map": poi.get("indoor_map"),  # 是否有室内地图
                        "photos": poi.get("photos", [])  # 照片信息
                    })
                return pois_data
            else:
                logger.warning(f"Amap POI Search Error: No POIs found for keywords: {keywords}")
                return None
        else:
            logger.warning(f"Amap POI Search Error: {data.get('info')} for keywords: {keywords}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Amap POI Search request failed: {e}")
        return None
    except (ValueError, KeyError) as e:
        logger.error(f"Error parsing Amap POI Search response: {e}")
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


@amap_api_handler("get_public_transit_segment_details")
def get_public_transit_segment_details(api_key, origin_lat, origin_lng, dest_lat, dest_lng, city, strategy=0):
    """
    Gets public transit route details using Amap Integrated Directions API，支持缓存.
    `city` is the origin city code or name.
    Strategy: 0 for recommended, other values for different preferences (e.g., less walking).
    Returns a dictionary like {"distance": meters, "duration": seconds, "polyline": "concatenated_polyline_string"} or None.
    Distance for transit is often walking distance + transit line distance, can be complex. Amap returns 'distance' field for the whole transit path.
    """
    if not api_key:
        logger.error("Amap API密钥未配置")
        return None

    # 首先检查缓存
    cached_result = distance_cache.get(origin_lat, origin_lng, dest_lat, dest_lng, 'public_transit', city)
    if cached_result:
        return cached_result

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

            result = {
                "distance": int(transit_path.get("distance", 0)), # Overall distance
                "duration": int(transit_path.get("duration", 0)), # Overall duration
                "polyline": full_polyline,
                "steps": detailed_steps,
                "segments": transit_path.get("segments", []),  # 添加完整的segments信息
                "cost": float(transit_path.get("cost", 0)),  # 公交费用
                "walking_distance": int(transit_path.get("walking_distance", 0)),  # 步行距离
                "nightflag": transit_path.get("nightflag", "0"),  # 是否夜班车
                "railway_flag": transit_path.get("railway_flag", "0")  # 是否包含地铁
            }
            
            # 将结果存入缓存
            distance_cache.set(origin_lat, origin_lng, dest_lat, dest_lng, result, 'public_transit', city)
            logger.debug(f"公交路线规划成功: {origin_lat},{origin_lng} -> {dest_lat},{dest_lng}")
            return result
        else:
            # 如果API成功但没有找到公交路线，这是正常情况（可能该路线没有公交）
            info_msg = data.get('info', 'Unknown error')
            if data.get("status") == "1":
                logger.info(f"未找到公交路线: ({origin_lng},{origin_lat}) -> ({dest_lng},{dest_lat}) in city {city}")
            else:
                logger.warning(f"高德公交API错误: {info_msg} from ({origin_lng},{origin_lat}) to ({dest_lng},{dest_lat}) in city {city}")
            return None
    except requests.exceptions.Timeout:
        logger.error(f"公交路线规划请求超时: ({origin_lng},{origin_lat}) -> ({dest_lng},{dest_lat})")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"公交路线规划请求失败: {e}")
        return None
    except (ValueError, KeyError, IndexError) as e:
        logger.error(f"公交路线规划响应解析错误: {e}")
        return None
    finally:
        time.sleep(0.05) # 增加50毫秒延迟以避免QPS超限


# get_driving_route_segment_details function has been replaced with the safe version above


# --- API Endpoints ---
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        logger.warning("注册请求中没有JSON数据")
        return jsonify({'message': 'No JSON data received'}), 400
        
    username = data.get('username')
    password = data.get('password')
    
    logger.info(f"收到用户注册请求: {username}")

    if not username or not password:
        return jsonify({'message': 'Username and password are required'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'message': 'Username already exists'}), 409

    new_user = User(username=username)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    logger.info(f"用户注册成功: {username}")
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
@app.route('/api/user/home', methods=['GET', 'POST'])
@login_required
def home_location():
    if request.method == 'POST':
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
            else:
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
        
        # Return the updated home location info
        return jsonify({
            'message': 'Home location updated successfully',
            'home_address': current_user.home_address,
            'home_latitude': current_user.home_latitude,
            'home_longitude': current_user.home_longitude
        }), 200
    
    # GET request
    else:
        return jsonify({
            'home_address': current_user.home_address,
            'home_latitude': current_user.home_latitude,
            'home_longitude': current_user.home_longitude
        }), 200

@app.route('/api/geocode/search', methods=['POST'])
def geocode_search():
    """地址搜索建议API"""
    try:
        data = request.get_json()
        address = data.get('address', '').strip()
        city = data.get('city', '')
        
        if not address:
            return jsonify({'suggestions': []}), 200
        
        if len(address) < 2:
            return jsonify({'suggestions': []}), 200
        
        api_key = app.config['AMAP_API_KEY']
        
        # 使用高德地图的输入提示API
        url = "https://restapi.amap.com/v3/assistant/inputtips"
        params = {
            'key': api_key,
            'keywords': address,
            'city': city,
            'datatype': 'all',
            'citylimit': 'true' if city else 'false'
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        suggestions = []
        if result.get('status') == '1' and result.get('tips'):
            for tip in result['tips'][:8]:  # 限制返回8个建议
                if tip.get('location') and tip.get('location') != '':
                    location_parts = tip['location'].split(',')
                    if len(location_parts) == 2:
                        try:
                            longitude = float(location_parts[0])
                            latitude = float(location_parts[1])
                            
                            suggestion = {
                                'id': tip.get('id', ''),
                                'name': tip.get('name', ''),
                                'address': tip.get('address', ''),
                                'district': tip.get('district', ''),
                                'latitude': latitude,
                                'longitude': longitude
                            }
                            suggestions.append(suggestion)
                        except (ValueError, IndexError):
                            continue
        
        return jsonify({'suggestions': suggestions}), 200
        
    except requests.exceptions.RequestException as e:
        logger.error(f"高德地址搜索API请求失败: {e}")
        return jsonify({'suggestions': [], 'error': '地址搜索服务暂时不可用'}), 500
    except Exception as e:
        logger.error(f"地址搜索处理错误: {e}")
        return jsonify({'suggestions': [], 'error': '地址搜索处理失败'}), 500

@app.route('/api/geocode/address', methods=['POST'])
def geocode_address_api():
    """地址解析API"""
    try:
        data = request.get_json()
        address = data.get('address', '').strip()
        city = data.get('city', '')
        
        if not address:
            return jsonify({'message': 'Address is required'}), 400
        
        api_key = app.config['AMAP_API_KEY']
        geocoded_result = geocode_address(api_key, address, city)
        
        if geocoded_result:
            return jsonify(geocoded_result), 200
        else:
            return jsonify({'message': 'Unable to geocode the address'}), 400
            
    except Exception as e:
        logger.error(f"地址解析API错误: {e}")
        return jsonify({'message': 'Address geocoding failed'}), 500

@app.route('/api/search-address', methods=['GET'])
def search_address():
    """地址搜索建议API - 兼容前端GET请求"""
    try:
        query = request.args.get('query', '').strip()
        city = request.args.get('city', '')
        
        logger.info(f"地址搜索请求: query={query}, city={city}")
        
        if not query:
            return jsonify({'suggestions': []}), 200
        
        if len(query) < 2:
            return jsonify({'suggestions': []}), 200
        
        api_key = app.config.get('AMAP_API_KEY')
        if not api_key:
            return jsonify({'suggestions': [], 'error': '服务配置错误'}), 500
        
        # 使用高德地图的输入提示API
        url = "https://restapi.amap.com/v3/assistant/inputtips"
        params = {
            'key': api_key,
            'keywords': query,
            'city': city,
            'datatype': 'all',
            'citylimit': 'true' if city else 'false'
        }
        
        logger.info(f"调用高德API: {url}, params: {params}")
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        # 确保正确处理中文响应
        if response.encoding is None or response.encoding == 'ISO-8859-1':
            response.encoding = 'utf-8'
        
        try:
            result = response.json()
        except UnicodeDecodeError:
            # 如果仍然有编码问题，强制使用utf-8解码
            content = response.content.decode('utf-8', errors='ignore')
            result = json.loads(content)
        
        logger.info(f"高德API响应状态: {result.get('status')}")
        
        suggestions = []
        if result.get('status') == '1' and result.get('tips'):
            for tip in result['tips'][:8]:  # 限制返回8个建议
                if tip.get('location') and tip.get('location') != '':
                    location_parts = tip['location'].split(',')
                    if len(location_parts) == 2:
                        try:
                            longitude = float(location_parts[0])
                            latitude = float(location_parts[1])
                            
                            suggestion = {
                                'id': tip.get('id', ''),
                                'name': tip.get('name', ''),
                                'address': tip.get('address', ''),
                                'district': tip.get('district', ''),
                                'location': f"{longitude},{latitude}"
                            }
                            suggestions.append(suggestion)
                        except (ValueError, IndexError):
                            continue
        
        logger.info(f"返回建议数量: {len(suggestions)}")
        return jsonify({'suggestions': suggestions}), 200
        
    except requests.exceptions.RequestException as e:
        logger.error(f"高德地址搜索API请求失败: {e}")
        return jsonify({'suggestions': [], 'error': '地址搜索服务暂时不可用'}), 500
    except Exception as e:
        logger.error(f"地址搜索处理错误: {e}")
        return jsonify({'suggestions': [], 'error': '地址搜索处理失败'}), 500

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
            max_results=25
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

@app.route('/api/search-shops', methods=['GET'])
def search_shops():
    """店铺搜索API - 兼容前端GET请求"""
    try:
        query = request.args.get('query', '').strip()
        city = request.args.get('city', '')
        
        if not query:
            return jsonify({'suggestions': []}), 200
        
        if len(query) < 2:
            return jsonify({'suggestions': []}), 200
        
        api_key = app.config.get('AMAP_API_KEY')
        if not api_key:
            return jsonify({'suggestions': [], 'error': '服务配置错误'}), 500
        
        # 使用search_poi函数搜索店铺
        results = search_poi(
            api_key=api_key,
            keywords=query,
            city=city,
            max_results=15
        )
        
        if results is None:
            return jsonify({'suggestions': [], 'error': '搜索服务暂时不可用'}), 500
        
        # 转换为前端期望的格式
        suggestions = []
        for result in results:
            if result.get('latitude') is not None and result.get('longitude') is not None:
                suggestion = {
                    'id': result.get('id', ''),
                    'name': result.get('name', ''),
                    'address': result.get('address', ''),
                    'latitude': result.get('latitude'),
                    'longitude': result.get('longitude'),
                    'distance': result.get('distance'),
                    'type': result.get('type', ''),
                    'typecode': result.get('typecode', '')
                }
                suggestions.append(suggestion)
        
        return jsonify({'suggestions': suggestions}), 200
        
    except Exception as e:
        logger.error(f"店铺搜索处理错误: {e}")
        return jsonify({'suggestions': [], 'error': '店铺搜索处理失败'}), 500

@app.route('/api/get-city-center', methods=['GET'])
def get_city_center():
    """获取城市中心坐标API"""
    try:
        adcode = request.args.get('adcode', '').strip()
        
        if not adcode:
            return jsonify({'success': False, 'error': '缺少行政区划代码'}), 400
        
        api_key = app.config.get('AMAP_API_KEY')
        if not api_key:
            return jsonify({'success': False, 'error': '服务配置错误'}), 500
        
        # 使用高德地图行政区查询API
        url = "https://restapi.amap.com/v3/config/district"
        params = {
            'key': api_key,
            'keywords': adcode,
            'subdistrict': 0,
            'extensions': 'base'
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if result.get('status') == '1' and result.get('districts'):
            district = result['districts'][0]
            center = district.get('center')
            if center:
                longitude, latitude = map(float, center.split(','))
                return jsonify({
                    'success': True,
                    'center': {
                        'longitude': longitude,
                        'latitude': latitude
                    },
                    'name': district.get('name', ''),
                    'level': district.get('level', '')
                }), 200
        
        return jsonify({'success': False, 'error': '未找到对应的行政区'}), 404
        
    except requests.exceptions.RequestException as e:
        logger.error(f"获取城市中心API请求失败: {e}")
        return jsonify({'success': False, 'error': '服务暂时不可用'}), 500
    except Exception as e:
        logger.error(f"获取城市中心处理错误: {e}")
        return jsonify({'success': False, 'error': '处理失败'}), 500

@app.route('/api/optimize-route', methods=['POST'])
def optimize_route_compat():
    """路线优化API - 兼容前端调用"""
    # 直接转发到现有的路线优化API
    return optimize_route_enhanced()

# --- Route Optimization Endpoint ---
MAX_SHOPS_FOR_OPTIMIZATION = 15 # Max shops (N) for TSP optimization (increased from 6)
MAX_SHOPS_FOR_EXACT_TSP = 6 # Max shops for exact TSP algorithm

@app.route('/api/route/optimize', methods=['POST'])
def optimize_route_enhanced():
    """增强的路线优化接口 - 支持智能连锁店选择"""
    try:
        # 增强的JSON解码处理
        try:
            data = request.get_json(force=True)
        except Exception as json_error:
            logger.error(f"JSON解码错误: {str(json_error)}")
            # 尝试手动解码
            try:
                raw_data = request.get_data()
                data = json.loads(raw_data.decode('utf-8', errors='ignore'))
            except Exception as fallback_error:
                logger.error(f"备用JSON解码也失败: {str(fallback_error)}")
                return jsonify({'message': 'Invalid JSON data. Please check encoding.'}), 400
        
        if not data:
            return jsonify({'message': 'Request body must be JSON.'}), 400
            
        # 检查是否为新的连锁店优化请求格式
        if 'chain_categories' in data or any(shop.get('type') == 'chain' for shop in data.get('shops', [])):
            return handle_chain_store_optimization(data)
        
        # 原有的数据验证
        validation_error = validate_route_request(data)
        if validation_error:
            return jsonify({'message': validation_error}), 400
            
        home_location_data = data.get('home_location')
        shops_data = data.get('shops')
        mode = data.get('mode', 'driving')
        city_param = data.get('city')
        top_n = data.get('top_n', 10)
        departure_time = data.get('departure_time')  # 实时路况支持
        algorithm_preference = data.get('algorithm', 'adaptive')  # 算法偏好
        api_key = app.config.get('AMAP_API_KEY')
        if not api_key:
            return jsonify({'message': 'Amap API key not configured on server.'}), 500
        # 检查店铺数量限制
        if len(shops_data) > MAX_SHOPS_FOR_OPTIMIZATION:
            return jsonify({
                'message': f'Too many shops for optimization. Please select {MAX_SHOPS_FOR_OPTIMIZATION} or fewer shops.'
            }), 400
        # 使用线程池处理API调用以提高性能
        with ThreadPoolExecutor(max_workers=3) as executor:
            result = process_route_optimization_threaded(
                executor, api_key, home_location_data, shops_data, mode, city_param, top_n, departure_time, algorithm_preference
            )
        return jsonify(result)
    except Exception as e:
        logger.error(f"路线优化处理错误: {str(e)}")
        return jsonify({
            'message': 'Internal server error during route optimization.',
            'error': str(e) if app.debug else 'Contact support'
        }), 500

def handle_chain_store_optimization(data):
    """处理连锁店智能优化请求"""
    try:
        logger.info("处理连锁店智能优化请求")
        
        # 验证必要字段
        home_location_data = data.get('home_location')
        if not home_location_data or 'latitude' not in home_location_data or 'longitude' not in home_location_data:
            return jsonify({'message': 'Missing or invalid home_location'}), 400
        
        mode = data.get('mode', 'driving')
        city_param = data.get('city')
        api_key = app.config.get('AMAP_API_KEY')
        
        if not api_key:
            return jsonify({'message': 'Amap API key not configured on server.'}), 500
        
        if not city_param:
            return jsonify({'message': 'City parameter is required for chain store optimization'}), 400
        
        # 处理两种请求格式
        chain_categories = {}
        private_shops = []
        
        if 'chain_categories' in data:
            # 新格式：直接提供连锁店类别
            chain_categories = data['chain_categories']
            private_shops = data.get('private_shops', [])
        else:
            # 兼容格式：从shops中分离连锁店和私人店铺
            shops_data = data.get('shops', [])
            
            for shop in shops_data:
                if shop.get('type') == 'chain':
                    brand_name = shop.get('brand') or shop.get('name')
                    if brand_name not in chain_categories:
                        chain_categories[brand_name] = []
                    # 对于"type": "chain"的请求，需要搜索分店
                    if 'branches' not in shop:
                        # 搜索连锁店分店
                        branches = search_chain_store_branches(api_key, brand_name, home_location_data, city_param)
                        chain_categories[brand_name] = branches
                    else:
                        chain_categories[brand_name] = shop['branches']
                else:
                    private_shops.append(shop)
        
        # 如果没有连锁店类别，返回错误
        if not chain_categories:
            return jsonify({'message': 'No chain store categories found for optimization'}), 400
        
        # 验证连锁店数据
        for brand_name, branches in chain_categories.items():
            if not branches:
                logger.warning(f"品牌 {brand_name} 没有找到分店")
            elif len(branches) > MAX_CHAIN_BRANCHES_PER_BRAND:
                # 限制每个品牌的分店数量，选择最近的分店
                logger.info(f"品牌 {brand_name} 分店过多 ({len(branches)})，限制为 {MAX_CHAIN_BRANCHES_PER_BRAND} 家")
                # 按距离家的位置排序，选择最近的分店
                home_lat = home_location_data['latitude']
                home_lng = home_location_data['longitude']
                
                branches_with_distance = []
                for branch in branches:
                    distance = calculate_haversine_distance(
                        home_lat, home_lng, 
                        branch['latitude'], branch['longitude']
                    )
                    branches_with_distance.append((distance, branch))
                
                branches_with_distance.sort(key=lambda x: x[0])
                chain_categories[brand_name] = [branch for _, branch in branches_with_distance[:MAX_CHAIN_BRANCHES_PER_BRAND]]
        
        # 创建TSP with Categories优化器
        optimizer = TSPWithCategoriesOptimizer(
            home_location_data, 
            chain_categories, 
            private_shops, 
            api_key, 
            city_param
        )
        
        # 执行优化（使用同步包装器）
        import asyncio
        try:
            # 尝试获取现有事件循环
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环正在运行，在线程池中执行
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, optimizer.optimize(mode, 60))
                    result = future.result(timeout=120)  # 2分钟超时
            else:
                result = loop.run_until_complete(optimizer.optimize(mode, 60))
        except RuntimeError:
            # 没有事件循环，创建新的
            result = asyncio.run(optimizer.optimize(mode, 60))
        
        logger.info(f"连锁店优化完成: {result.get('success', False)}")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"连锁店优化处理错误: {str(e)}")
        return jsonify({
            'message': 'Chain store optimization failed',
            'error': str(e) if app.debug else 'Contact support'
        }), 500

def search_chain_store_branches(api_key, brand_name, home_location, city, max_results=MAX_CHAIN_BRANCHES_PER_BRAND):
    """搜索连锁店分店"""
    try:
        logger.info(f"搜索连锁店分店: {brand_name} in {city}")
        
        # 构建搜索半径（基于城市大小调整）
        radius = 10000  # 默认10km半径
        
        # 使用POI搜索API
        location_str = f"{home_location['longitude']},{home_location['latitude']}"
        
        branches = search_poi(
            api_key, 
            brand_name, 
            city=city,
            location=location_str,
            radius=radius,
            max_results=max_results
        )
        
        if not branches:
            logger.warning(f"未找到 {brand_name} 的分店")
            return []
        
        # 转换为标准格式
        formatted_branches = []
        for branch in branches:
            # 修复：直接使用已解析的坐标字段
            latitude = branch.get('latitude')
            longitude = branch.get('longitude')
            
            if latitude is not None and longitude is not None:
                try:
                    formatted_branch = {
                        'id': branch.get('id', f"{brand_name}_{len(formatted_branches)}"),
                        'name': branch.get('name', brand_name),
                        'latitude': float(latitude),
                        'longitude': float(longitude),
                        'address': branch.get('address', ''),
                        'brand': brand_name,
                        'type': 'chain'
                    }
                    
                    # 验证坐标有效性
                    if formatted_branch['latitude'] != 0 and formatted_branch['longitude'] != 0:
                        formatted_branches.append(formatted_branch)
                except (ValueError, TypeError) as e:
                    logger.warning(f"分店坐标解析失败: {branch.get('name', 'Unknown')} - {e}")
                    continue
            else:
                logger.warning(f"分店缺少坐标信息: {branch.get('name', 'Unknown')}")
        
        logger.info(f"找到 {len(formatted_branches)} 家 {brand_name} 分店")
        return formatted_branches
        
    except Exception as e:
        logger.error(f"搜索连锁店分店失败: {str(e)}")
        return []

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

def process_route_optimization_threaded(executor, api_key, home_location_data, shops_data, mode, city_param, top_n, departure_time=None, algorithm_preference='adaptive'):
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
    # 智能构建距离矩阵（优先使用缓存，批量处理API调用）
    cost_matrix = [[None for _ in range(num_points)] for _ in range(num_points)]
    
    # 首先检查缓存，收集需要API调用的点对
    api_tasks = []
    cache_hits = 0
    
    for i in range(num_points):
        for j in range(i + 1, num_points):
            p1_lat, p1_lon = all_coords[i]
            p2_lat, p2_lon = all_coords[j]
            
            # 检查缓存
            if mode == "public_transit":
                cached_result = distance_cache.get(p1_lat, p1_lon, p2_lat, p2_lon, 'public_transit', city_param)
            else:
                cached_result = distance_cache.get(p1_lat, p1_lon, p2_lat, p2_lon, 'driving')
            
            if cached_result:
                cost_matrix[i][j] = cached_result
                cost_matrix[j][i] = cached_result
                cache_hits += 1
            else:
                # 需要API调用
                if mode == "public_transit":
                    task = executor.submit(
                        get_public_transit_segment_details,
                        api_key, p1_lat, p1_lon, p2_lat, p2_lon, city_param
                    )
                else:
                    task = executor.submit(
                        get_driving_route_segment_details,
                        api_key, p1_lat, p1_lon, p2_lat, p2_lon, 5, departure_time
                    )
                api_tasks.append((i, j, task))
    
    logger.info(f"缓存命中: {cache_hits}, API调用: {len(api_tasks)}")
    
    # 批量等待API调用完成
    for i, j, task in api_tasks:
        try:
            segment_details = task.result(timeout=30)  # 30秒超时
            if segment_details is None:
                if mode == "public_transit":
                    # 公交路线查找失败时，明确告诉用户这是因为没有找到公交路线
                    p1_lat, p1_lon = all_coords[i]
                    p2_lat, p2_lon = all_coords[j]
                    
                    # 首先尝试驾车路线作为备选方案
                    try:
                        driving_fallback = get_driving_route_segment_details(
                            api_key, p1_lat, p1_lon, p2_lat, p2_lon, 5, departure_time
                        )
                        if driving_fallback:
                            # 使用驾车路线但明确标注
                            segment_details = driving_fallback.copy()
                            segment_details["steps"] = [{
                                "type": "fallback",
                                "instruction": f"⚠️ 未找到公交路线，建议驾车前往：从{all_points_objects[i]['name']}到{all_points_objects[j]['name']}"
                            }]
                            segment_details["mode"] = "driving_fallback"
                            segment_details["is_fallback"] = True
                            segment_details["fallback_reason"] = "公交路线不可达"
                            logger.warning(f"公交路线查找失败，使用驾车路线作为备选: {all_points_objects[i]['name']} -> {all_points_objects[j]['name']}")
                        else:
                            raise Exception("驾车备选方案也失败")
                    except:
                        # 连驾车路线也获取失败，则使用最基本的估算
                        distance = calculate_haversine_distance(p1_lat, p1_lon, p2_lat, p2_lon)
                        travel_time = max(300, (distance/1000)/(40/3.6))  # 最少5分钟，按40km/h估算
                        
                        segment_details = {
                            "distance": int(distance),
                            "duration": int(travel_time),
                            "polyline": "",
                            "steps": [{
                                "type": "unavailable",
                                "instruction": f"❌ 该路段暂无可用路线信息：从{all_points_objects[i]['name']}到{all_points_objects[j]['name']}（直线距离估算：{distance/1000:.1f}公里）"
                            }],
                            "segments": [],
                            "cost": 0.0,
                            "walking_distance": 0,
                            "mode": "unavailable",
                            "is_fallback": True,
                            "fallback_reason": "路线信息不可用",
                            "nightflag": "0",
                            "railway_flag": "0"
                        }
                        logger.error(f"无法获取任何路线信息，使用直线距离估算: {all_points_objects[i]['name']} -> {all_points_objects[j]['name']}")
                    
                    # 不将估算/备选数据存储到缓存中，避免误导
                    # distance_cache.set(p1_lat, p1_lon, p2_lat, p2_lon, segment_details, 'public_transit', city_param)
                else:
                    raise Exception(f'Failed to get {mode} route details between {all_points_objects[i]["name"]} and {all_points_objects[j]["name"]}')
            else:
                # API成功返回数据，存储到缓存
                if mode == "public_transit":
                    distance_cache.set(all_coords[i][0], all_coords[i][1], all_coords[j][0], all_coords[j][1], segment_details, 'public_transit', city_param)
                else:
                    distance_cache.set(all_coords[i][0], all_coords[i][1], all_coords[j][0], all_coords[j][1], segment_details, 'driving')
            cost_matrix[i][j] = segment_details
            cost_matrix[j][i] = segment_details
        except Exception as e:
            logger.error(f"API调用失败 {i}->{j}: {e}")
            raise Exception(f'Route calculation failed between points {i} and {j}: {str(e)}')
    # 继续TSP计算...
    return complete_tsp_calculation(all_points_objects, cost_matrix, top_n, algorithm_preference)

def complete_tsp_calculation(all_points_objects, cost_matrix, top_n, algorithm_preference='adaptive'):
    """完成TSP计算并返回结果，使用改进的自适应优化算法"""
    shop_indices = list(range(1, len(all_points_objects)))
    total_stay_duration_val = sum(all_points_objects[shop_idx].get('stay_duration', 0) for shop_idx in shop_indices)
    
    if not shop_indices:
        # 处理只有家的情况
        return {
            "route_candidates": [create_single_point_route(all_points_objects[0])],
            "message": "No shops to visit. Only home location provided."
        }
    
    # 创建TSP优化器实例
    optimizer = TSPOptimizer(cost_matrix, all_points_objects)
    
    # 根据算法偏好选择优化策略
    try:
        if algorithm_preference == 'exact':
            best_routes, best_costs = optimizer._exact_tsp_solution(shop_indices)
        elif algorithm_preference == 'ortools' and ORTOOLS_AVAILABLE:
                            best_routes, best_costs = optimizer.ortools_solve(max_time_seconds=20)
        elif algorithm_preference == 'genetic':
            best_routes, best_costs = optimizer.genetic_algorithm_solve(population_size=30, generations=50)
        elif algorithm_preference == 'heuristic':
            best_routes, best_costs = optimizer._heuristic_tsp_solution(shop_indices)
        else:  # adaptive
                            best_routes, best_costs = optimizer.adaptive_solve(max_time_seconds=20)
        
        # 构建结果数据
        all_route_results = []
        
        # 处理时间优化的路线
        if 'time' in best_routes and best_routes['time']:
            for i, route_indices in enumerate(best_routes['time']):
                if route_indices is None:
                    continue
                    
                # 构建路线段信息
                route_segments = []
                total_distance = 0
                total_time = 0
                valid_route = True
                
                for j in range(len(route_indices) - 1):
                    u, v = route_indices[j], route_indices[j+1]
                    if cost_matrix[u][v] is None:
                        valid_route = False
                        break
                        
                    segment_info = cost_matrix[u][v]
                    total_distance += segment_info['distance']
                    total_time += segment_info['duration']
                    
                    # 构建路线段信息
                    segment_data = {
                        "from_name": all_points_objects[u]["name"],
                        "to_name": all_points_objects[v]["name"],
                        "from_id": all_points_objects[u]["id"],
                        "to_id": all_points_objects[v]["id"],
                        "distance": segment_info['distance'],
                        "duration": segment_info['duration'],
                        "polyline": segment_info['polyline'],
                        "steps": segment_info.get('steps', [])
                    }
                    
                    # 对于公交路线，添加完整的segments信息
                    if 'segments' in segment_info:
                        segment_data['transit_segments'] = segment_info['segments']
                        segment_data['mode'] = 'public_transit'
                    else:
                        segment_data['mode'] = 'driving'
                    
                    route_segments.append(segment_data)
                
                if valid_route:
                    optimized_order = [all_points_objects[idx] for idx in route_indices]
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
                        'optimization_type': 'time',
                        'is_optimized': True,
                        'rank': i + 1
                    })
        
        # 处理距离优化的路线
        if 'distance' in best_routes and best_routes['distance']:
            for i, route_indices in enumerate(best_routes['distance']):
                if route_indices is None:
                    continue
                    
                # 构建路线段信息
                route_segments = []
                total_distance = 0
                total_time = 0
                valid_route = True
                
                for j in range(len(route_indices) - 1):
                    u, v = route_indices[j], route_indices[j+1]
                    if cost_matrix[u][v] is None:
                        valid_route = False
                        break
                        
                    segment_info = cost_matrix[u][v]
                    total_distance += segment_info['distance']
                    total_time += segment_info['duration']
                    
                    # 构建路线段信息
                    segment_data = {
                        "from_name": all_points_objects[u]["name"],
                        "to_name": all_points_objects[v]["name"],
                        "from_id": all_points_objects[u]["id"],
                        "to_id": all_points_objects[v]["id"],
                        "distance": segment_info['distance'],
                        "duration": segment_info['duration'],
                        "polyline": segment_info['polyline'],
                        "steps": segment_info.get('steps', [])
                    }
                    
                    # 对于公交路线，添加完整的segments信息
                    if 'segments' in segment_info:
                        segment_data['transit_segments'] = segment_info['segments']
                        segment_data['mode'] = 'public_transit'
                    else:
                        segment_data['mode'] = 'driving'
                    
                    route_segments.append(segment_data)
                
                if valid_route:
                    optimized_order = [all_points_objects[idx] for idx in route_indices]
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
                        'optimization_type': 'distance',
                        'is_optimized': True,
                        'rank': i + 1
                    })
        
        if not all_route_results:
            raise Exception('Could not find any valid routes')
        
        # 生成候选路线
        route_candidates = generate_enhanced_route_candidates(all_route_results, top_n)
        
        # 确定实际使用的算法
        if algorithm_preference == 'exact':
            algorithm_used = "精确算法（暴力枚举）"
        elif algorithm_preference == 'ortools' and ORTOOLS_AVAILABLE:
            algorithm_used = "Or-Tools工业级优化器"
        elif algorithm_preference == 'genetic':
            algorithm_used = "遗传算法"
        elif algorithm_preference == 'heuristic':
            algorithm_used = "启发式算法+2-opt"
        else:
            num_shops = len(shop_indices)
            if num_shops <= 6:
                algorithm_used = "自适应选择：精确算法"
            elif num_shops <= 15 and ORTOOLS_AVAILABLE:
                algorithm_used = "自适应选择：Or-Tools"
            elif num_shops <= 25:
                algorithm_used = "自适应选择：遗传算法"
            else:
                algorithm_used = "自适应选择：启发式+2-opt"
        
        cache_stats = distance_cache.get_cache_stats()
        
        return {
            "route_candidates": route_candidates,
            "algorithm_used": algorithm_used,
            "cache_stats": cache_stats,
            "message": f"Successfully generated {len(route_candidates)} optimized route candidates using {algorithm_used}."
        }
        
    except Exception as e:
        logger.error(f"TSP优化过程中出错: {str(e)}")
        raise Exception(f'TSP optimization failed: {str(e)}')

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
    existing_permutations = set(route_result.get('permutation', tuple()) for route_result in routes_by_time)
    for i, route_result in enumerate(routes_by_distance):
        route_perm = route_result.get('permutation', tuple())
        if route_perm not in existing_permutations:
            candidate = route_result['route_data'].copy()
            candidate['optimization_type'] = 'distance'
            candidate['rank_in_category'] = i + 1
            candidate['distance_rank'] = i + 1
            route_candidates.append(candidate)
            existing_permutations.add(route_perm)
    return route_candidates[:top_n]

def generate_enhanced_route_candidates(all_route_results, top_n):
    """生成增强的候选路线列表，支持混合优化算法的结果"""
    route_candidates = []
    
    # 分别处理时间优化和距离优化的结果
    time_routes = [r for r in all_route_results if r.get('optimization_type') == 'time']
    distance_routes = [r for r in all_route_results if r.get('optimization_type') == 'distance']
    
    # 按时间优化的路线
    for i, route_result in enumerate(time_routes):
        candidate = route_result['route_data'].copy()
        candidate['optimization_type'] = 'time'
        candidate['rank_in_category'] = i + 1
        candidate['time_rank'] = i + 1
        candidate['is_optimized'] = route_result.get('is_optimized', False)
        route_candidates.append(candidate)
    
    # 按距离优化的路线（避免重复）
    existing_routes = set()
    for route in time_routes:
        # 使用路线的店铺访问顺序作为唯一标识
        order_key = tuple(p['id'] for p in route['route_data']['optimized_order'])
        existing_routes.add(order_key)
    
    for i, route_result in enumerate(distance_routes):
        order_key = tuple(p['id'] for p in route_result['route_data']['optimized_order'])
        if order_key not in existing_routes:
            candidate = route_result['route_data'].copy()
            candidate['optimization_type'] = 'distance'
            candidate['rank_in_category'] = i + 1
            candidate['distance_rank'] = i + 1
            candidate['is_optimized'] = route_result.get('is_optimized', False)
            route_candidates.append(candidate)
            existing_routes.add(order_key)
    
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

@app.route('/api/cache/stats', methods=['GET'])
def get_cache_stats():
    """获取缓存统计信息"""
    try:
        stats = distance_cache.get_cache_stats()
        return jsonify({
            'cache_stats': stats,
            'message': 'Cache statistics retrieved successfully.'
        }), 200
    except Exception as e:
        logger.error(f"获取缓存统计信息失败: {str(e)}")
        return jsonify({'message': 'Failed to get cache statistics.'}), 500

@app.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    """清理过期缓存"""
    try:
        old_size = len(distance_cache.cache)
        distance_cache.clear_expired()
        new_size = len(distance_cache.cache)
        
        return jsonify({
            'message': f'Expired cache cleared. Removed {old_size - new_size} expired entries.',
            'entries_before': old_size,
            'entries_after': new_size
        }), 200
    except Exception as e:
        logger.error(f"清理缓存失败: {str(e)}")
        return jsonify({'message': 'Failed to clear cache.'}), 500

@app.route('/api/cache/clear-all', methods=['POST'])
def clear_all_cache():
    """清空所有缓存（谨慎使用）"""
    try:
        old_size = len(distance_cache.cache)
        distance_cache.cache.clear()
        distance_cache.hit_count = 0
        distance_cache.miss_count = 0
        
        return jsonify({
            'message': f'All cache cleared. Removed {old_size} entries.',
            'entries_removed': old_size
        }), 200
    except Exception as e:
        logger.error(f"清空缓存失败: {str(e)}")
        return jsonify({'message': 'Failed to clear all cache.'}), 500

@app.route('/api/cache/optimize', methods=['POST'])
def optimize_cache():
    """优化缓存：清理过期条目，压缩存储"""
    try:
        result = distance_cache.optimize_cache()
        
        return jsonify({
            'message': 'Cache optimization completed.',
            'optimization_result': result
        }), 200
    except Exception as e:
        logger.error(f"缓存优化失败: {str(e)}")
        return jsonify({'message': 'Failed to optimize cache.'}), 500

@app.route('/api/cache/clear-fallback', methods=['POST'])
def clear_fallback_cache():
    """清除所有备选路线和估算数据的缓存"""
    try:
        cleared_count = 0
        keys_to_remove = []
        
        # 查找所有包含备选数据的缓存条目
        for key, value in distance_cache.cache.items():
            if isinstance(value, dict) and 'data' in value:
                data = value['data']
                if (data.get('is_fallback') or 
                    data.get('mode') in ['driving_fallback', 'unavailable'] or
                    any(step.get('type') in ['fallback', 'unavailable'] for step in data.get('steps', []))):
                    keys_to_remove.append(key)
                    cleared_count += 1
        
        # 删除找到的备选数据缓存
        for key in keys_to_remove:
            del distance_cache.cache[key]
        
        logger.info(f"已清除 {cleared_count} 个备选路线缓存条目")
        return jsonify({
            'message': f'Cleared {cleared_count} fallback route cache entries',
            'cleared_items': cleared_count,
            'cache_stats': distance_cache.get_cache_stats()
        }), 200
    except Exception as e:
        logger.error(f"清除备选缓存失败: {e}")
        return jsonify({'message': f'Failed to clear fallback cache: {str(e)}'}), 500

@app.route('/api/algorithms/info', methods=['GET'])
def get_algorithms_info():
    """获取可用算法信息"""
    try:
        algorithms_info = {
            'available_algorithms': {
                'exact': {
                    'name': '精确算法',
                    'description': '暴力枚举所有可能路径，保证全局最优',
                    'time_complexity': 'O(n!)',
                    'recommended_for': '≤6个店铺',
                    'available': True
                },
                'ortools': {
                    'name': 'Or-Tools工业级优化器',
                    'description': 'Google开源的约束求解器，工业级性能',
                    'time_complexity': 'O(n²log n)',
                    'recommended_for': '7-15个店铺',
                    'available': ORTOOLS_AVAILABLE
                },
                'genetic': {
                    'name': '遗传算法',
                    'description': '模拟生物进化的智能优化算法',
                    'time_complexity': 'O(g×p×n²)',
                    'recommended_for': '16-25个店铺',
                    'available': True
                },
                'heuristic': {
                    'name': '启发式算法+2-opt',
                    'description': '最近邻+局部搜索优化',
                    'time_complexity': 'O(n²)',
                    'recommended_for': '>25个店铺',
                    'available': True
                },
                'adaptive': {
                    'name': '自适应算法选择',
                    'description': '根据问题规模自动选择最适合的算法',
                    'time_complexity': '动态选择',
                    'recommended_for': '任意规模',
                    'available': True
                }
            },
            'ortools_status': ORTOOLS_AVAILABLE,
            'current_limits': {
                'max_shops_optimization': MAX_SHOPS_FOR_OPTIMIZATION,
                'max_shops_exact': MAX_SHOPS_FOR_EXACT_TSP
            }
        }
        
        return jsonify(algorithms_info), 200
    except Exception as e:
        logger.error(f"获取算法信息失败: {str(e)}")
        return jsonify({'message': 'Failed to get algorithms info.'}), 500

@app.route('/api/algorithms/benchmark', methods=['POST'])
def benchmark_algorithms():
    """算法性能测试接口 - 使用真实地理位置数据"""
    try:
        data = request.get_json()
        test_points = data.get('test_points', 8)  # 默认测试8个点
        city = data.get('city', '北京市')  # 测试城市
        use_real_data = data.get('use_real_data', True)  # 是否使用真实数据
        
        if test_points > 12:
            return jsonify({'message': 'Test points limited to 12 for safety.'}), 400
        
        api_key = app.config.get('AMAP_API_KEY')
        if not api_key:
            return jsonify({'message': 'Amap API key not configured on server.'}), 500
        
        # 创建测试点对象
        test_points_objects = []
        cost_matrix = []
        
        if use_real_data:
            # 使用真实地理位置数据 - 北京市知名地点
            real_locations = [
                {"name": "天安门广场", "lat": 39.903924, "lng": 116.391454},
                {"name": "故宫博物院", "lat": 39.916668, "lng": 116.397068},
                {"name": "王府井步行街", "lat": 39.909425, "lng": 116.417482},
                {"name": "三里屯太古里", "lat": 39.936716, "lng": 116.455921},
                {"name": "颐和园", "lat": 39.999302, "lng": 116.275290},
                {"name": "北京大学", "lat": 39.989584, "lng": 116.316835},
                {"name": "鸟巢(国家体育场)", "lat": 39.993415, "lng": 116.397827},
                {"name": "什刹海", "lat": 39.942050, "lng": 116.381476},
                {"name": "天坛公园", "lat": 39.881606, "lng": 116.407395},
                {"name": "北京南站", "lat": 39.865698, "lng": 116.378569},
                {"name": "首都机场", "lat": 40.080111, "lng": 116.603250},
                {"name": "中关村", "lat": 39.959920, "lng": 116.298056}
            ]
            
            # 选择指定数量的测试点
            selected_locations = real_locations[:test_points]
            
            for i, loc in enumerate(selected_locations):
                test_points_objects.append({
                    'id': f'point_{i}',
                    'name': loc['name'] if i > 0 else f"起点({loc['name']})",
                    'latitude': loc['lat'],
                    'longitude': loc['lng'],
                    'stay_duration': 0 if i == 0 else 300
                })
            
            # 使用真实的距离矩阵（调用高德API）
            logger.info(f"正在获取 {test_points} 个真实地点之间的距离数据...")
            cost_matrix = [[None for _ in range(test_points)] for _ in range(test_points)]
            
            # 批量获取距离数据
            api_calls = []
            with ThreadPoolExecutor(max_workers=3) as executor:
                for i in range(test_points):
                    for j in range(i + 1, test_points):
                        loc1 = selected_locations[i]
                        loc2 = selected_locations[j]
                        
                        future = executor.submit(
                            get_driving_route_segment_details,
                            api_key, loc1['lat'], loc1['lng'], loc2['lat'], loc2['lng']
                        )
                        api_calls.append((i, j, future))
                
                # 收集结果
                for i, j, future in api_calls:
                    try:
                        result = future.result(timeout=30)
                        if result:
                            cost_matrix[i][j] = result
                            cost_matrix[j][i] = result
                        else:
                            # 如果API调用失败，使用估算距离
                            loc1 = selected_locations[i]
                            loc2 = selected_locations[j]
                            estimated_distance = calculate_haversine_distance(
                                loc1['lat'], loc1['lng'], loc2['lat'], loc2['lng']
                            )
                            fallback_data = {
                                'duration': int(estimated_distance * 3),  # 估算时间：每公里3分钟
                                'distance': int(estimated_distance * 1000),
                                'polyline': '',
                                'steps': []
                            }
                            cost_matrix[i][j] = fallback_data
                            cost_matrix[j][i] = fallback_data
                    except Exception as e:
                        logger.warning(f"获取距离数据失败 {i}-{j}: {e}")
                        # 使用更简单的回退方案
                        fallback_data = {
                            'duration': 1800,  # 30分钟
                            'distance': 10000,  # 10公里
                            'polyline': '',
                            'steps': []
                        }
                        cost_matrix[i][j] = fallback_data
                        cost_matrix[j][i] = fallback_data
        else:
            # 使用模拟数据（改进的生成方式）
            logger.info(f"使用模拟数据生成 {test_points} 个测试点")
            import random
            import math
            
            # 基于北京市中心的模拟坐标
            center_lat, center_lng = 39.904989, 116.405285
            
            for i in range(test_points):
                # 在中心点周围随机生成点，模拟真实的地理分布
                angle = random.uniform(0, 2 * math.pi)
                radius = random.uniform(0.01, 0.1)  # 大约1-10公里范围
                
                lat = center_lat + radius * math.cos(angle)
                lng = center_lng + radius * math.sin(angle)
                
                test_points_objects.append({
                    'id': f'point_{i}',
                    'name': f'Point {i}' if i > 0 else 'Home',
                    'latitude': lat,
                    'longitude': lng,
                    'stay_duration': 0 if i == 0 else 300
                })
            
            # 生成基于距离的模拟成本矩阵
            cost_matrix = [[None for _ in range(test_points)] for _ in range(test_points)]
            for i in range(test_points):
                for j in range(i + 1, test_points):
                    distance_km = calculate_haversine_distance(
                        test_points_objects[i]['latitude'], test_points_objects[i]['longitude'],
                        test_points_objects[j]['latitude'], test_points_objects[j]['longitude']
                    )
                    
                    # 基于真实距离计算时间和成本
                    duration = max(300, int(distance_km * 3 * 60))  # 每公里3分钟，最少5分钟
                    distance_m = int(distance_km * 1000)
                    
                    cost_data = {
                        'duration': duration,
                        'distance': distance_m,
                        'polyline': '',
                        'steps': []
                    }
                    cost_matrix[i][j] = cost_data
                    cost_matrix[j][i] = cost_data
        
        # 创建优化器并测试不同算法
        optimizer = TSPOptimizer(cost_matrix, test_points_objects)
        benchmark_results = {}
        
        # 测试精确算法
        if test_points <= 6:
            start_time = time.time()
            try:
                exact_result, exact_costs = optimizer._exact_tsp_solution(list(range(1, test_points)))
                exact_time = time.time() - start_time
                benchmark_results['exact'] = {
                    'execution_time': round(exact_time, 4),
                    'success': True,
                    'route_found': exact_result is not None,
                    'best_time_cost': exact_costs.get('time') if exact_costs else None,
                    'best_distance_cost': exact_costs.get('distance') if exact_costs else None
                }
            except Exception as e:
                benchmark_results['exact'] = {
                    'execution_time': 0,
                    'success': False,
                    'error': str(e)
                }
        
        # 测试Or-Tools
        if ORTOOLS_AVAILABLE:
            start_time = time.time()
            try:
                ortools_result, _ = optimizer.ortools_solve(max_time_seconds=5)
                ortools_time = time.time() - start_time
                benchmark_results['ortools'] = {
                    'execution_time': round(ortools_time, 4),
                    'success': True,
                    'route_found': ortools_result is not None
                }
            except Exception as e:
                benchmark_results['ortools'] = {
                    'execution_time': 0,
                    'success': False,
                    'error': str(e)
                }
        
        # 测试遗传算法
        start_time = time.time()
        try:
            genetic_result, _ = optimizer.genetic_algorithm_solve(population_size=20, generations=30)
            genetic_time = time.time() - start_time
            benchmark_results['genetic'] = {
                'execution_time': round(genetic_time, 4),
                'success': True,
                'route_found': genetic_result is not None
            }
        except Exception as e:
            benchmark_results['genetic'] = {
                'execution_time': 0,
                'success': False,
                'error': str(e)
            }
        
        # 测试启发式算法
        start_time = time.time()
        try:
            heuristic_result, _ = optimizer._heuristic_tsp_solution(list(range(1, test_points)))
            heuristic_time = time.time() - start_time
            benchmark_results['heuristic'] = {
                'execution_time': round(heuristic_time, 4),
                'success': True,
                'route_found': heuristic_result is not None
            }
        except Exception as e:
            benchmark_results['heuristic'] = {
                'execution_time': 0,
                'success': False,
                'error': str(e)
            }
        
        # 测试自适应算法
        start_time = time.time()
        try:
            adaptive_result, _ = optimizer.adaptive_solve(max_time_seconds=10)
            adaptive_time = time.time() - start_time
            benchmark_results['adaptive'] = {
                'execution_time': round(adaptive_time, 4),
                'success': True,
                'route_found': adaptive_result is not None
            }
        except Exception as e:
            benchmark_results['adaptive'] = {
                'execution_time': 0,
                'success': False,
                'error': str(e)
            }
        
        return jsonify({
            'test_configuration': {
                'test_points': test_points,
                'city': city,
                'use_real_data': use_real_data,
                'matrix_size': f'{test_points}x{test_points}',
                'test_locations': [p['name'] for p in test_points_objects]
            },
            'benchmark_results': benchmark_results,
            'message': f'Benchmark completed for {test_points} points.'
        }), 200
        
    except Exception as e:
        logger.error(f"算法性能测试失败: {str(e)}")
        return jsonify({'message': f'Benchmark failed: {str(e)}'}), 500

# get_driving_route function removed - functionality integrated into get_driving_route_segment_details

# --- Database Initialization ---
def init_db():
    with app.app_context():
        db.create_all()
    print("Database initialized!")

# Initialize database when the app starts
init_db()

# 在search_chain_store_branches函数之后添加新函数

def classify_and_search_shops(api_key, shop_names, home_location, city):
    """
    智能分类和搜索店铺
    根据搜索结果数量自动判断店铺类型：
    - 搜索结果 > 1：连锁店铺，使用所有搜索结果
    - 搜索结果 = 1：私人店铺，直接使用该结果
    - 搜索结果 = 0：未找到，记录错误
    
    Args:
        api_key: 高德API密钥
        shop_names: 店铺名称列表
        home_location: 用户家位置
        city: 城市名称
        
    Returns:
        dict: {
            'chain_categories': {brand_name: [branches]},
            'private_shops': [shop_objects],
            'not_found': [shop_names]
        }
    """
    result = {
        'chain_categories': {},
        'private_shops': [],
        'not_found': []
    }
    
    logger.info(f"开始智能分类搜索 {len(shop_names)} 个店铺")
    
    for shop_name in shop_names:
        try:
            logger.info(f"搜索店铺: {shop_name}")
            
            # 搜索店铺
            location_str = f"{home_location['longitude']},{home_location['latitude']}"
            search_results = search_poi(
                api_key,
                shop_name,
                city=city,
                location=location_str,
                radius=15000,  # 15km半径
                max_results=25
            )
            
            if not search_results:
                logger.warning(f"未找到店铺: {shop_name}")
                result['not_found'].append(shop_name)
                continue
            
            logger.info(f"店铺 {shop_name} 搜索到 {len(search_results)} 个结果")
            
            if len(search_results) == 1:
                # 私人店铺（唯一结果）
                shop = search_results[0]
                latitude = shop.get('latitude')
                longitude = shop.get('longitude')
                
                if latitude is not None and longitude is not None:
                    try:
                        formatted_shop = {
                            'id': shop.get('id', f"private_{shop_name}_{len(result['private_shops'])}"),
                            'name': shop.get('name', shop_name),
                            'latitude': float(latitude),
                            'longitude': float(longitude),
                            'address': shop.get('address', ''),
                            'type': 'private'
                        }
                        
                        # 验证坐标有效性
                        if formatted_shop['latitude'] != 0 and formatted_shop['longitude'] != 0:
                            result['private_shops'].append(formatted_shop)
                            logger.info(f"归类为私人店铺: {shop_name}")
                        else:
                            logger.warning(f"店铺 {shop_name} 坐标无效")
                            result['not_found'].append(shop_name)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"店铺 {shop_name} 坐标解析失败: {e}")
                        result['not_found'].append(shop_name)
                else:
                    logger.warning(f"店铺 {shop_name} 缺少坐标信息")
                    result['not_found'].append(shop_name)
                    
            else:
                # 连锁店铺（多个结果）
                logger.info(f"归类为连锁店铺: {shop_name} (找到 {len(search_results)} 家分店)")
                logger.info(f"搜索结果样本: {search_results[0] if search_results else 'None'}")
                
                # 处理连锁店分店
                formatted_branches = []
                for branch in search_results:
                    # 修复：直接使用已解析的坐标字段
                    latitude = branch.get('latitude')
                    longitude = branch.get('longitude')
                    
                    # 添加调试日志
                    logger.info(f"处理分店: {branch.get('name', 'Unknown')}, latitude: {latitude}, longitude: {longitude}")
                    
                    if latitude is not None and longitude is not None:
                        try:
                            latitude = float(latitude)
                            longitude = float(longitude)
                            
                            if latitude != 0 and longitude != 0:
                                # 计算距离用于排序
                                distance = calculate_haversine_distance(
                                    home_location['latitude'], home_location['longitude'],
                                    latitude, longitude
                                )
                                
                                formatted_branch = {
                                    'id': branch.get('id', f"chain_{shop_name}_{len(formatted_branches)}"),
                                    'name': branch.get('name', shop_name),
                                    'latitude': latitude,
                                    'longitude': longitude,
                                    'address': branch.get('address', ''),
                                    'brand': shop_name,
                                    'type': 'chain',
                                    'distance_to_home': distance
                                }
                                formatted_branches.append(formatted_branch)
                                logger.info(f"成功添加分店: {branch.get('name')} ({latitude}, {longitude})")
                        except (ValueError, TypeError) as e:
                            logger.warning(f"分店坐标解析失败: {branch.get('name', 'Unknown')} - {e}")
                            continue
                    else:
                        logger.warning(f"分店缺少坐标信息: {branch.get('name', 'Unknown')} - latitude: {latitude}, longitude: {longitude}")
                        continue
                
                if formatted_branches:
                    # 按距离排序，选择最近的分店
                    formatted_branches.sort(key=lambda x: x['distance_to_home'])
                    
                    # 限制分店数量
                    if len(formatted_branches) > MAX_CHAIN_BRANCHES_PER_BRAND:
                        logger.info(f"连锁店 {shop_name} 分店过多，限制为 {MAX_CHAIN_BRANCHES_PER_BRAND} 家最近的")
                        formatted_branches = formatted_branches[:MAX_CHAIN_BRANCHES_PER_BRAND]
                    
                    # 移除距离字段（仅用于排序）
                    for branch in formatted_branches:
                        branch.pop('distance_to_home', None)
                    
                    result['chain_categories'][shop_name] = formatted_branches
                    logger.info(f"连锁店 {shop_name} 成功添加 {len(formatted_branches)} 家分店")
                else:
                    logger.warning(f"连锁店 {shop_name} 没有有效分店")
                    result['not_found'].append(shop_name)
                    
        except Exception as e:
            logger.error(f"搜索店铺 {shop_name} 时发生错误: {str(e)}")
            result['not_found'].append(shop_name)
    
    logger.info(f"智能分类完成 - 连锁店: {len(result['chain_categories'])}, 私人店: {len(result['private_shops'])}, 未找到: {len(result['not_found'])}")
    return result

@app.route('/api/route/smart-optimize', methods=['POST'])
def smart_optimize_route():
    """
    全新的智能路线优化接口
    用户只需提供店铺名称，系统自动分类并优化
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'Request body must be JSON.'}), 400
        
        # 验证必要字段
        home_location_data = data.get('home_location')
        if not home_location_data or 'latitude' not in home_location_data or 'longitude' not in home_location_data:
            return jsonify({'message': 'Missing or invalid home_location'}), 400
        
        shop_names = data.get('shop_names', [])
        if not shop_names or not isinstance(shop_names, list):
            return jsonify({'message': 'shop_names must be a non-empty list'}), 400
        
        mode = data.get('mode', 'driving')
        city_param = data.get('city')
        api_key = app.config.get('AMAP_API_KEY')
        
        if not api_key:
            return jsonify({'message': 'Amap API key not configured on server.'}), 500
        
        if not city_param:
            return jsonify({'message': 'City parameter is required'}), 400
        
        logger.info(f"收到智能优化请求: {len(shop_names)} 个店铺, 城市: {city_param}")
        
        # 智能分类和搜索店铺
        classification_result = classify_and_search_shops(
            api_key, shop_names, home_location_data, city_param
        )
        
        chain_categories = classification_result['chain_categories']
        private_shops = classification_result['private_shops']
        not_found = classification_result['not_found']
        
        # 如果是预览模式，只返回分类结果
        if data.get('preview_only', False):
            return jsonify({
                'success': True,
                'classification_summary': {
                    'chain_stores': len(chain_categories),
                    'private_shops': len(private_shops),
                    'not_found': len(not_found),
                    'chain_store_details': {brand: len(branches) for brand, branches in chain_categories.items()}
                },
                'chain_categories': chain_categories,
                'private_shops': private_shops,
                'not_found': not_found,
                'preview_mode': True
            })
        
        # 检查是否有有效店铺
        total_valid_shops = len(chain_categories) + len(private_shops)
        if total_valid_shops == 0:
            return jsonify({
                'success': False,
                'message': '没有找到有效的店铺',
                'not_found': not_found
            }), 400
        
        # 如果只有私人店铺，使用传统TSP算法
        if len(chain_categories) == 0:
            logger.info("只有私人店铺，使用传统TSP算法")
            
            # 构建传统请求格式
            traditional_request = {
                'home_location': home_location_data,
                'shops': private_shops,
                'mode': mode,
                'city': city_param,
                'algorithm': 'adaptive'
            }
            
            # 使用现有的路线优化逻辑
            with ThreadPoolExecutor(max_workers=3) as executor:
                result = process_route_optimization_threaded(
                    executor, api_key, home_location_data, private_shops, 
                    mode, city_param, 10, None, 'adaptive'
                )
            
            return jsonify({
                'success': True,
                'result_type': 'traditional_tsp',
                'classification_summary': {
                    'chain_stores': 0,
                    'private_shops': len(private_shops),
                    'not_found': len(not_found)
                },
                **result
            })
        
        # 使用TSP with Categories算法
        logger.info(f"使用TSP with Categories算法: {len(chain_categories)} 个连锁品牌")
        
        optimizer = TSPWithCategoriesOptimizer(
            home_location_data,
            chain_categories,
            private_shops,
            api_key,
            city_param
        )
        
        # 执行优化
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, optimizer.optimize(mode, 120))
                    optimization_result = future.result(timeout=180)  # 3分钟超时
            else:
                optimization_result = loop.run_until_complete(optimizer.optimize(mode, 120))
        except RuntimeError:
            optimization_result = asyncio.run(optimizer.optimize(mode, 120))
        
        # 添加分类摘要信息
        optimization_result['classification_summary'] = {
            'chain_stores': len(chain_categories),
            'private_shops': len(private_shops),
            'not_found': len(not_found),
            'chain_store_details': {brand: len(branches) for brand, branches in chain_categories.items()}
        }
        optimization_result['result_type'] = 'tsp_with_categories'
        
        if not_found:
            optimization_result['warnings'] = [f"未找到以下店铺: {', '.join(not_found)}"]
        
        logger.info(f"智能优化完成: {optimization_result.get('success', False)}")
        return jsonify(optimization_result)
        
    except Exception as e:
        logger.error(f"智能路线优化失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Smart route optimization failed',
            'error': str(e) if app.debug else 'Contact support'
        }), 500

@app.route('/api/route/multi-candidates', methods=['POST'])
def generate_multiple_route_candidates():
    """
    生成多个路线候选方案接口
    专门用于处理连锁店铺的多种分店组合，按时间和距离分别返回前5个候选路线
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'Request body must be JSON.'}), 400
        
        # 验证必要字段
        home_location_data = data.get('home_location')
        if not home_location_data or 'latitude' not in home_location_data or 'longitude' not in home_location_data:
            return jsonify({'message': 'Missing or invalid home_location'}), 400
        
        shop_names = data.get('shop_names', [])
        if not shop_names or not isinstance(shop_names, list):
            return jsonify({'message': 'shop_names must be a non-empty list'}), 400
        
        mode = data.get('mode', 'driving')
        city_param = data.get('city')
        max_candidates = data.get('max_candidates', 5)  # 默认5个候选
        api_key = app.config.get('AMAP_API_KEY')
        
        if not api_key:
            return jsonify({'message': 'Amap API key not configured on server.'}), 500
        
        if not city_param:
            return jsonify({'message': 'City parameter is required'}), 400
        
        logger.info(f"收到多候选路线请求: {len(shop_names)} 个店铺, 最多 {max_candidates} 个候选")
        
        # 智能分类和搜索店铺
        classification_result = classify_and_search_shops(
            api_key, shop_names, home_location_data, city_param
        )
        
        chain_categories = classification_result['chain_categories']
        private_shops = classification_result['private_shops']
        not_found = classification_result['not_found']
        
        # 检查是否有有效店铺
        total_valid_shops = len(chain_categories) + len(private_shops)
        if total_valid_shops == 0:
            return jsonify({
                'success': False,
                'message': '没有找到有效的店铺',
                'not_found': not_found
            }), 400
        
        # 创建增强的TSP优化器
        optimizer = TSPWithCategoriesOptimizer(
            home_location_data,
            chain_categories,
            private_shops,
            api_key,
            city_param
        )
        
        # 执行优化
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, optimizer.optimize(mode, 120))
                    optimization_result = future.result(timeout=180)
            else:
                optimization_result = loop.run_until_complete(optimizer.optimize(mode, 120))
        except RuntimeError:
            optimization_result = asyncio.run(optimizer.optimize(mode, 120))
        
        if not optimization_result.get('success'):
            return jsonify({
                'success': False,
                'message': '路线优化失败',
                'error': optimization_result.get('error', 'Unknown error')
            }), 500
        
        # 提取候选路线
        route_candidates = optimization_result.get('route_candidates', {})
        
        # 构建响应
        response = {
            'success': True,
            'total_candidates': optimization_result.get('total_candidates', 0),
            'classification_summary': {
                'chain_stores': len(chain_categories),
                'private_shops': len(private_shops),
                'not_found': len(not_found),
                'chain_store_details': {brand: len(branches) for brand, branches in chain_categories.items()}
            },
            'route_candidates': {
                'by_time_optimized': route_candidates.get('by_time', [])[:max_candidates],
                'by_distance_optimized': route_candidates.get('by_distance', [])[:max_candidates],
            },
            'optimization_summary': optimization_result.get('summary', {}),
            'message': f'成功生成 {len(route_candidates.get("all", []))} 个路线候选，按时间和距离分别排序'
        }
        
        if not_found:
            response['warnings'] = [f"未找到以下店铺: {', '.join(not_found)}"]
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"多候选路线生成失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Multiple route candidates generation failed',
            'error': str(e) if app.debug else 'Contact support'
        }), 500

# --- User City Preference Endpoints ---
@app.route('/api/user/city-preference', methods=['GET', 'POST'])
@login_required
def city_preference():
    if request.method == 'POST':
        data = request.get_json()
        province = data.get('province')
        city = data.get('city')
        
        logger.info(f"保存用户城市偏好: province={province}, city={city}")
        
        # 更新用户城市偏好
        current_user.preferred_province = province
        current_user.preferred_city = city
        db.session.commit()
        
        return jsonify({
            'message': 'City preference updated successfully',
            'preferred_province': current_user.preferred_province,
            'preferred_city': current_user.preferred_city
        }), 200
    
    # GET request
    else:
        return jsonify({
            'preferred_province': current_user.preferred_province,
            'preferred_city': current_user.preferred_city
        }), 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # Note: Binding to '0.0.0.0' is crucial for Docker
    app.run(host='0.0.0.0', port=5000, debug=True)
