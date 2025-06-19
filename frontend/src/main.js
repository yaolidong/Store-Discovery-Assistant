const { createApp } = Vue;
const { createRouter, createWebHashHistory } = VueRouter;
const Login = {
  template: `
    <div>
      <h2>Login</h2>
      <form @submit.prevent="loginUser">
        <div>
          <label for="username">Username:</label>
          <input type="text" id="username" v-model="username" required>
        </div>
        <div>
          <label for="password">Password:</label>
          <input type="password" id="password" v-model="password" required>
        </div>
        <button type="submit">Login</button>
      </form>
      <p v-if="errorMessage">{{ errorMessage }}</p>
      <p>Don't have an account? <router-link to="/register">Register here</router-link></p>
    </div>
  `,
  data() {
    return {
      username: '',
      password: '',
      showDebugInfo: false, // 是否显示调试信息
      errorMessage: ''
    };
  },
  methods: {
    async loginUser() {
      this.errorMessage = '';
      try {
        const response = await axios.post('/api/login', {
          username: this.username,
          password: this.password
        });
        // Store token properly if backend sends one, e.g., response.data.token
        localStorage.setItem('userToken', response.data.token || 'fakeToken');
        this.$router.push('/'); // Redirect first
        // Show notification after navigation
        this.$nextTick(() => {
          // Find and use notification component if available
          setTimeout(() => {
            const app = document.querySelector('#app').__vueParentComponent;
            if (app && app.ctx && app.ctx.$refs && app.ctx.$refs.notification) {
              app.ctx.$refs.notification.success('登录成功！');
            }
          }, 100);
        });
      } catch (error) {
        console.error('Login error:', error);
        if (error.response) {
          // 服务器响应了，但状态码不在2xx范围内
          this.errorMessage = error.response.data.message || '登录失败，请检查用户名和密码';
        } else if (error.request) {
          // 请求已发出，但没有收到响应
          this.errorMessage = '无法连接到服务器，请检查网络连接或稍后重试';
        } else {
          // 请求配置出错
          this.errorMessage = '登录请求出错，请稍后重试';
        }
      }
    }
  }
};

const Register = {
  template: `
    <div>
      <h2>Register</h2>
      <form @submit.prevent="registerUser">
        <div>
          <label for="username">Username:</label>
          <input type="text" id="username" v-model="username" required>
        </div>
        <div>
          <label for="password">Password:</label>
          <input type="password" id="password" v-model="password" required>
        </div>
        <button type="submit">Register</button>
      </form>
      <p v-if="successMessage">{{ successMessage }}</p>
      <p v-if="errorMessage">{{ errorMessage }}</p>
      <p>Already have an account? <router-link to="/login">Login here</router-link></p>
    </div>
  `,
  data() {
    return {
      username: '',
      password: '',
      successMessage: '',
      errorMessage: ''
    };
  },
  methods: {
    async registerUser() {
      this.successMessage = '';
      this.errorMessage = '';
      try {
        const response = await axios.post('/api/register', {
          username: this.username,
          password: this.password
        });
        this.successMessage = response.data.message;
        this.$router.push('/login');
        // Show notification after navigation
        this.$nextTick(() => {
          setTimeout(() => {
            const app = document.querySelector('#app').__vueParentComponent;
            if (app && app.ctx && app.ctx.$refs && app.ctx.$refs.notification) {
              app.ctx.$refs.notification.success('注册成功！请登录');
            }
          }, 100);
        });
      } catch (error) {
        this.errorMessage = (error.response && error.response.data && error.response.data.message) || 'Registration failed. Please try again.';
        console.error('Registration error:', error);
      }
    }
  }
};

// 自定义通知组件
const NotificationComp = {
  name: 'Notification',
  template: `
    <div v-if="notifications.length > 0" class="notification-container">
      <div 
        v-for="notification in notifications" 
        :key="notification.id"
        :class="['notification', notification.type]"
        @click="removeNotification(notification.id)"
      >
        <div class="notification-icon">
          <span v-if="notification.type === 'success'">✓</span>
          <span v-else-if="notification.type === 'error'">✗</span>
          <span v-else-if="notification.type === 'warning'">⚠</span>
          <span v-else>ℹ</span>
        </div>
        <div class="notification-content">
          <div class="notification-title" v-if="notification.title">{{ notification.title }}</div>
          <div class="notification-message">{{ notification.message }}</div>
        </div>
        <div class="notification-close">&times;</div>
      </div>
    </div>
  `,
  data() {
    return {
      notifications: []
    };
  },
  methods: {
    show(message, type = 'info', title = '', duration = 4000) {
      const id = Date.now();
      const notification = { id, message, type, title };
      
      this.notifications.push(notification);
      
      if (duration > 0) {
        setTimeout(() => {
          this.removeNotification(id);
        }, duration);
      }
      
      return id;
    },
    
    removeNotification(id) {
      const index = this.notifications.findIndex(n => n.id === id);
      if (index > -1) {
        this.notifications.splice(index, 1);
      }
    },
    
    success(message, title = '成功') {
      return this.show(message, 'success', title);
    },
    
    error(message, title = '错误') {
      return this.show(message, 'error', title, 6000);
    },
    
    warning(message, title = '警告') {
      return this.show(message, 'warning', title, 5000);
    },
    
    info(message, title = '提示') {
      return this.show(message, 'info', title);
    }
  }
};

const MapDisplayComp = {
  name: 'MapDisplay',
  template: `<div id="map-container-js" style="width: 100%; height: 500px; border: 1px solid #ccc; border-radius: 8px;"></div>`,
  data() {
    return {
      map: null,
      markers: [],
      driving: null,
      homeMarker: null,
      shopMarkers: [],
      isInitialized: false,
      isInitializing: false,
      initRetryCount: 0,
      maxInitRetries: 5
    };
  },
  
  async mounted() {
    await this.initializeMap();
  },
  
  methods: {
    // 改进的地图初始化方法
    async initializeMap() {
      if (this.isInitializing || this.isInitialized) {
        return;
      }
      
      this.isInitializing = true;
      
      try {
        // 等待高德地图API加载
        await this.waitForAmapAPI();
        
        // 初始化地图
        this.map = new AMap.Map('map-container-js', {
          zoom: 11,
          center: [116.397428, 39.90923],
          resizeEnable: true,
          mapStyle: 'amap://styles/normal',
          features: ['bg', 'point', 'road', 'building'],
          viewMode: '2D'
        });

        // 等待地图完全加载
        await this.waitForMapReady();
        
        // 加载地图插件
        await this.loadMapPlugins();
        
        this.isInitialized = true;
        this.initRetryCount = 0;
        console.log("地图初始化成功");
        
        // 触发初始化完成事件
        this.$emit('mapInitialized', this.map);
        
      } catch (error) {
        console.error("地图初始化失败:", error);
        await this.handleInitializationError(error);
      } finally {
        this.isInitializing = false;
      }
    },
    
    // 等待高德地图API加载
    waitForAmapAPI() {
      return new Promise((resolve, reject) => {
        const checkAmap = () => {
          if (window.AMap) {
            resolve();
          } else if (this.initRetryCount < this.maxInitRetries) {
            this.initRetryCount++;
            setTimeout(checkAmap, 1000);
          } else {
            reject(new Error('高德地图API加载超时'));
          }
        };
        checkAmap();
      });
    },
    
    // 等待地图准备就绪
    waitForMapReady() {
      return new Promise((resolve) => {
        if (this.map) {
          this.map.on('complete', () => {
            resolve();
          });
        } else {
          resolve();
        }
      });
    },
    
    // 加载地图插件
    async loadMapPlugins() {
      return new Promise((resolve, reject) => {
        AMap.plugin(['AMap.ToolBar', 'AMap.Scale', 'AMap.Driving'], () => {
          try {
            // 添加地图控件
            this.map.addControl(new AMap.ToolBar({
              position: 'RB'
            }));
            this.map.addControl(new AMap.Scale({
              position: 'LB'
            }));
            
            console.log("地图插件加载成功");
            resolve();
          } catch (error) {
            console.error("地图插件加载失败:", error);
            reject(error);
          }
        });
      });
    },
    
    // 处理初始化错误
    async handleInitializationError(error) {
      if (this.initRetryCount < this.maxInitRetries) {
        console.log(`地图初始化失败，${2}秒后重试 (${this.initRetryCount + 1}/${this.maxInitRetries})`);
        await new Promise(resolve => setTimeout(resolve, 2000));
        await this.initializeMap();
      } else {
        this.$emit('mapInitializationFailed', error);
        this.$emit('notify', '地图初始化失败，请刷新页面重试', 'error');
      }
    },
    
    // 安全的清除操作
    clearAllMarkersAndRoutes() {
      if (!this.isInitialized || !this.map) {
        return;
      }
      
      try {
        // 清除路线
        if (this.driving) {
          this.driving.clear();
          this.driving = null;
        }
        
        // 清除家的标记
        if (this.homeMarker) {
          this.map.remove(this.homeMarker);
          this.homeMarker = null;
        }
        
        // 清除店铺标记
        this.shopMarkers.forEach(marker => {
          try {
            this.map.remove(marker);
          } catch (e) {
            console.warn('移除店铺标记失败:', e);
          }
        });
        this.shopMarkers = [];
        
        // 清除其他标记
        if (this.markers) {
          this.markers.forEach(marker => {
            try {
              this.map.remove(marker);
            } catch (e) {
              console.warn('移除标记失败:', e);
            }
          });
          this.markers = [];
        }
        
        console.log("地图清除完成");
        
      } catch (error) {
        console.error("清除地图元素时出错:", error);
      }
    },
    
    // 改进的设置家位置方法
    async setHomeLocation(longitude, latitude, address) {
      if (!this.isInitialized) {
        console.warn("地图未初始化，等待初始化完成");
        await this.waitForInitialization();
      }
      
      // 数据验证
      const lng = parseFloat(longitude);
      const lat = parseFloat(latitude);
      
      if (isNaN(lng) || isNaN(lat)) {
        console.error('无效的经纬度数据:', { longitude, latitude, address });
        this.$emit('notify', '家的位置坐标无效', 'error');
        return false;
      }
      
      try {
        // 清除现有的家标记
        if (this.homeMarker) {
          this.map.remove(this.homeMarker);
        }
        
        // 创建家的标记
        const position = new AMap.LngLat(lng, lat);
        this.homeMarker = new AMap.Marker({
          position: position,
          title: `家: ${address}`,
          icon: new AMap.Icon({
            size: new AMap.Size(25, 34),
            image: 'https://webapi.amap.com/theme/v1.3/markers/n/mark_r.png'
          }),
          offset: new AMap.Pixel(-13, -30),
          anchor: 'bottom-center'
        });
        
        this.map.add(this.homeMarker);
        
        // 设置地图中心和缩放级别
        this.map.setCenter(position);
        this.map.setZoom(14);
        
        console.log("家的位置设置成功:", address);
        return true;
        
      } catch (error) {
        console.error("设置家位置失败:", error);
        this.$emit('notify', '设置家的位置失败', 'error');
        return false;
      }
    },
    
    // 等待地图初始化完成
    waitForInitialization() {
      return new Promise((resolve) => {
        if (this.isInitialized) {
          resolve();
          return;
        }
        
        const checkInitialized = () => {
          if (this.isInitialized) {
            resolve();
          } else {
            setTimeout(checkInitialized, 100);
          }
        };
        checkInitialized();
      });
    },
    
    // 改进的添加店铺标记方法
    async addShopMarker(shop) {
      if (!this.isInitialized) {
        await this.waitForInitialization();
      }
      
      if (!this.map || !shop.longitude || !shop.latitude) {
        console.error("无法添加店铺标记：地图未初始化或店铺坐标缺失");
        return false;
      }
      
      try {
        const position = new AMap.LngLat(
          parseFloat(shop.longitude), 
          parseFloat(shop.latitude)
        );
        
        const marker = new AMap.Marker({
          position: position,
          title: `店铺: ${shop.name}`,
          icon: new AMap.Icon({
            size: new AMap.Size(25, 34),
            image: 'https://webapi.amap.com/theme/v1.3/markers/n/mark_b.png'
          }),
          offset: new AMap.Pixel(-13, -30),
          anchor: 'bottom-center'
        });
        
        // 存储店铺信息
        marker.shopInfo = shop;
        
        this.map.add(marker);
        this.shopMarkers.push(marker);
        
        // 更新地图视野
        this.updateMapView();
        
        return true;
        
      } catch (error) {
        console.error("添加店铺标记失败:", error);
        this.$emit('notify', `添加 ${shop.name} 标记失败`, 'error');
        return false;
      }
    },
    
    // 改进的地图视野更新
    updateMapView() {
      if (!this.isInitialized || !this.map) {
        return;
      }
      
      try {
        const allMarkers = [...this.shopMarkers];
        if (this.homeMarker) {
          allMarkers.push(this.homeMarker);
        }
        
        if (allMarkers.length > 1) {
          this.map.setFitView(allMarkers, false, [50, 50, 50, 50], 18);
        } else if (allMarkers.length === 1) {
          this.map.setCenter(allMarkers[0].getPosition());
          this.map.setZoom(15);
        }
      } catch (error) {
        console.error("更新地图视野失败:", error);
      }
    },
    
    // 改进的路线绘制方法
    async drawOptimizedRoute(routeData) {
      if (!this.isInitialized) {
        await this.waitForInitialization();
      }
      
      if (!this.map || !routeData) {
        console.error('地图未初始化或没有路线数据');
        return false;
      }
      
      try {
        // 先清除旧路线，但保留标记
        this.clearRouteOnly();
        
        const allMapElements = [];
        
        // 绘制路线段
        if (routeData.route_segments && routeData.route_segments.length > 0) {
          routeData.route_segments.forEach((segment, index) => {
            if (segment.polyline) {
              try {
                const path = this.parsePolyline(segment.polyline);
                if (path.length > 0) {
                  const polyline = new AMap.Polyline({
                    path: path,
                    strokeColor: this.getRouteColor(index),
                    strokeOpacity: 0.8,
                    strokeWeight: 6,
                    strokeStyle: 'solid'
                  });
                  
                  this.map.add(polyline);
                  allMapElements.push(polyline);
                }
              } catch (error) {
                console.warn(`绘制路线段 ${index} 失败:`, error);
              }
            }
          });
        }
        
        // 标记路线点
        if (routeData.optimized_order && routeData.optimized_order.length > 0) {
          routeData.optimized_order.forEach((point, index) => {
            try {
              const isHome = point.id === 'home';
              const marker = new AMap.Marker({
                position: new AMap.LngLat(point.longitude, point.latitude),
                title: point.name,
                label: {
                  content: (index + 1).toString(),
                  direction: 'center',
                  style: {
                    fontSize: '12px',
                    fontWeight: 'bold',
                    color: 'white',
                    background: isHome ? '#ff4444' : '#4444ff',
                    border: 'none',
                    borderRadius: '50%',
                    padding: '2px 6px'
                  }
                },
                icon: new AMap.Icon({
                  size: new AMap.Size(25, 34),
                  image: isHome ? 
                    'https://webapi.amap.com/theme/v1.3/markers/n/mark_r.png' : 
                    'https://webapi.amap.com/theme/v1.3/markers/n/mark_b.png'
                }),
                offset: new AMap.Pixel(-13, -30)
              });
              
              this.map.add(marker);
              allMapElements.push(marker);
            } catch (error) {
              console.warn(`标记点 ${index} 失败:`, error);
            }
          });
        }
        
        // 自动调整视野
        if (allMapElements.length > 0) {
          setTimeout(() => {
            try {
              this.map.setFitView(allMapElements, false, [60, 60, 60, 60], 18);
            } catch (error) {
              console.warn("调整地图视野失败:", error);
            }
          }, 100);
        }
        
        console.log("路线绘制完成");
        return true;
        
      } catch (error) {
        console.error("绘制路线失败:", error);
        this.$emit('notify', '路线绘制失败', 'error');
        return false;
      }
    },
    
    // 只清除路线，保留标记
    clearRouteOnly() {
      if (this.driving) {
        try {
          this.driving.clear();
          this.driving = null;
        } catch (error) {
          console.warn("清除驾车路线失败:", error);
        }
      }
      
      // 清除地图上的折线
      this.map.getAllOverlays('polyline').forEach(polyline => {
        try {
          this.map.remove(polyline);
        } catch (error) {
          console.warn("移除折线失败:", error);
        }
      });
    },
    
    // 解析折线坐标
    parsePolyline(polylineStr) {
      if (!polylineStr) return [];
      
      try {
        return polylineStr.split(';').map(coordStr => {
          const parts = coordStr.split(',');
          return new AMap.LngLat(parseFloat(parts[0]), parseFloat(parts[1]));
        }).filter(coord => 
          !isNaN(coord.lng) && !isNaN(coord.lat)
        );
      } catch (error) {
        console.error("解析折线坐标失败:", error);
        return [];
      }
    },
    
    // 获取路线颜色
    getRouteColor(index) {
      const colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7'];
      return colors[index % colors.length];
    },
    
    // 设置城市中心
    setCenterToCity(longitude, latitude, cityName) {
      if (!this.isInitialized || !this.map) {
        console.warn("地图未初始化，无法设置城市中心");
        return;
      }
      
      try {
        const newCenter = new AMap.LngLat(longitude, latitude);
        this.map.setCenter(newCenter);
        this.map.setZoom(11);
        console.log(`已切换到城市: ${cityName}`);
      } catch (error) {
        console.error("设置城市中心失败:", error);
      }
    }
  },
  
  // 组件销毁时清理资源
  beforeUnmount() {
    try {
      if (this.driving) {
        this.driving.clear();
        this.driving = null;
      }
      
      this.clearAllMarkersAndRoutes();
      
      if (this.map) {
        this.map.destroy();
        this.map = null;
      }
      
      this.isInitialized = false;
      console.log("地图组件资源清理完成");
    } catch (error) {
      console.error("清理地图资源时出错:", error);
    }
  }
};

// 数据验证工具类
class DataValidator {
  static validateCoordinates(latitude, longitude) {
    const lat = parseFloat(latitude);
    const lng = parseFloat(longitude);
    if (isNaN(lat) || isNaN(lng)) {
      return { valid: false, error: '经纬度必须是有效数字' };
    }
    if (lat < -90 || lat > 90) {
      return { valid: false, error: '纬度必须在-90到90之间' };
    }
    if (lng < -180 || lng > 180) {
      return { valid: false, error: '经度必须在-180到180之间' };
    }
    return { valid: true, latitude: lat, longitude: lng };
  }
  static validateShop(shop) {
    const errors = [];
    if (!shop.id) {
      errors.push('店铺ID不能为空');
    }
    if (!shop.name || shop.name.trim().length === 0) {
      errors.push('店铺名称不能为空');
    }
    if (shop.type !== 'chain') {
      const coordValidation = this.validateCoordinates(shop.latitude, shop.longitude);
      if (!coordValidation.valid) {
        errors.push(`坐标验证失败: ${coordValidation.error}`);
      }
    }
    if (shop.stay_duration !== undefined) {
      const duration = parseFloat(shop.stay_duration);
      if (isNaN(duration) || duration < 0) {
        errors.push('停留时间必须是非负数');
      }
    }
    return {
      valid: errors.length === 0,
      errors: errors
    };
  }
  static validateHomeLocation(homeLocation) {
    if (!homeLocation) {
      return { valid: false, error: '家的位置不能为空' };
    }
    if (!homeLocation.latitude || !homeLocation.longitude) {
      return { valid: false, error: '家的经纬度信息缺失' };
    }
    return this.validateCoordinates(homeLocation.latitude, homeLocation.longitude);
  }
}

// 状态管理类
class RouteState {
  constructor() {
    this.reset();
  }
  reset() {
    this.isPlanning = false;
    this.isLoading = false;
    this.routeCombinations = [];
    this.currentRouteIndex = 0;
    this.routeInfo = null;
    this.showRouteInfo = false;
    this.routeSummary = null;
    this.selectedRouteId = null;
    this.errors = [];
  }
  setPlanning(status) {
    this.isPlanning = status;
    if (status) {
      this.isLoading = true;
      this.errors = [];
    }
  }
  setLoading(status) {
    this.isLoading = status;
  }
  addError(error) {
    this.errors.push({
      message: error,
      timestamp: new Date(),
      id: Date.now()
    });
  }
  setRouteCombinations(combinations) {
    this.routeCombinations = combinations || [];
    this.currentRouteIndex = 0;
  }
  selectRoute(index) {
    if (index >= 0 && index < this.routeCombinations.length) {
      this.currentRouteIndex = index;
      this.selectedRouteId = this.routeCombinations[index]?.id;
      return this.routeCombinations[index];
    }
    return null;
  }
  getCurrentRoute() {
    return this.routeCombinations[this.currentRouteIndex] || null;
  }
  hasRoutes() {
    return this.routeCombinations.length > 0;
  }
}

const Dashboard = {
  components: {
    'map-display': MapDisplayComp,
    'notification': NotificationComp
  },
  template: `
    <div class="dashboard-container">
      <notification ref="notification"></notification>
      
      <header class="app-header">
        <h1>🏪 智能探店助手</h1>
        <p class="subtitle">轻松规划您的探店之旅</p>
      </header>

      <!-- 城市选择部分 -->
      <div class="section city-section">
        <h3><i class="icon">🌍</i> 选择您的城市</h3>
        <div class="city-selection-form">
          <div class="form-group">
            <label for="province-select">省份:</label>
            <select id="province-select" v-model="selectedProvince" @change="onProvinceChange">
              <option disabled value="">请选择省份</option>
              <option v-for="province in provinces" :key="province.name" :value="province.name">
                {{ province.name }}
              </option>
            </select>
          </div>
          <div class="form-group">
            <label for="city-select">城市:</label>
            <select id="city-select" v-model="selectedCity" @change="onCityChange">
              <option disabled value="">请选择城市</option>
              <option v-for="city in availableCities" :key="city.name" :value="city.name">
                {{ city.name }}
              </option>
            </select>
          </div>
        </div>
      </div>

      <!-- 地图显示 -->
      <div class="section map-section">
        <h3><i class="icon">🗺️</i> 地图</h3>
        <map-display 
          ref="mapDisplayRef" 
          @routeCalculated="onRouteCalculated"
          @notify="showNotification"
          class="map-display-component"
        ></map-display>
      </div>

      <!-- 家的位置设置 -->
      <div class="section home-section">
        <h3><i class="icon">🏠</i> 设置家的位置</h3>
        <div class="input-container">
          <input 
            type="text" 
            v-model="homeAddress" 
            @input="onAddressInput"
            @focus="showAddressSuggestions = true"
            @blur="hideAddressSuggestions"
            placeholder="请输入您家的地址" 
            class="address-input"
            autocomplete="off"
          />
          <div v-if="showAddressSuggestions && addressSuggestions.length > 0" class="suggestions-dropdown">
            <div 
              v-for="suggestion in addressSuggestions" 
              :key="suggestion.id"
              @mousedown="selectAddressSuggestion(suggestion)"
              class="suggestion-item"
            >
              <div class="suggestion-name">{{ suggestion.name }}</div>
              <div class="suggestion-address">{{ suggestion.address }}</div>
            </div>
          </div>
        </div>
        <div v-if="homeAddress && homeLocation" class="location-display">
          <i class="icon">📍</i> {{ homeAddress }}
        </div>
      </div>

      <!-- 店铺列表 -->
      <div class="section shops-section">
        <h3><i class="icon">🛍️</i> 今天要探访的店铺</h3>
        <div class="input-container">
          <input 
            type="text" 
            v-model="shopInput" 
            @input="onShopInput"
            @focus="showShopSuggestions = true"
            @blur="hideShopSuggestions"
            placeholder="搜索店铺名称，如 '肯德基'、'星巴克'" 
            class="shop-input"
            autocomplete="off"
          />
          <div v-if="showShopSuggestions && shopSuggestions.length > 0" class="shop-suggestions">
            <div 
              v-for="suggestion in shopSuggestions" 
              :key="suggestion.id"
              @mousedown="selectShopSuggestion(suggestion)"
              class="suggestion-item"
            >
              <div v-if="suggestion.type === 'chain'">
                <div class="suggestion-name">
                  <strong>{{ suggestion.name }}</strong>
                  <span class="badge chain">连锁店铺</span>
                </div>
                <div class="suggestion-address">{{ suggestion.address }}</div>
                <div class="suggestion-status">{{ suggestion.status }}</div>
              </div>
              <div v-else>
                <div class="suggestion-name">{{ suggestion.name }}</div>
                <div class="suggestion-address">{{ suggestion.address }}</div>
                <div class="suggestion-distance" v-if="suggestion.distance">{{ Math.round(suggestion.distance) }}m</div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="shopsToVisit.length > 0" class="shops-list">
          <div v-for="shop in shopsToVisit" :key="shop.id" 
               :class="['shop-card', { 'chain-shop': shop.type === 'chain', 'private-shop': shop.type === 'private' }]">
            <div class="shop-info">
              <div class="shop-name">
                {{ shop.name }}
                <span v-if="shop.type === 'chain'" class="shop-type-badge chain">🔗 连锁店</span>
                <span v-else class="shop-type-badge private">🏪 私人店铺</span>
              </div>
              <div class="shop-address">{{ shop.address }}</div>
              <div v-if="shop.type === 'chain'" class="chain-note">
                系统将在路线规划时自动选择最优分店位置
              </div>
              
              <!-- 停留时间设置 -->
              <div class="stay-duration-setting">
                <label class="stay-label">
                  <i class="icon">⏱️</i> 停留时间:
                </label>
                <div class="stay-input-group">
                  <input 
                    type="number" 
                    :value="getStayDuration(shop.id)"
                    @input="setStayDuration(shop.id, parseInt($event.target.value) || defaultStayDuration)"
                    min="5" 
                    max="300" 
                    step="5"
                    class="stay-input"
                  >
                  <span class="stay-unit">分钟</span>
                </div>
              </div>
            </div>
            <button @click="removeShop(shop.id)" class="remove-btn">×</button>
          </div>
        </div>
        <div v-else class="empty-state">
          <i class="icon">📝</i>
          <p>还没有添加店铺，开始搜索并添加您要探访的店铺吧！</p>
        </div>
      </div>

      <!-- 路线规划部分 -->
      <div class="section route-section">
        <h3><i class="icon">🚗</i> 路线规划</h3>
        
        <!-- 时间设置 -->
        <div class="time-settings">
          <div class="time-setting-group">
            <label for="departure-time" class="time-label">
              <i class="icon">🕐</i> 出发时间
            </label>
            <input 
              type="time" 
              id="departure-time"
              v-model="departureTime" 
              class="time-input"
            >
          </div>
          
          <div class="time-setting-group">
            <label for="default-stay" class="time-label">
              <i class="icon">⏱️</i> 默认驻店时间
            </label>
            <div class="duration-input-group">
              <input 
                type="number" 
                id="default-stay"
                v-model.number="defaultStayDuration" 
                min="5" 
                max="300" 
                step="5"
                class="duration-input"
              >
              <span class="duration-unit">分钟</span>
            </div>
          </div>
        </div>
        
        <div class="travel-mode-selector">
          <button 
            @click="travelMode = 'DRIVING'"
            :class="['mode-btn', { active: travelMode === 'DRIVING' }]"
          >
            🚗 驾车
          </button>
          <button 
            @click="travelMode = 'TRANSIT'"
            :class="['mode-btn', { active: travelMode === 'TRANSIT' }]"
          >
            🚌 公交
          </button>
        </div>
        <button @click="getDirections" class="get-route-btn" :disabled="!canGetRoute">
          {{ routeButtonText }}
        </button>
        
        <!-- 路线信息显示 -->
        <div v-if="routeCombinations && routeCombinations.length > 0" class="route-options">
          <h3>
            <i class="icon">🛣️</i> 
            可选路线方案
            <span class="route-info-badge">智能分析所有分店和访问顺序</span>
          </h3>
          
          <div class="route-categories">
            <!-- 按时间优化的路线 -->
            <div class="route-category">
              <h4><i class="icon">⏱️</i> 按时间优化的路线</h4>
              <div class="route-list">
                <div 
                  v-for="(route, index) in routeCombinations.filter(r => r.type === 'time')" 
                  :key="route.id"
                  :class="['route-item', { 'active': route.id === selectedRouteId }]"
                >
                   <div class="route-number">{{ index + 1 }}</div>
                   <div class="route-details">
                     <div class="route-header">
                       <span class="route-type-badge time">时间优先</span>
                       <span class="route-rank">第{{ route.rank }}名</span>
                     </div>
                     <div class="route-shops">
                       {{ route && route.combination ? route.combination.map(function(s){return s.name;}).join(' → ') : '加载中...' }}
                     </div>
                     <div class="route-summary">
                       <span class="time-value">{{ formatDuration((route.totalTime / 60)) }}</span>
                       <span class="separator">|</span>
                       <span class="distance-value">{{ formatDistance(route.totalDistance) }}</span>
                     </div>
                   </div>
                   <button @click="selectRoute(route)" class="select-route-btn">选择</button>
                </div>
              </div>
            </div>
            
            <!-- 按距离优化的路线 -->
            <div class="route-category">
              <h4><i class="icon">📍</i> 按距离优化的路线</h4>
              <div class="route-list">
                <div 
                  v-for="(route, index) in routeCombinations.filter(r => r.type === 'distance')" 
                  :key="route.id"
                  :class="['route-item', { 'active': route.id === selectedRouteId }]"
                >
                   <div class="route-number">{{ index + 1 }}</div>
                   <div class="route-details">
                     <div class="route-header">
                       <span class="route-type-badge distance">距离优先</span>
                       <span class="route-rank">第{{ route.rank }}名</span>
                     </div>
                     <div class="route-shops">
                       {{ route && route.combination ? route.combination.map(function(s){return s.name;}).join(' → ') : '加载中...' }}
                     </div>
                     <div class="route-summary">
                       <span class="time-value">{{ formatDuration((route.totalTime / 60)) }}</span>
                       <span class="separator">|</span>
                       <span class="distance-value">{{ formatDistance(route.totalDistance) }}</span>
                     </div>
                   </div>
                   <button @click="selectRoute(route)" class="select-route-btn">选择</button>
                </div>
              </div>
            </div>
          </div>
           
           <!-- 路线统计信息 -->
           <div class="route-statistics">
             <div class="stat-item">
              <span class="stat-label">点击路线可查看详细指导</span>
              <span class="stat-value">{{ selectedRouteId ? '已选择' : '未选择' }}</span>
             </div>
           </div>
         </div>

         <!-- 当前路线详细信息 -->
         <div v-if="showRouteInfo && routeInfo" class="route-info">
           <div class="route-summary">
             <h3><i class="icon">📋</i> 路线摘要</h3>
             <div class="summary-grid">
               <div class="summary-item">
                 <span class="summary-label">总时间</span>
                 <span class="summary-value">{{ routeSummary && routeSummary.totalTime ? routeSummary.totalTime : '计算中...' }}</span>
               </div>
               <div class="summary-item">
                 <span class="summary-label">总距离</span>
                 <span class="summary-value">{{ routeSummary && routeSummary.totalDistance ? routeSummary.totalDistance : '计算中...' }}</span>
               </div>
               <div class="summary-item">
                 <span class="summary-label">优化类型</span>
                 <span class="summary-value">{{ routeSummary && routeSummary.optimizationType ? routeSummary.optimizationType : '未知' }}</span>
               </div>
               <div class="summary-item">
                 <span class="summary-label">出行方式</span>
                 <span class="summary-value">{{ travelMode === 'TRANSIT' ? '公交' : '驾车' }}</span>
               </div>
             </div>
           </div>
           
           <!-- 详细路线步骤 -->
           <div class="route-details">
             <h3><i class="icon">🗺️</i> 详细路线指导</h3>
             
             <!-- 公交路线详细显示 -->
             <div v-if="travelMode === 'TRANSIT' && routeInfo && routeInfo.route_segments && routeInfo.route_segments.length > 0" class="transit-route-details">
               <div v-for="(segment, index) in routeInfo.route_segments" :key="'transit_segment_' + index" class="transit-segment">
                 <div class="segment-header">
                   <span class="segment-number">{{ index + 1 }}</span>
                   <span class="segment-title">
                     <i class="icon">{{ getSegmentIcon(segment.type) }}</i>
                     {{ segment.from_name }} → {{ segment.to_name }}
                   </span>
                 </div>
                 <div class="segment-content">
                   <div class="segment-stats">
                     <span class="stat-time">⏱️ {{ formatDuration((segment.duration || 0) / 60) }}</span>
                     <span class="stat-distance">📏 {{ formatDistance(segment.distance || 0) }}</span>
                     <span v-if="segment.cost" class="stat-cost">💰 {{ segment.cost }}元</span>
                   </div>
                   
                   <!-- 步行段详细指导 -->
                   <div v-if="segment.type === 'walking'" class="walking-instructions">
                     <div class="instruction-header">
                       <i class="icon">🚶</i>
                       <span class="instruction-title">步行指导</span>
                     </div>
                     <div v-if="segment.steps && segment.steps.length > 0" class="instruction-steps">
                       <div v-for="(step, stepIndex) in segment.steps" :key="'walk_step_' + stepIndex" class="instruction-step">
                         <div class="step-content">
                           <i class="step-icon">➤</i>
                           <span class="step-text">{{ step.instruction || '继续步行' }}</span>
                         </div>
                         <div v-if="step.distance || step.duration" class="step-meta">
                           <span v-if="step.distance" class="step-distance">{{ step.distance }}米</span>
                           <span v-if="step.duration" class="step-duration">{{ Math.round(step.duration / 60) }}分钟</span>
                         </div>
                       </div>
                     </div>
                     <div v-else class="simple-instruction">
                       从 {{ segment.from_name }} 步行至 {{ segment.to_name }}
                     </div>
                   </div>
                   
                   <!-- 公交段详细指导 -->
                   <div v-else-if="segment.type === 'bus'" class="bus-instructions">
                     <div class="instruction-header">
                       <i class="icon">🚌</i>
                       <span class="instruction-title">公交指导</span>
                     </div>
                     <div v-if="segment.lines && segment.lines.length > 0" class="bus-lines">
                       <div v-for="(line, lineIndex) in segment.lines" :key="'bus_line_' + lineIndex" class="bus-line">
                         <div class="line-info">
                           <div class="line-header">
                             <span class="line-number">{{ extractBusNumber(line.name) }}路</span>
                             <span class="line-name">{{ line.name }}</span>
                           </div>
                           <div class="line-route">
                             <div class="station-info departure">
                               <span class="station-label">上车站</span>
                               <span class="station-name">{{ line.departure_stop ? line.departure_stop.name : segment.from_name }}</span>
                             </div>
                             <div class="route-arrow">
                               <i class="icon">🚌</i>
                               <span class="stops-count">{{ calculateStopsCount(line) }}站</span>
                               <i class="icon">→</i>
                             </div>
                             <div class="station-info arrival">
                               <span class="station-label">下车站</span>
                               <span class="station-name">{{ line.arrival_stop ? line.arrival_stop.name : segment.to_name }}</span>
                             </div>
                           </div>
                           <div v-if="line.via_stops && line.via_stops.length > 0" class="via-stops">
                             <span class="via-label">途径站点：</span>
                             <span class="via-stations">{{ line.via_stops.map(s => s.name).join(' → ') }}</span>
                           </div>
                         </div>
                       </div>
                     </div>
                     <div v-else class="simple-instruction">
                       乘坐公交从 {{ segment.from_name }} 到 {{ segment.to_name }}
                     </div>
                   </div>
                   
                   <!-- 地铁段详细指导 -->
                   <div v-else-if="segment.type === 'subway' || segment.type === 'railway'" class="subway-instructions">
                     <div class="instruction-header">
                       <i class="icon">🚇</i>
                       <span class="instruction-title">地铁指导</span>
                     </div>
                     <div v-if="segment.railway" class="subway-lines">
                       <div class="subway-line">
                         <div class="line-info">
                           <div class="line-header">
                             <span class="subway-line-number">{{ extractSubwayLine(segment.railway.name) }}</span>
                             <span v-if="segment.railway.trip" class="train-number">{{ segment.railway.trip }}</span>
                           </div>
                           <div class="line-route">
                             <div class="station-info departure">
                               <span class="station-label">进站</span>
                               <span class="station-name">{{ segment.railway.departure_stop ? segment.railway.departure_stop.name : segment.from_name }}</span>
                             </div>
                             <div class="route-arrow">
                               <i class="icon">🚇</i>
                               <span class="stops-count">{{ calculateSubwayStops(segment.railway) }}站</span>
                               <i class="icon">→</i>
                             </div>
                             <div class="station-info arrival">
                               <span class="station-label">出站</span>
                               <span class="station-name">{{ segment.railway.arrival_stop ? segment.railway.arrival_stop.name : segment.to_name }}</span>
                             </div>
                           </div>
                           <div v-if="segment.railway.via_stops && segment.railway.via_stops.length > 0" class="via-stops">
                             <span class="via-label">途径站点：</span>
                             <span class="via-stations">{{ segment.railway.via_stops.map(s => s.name).join(' → ') }}</span>
                           </div>
                         </div>
                       </div>
                     </div>
                     <div v-else class="simple-instruction">
                       乘坐地铁从 {{ segment.from_name }} 到 {{ segment.to_name }}
                     </div>
                   </div>
                   
                   <!-- 其他交通方式 -->
                   <div v-else class="other-instructions">
                     <div v-if="segment.steps && segment.steps.length > 0" class="instruction-steps">
                       <div v-for="(step, stepIndex) in segment.steps" :key="'other_step_' + stepIndex" class="instruction-step">
                         <div class="step-content">
                           <i class="step-icon">➤</i>
                           <span class="step-text">{{ step.instruction || '按路线前行' }}</span>
                         </div>
                       </div>
                     </div>
                     <div v-else class="simple-instruction">
                       从 {{ segment.from_name }} 前往 {{ segment.to_name }}
                     </div>
                   </div>
                 </div>
               </div>
             </div>
             
             <!-- 驾车路线显示 -->
             <div v-else-if="travelMode === 'DRIVING' && routeInfo && routeInfo.route_segments && routeInfo.route_segments.length > 0" class="driving-route-details">
               <div v-for="(segment, index) in routeInfo.route_segments" :key="'driving_segment_' + index" class="route-segment">
                 <div class="segment-header">
                   <span class="segment-number">{{ index + 1 }}</span>
                   <span class="segment-from-to">
                    {{ segment.from_name }} → {{ segment.to_name }}
                   </span>
                 </div>
                 <div class="segment-details">
                   <div class="segment-stats">
                     <span>距离: {{ formatDistance(segment && segment.distance ? segment.distance : 0) }}</span>
                     <span>时间: {{ formatDuration(((segment && segment.duration ? segment.duration : 0) / 60)) }}</span>
                   </div>
                   <div v-if="segment && segment.steps && segment.steps.length > 0" class="segment-steps">
                     <div v-for="(step, stepIndex) in segment.steps.slice(0, 3)" :key="'step_' + stepIndex" class="step-item">
                       {{ step.instruction || '无详细指导' }}
                     </div>
                     <div v-if="segment.steps.length > 3" class="more-steps">
                       ...还有{{ segment.steps.length - 3 }}个步骤
                     </div>
                   </div>
                 </div>
               </div>
             </div>
             
             <!-- 访问顺序显示 -->
             <div v-else-if="routeInfo && routeInfo.optimized_order && routeInfo.optimized_order.length > 0" class="route-order">
               <h4><i class="icon">🚩</i> 最优访问顺序</h4>
               <div class="order-list">
                 <div v-for="(point, index) in routeInfo.optimized_order" :key="'order_' + index" class="order-item">
                   <span class="order-number">{{ index + 1 }}</span>
                   <div class="order-info">
                     <div class="order-name">{{ point.name }}</div>
                     <div v-if="point.address" class="order-address">{{ point.address }}</div>
                   </div>
                 </div>
               </div>
             </div>
             
             <!-- 无详细路线时的提示 -->
             <div v-else class="no-route-details">
               <p>路线详情正在加载中...</p>
               <p v-if="showDebugInfo">调试信息：routeInfo 结构 - {{ JSON.stringify(routeInfo, null, 2) }}</p>
             </div>
           </div>
         </div>

         <!-- 加载状态指示器 -->
         <div v-if="isLoading" class="loading-indicator">
           <div class="loading-spinner"></div>
           <p>正在进行路线规划计算，请稍候...</p>
         </div>

         <button @click="logoutUser" class="logout-btn">
           <i class="icon">👋</i> 退出登录
         </button>
      </div>
    </div>
  `,
  data() {
    return {
      // 界面状态
      isLoading: false,
      notificationMessage: '',
      notificationType: 'info',
      notificationDuration: 3000,
      
      // 地图相关
      mapDisplayRef: null,
      isPickModeActive: false,
      
      // 城市和家庭位置
      provinces: [], // 省份列表
      selectedProvince: '', // 选中的省份
      availableCities: [], // 可选的城市列表
      cities: [], // 保留以备后用，但主要逻辑转到provinces
      selectedCity: '',
      homeAddress: '',
      homeLocation: null,
      addressSuggestions: [],
      showAddressSuggestions: false,
      currentHomeLocation: null,
      showDebugInfo: true, // 是否显示调试信息
      
      // 添加这些变量
      homeAddressInput: '',
      homeLatitudeInput: '',
      homeLongitudeInput: '',
      
      // 店铺搜索
      shopInput: '',
      shopSuggestions: [],
      showShopSuggestions: false,
      
      // 探店列表
      shopsToVisit: [],
      
      // 路线规划
      travelMode: 'DRIVING',
      departureTime: '',
      defaultStayDuration: 30,
      stayDurations: {},
      routeInfo: null,
      showRouteInfo: false,
      routeSummary: null,
      
      // 多路线组合
      routeCombinations: [], // 所有可能的路线组合
      currentRouteIndex: 0, // 当前显示的路线索引
      currentRouteShops: [], // 当前路线包含的店铺
      selectedRouteId: null // 当前选中的路线ID
    };
  },
  computed: {
    canGetRoute() {
      const homeValid = this.homeAddress && 
                       this.homeLocation && 
                       this.homeLocation.latitude && 
                       this.homeLocation.longitude &&
                       !isNaN(parseFloat(this.homeLocation.latitude)) &&
                       !isNaN(parseFloat(this.homeLocation.longitude));
      const shopsValid = this.shopsToVisit.length > 0;
      return homeValid && shopsValid;
    },

    routeButtonText() {
      if (!this.homeAddress || !this.homeLocation) {
        return '请先设置家的位置';
      }
      if (this.shopsToVisit.length === 0) {
        return '请先添加店铺';
      }
      return '🚀 获取路线';
    },

    homeLocationStatus() {
      if (!this.homeAddress) {
        return { valid: false, message: '❌ 未设置家的地址' };
      }
      if (!this.homeLocation) {
        return { valid: false, message: '❌ 家的位置数据缺失' };
      }
      if (!this.homeLocation.latitude || !this.homeLocation.longitude) {
        return { valid: false, message: '❌ 家的经纬度缺失' };
      }
      if (isNaN(parseFloat(this.homeLocation.latitude)) || isNaN(parseFloat(this.homeLocation.longitude))) {
        return { valid: false, message: '❌ 家的经纬度格式无效' };
      }
      return { 
        valid: true, 
        message: `✅ 已设置 (${parseFloat(this.homeLocation.latitude).toFixed(4)}, ${parseFloat(this.homeLocation.longitude).toFixed(4)})` 
      };
    },

    shopsStatus() {
      if (this.shopsToVisit.length === 0) {
        return { valid: false, message: '❌ 未添加任何店铺' };
      }
      const chainStores = this.shopsToVisit.filter(s => s.type === 'chain');
      const privateStoresWithCoords = this.shopsToVisit.filter(s => 
        s.type !== 'chain' && s.latitude && s.longitude && 
        !isNaN(parseFloat(s.latitude)) && !isNaN(parseFloat(s.longitude))
      );
      const privateStoresPending = this.shopsToVisit.filter(s => 
        s.type !== 'chain' && (!s.latitude || !s.longitude || 
        isNaN(parseFloat(s.latitude)) || isNaN(parseFloat(s.longitude)))
      );
      
      const totalPrivateStores = privateStoresWithCoords.length + privateStoresPending.length;
      
      if (chainStores.length === 0 && totalPrivateStores === 0) {
        return { valid: false, message: '❌ 没有有效的店铺数据' };
      }
      
      let message = `✅ ${this.shopsToVisit.length} 个店铺`;
      if (chainStores.length > 0) message += ` (${chainStores.length} 连锁`;
      if (totalPrivateStores > 0) {
        if (chainStores.length > 0) message += `, `;
        else message += ` (`;
        message += `${totalPrivateStores} 私人`;
        if (privateStoresPending.length > 0) {
          message += `, ${privateStoresPending.length} 待定位`;
        }
      }
      message += ')';
      
      return { valid: true, message };
    }
  },
  methods: {
    // 通知方法
    showNotification(message, type = 'info', title = '') {
      if (this.$refs.notification) {
        if (type === 'success') {
          this.$refs.notification.success(message, title);
        } else if (type === 'error') {
          this.$refs.notification.error(message, title);
        } else if (type === 'warning') {
          this.$refs.notification.warning(message, title);
        } else {
          this.$refs.notification.info(message, title);
        }
      }
    },
    
    async logoutUser() {
      localStorage.removeItem('userToken');
      localStorage.removeItem('homeLocation'); // 清除保存的家地址
      this.showNotification('已成功退出登录！', 'success');
      this.$router.push('/login');
    },
    
    // --- 省市选择 ---
    loadProvinceCityData() {
        // 在实际应用中，这个数据应该从后端获取或从一个JSON文件加载
        this.provinces = [
            { name: '北京', cities: [{ name: '北京', lng: 116.4074, lat: 39.9042 }] },
            { name: '上海', cities: [{ name: '上海', lng: 121.4737, lat: 31.2304 }] },
            { name: '天津', cities: [{ name: '天津', lng: 117.2008, lat: 39.0842 }] },
            { name: '重庆', cities: [{ name: '重庆', lng: 106.5516, lat: 29.5630 }] },
            { 
                name: '广东', 
                cities: [
                    { name: '广州', lng: 113.2644, lat: 23.1291 },
                    { name: '深圳', lng: 114.0579, lat: 22.5431 },
                    { name: '东莞', lng: 113.7518, lat: 23.0205 },
                    { name: '佛山', lng: 113.1227, lat: 23.0215 }
                ]
            },
            {
                name: '江苏',
                cities: [
                    { name: '南京', lng: 118.7969, lat: 32.0603 },
                    { name: '苏州', lng: 120.6214, lat: 31.3029 },
                    { name: '无锡', lng: 120.2958, lat: 31.5698 }
                ]
            },
            {
                name: '浙江',
                cities: [
                    { name: '杭州', lng: 120.1551, lat: 30.2741 },
                    { name: '宁波', lng: 121.5629, lat: 29.8683 },
                    { name: '温州', lng: 120.6993, lat: 27.9943 }
                ]
            }
        ];
        
        // 尝试从本地存储加载
        const savedProvince = localStorage.getItem('selectedProvince');
        const savedCity = localStorage.getItem('selectedCity');

        if (savedProvince && this.provinces.some(p => p.name === savedProvince)) {
            this.selectedProvince = savedProvince;
            this.updateAvailableCities();
            if (savedCity && this.availableCities.some(c => c.name === savedCity)) {
                this.selectedCity = savedCity;
                this.onCityChange(); // 确保地图更新
            }
        }
    },

    updateAvailableCities() {
        const province = this.provinces.find(p => p.name === this.selectedProvince);
        if (province) {
            this.availableCities = province.cities;
        } else {
            this.availableCities = [];
        }
    },

    onProvinceChange() {
        this.updateAvailableCities();
        // 默认选择第一个城市（通常是省会）
        if (this.availableCities.length > 0) {
            this.selectedCity = this.availableCities[0].name;
            this.onCityChange();
        } else {
            this.selectedCity = '';
        }
    },

    onCityChange() {
        if (!this.selectedCity) return;
        
        const city = this.availableCities.find(c => c.name === this.selectedCity);
        if (city) {
            localStorage.setItem('selectedProvince', this.selectedProvince);
            localStorage.setItem('selectedCity', this.selectedCity);
            const mapDisplay = this.$refs.mapDisplayRef;
            if (mapDisplay) {
                mapDisplay.setCenterToCity(city.lng, city.lat, city.name);
            }
        }
    },
    
    // 保存家的位置到本地存储
    async saveHomeLocation() {
      // ... （确保 homeAddressInput, homeLatitudeInput, homeLongitudeInput 有效） ...
      const address = this.homeAddressInput;
      const latitude = parseFloat(this.homeLatitudeInput);
      const longitude = parseFloat(this.homeLongitudeInput);

      if (!address || isNaN(latitude) || isNaN(longitude)) {
        this.showNotification('地址或经纬度无效，无法保存。', 'error');
        console.error('保存家位置错误: 地址或经纬度无效', { address, latitude, longitude });
        return;
      }

      const homeData = {
        address: address,
        location: {
          latitude: latitude,
          longitude: longitude
        }
      };

      // 用于调试：记录将要保存到 localStorage 的数据
      console.log('Attempting to save homeLocation to localStorage. Data:', JSON.stringify(homeData)); 
      
      localStorage.setItem('homeLocation', JSON.stringify(homeData));
      this.homeAddress = address;
      this.homeLocation = homeData.location;
      this.showNotification('家已成功保存到本地！', 'success');
      
      // 更新地图显示
      this.$nextTick(() => {
        const mapDisplay = this.$refs.mapDisplayRef;
        if (mapDisplay && this.homeLocation) {
          mapDisplay.setHomeLocation(
            this.homeLocation.longitude, 
            this.homeLocation.latitude, 
            this.homeAddress
          );
        }
      });
      // ... 如果有后端保存逻辑，也在这里处理 ...
    },

    loadHomeLocation() {
      const savedHomeLocation = localStorage.getItem('homeLocation');
      if (savedHomeLocation) {
        try {
          const data = JSON.parse(savedHomeLocation);
          // 增强校验：确保 data.address 是字符串，data.location 是包含有效经纬度的对象
          if (data && 
              typeof data.address === 'string' &&
              data.location &&
              typeof data.location === 'object' &&
              Object.prototype.hasOwnProperty.call(data.location, 'latitude') &&
              Object.prototype.hasOwnProperty.call(data.location, 'longitude') &&
              typeof data.location.latitude === 'number' && !isNaN(data.location.latitude) &&
              typeof data.location.longitude === 'number' && !isNaN(data.location.longitude)) {
            
            this.homeAddress = data.address;
            this.homeLocation = {
                latitude: data.location.latitude,
                longitude: data.location.longitude
            };
            
            // 在地图上显示家的位置
            this.$nextTick(() => {
              const mapDisplay = this.$refs.mapDisplayRef;
              if (mapDisplay && this.homeLocation && 
                  typeof this.homeLocation.longitude === 'number' && 
                  typeof this.homeLocation.latitude === 'number') {
                mapDisplay.setHomeLocation(
                  this.homeLocation.longitude, 
                  this.homeLocation.latitude, 
                  this.homeAddress
                );
              } else if (mapDisplay) {
                console.error('Error in loadHomeLocation: this.homeLocation is invalid before calling mapDisplay.setHomeLocation.', this.homeLocation);
              }
            });
            console.log('已加载保存的家地址:', this.homeAddress);
          } else {
            console.error('加载的家地址数据格式无效 (结构、类型或值错误)。实际数据:', data);
            localStorage.removeItem('homeLocation'); // 清除无效数据
          }
        } catch (error) {
          console.error('加载家地址失败 (JSON 解析错误或其他异常):', error, '原始数据:', savedHomeLocation);
          localStorage.removeItem('homeLocation');
        }
      } else {
        console.log('未找到保存的家地址。');
      }
    },
    
    selectCity(city) {
      this.selectedCity = city.name;
      localStorage.setItem('selectedCity', city.name); // 保存选择的城市
      const mapDisplay = this.$refs.mapDisplayRef;
      if (mapDisplay) {
        mapDisplay.setCenterToCity(city.lng, city.lat, city.name);
      }
    },
    
    // 检测是否为连锁店品牌
    isChainStore(shopName) {
      const chainBrands = [
        '麦当劳', 'mcdonald',
        '肯德基', 'kfc',
        '星巴克', 'starbucks',
        '必胜客', 'pizza hut',
        '汉堡王', 'burger king',
        '全家',
        '7-eleven', '711',
        '便利蜂',
        '罗森', 'lawson'
      ];

      const name = shopName.toLowerCase();
      return chainBrands.some(brand => 
        name.includes(brand.toLowerCase())
      );
    },
    
    // 判断单个店铺是否为连锁店
    isChainStoreItem(shop) {
      if (!shop || !shop.name) return false;
      return this.isChainStore(shop.name);
    },
    
    // 获取已选店铺中的连锁店
    getExistingChainStores() {
      return this.shopsToVisit.filter(shop => this.isChainStoreItem(shop));
    },
    
    // 获取已选店铺中的非连锁店
    getNonChainStores() {
      return this.shopsToVisit.filter(shop => !this.isChainStoreItem(shop));
    },
    
    // 检测是否有多品牌优化
    hasMultiBrandOptimization() {
      return this.shopSuggestions.some(shop => shop.isMultiBrandOptimal);
    },
    
    // 获取优化信息
    getOptimizationInfo() {
      const uniqueBrands = new Set();
      this.shopSuggestions.forEach(shop => {
        if (shop.brands) {
          shop.brands.forEach(brand => uniqueBrands.add(brand));
        }
      });
      
      if (uniqueBrands.size > 1) {
        const brandArray = Array.from(uniqueBrands);
        // 估算组合数（每个品牌最多8家店铺）
        const combinationCount = Math.pow(8, brandArray.length);
        return combinationCount > 100 ? '100+' : combinationCount.toString();
      }
      
      return '单品牌';
    },
    
    // 获取当前时间（HH:MM格式）
    getCurrentTime() {
      const now = new Date();
      const hours = now.getHours().toString().padStart(2, '0');
      const minutes = now.getMinutes().toString().padStart(2, '0');
      return `${hours}:${minutes}`;
    },
    
    // 获取店铺停留时间
    getStayDuration(shopId) {
      return this.stayDurations[shopId] || this.defaultStayDuration;
    },
    
    // 设置店铺停留时间
    setStayDuration(shopId, duration) {
      this.stayDurations[shopId] = duration;
    },
    
    // 计算时间点（从出发时间开始，加上行程时间和停留时间）
    calculateArrivalTimes(routeInfo) {
      if (!routeInfo || !routeInfo.shops) return [];
      
      const startTime = this.parseTime(this.departureTime);
      const times = [];
      let currentTime = startTime;
      
      // 添加出发时间
      times.push({
        type: 'departure',
        location: '家',
        time: this.formatTime24(currentTime),
        description: '从家出发'
      });
      
      // 计算每个店铺的到达和离开时间
      for (let i = 0; i < routeInfo.shops.length; i++) {
        const shop = routeInfo.shops[i];
        
        // 计算到达该店铺的时间
        let travelTime = this.extractTravelTimeForSegment(routeInfo, i);
        
        currentTime = this.addMinutes(currentTime, travelTime);
        const arrivalTime = this.formatTime24(currentTime);
        
        // 停留时间
        const stayDuration = this.getStayDuration(shop.id);
        const departureTime = this.formatTime24(this.addMinutes(currentTime, stayDuration));
        
        times.push({
          type: 'arrival',
          location: shop.name,
          address: shop.address,
          time: arrivalTime,
          departureTime: departureTime,
          stayDuration: stayDuration,
          description: `到达${shop.name}，停留${stayDuration}分钟`,
          travelTime: travelTime
        });
        
        // 更新当前时间为离开时间
        currentTime = this.addMinutes(currentTime, stayDuration);
      }
      
      // 计算回家时间
      const finalTravelTime = this.extractReturnTravelTime(routeInfo);
      currentTime = this.addMinutes(currentTime, finalTravelTime);
      times.push({
        type: 'return',
        location: '家',
        time: this.formatTime24(currentTime),
        description: '回到家',
        travelTime: finalTravelTime
      });
      
      return times;
    },
    
    // 从路线指导中提取特定段的行程时间
    extractTravelTimeForSegment(routeInfo, segmentIndex) {
      if (!routeInfo.instructions || routeInfo.instructions.length === 0) {
        // 没有详细指导时，使用平均时间
        return Math.round(routeInfo.time / routeInfo.shops.length / 60) || 15;
      }
      
      // 尝试从指导文本中提取时间
      let totalTime = 0;
      let foundTimes = 0;
      
      for (const instruction of routeInfo.instructions) {
        // 匹配各种时间格式
        const timeMatches = instruction.match(/(\d+)分钟|(\d+)小时|约(\d+)分钟|预计(\d+)分钟|行车时间约(\d+)分钟/g);
        
        if (timeMatches) {
          timeMatches.forEach(match => {
            const minutes = parseInt(match.match(/(\d+)/)[1]);
            if (match.includes('小时')) {
              totalTime += minutes * 60;
      } else {
              totalTime += minutes;
            }
            foundTimes++;
          });
        }
      }
      
      if (foundTimes > 0) {
        // 平均分配到每个路段
        return Math.round(totalTime / Math.max(foundTimes, routeInfo.shops.length));
      }
      
      // 备用计算：基于总时间和店铺数量
      return Math.round(routeInfo.time / routeInfo.shops.length / 60) || 15;
    },
    
    // 提取返回家的行程时间
    extractReturnTravelTime(routeInfo) {
      // 假设返回时间与最后一段相似
      return this.extractTravelTimeForSegment(routeInfo, routeInfo.shops.length - 1);
    },
    
    // 初始化筛选选项
    initializeStoreFilters(routes) {
      this.availableStoreFilters = {};
      this.selectedStoreFilters = {};
      
      // 收集所有路线中的连锁店信息
      const allCombinations = [...routes.byDistance, ...routes.byTime];
      
      allCombinations.forEach(route => {
        route.chainCombination.forEach(store => {
          if (store.selectedBrand) {
            if (!this.availableStoreFilters[store.selectedBrand]) {
              this.availableStoreFilters[store.selectedBrand] = [];
            }
            
            // 避免重复添加同一家店
            const exists = this.availableStoreFilters[store.selectedBrand].find(s => s.id === store.id);
            if (!exists) {
              this.availableStoreFilters[store.selectedBrand].push({
                id: store.id,
                name: store.name,
                address: store.address,
                longitude: store.longitude,
                latitude: store.latitude
              });
            }
          }
        });
      });
      
      // 初始化为全选状态
      Object.keys(this.availableStoreFilters).forEach(brand => {
        this.selectedStoreFilters[brand] = this.availableStoreFilters[brand].map(store => store.id);
      });
    },
    
    // 切换筛选面板显示
    toggleFilters() {
      this.showFilters = !this.showFilters;
    },
    
    // 切换店铺筛选状态
    toggleStoreFilter(brand, storeId) {
      if (!this.selectedStoreFilters[brand]) {
        this.selectedStoreFilters[brand] = [];
      }
      
      const index = this.selectedStoreFilters[brand].indexOf(storeId);
      if (index > -1) {
        this.selectedStoreFilters[brand].splice(index, 1);
      } else {
        this.selectedStoreFilters[brand].push(storeId);
      }
    },
    
    // 全选/取消全选某个品牌
    toggleBrandFilter(brand, selectAll) {
      if (selectAll) {
        this.selectedStoreFilters[brand] = this.availableStoreFilters[brand].map(store => store.id);
      } else {
        this.selectedStoreFilters[brand] = [];
      }
    },
    
    // 根据筛选条件过滤路线
    getFilteredRoutes(routes) {
      if (!this.showFilters || Object.keys(this.selectedStoreFilters).length === 0) {
        return routes;
      }
      
      const filterRoute = (route) => {
        // 检查路线中的连锁店是否符合筛选条件
        return route.chainCombination.every(store => {
          if (!store.selectedBrand) return true; // 非连锁店总是通过
          
          const selectedStores = this.selectedStoreFilters[store.selectedBrand] || [];
          return selectedStores.includes(store.id);
        });
      };
      
      return {
        byDistance: routes.byDistance.filter(filterRoute),
        byTime: routes.byTime.filter(filterRoute),
        totalCombinations: routes.totalCombinations,
        analyzedCombinations: routes.analyzedCombinations
      };
    },
    
    // 解析时间字符串为分钟数
    parseTime(timeStr) {
      const [hours, minutes] = timeStr.split(':').map(Number);
      return hours * 60 + minutes;
    },
    
    // 添加分钟数
    addMinutes(totalMinutes, minutesToAdd) {
      return totalMinutes + minutesToAdd;
    },
    
    // 格式化时间为HH:MM
    formatTime24(totalMinutes) {
      const hours = Math.floor(totalMinutes / 60) % 24;
      const minutes = totalMinutes % 60;
      return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
    },
    
    // 提取公交车号
    extractBusNumber(lineName) {
      if (!lineName) return null;
      
      // 匹配各种公交车号格式
      const patterns = [
        /(\d+)路/,           // "123路"
        /(\d+)号线/,         // "123号线" 
        /(\d+)[^\d]/,        // "123" 后面跟非数字
        /^(\d+)$/,           // 纯数字 "123"
        /([A-Z]\d+)/,        // "B12", "K123"
        /(\d+[A-Z])/         // "123A", "456B"
      ];
      
      for (const pattern of patterns) {
        const match = lineName.match(pattern);
        if (match) {
          return match[1];
        }
      }
      
      return lineName; // 如果没有匹配到，返回原名称
    },
    
    // 提取地铁线路号
    extractSubwayLine(lineName) {
      if (!lineName) return '地铁';
      
      // 地铁线路的常见格式
      const subwayPatterns = [
        /(地铁\d+号线)/,       // "地铁1号线"
        /(\d+号线)/,           // "1号线"
        /(号线\d+)/,           // "号线1"
        /(地铁[一二三四五六七八九十]+号线)/, // "地铁一号线"
      ];
      
      for (const pattern of subwayPatterns) {
        const match = lineName.match(pattern);
        if (match) {
          return match[1];
        }
      }
      
      // 如果包含"地铁"但没有匹配到标准格式
      if (lineName.includes('地铁')) {
        return lineName;
      }
      
      // 如果包含"号线"
      if (lineName.includes('号线')) {
        return lineName;
      }
      
      // 默认返回带"地铁"前缀
      return `地铁${lineName}`;
    },
    
    // 高级连锁店组合优化算法 - 支持多连锁店m×n组合计算
    async selectOptimalChainStore(chainStores, existingShops = []) {
      if (!this.homeLocation || chainStores.length === 0) {
        return chainStores.slice(0, 5);
      }
      
      // 检测是否有多个连锁店品牌
      const chainGroups = this.groupChainStoresByBrand(chainStores);
      const brandCount = Object.keys(chainGroups).length;
      
      console.log(`🧠 智能连锁店分析: 检测到${brandCount}个品牌，共${chainStores.length}家门店`);
      console.log('品牌分组:', Object.keys(chainGroups).map(brand => 
        `${brand}(${chainGroups[brand].length}家)`
      ));
      
      // 如果是多品牌连锁店，使用组合优化算法
      if (brandCount > 1) {
        return await this.optimizeMultiBrandCombinations(chainGroups, existingShops);
      }
      
      // 单品牌的情况，使用原有逻辑
      return await this.optimizeSingleBrandStores(chainStores, existingShops);
    },
    
    // 按品牌对连锁店分组
    groupChainStoresByBrand(chainStores) {
      const groups = {};
      const chainBrands = {
        '麦当劳': ['麦当劳', 'McDonald', 'mcdonald'],
        '肯德基': ['肯德基', 'KFC', 'kfc'],
        '星巴克': ['星巴克', 'Starbucks', 'starbucks'],
        '必胜客': ['必胜客', 'Pizza Hut', 'pizzahut'],
        '汉堡王': ['汉堡王', 'Burger King', 'burgerking'],
        '德克士': ['德克士'],
        '全家': ['全家', 'FamilyMart'],
        '7-Eleven': ['7-Eleven', '711', '7-11'],
        '便利蜂': ['便利蜂'],
        '罗森': ['罗森', 'Lawson']
      };
      
      chainStores.forEach(store => {
        let assigned = false;
        const storeName = store.name.toLowerCase();
        
        for (const [brand, keywords] of Object.entries(chainBrands)) {
          if (keywords.some(keyword => storeName.includes(keyword.toLowerCase()))) {
            if (!groups[brand]) groups[brand] = [];
            groups[brand].push(store);
            assigned = true;
            break;
          }
        }
        
        // 如果没有匹配到已知品牌，创建新组
        if (!assigned) {
          const firstWord = store.name.split(/[（\(]|分店|店/)[0].trim();
          if (!groups[firstWord]) groups[firstWord] = [];
          groups[firstWord].push(store);
        }
      });
      
      return groups;
    },
    
    // 多品牌组合优化算法
    async optimizeMultiBrandCombinations(chainGroups, existingShops) {
      const brands = Object.keys(chainGroups);
      const homePos = new AMap.LngLat(this.homeLocation.longitude, this.homeLocation.latitude);
      
      console.log(`🔍 开始多品牌组合优化: ${brands.join(' × ')}`);
      
      // 启发式预筛选：每个品牌只保留距离家较近的店铺
      const maxStoresPerBrand = 8; // 限制每个品牌最多考虑8家店铺
      const filteredGroups = {};
      
      for (const brand of brands) {
        const stores = chainGroups[brand];
        const storesWithDistance = stores.map(store => ({
          ...store,
          distanceToHome: this.calculateDistance(
            this.homeLocation.longitude, this.homeLocation.latitude,
            store.longitude, store.latitude
          )
        }));
        
        // 只保留距离较近的店铺，减少组合数量
        filteredGroups[brand] = storesWithDistance
          .sort((a, b) => a.distanceToHome - b.distanceToHome)
          .slice(0, maxStoresPerBrand)
          .filter(store => store.distanceToHome < 10000); // 过滤超过10km的店铺
      }
      
      // 计算所有可能的组合数量
      let totalCombinations = 1;
      for (const brand of brands) {
        totalCombinations *= filteredGroups[brand].length;
      }
      
      console.log(`📊 组合分析: ${brands.map(b => `${b}(${filteredGroups[b].length}家)`).join(' × ')} = ${totalCombinations}种组合`);
      
      // 如果组合数过多，进一步筛选
      if (totalCombinations > 200) {
        console.log('⚠️ 组合数过多，进行进一步筛选...');
        for (const brand of brands) {
          filteredGroups[brand] = filteredGroups[brand].slice(0, 5);
        }
        totalCombinations = brands.reduce((total, brand) => total * filteredGroups[brand].length, 1);
        console.log(`📊 筛选后组合数: ${totalCombinations}`);
      }
      
      // 生成所有组合并计算最优路线
      const combinations = this.generateStoreCombinations(filteredGroups);
      console.log(`🚀 开始评估${combinations.length}种组合...`);
      
      const results = [];
      let processedCount = 0;
      
      for (const combination of combinations) {
        try {
          // 包含已有店铺的完整路线
          const fullShopList = [...existingShops, ...combination];
          const routeTime = await this.calculateOptimalRouteTime(homePos, fullShopList);
          
          results.push({
            combination,
            totalRouteTime: routeTime,
            routeScore: routeTime + combination.reduce((sum, shop) => sum + shop.distanceToHome, 0) / 1000,
            brands: combination.map(shop => this.getBrandFromShop(shop))
          });
          
          processedCount++;
          if (processedCount % 20 === 0) {
            console.log(`📈 已处理 ${processedCount}/${combinations.length} 种组合`);
          }
        } catch (error) {
          console.warn('组合计算失败:', error);
        }
      }
      
      // 选择最优组合
      if (results.length === 0) {
        console.warn('没有找到有效的组合，回退到简单选择');
        return Object.values(filteredGroups).flat().slice(0, 5);
      }
      
      const bestResult = results.sort((a, b) => a.routeScore - b.routeScore)[0];
      const worstResult = results[results.length - 1];
      
      console.log(`🏆 最优组合: ${bestResult.brands.join(' + ')}`);
      console.log(`⏱️ 最优路线时间: ${Math.round(bestResult.totalRouteTime)}分钟`);
      console.log(`📊 优化效果: 比最差组合节省${Math.round(worstResult.totalRouteTime - bestResult.totalRouteTime)}分钟`);
      
      // 返回最优组合，并添加一些次优选择
      const topResults = results.slice(0, 5);
      const optimizedStores = [];
      
      topResults.forEach((result, resultIndex) => {
        result.combination.forEach(store => {
          optimizedStores.push({
            ...store,
            isOptimalCombination: resultIndex === 0, // 最优组合标记
            isMultiBrandOptimal: true, // 多品牌优化标记
            totalRouteTime: result.totalRouteTime,
            combinationRank: resultIndex + 1,
            brands: result.brands
          });
        });
      });
      
      return optimizedStores;
    },
    
    // 生成店铺组合（笛卡尔积）
    generateStoreCombinations(filteredGroups) {
      const brands = Object.keys(filteredGroups);
      const combinations = [];
      
      function generateRecursive(currentCombination, brandIndex) {
        if (brandIndex >= brands.length) {
          combinations.push([...currentCombination]);
        return;
      }
        
        const brand = brands[brandIndex];
        for (const store of filteredGroups[brand]) {
          currentCombination.push(store);
          generateRecursive(currentCombination, brandIndex + 1);
          currentCombination.pop();
        }
      }
      
      generateRecursive([], 0);
      return combinations;
    },
    
    // 获取店铺所属品牌
    getBrandFromShop(shop) {
      const name = shop.name.toLowerCase();
      if (name.includes('麦当劳') || name.includes('mcdonald')) return '麦当劳';
      if (name.includes('肯德基') || name.includes('kfc')) return '肯德基';
      if (name.includes('星巴克') || name.includes('starbucks')) return '星巴克';
      if (name.includes('必胜客') || name.includes('pizza hut')) return '必胜客';
      if (name.includes('汉堡王') || name.includes('burger king')) return '汉堡王';
      if (name.includes('全家')) return '全家';
      if (name.includes('7-eleven') || name.includes('711')) return '7-Eleven';
      if (name.includes('便利蜂')) return '便利蜂';
      if (name.includes('罗森') || name.includes('lawson')) return '罗森';
      return null;
    },
    
    // 单品牌店铺优化（原有逻辑的改进版）
    async optimizeSingleBrandStores(chainStores, existingShops) {
      const homePos = new AMap.LngLat(this.homeLocation.longitude, this.homeLocation.latitude);
      
      // 如果没有其他店铺，直接按距离排序
      if (existingShops.length === 0) {
        const storesWithDistance = chainStores.map(store => {
          const distance = this.calculateDistance(
            this.homeLocation.longitude, this.homeLocation.latitude,
            store.longitude, store.latitude
          );
          return { ...store, distanceToHome: distance, totalRouteTime: distance / 30 };
        });
        
        return storesWithDistance
          .sort((a, b) => a.distanceToHome - b.distanceToHome)
          .slice(0, 5);
      }
      
      // 有其他店铺时，计算整体路线优化
      const chainStoreAnalysis = [];
      
      for (const chainStore of chainStores) {
        try {
          const fullShopList = [...existingShops, chainStore];
          const routeTime = await this.calculateOptimalRouteTime(homePos, fullShopList);
          
          chainStoreAnalysis.push({
            ...chainStore,
            totalRouteTime: routeTime,
            routeScore: routeTime + (chainStore.distance || 0) / 1000
          });
        } catch (error) {
          const distance = this.calculateDistance(
            this.homeLocation.longitude, this.homeLocation.latitude,
            chainStore.longitude, chainStore.latitude
          );
          chainStoreAnalysis.push({
            ...chainStore,
            totalRouteTime: distance / 30,
            routeScore: distance / 30,
            isEstimated: true
          });
        }
      }
      
      return chainStoreAnalysis
        .sort((a, b) => a.routeScore - b.routeScore)
        .slice(0, 5);
    },
    
    // 计算最优路线总时间
    async calculateOptimalRouteTime(homePos, shops, travelMode = 'DRIVING') {
      if (shops.length === 0) return 0;
      if (shops.length === 1) {
        return this.calculateTravelTime(
          homePos, 
          shops[0], 
          travelMode
        ) * 2; // 往返时间
      }
      
      // 使用最近邻算法计算路线时间
      const unvisited = [...shops];
      let currentPos = homePos;
      let totalTime = 0;
      
      while (unvisited.length > 0) {
        let nearest = unvisited[0];
        let minTime = this.calculateTravelTime(currentPos, nearest, travelMode);
        
        for (let i = 1; i < unvisited.length; i++) {
          const shop = unvisited[i];
          const travelTime = this.calculateTravelTime(currentPos, shop, travelMode);
          
          if (travelTime < minTime) {
            nearest = shop;
            minTime = travelTime;
          }
        }
        
        totalTime += minTime;
        currentPos = new AMap.LngLat(nearest.longitude, nearest.latitude);
        unvisited.splice(unvisited.indexOf(nearest), 1);
      }
      
      // 加上返回家的时间
      totalTime += this.calculateTravelTime(currentPos, homePos, travelMode);
      
      return totalTime;
    },
    
    // 计算两点间的预估旅行时间（根据出行方式调整）
    calculateTravelTime(pos1, pos2, travelMode = 'DRIVING') {
      const distance = this.calculateDistance(
        pos1.lng || pos1.longitude, pos1.lat || pos1.latitude,
        pos2.lng || pos2.longitude, pos2.lat || pos2.latitude
      );
      
      // 根据出行方式设置不同的速度
      let speedMeterPerMinute;
      
      if (travelMode === 'DRIVING') {
        // 驾车：城市内平均速度约25-35公里/小时，考虑红绿灯和拥堵
        // 30公里/小时 = 500米/分钟
        speedMeterPerMinute = 1000;
      } else if (travelMode === 'TRANSIT') {
        // 公交：包含等车、换乘时间，平均约15-20公里/小时
        // 18公里/小时 = 300米/分钟
        speedMeterPerMinute = 300;
      } else {
        // 步行：约5公里/小时
        // 5公里/小时 = 83米/分钟，但考虑城市步行，使用更保守的值
        speedMeterPerMinute = 70;
      }
      
      return distance / speedMeterPerMinute;
    },
    
    // 计算两点间距离（简化版）
    calculateDistance(lng1, lat1, lng2, lat2) {
      if (window.AMap && AMap.GeometryUtil) {
        return AMap.GeometryUtil.distance(
          new AMap.LngLat(lng1, lat1),
          new AMap.LngLat(lng2, lat2)
        );
      }
      
      // 备用计算方法（haversine公式简化版）
      const R = 6371000; // 地球半径（米）
      const dLat = (lat2 - lat1) * Math.PI / 180;
      const dLng = (lng2 - lng1) * Math.PI / 180;
      const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                Math.sin(dLng/2) * Math.sin(dLng/2);
      const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
      return R * c;
    },
    
    // 地址输入自动完成
    async onAddressInput() {
      if (this.homeAddress.trim().length < 2) {
        this.addressSuggestions = [];
          return;
      }

      try {
        const payload = {
          keywords: this.homeAddress.trim(),
        };
        
        if (this.selectedCity) {
          payload.city = this.selectedCity;
        }
        
        const response = await axios.post('/api/shops/find', payload);
        if (response.data.shops && response.data.shops.length > 0) {
          this.addressSuggestions = response.data.shops.slice(0, 5);
        } else {
          this.addressSuggestions = [];
        }
      } catch (error) {
        console.error('Error fetching address suggestions:', error);
        this.addressSuggestions = [];
      }
    },
    
    hideAddressSuggestions() {
      setTimeout(() => {
        this.showAddressSuggestions = false;
      }, 200);
    },
    
    selectAddressSuggestion(suggestion) {
      this.homeAddress = suggestion.address || suggestion.name;
      this.homeLocation = {
        longitude: suggestion.longitude,
        latitude: suggestion.latitude,
        address: suggestion.address || suggestion.name
      };
      
      // 添加这些行来设置Input变量
      this.homeAddressInput = suggestion.address || suggestion.name;
      this.homeLatitudeInput = suggestion.latitude ? suggestion.latitude.toString() : '';
      this.homeLongitudeInput = suggestion.longitude ? suggestion.longitude.toString() : '';
      
      this.showAddressSuggestions = false;
      this.addressSuggestions = [];
      
      // 保存家的位置到本地存储
      this.saveHomeLocation();
      
      // 在地图上显示家的位置
      const mapDisplay = this.$refs.mapDisplayRef;
      if (mapDisplay && suggestion.latitude && suggestion.longitude) {
        mapDisplay.setHomeLocation(suggestion.longitude, suggestion.latitude, this.homeAddress);
      }
    },
    
    // 店铺输入自动完成 - 重新设计的正确逻辑
    async onShopInput() {
      if (this.shopInput.trim().length < 2) {
        this.shopSuggestions = [];
        return;
      }
      
      try {
        const payload = {
          keywords: this.shopInput.trim(),
        };
        
        if (this.selectedCity) {
          payload.city = this.selectedCity;
        }
        
        console.log('搜索店铺参数:', payload);
        const response = await axios.post('/api/shops/find', payload);
        
        if (response.data.shops && response.data.shops.length > 0) {
          // 返回前8个建议
          this.shopSuggestions = response.data.shops.slice(0, 8);
          console.log('店铺建议:', this.shopSuggestions);
        } else {
          this.shopSuggestions = [];
          this.showNotification(`未找到"${this.shopInput}"相关店铺，请尝试其他关键词`, 'warning');
        }
      } catch (error) {
        console.error('Error fetching shop suggestions:', error);
        this.shopSuggestions = [];
        this.showNotification('搜索失败，请检查网络连接', 'error');
      }
    },
    
    hideShopSuggestions() {
      setTimeout(() => {
        this.showShopSuggestions = false;
      }, 200);
    },
    
    // 修正此方法以正确处理连锁店和私人店铺
    selectShopSuggestion(suggestion) {
      this.addShopByName(suggestion.name);
      this.shopSuggestions = [];
      this.shopInput = '';
    },
    
    removeShop(shopId) {
      this.shopsToVisit = this.shopsToVisit.filter(shop => shop.id !== shopId);
      
      // 从地图移除标记
      const mapDisplay = this.$refs.mapDisplayRef;
      if (mapDisplay) {
        mapDisplay.removeShopMarker(shopId);
      }
      
      // 清除路线信息
      this.routeInfo = null;
    },
    
    // 执行连锁店组合优化
    async performChainStoreOptimization(chainStores, privateStores) {
      const homePos = new AMap.LngLat(this.homeLocation.longitude, this.homeLocation.latitude);
      
      // 获取每个连锁店品牌的所有分店位置
      const chainBrandStores = {};
      for (const chainStore of chainStores) {
        console.log(`🔍 获取${chainStore.brandName}的所有分店...`);
        
        try {
          const payload = { keywords: chainStore.brandName };
          if (this.selectedCity) {
            payload.city = this.selectedCity;
          }
          
          const response = await axios.post('/api/shops/find', payload);
          if (response.data.shops && response.data.shops.length > 0) {
            // 筛选距离家较近的分店（减少组合数量）
            const nearbyStores = response.data.shops
              .map(store => ({
                ...store,
                distanceToHome: this.calculateDistance(
                  this.homeLocation.longitude, this.homeLocation.latitude,
                  store.longitude, store.latitude
                )
              }))
              .filter(store => store.distanceToHome < 15000) // 15km以内
              .sort((a, b) => a.distanceToHome - b.distanceToHome)
              .slice(0, 8); // 最多8家分店
            
            chainBrandStores[chainStore.brandName] = nearbyStores;
            console.log(`${chainStore.brandName}: 找到${nearbyStores.length}家附近分店`);
          }
        } catch (error) {
          console.error(`获取${chainStore.brandName}分店失败:`, error);
          chainBrandStores[chainStore.brandName] = [];
        }
      }
      
      // 生成所有可能的组合
      const combinations = this.generateChainStoreCombinations(chainBrandStores);
      console.log(`📊 生成${combinations.length}种分店组合`);
      
      if (combinations.length === 0) {
        throw new Error('未找到有效的连锁店分店组合');
      }
      
      // 计算每种组合的路线
      const routeResults = [];
      let processedCount = 0;
      
             for (const combination of combinations.slice(0, 50)) { // 限制最多计算50种组合
         try {
           const allStores = [...privateStores, ...combination];
           const routeTime = await this.calculateOptimalRouteTime(homePos, allStores, this.travelMode);
           const routeDistance = this.calculateTotalDistance(homePos, allStores, this.travelMode);
           
           routeResults.push({
             stores: allStores,
             chainCombination: combination,
             totalTime: routeTime,
             totalDistance: routeDistance,
             routeScore: routeTime * 0.7 + routeDistance / 100 * 0.3 // 综合评分
           });
          
          processedCount++;
          if (processedCount % 10 === 0) {
            console.log(`📈 已计算${processedCount}/${Math.min(combinations.length, 50)}种组合`);
          }
        } catch (error) {
          console.warn('组合路线计算失败:', error);
        }
      }
      
      if (routeResults.length === 0) {
        throw new Error('所有组合的路线计算都失败了');
      }
      
      // 生成多个候选路线：按距离和时间分别排序
      const routesByDistance = [...routeResults].sort((a, b) => a.totalDistance - b.totalDistance);
      const routesByTime = [...routeResults].sort((a, b) => a.totalTime - b.totalTime);
      
      return {
        byDistance: routesByDistance.slice(0, 3), // 前3个最短距离路线
        byTime: routesByTime.slice(0, 3), // 前3个最短时间路线
        totalCombinations: combinations.length,
        analyzedCombinations: processedCount
      };
    },
    
    // 生成连锁店组合（笛卡尔积）
    generateChainStoreCombinations(chainBrandStores) {
      const brands = Object.keys(chainBrandStores);
      const combinations = [];
      
      function generateRecursive(currentCombination, brandIndex) {
        if (brandIndex >= brands.length) {
          if (currentCombination.length > 0) {
            combinations.push([...currentCombination]);
          }
          return;
        }
        
        const brand = brands[brandIndex];
        const stores = chainBrandStores[brand];
        
        for (const store of stores) {
          currentCombination.push({
            ...store,
            selectedBrand: brand
          });
          generateRecursive(currentCombination, brandIndex + 1);
          currentCombination.pop();
        }
      }
      
      generateRecursive([], 0);
      return combinations;
    },
    
    // 计算路线总距离
    calculateTotalDistance(homePos, stores, travelMode = 'DRIVING') {
      if (stores.length === 0) return 0;
      
      let totalDistance = 0;
      let currentPos = homePos;
      
      // 使用贪心算法计算最优顺序的总距离
      const unvisited = [...stores];
      
      while (unvisited.length > 0) {
        let nearest = unvisited[0];
        let minDistance = this.calculateDistance(
          currentPos.lng || currentPos.longitude, currentPos.lat || currentPos.latitude,
          nearest.longitude, nearest.latitude
        );
        
        for (let i = 1; i < unvisited.length; i++) {
          const store = unvisited[i];
          const distance = this.calculateDistance(
            currentPos.lng || currentPos.longitude, currentPos.lat || currentPos.latitude,
            store.longitude, store.latitude
          );
          
          if (distance < minDistance) {
            nearest = store;
            minDistance = distance;
          }
        }
        
        totalDistance += minDistance;
        currentPos = new AMap.LngLat(nearest.longitude, nearest.latitude);
        unvisited.splice(unvisited.indexOf(nearest), 1);
      }
      
      // 加上返回家的距离
      totalDistance += this.calculateDistance(
        currentPos.lng, currentPos.lat,
        homePos.lng || homePos.longitude, homePos.lat || homePos.latitude
      );
      
      return totalDistance;
    },
    
    // 选择特定路线
    async selectRoute(selectedRoute) {
      try {
        this.showNotification('正在生成详细路线指导...', 'info', '🗺️ 路线生成中');
        
        // 在地图上显示选中的路线
        const mapDisplay = this.$refs.mapDisplayRef;
        if (mapDisplay) {
          // 清除现有标记
          mapDisplay.clearAllMarkers();
          
          // 添加家的位置
          mapDisplay.setHomeLocation(
            this.homeLocation.longitude,
            this.homeLocation.latitude, 
            this.homeAddress
          );
          
          // 添加选中路线的店铺标记
          selectedRoute.stores.forEach(store => {
            mapDisplay.addShopMarker(store);
          });
          
          // 显示路线
          mapDisplay.displayRoute(this.homeAddress, selectedRoute.stores, this.travelMode);
        }
        
        // 更新路线信息为单一路线模式
        this.routeInfo = {
          type: 'single_route',
          distance: selectedRoute.totalDistance,
          time: selectedRoute.totalTime * 60, // 转换为秒
          shops: selectedRoute.stores,
          travelMode: this.travelMode,
          isSelected: true,
          selectedFrom: 'optimization'
        };
        
        this.showNotification('路线已选择，正在生成详细指导', 'success', '✅ 路线已确定');
        
      } catch (error) {
        console.error('选择路线失败:', error);
        this.showNotification('路线选择失败，请重试', 'error');
      }
    },
    
    onRouteCalculated(routeData) {
      this.routeInfo = routeData;
    },
    
    formatDistance(distance) {
      if (distance < 1000) {
        return `${Math.round(distance)}米`;
      } else {
        return `${(distance / 1000).toFixed(1)}公里`;
      }
    },
    
    formatTime(seconds) {
      if (seconds === null || isNaN(seconds)) return '未知';
      const h = Math.floor(seconds / 3600);
      const m = Math.floor((seconds % 3600) / 60);
      return `${h > 0 ? h + '小时' : ''}${m}分钟`;
    },
// 修改getDirections方法以适配当前后端响应格式

    // 修复的异步处理逻辑
    async getDirections() {
        if (this.isPlanning) return;
        this.isPlanning = true;
        this.isLoading = true;
        
        try {
            // 前置验证
            if (!this.homeLocation || !this.homeLocation.latitude || !this.homeLocation.longitude) {
                this.showNotification('请先设置家的位置', 'error');
                return;
            }
            if (!this.shopsToVisit || this.shopsToVisit.length === 0) {
                this.showNotification('请先添加要探访的店铺', 'error');
                return;
            }

            // 修复：分别处理私人店铺和连锁店铺，确保私人店铺不会被错误过滤
            const privateStores = [];
            const chainStores = [];
            const pendingStores = []; // 需要查询坐标信息的店铺

            // 重新分类店铺
            for (const shop of this.shopsToVisit) {
                if (shop.type === 'chain') {
                    chainStores.push(shop);
                } else {
                    // 对于私人店铺，检查是否有坐标信息
                    if (shop.latitude && shop.longitude && 
                        !isNaN(parseFloat(shop.latitude)) && !isNaN(parseFloat(shop.longitude))) {
                        privateStores.push(shop);
                    } else {
                        // 如果没有坐标信息，标记为需要查询
                        pendingStores.push(shop);
                    }
                }
            }

            console.log('🏪 店铺分类结果:', {
                privateStores: privateStores.length,
                chainStores: chainStores.length,
                pendingStores: pendingStores.length
            });

            let allShops = [...privateStores];

            // 处理需要查询坐标的私人店铺
            if (pendingStores.length > 0) {
                this.showNotification(`正在获取${pendingStores.length}个私人店铺的详细信息...`, 'info');
                
                for (const pendingShop of pendingStores) {
                    try {
                        const response = await axios.post('/api/shops/find', {
                            keywords: pendingShop.name,
                            city: this.selectedCity,
                            latitude: this.homeLocation.latitude,
                            longitude: this.homeLocation.longitude,
                            radius: 50000,
                            get_details: true
                        });

                        const shops = response.data.shops || [];
                        if (shops.length > 0) {
                            // 找到最接近的店铺
                            const closestShop = shops
                                .filter(s => s.latitude && s.longitude)
                                .map(s => ({
                                    ...s,
                                    distanceToHome: this.calculateDistanceSafe(
                                        this.homeLocation.longitude,
                                        this.homeLocation.latitude,
                                        s.longitude,
                                        s.latitude
                                    )
                                }))
                                .sort((a, b) => a.distanceToHome - b.distanceToHome)[0];

                            if (closestShop) {
                                allShops.push({
                                    id: pendingShop.id,
                                    name: closestShop.name,
                                    latitude: parseFloat(closestShop.latitude),
                                    longitude: parseFloat(closestShop.longitude),
                                    address: closestShop.address || '地址未知',
                                    stay_duration: this.getStayDuration(pendingShop.id) * 60,
                                    type: 'private'
                                });
                                console.log(`✅ 找到私人店铺: ${closestShop.name}`);
                            } else {
                                console.warn(`⚠️ 未找到私人店铺坐标: ${pendingShop.name}`);
                                this.showNotification(`未找到"${pendingShop.name}"的具体位置`, 'warning');
                            }
                        } else {
                            console.warn(`⚠️ 搜索私人店铺失败: ${pendingShop.name}`);
                            this.showNotification(`未找到店铺"${pendingShop.name}"`, 'warning');
                        }
                    } catch (error) {
                        console.error(`搜索私人店铺 ${pendingShop.name} 失败:`, error);
                    }
                }
            }

            // 并发处理连锁店分店搜索
            if (chainStores.length > 0) {
                this.showNotification(`正在搜索${chainStores.length}个连锁品牌的分店...`, 'info');
                const searchTasks = chainStores.map(chainStore => 
                    this.searchChainStoreNearby(chainStore)
                );
                const searchResults = await Promise.allSettled(searchTasks);
                searchResults.forEach((result, index) => {
                    if (result.status === 'fulfilled' && result.value) {
                        allShops.push(result.value);
                        console.log(`✅ 找到连锁店铺: ${result.value.name}`);
                    } else {
                        console.error(`搜索 ${chainStores[index].name} 失败:`, result.reason);
                        this.showNotification(`${chainStores[index].name} 分店搜索失败`, 'warning');
                    }
                });
            }

            console.log('🎯 最终用于路线规划的店铺:', allShops);
            
            // 继续后续逻辑
            await this.processRouteOptimization(allShops);
        } catch (error) {
            console.error('路线规划失败:', error);
            this.handleRouteError(error);
        } finally {
            this.isLoading = false;
            this.isPlanning = false;
        }
    },

    // 辅助方法：搜索单个连锁店附近分店
    async searchChainStoreNearby(chainStore) {
        try {
            const response = await axios.post('/api/shops/find', {
                keywords: chainStore.name,
                city: this.selectedCity,
                latitude: this.homeLocation.latitude,
                longitude: this.homeLocation.longitude,
                radius: 20000,
                get_details: true
            });
            const branches = response.data.shops || [];
            if (branches.length > 0) {
                const validBranches = branches.filter(b => {
                    return b.latitude && b.longitude && 
                           !isNaN(parseFloat(b.latitude)) && !isNaN(parseFloat(b.longitude));
                });
                if (validBranches.length > 0) {
                    const nearbyBranches = validBranches
                        .map(branch => ({
                            ...branch,
                            distanceToHome: this.calculateDistanceSafe(
                                this.homeLocation.longitude, 
                                this.homeLocation.latitude, 
                                branch.longitude, 
                                branch.latitude
                            )
                        }))
                        .filter(b => b.distanceToHome != null && b.distanceToHome < 50000)
                        .sort((a, b) => a.distanceToHome - b.distanceToHome)
                        .slice(0, 1);
                    if (nearbyBranches.length > 0) {
                        const selectedBranch = nearbyBranches[0];
                        return {
                            id: selectedBranch.id || `chain_${chainStore.name}_${Date.now()}`,
                            name: selectedBranch.name,
                            latitude: parseFloat(selectedBranch.latitude),
                            longitude: parseFloat(selectedBranch.longitude),
                            address: selectedBranch.address || '地址未知',
                            stay_duration: this.getStayDuration(chainStore.id) * 60,
                            type: 'chain',
                            brand: chainStore.name
                        };
                    }
                }
            }
            return null;
        } catch (error) {
            console.error(`搜索 ${chainStore.name} 分店失败:`, error);
            throw error;
        }
    },

    // 处理路线优化的独立方法
    async processRouteOptimization(allShops) {
        if (allShops.length === 0) {
            this.showNotification('没有找到可用的店铺进行路线规划', 'error');
            return;
        }
        this.showNotification(`正在计算${allShops.length}个店铺的最优路线组合...`, 'info');
        const payload = {
            home_location: {
                latitude: parseFloat(this.homeLocation.latitude),
                longitude: parseFloat(this.homeLocation.longitude)
            },
            shops: allShops.map(shop => ({
                id: shop.id,
                name: shop.name,
                latitude: parseFloat(shop.latitude),
                longitude: parseFloat(shop.longitude),
                address: shop.address,
                stay_duration: shop.stay_duration || (this.getStayDuration(shop.id) * 60)
            })),
            mode: this.travelMode === 'TRANSIT' ? 'public_transit' : this.travelMode.toLowerCase(),
            city: this.selectedCity || '北京',
            top_n: 10
        };
        const response = await axios.post('/api/route/optimize', payload);
        const routesData = response.data;
        if (!routesData || !routesData.route_candidates) {
            this.showNotification('服务器返回数据格式错误', 'error');
            return;
        }
        this.processRouteResults(routesData);
    },

    // 处理路线结果
    processRouteResults(routesData) {
        if (!routesData || !routesData.route_candidates || routesData.route_candidates.length === 0) {
            this.showNotification('未能计算出有效路线', 'warning');
            return;
        }

        const allRoutes = routesData.route_candidates;
        console.log('🔍 收到的路线数据:', allRoutes);

        // 按时间从短到长排序，取前5个
        const timeRoutes = [...allRoutes]
            .sort((a, b) => a.total_overall_duration - b.total_overall_duration)
            .slice(0, 5);

        // 按距离从短到长排序，取前5个  
        const distanceRoutes = [...allRoutes]
            .sort((a, b) => a.total_distance - b.total_distance)
            .slice(0, 5);

        console.log('⏱️ 按时间排序的路线:', timeRoutes);
        console.log('📍 按距离排序的路线:', distanceRoutes);
        
        // 转换路线数据格式
        const formatRoute = (route, index, type) => ({
            id: `route_${type}_${index}`,
            type: type,
            optimizationType: type === 'time' ? '时间最短' : '距离最短',
            rank: index + 1,
            combination: route.optimized_order || [],
            totalTime: Math.round(route.total_overall_duration),
            totalDistance: Math.round(route.total_distance),
            routeData: route,
            originalIndex: index
        });
        
        // 生成最终的路线组合数组
        this.routeCombinations = [
            ...timeRoutes.map((route, index) => formatRoute(route, index, 'time')),
            ...distanceRoutes.map((route, index) => formatRoute(route, index, 'distance'))
        ];
        
        console.log('🚗 最终生成的路线组合:', this.routeCombinations);
        
        if (this.routeCombinations.length === 0) {
            this.showNotification('未能计算出有效路线', 'warning');
            return;
        }
        
        // 清除当前路线详情，等待用户点击
        this.routeInfo = null;
        this.showRouteInfo = false;
        
        this.showNotification(`🎉 成功获取候选路线! 时间优化(${timeRoutes.length}条), 距离优化(${distanceRoutes.length}条)`, 'success');
    },

    // 错误处理方法
    handleRouteError(error) {
        let errorMessage = '路线规划失败';
        if (error.response) {
            errorMessage = error.response.data?.message || `服务器错误 (${error.response.status})`;
        } else if (error.request) {
            errorMessage = '网络连接失败，请检查网络设置';
        } else {
            errorMessage = '请求配置错误，请刷新页面重试';
        }
        this.showNotification(errorMessage, 'error');
    },

    // 选择特定路线的方法
    async selectRoute(routeOption) {
      // 如果是路线候选（只有摘要信息），从后端获取详细信息
      if (routeOption.id && !routeOption.routeData && !routeOption.steps) {
        try {
          this.showNotification('正在获取详细路线信息...', 'info');
          
          const response = await fetch(`http://localhost:5000/api/route/directions/${routeOption.id}`);
          if (!response.ok) {
            throw new Error('无法获取路线详情');
          }
          
          const detailedRoute = await response.json();
          console.log('获取到详细路线信息:', detailedRoute);
          console.log('原始segments:', detailedRoute.segments);
          
          // 更新路线信息显示，确保数据结构与模板匹配
          const processedTransitSegments = this.processTransitSegments(detailedRoute.segments || []);
          console.log('处理后的公交段:', processedTransitSegments);
          
          this.routeInfo = {
            segments: detailedRoute.segments || [],
            steps: detailedRoute.steps || [],
            distance: detailedRoute.distance,
            duration: detailedRoute.duration,
            cost: detailedRoute.cost,
            walking_distance: detailedRoute.walking_distance,
            polyline: detailedRoute.polyline,
            // 为了兼容模板，添加route_segments字段，确保公交详细步骤可见
            route_segments: processedTransitSegments.map(segment => ({
              ...segment,
              mode: 'public_transit' // 确保标记为公交模式
            }))
          };
          
          console.log('最终的routeInfo:', this.routeInfo);
          console.log('route_segments:', this.routeInfo.route_segments);
          this.showRouteInfo = true;
          this.selectedRouteId = routeOption.id;
          
          this.routeSummary = {
            totalTime: this.formatDuration(detailedRoute.duration / 60),
            totalDistance: this.formatDistance(detailedRoute.distance),
            optimizationType: routeOption.summary || '公交路线',
            walkingDistance: this.formatDistance(detailedRoute.walking_distance || 0)
          };
          
          // 在地图上显示路线
          const mapDisplay = this.$refs.mapDisplayRef;
          if (mapDisplay && detailedRoute.polyline) {
            mapDisplay.drawOptimizedRoute({ 
              polyline: detailedRoute.polyline,
              segments: detailedRoute.segments
            });
          }
          
          this.showNotification('路线详情已加载', 'success');
          
        } catch (error) {
          console.error('获取路线详情失败:', error);
          this.showNotification('获取路线详情失败，请重试', 'error');
        }
        return;
      }
      
      // 处理已有完整数据的路线
      if (!routeOption || !routeOption.routeData) {
          console.warn('没有路线数据可显示');
          return;
      }
      
      console.log('选择路线:', routeOption);
      console.log('当前出行方式:', this.travelMode);
      console.log('路线数据结构:', routeOption.routeData);
      
      const mapDisplay = this.$refs.mapDisplayRef;
      if (mapDisplay) {
          // 在地图上绘制路线
          mapDisplay.drawOptimizedRoute(routeOption.routeData);
      }
      
      // 预处理路线数据，确保公交路线段有正确的结构
      console.log('原始route_segments:', routeOption.routeData.route_segments);
      const processedRouteInfo = this.preprocessRouteData(routeOption.routeData);
      console.log('预处理后的routeInfo:', processedRouteInfo);
      console.log('预处理后的route_segments:', processedRouteInfo.route_segments);
      
      // 更新路线信息显示
      this.routeInfo = processedRouteInfo;
      this.selectedRoute = processedRouteInfo; // 重要：确保Dashboard.vue能获取到正确的数据
      this.showRouteInfo = true;
      this.currentSelectedRoute = routeOption;
      
      this.routeSummary = {
          totalTime: this.formatDuration(routeOption.totalTime / 60),
          totalDistance: this.formatDistance(routeOption.totalDistance),
          optimizationType: `${routeOption.optimizationType} (第${routeOption.rank}选择)`,
          combination: routeOption.combination.map(s => s.name).join(' → ')
      };
      
      // 更新UI中的选中状态
      this.selectedRouteId = routeOption.id;
      
      console.log('路线信息已更新:', {
        routeInfo: this.routeInfo,
        showRouteInfo: this.showRouteInfo,
        routeSummary: this.routeSummary
      });
      
      const realText = routeOption.isReal ? '(真实计算)' : '(模拟数据)';
      this.showNotification(`已选择: ${routeOption.optimizationType} 第${routeOption.rank}候选路线 ${realText}`, 'info');
    },

    // 预处理路线数据，确保公交段有正确的数据结构
    preprocessRouteData(routeData) {
      if (!routeData || !routeData.route_segments) {
        console.log('没有route_segments，返回原始数据');
        return routeData;
      }
      
      console.log('开始预处理route_segments，当前出行方式:', this.travelMode);
      
      // 处理每个路线段，确保有正确的类型和数据结构
      const processedSegments = routeData.route_segments.map((segment, index) => {
        console.log(`处理第${index}个segment:`, segment);
        const processedSegment = { ...segment };
        
        // 关键修复：检查segment是否有transit_segments（公交详细信息）
        if (segment.transit_segments && Array.isArray(segment.transit_segments)) {
          console.log(`segment ${index} 有transit_segments，设置为公交模式`);
          // 使用transit_segments处理公交路线的详细步骤
          const transitSteps = this.processTransitSegments(segment.transit_segments);
          processedSegment.steps = transitSteps[0]?.steps || [];
          processedSegment.mode = 'public_transit';
          console.log(`segment ${index} 处理后的mode:`, processedSegment.mode);
          return processedSegment;
        }
        
        // 如果有segments数据(来自公交API)，提取其中的公交/地铁信息
        if (segment.segments && Array.isArray(segment.segments)) {
          console.log(`segment ${index} 有segments，设置为公交模式`);
          const transitSteps = this.processTransitSegments(segment.segments);
          processedSegment.steps = transitSteps[0]?.steps || [];
          processedSegment.mode = 'public_transit';
          console.log(`segment ${index} 处理后的mode:`, processedSegment.mode);
          return processedSegment;
        }
        
        // 如果当前是公交出行方式，但segment没有明确的公交信息，强制设置为公交模式
        if (this.travelMode === 'TRANSIT' && !segment.mode) {
          console.log(`segment ${index} 当前是公交出行方式，强制设置为公交模式`);
          processedSegment.mode = 'public_transit';
          // 如果有steps，检查是否包含公交信息
          if (segment.steps && Array.isArray(segment.steps)) {
            processedSegment.steps = segment.steps;
          } else {
            // 创建基本的公交指导步骤
            processedSegment.steps = [{
              type: 'transit',
              instruction: `乘坐公交从${segment.from_name || '起点'}到${segment.to_name || '终点'}`
            }];
          }
          console.log(`segment ${index} 强制设置后的mode:`, processedSegment.mode);
          return processedSegment;
        }
        
        // 根据segment中的数据判断交通方式类型
        if (segment.walking) {
          processedSegment.type = 'walking';
          processedSegment.steps = segment.walking.steps || [];
        } else if (segment.bus) {
          processedSegment.type = 'bus';
          processedSegment.lines = segment.bus.lines || [];
        } else if (segment.railway) {
          processedSegment.type = 'railway';
          // 确保railway数据结构正确
        } else if (segment.subway) {
          processedSegment.type = 'subway';
          processedSegment.railway = segment.subway;
        } else if (segment.steps && Array.isArray(segment.steps)) {
          // 检查steps中是否有公交信息
          const hasTransitInfo = segment.steps.some(step => 
            step.type === 'bus' || step.type === 'railway' || step.instruction.includes('公交') || step.instruction.includes('地铁')
          );
          
          if (hasTransitInfo) {
            // 将steps转换为route_segments格式
            return segment.steps.map(step => ({
              from_name: step.from || segment.from_name || '起点',
              to_name: step.to || segment.to_name || '终点',
              type: step.type || 'unknown',
              instruction: step.instruction,
              duration: step.duration || 0,
              distance: step.distance || 0
            }));
          }
        }
        
        // 确保每个segment都有from_name和to_name
        if (!processedSegment.from_name) {
          processedSegment.from_name = '起点';
        }
        if (!processedSegment.to_name) {
          processedSegment.to_name = '终点';
        }
        
        return processedSegment;
      }).flat(); // 使用flat()来处理可能的嵌套数组
      
      return {
        ...routeData,
        route_segments: processedSegments
      };
    },
    // 辅助方法：安全计算距离
    calculateDistanceSafe(lng1, lat1, lng2, lat2) {
      try {
          const lon1 = parseFloat(lng1);
          const lat1Val = parseFloat(lat1);
          const lon2 = parseFloat(lng2);
          const lat2Val = parseFloat(lat2);
          
          if (isNaN(lon1) || isNaN(lat1Val) || isNaN(lon2) || isNaN(lat2Val)) {
              console.warn('距离计算参数无效:', { lng1, lat1, lng2, lat2 });
              return null;
          }
          
          if (window.AMap && AMap.GeometryUtil) {
              return AMap.GeometryUtil.distance(
                  new AMap.LngLat(lon1, lat1Val),
                  new AMap.LngLat(lon2, lat2Val)
              );
          }
          
          // 备用计算方法（haversine公式）
          const R = 6371000; // 地球半径（米）
          const dLat = (lat2Val - lat1Val) * Math.PI / 180;
          const dLng = (lon2 - lon1) * Math.PI / 180;
          const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                    Math.cos(lat1Val * Math.PI / 180) * Math.cos(lat2Val * Math.PI / 180) *
                    Math.sin(dLng/2) * Math.sin(dLng/2);
          const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
          return R * c;
      } catch (error) {
          console.error('距离计算失败:', error);
          return null;
      }
    },

    // 显示选定的路线
    displayRoute(routeOption) {
      if (!routeOption || !routeOption.routeData) {
          console.warn('没有路线数据可显示');
          return;
      }
      
      const mapDisplay = this.$refs.mapDisplayRef;
      if (mapDisplay) {
          // 在地图上绘制路线
          mapDisplay.drawOptimizedRoute(routeOption.routeData);
      }
      
      // 更新路线信息显示
      this.routeInfo = routeOption.routeData;
      this.showRouteInfo = true;
      this.routeSummary = {
          totalTime: this.formatDuration(routeOption.totalTime / 60), // 转换为分钟
          totalDistance: this.formatDistance(routeOption.totalDistance),
          optimizationType: routeOption.optimizationType,
          combination: routeOption.combination.map(s => s.name).join(' → ')
      };
      
      console.log('显示路线信息:', this.routeSummary);
    },

    // 切换到指定路线
    switchToRoute(index) {
      if (this.routeCombinations && index >= 0 && index < this.routeCombinations.length) {
          this.currentRouteIndex = index;
          this.displayRoute(this.routeCombinations[index]);
          this.showNotification(`已切换到路线 ${index + 1}: ${this.routeCombinations[index].optimizationType}`, 'info');
      }
    },

    // 获取停留时间的安全方法
    getStayDuration(shopId) {
        if (!shopId) return this.defaultStayDuration || 30;
        return this.stayDurations?.[shopId] || this.defaultStayDuration || 30;
    },

    // 添加调试方法
    debugRouteData() {
        console.log('=== 路线规划调试信息 ===');
        console.log('家的位置:', this.homeLocation);
        console.log('店铺列表:', this.shopsToVisit);
        console.log('选择的城市:', this.selectedCity);
        console.log('出行方式:', this.travelMode);
        console.log('是否可以计算路线:', this.canGetRoute);
        console.log('========================');
    },

    // 生成所有店铺组合的方法
    generateAllStoreCombinations(chainStoreGroups, privateStores) {
        const brandNames = Object.keys(chainStoreGroups);
        const combinations = [];
        
        if (brandNames.length === 0) {
            // 只有私人店铺
            return privateStores.length > 0 ? [privateStores] : [];
        }
        
        // 生成连锁店的笛卡尔积
        function generateCartesianProduct(groups, currentCombination, brandIndex) {
            if (brandIndex >= brandNames.length) {
                // 添加私人店铺到每个组合
                combinations.push([...currentCombination, ...privateStores]);
                return;
            }
            
            const currentBrand = brandNames[brandIndex];
            const stores = groups[currentBrand];
            
            if (stores.length === 0) {
                // 如果某个品牌没有找到店铺，跳过
                generateCartesianProduct(groups, currentCombination, brandIndex + 1);
            } else {
                for (const store of stores) {
                    currentCombination.push(store);
                    generateCartesianProduct(groups, currentCombination, brandIndex + 1);
                    currentCombination.pop();
                }
            }
        }
        
        generateCartesianProduct(chainStoreGroups, [], 0);
        
        console.log(`连锁店组合生成完成: ${combinations.length} 种组合`);
        return combinations;
    },

    // 生成路线的唯一标识
    generateRouteKey(combination) {
        return combination
            .map(shop => shop.id)
            .sort()
            .join('-');
    },

    // 显示选定的路线
    displayRoute(routeOption) {
        if (!routeOption || !routeOption.routeData) {
            return;
        }
        
        const mapDisplay = this.$refs.mapDisplayRef;
        if (mapDisplay) {
            // 在地图上绘制路线
            mapDisplay.drawOptimizedRoute(routeOption.routeData);
        }
        
        // 更新路线信息显示
        this.routeInfo = routeOption.routeData;
        this.showRouteInfo = true;
        this.routeSummary = {
            totalTime: this.formatDuration(routeOption.totalTime),
            totalDistance: this.formatDistance(routeOption.totalDistance),
            combination: routeOption.combination.map(s => s.name).join(' → ')
        };
    },

    // 切换到指定路线
    switchToRoute(index) {
        if (this.routeCombinations && index >= 0 && index < this.routeCombinations.length) {
            this.currentRouteIndex = index;
            this.displayRoute(this.routeCombinations[index]);
            this.showNotification(`已切换到路线 ${index + 1}`, 'info');
        }
    },

    // 添加格式化方法
    formatDuration(minutes) {
      if (isNaN(minutes) || minutes < 0) return '计算中';
      if (minutes < 60) {
        return `${Math.round(minutes)}分钟`;
      }
      const hours = Math.floor(minutes / 60);
      const remainingMinutes = Math.round(minutes % 60);
      return `${hours}小时${remainingMinutes}分钟`;
    },

    formatDistance(meters) {
      if (isNaN(meters) || meters < 0) return '计算中';
      if (meters < 1000) {
        return `${Math.round(meters)}米`;
      }
      return `${(meters / 1000).toFixed(1)}公里`;
    },

    // 添加店铺名称到探店列表
    async addShopByName(shopName) {
      if (!shopName || shopName.trim().length < 2) {
        this.showNotification('请输入有效的店铺名称', 'warning');
        return;
      }

      try {
        // 仅添加店铺名称到列表中，不立即查询详细信息
        this.shopsToVisit.push({
          id: Date.now().toString(), // 临时ID
          name: shopName.trim(),
          address: '待查询',
          latitude: null,
          longitude: null,
          type: this.isChainStore(shopName) ? 'chain' : 'private',
          status: 'pending',
          actualShops: [] // 用于存储该名称对应的所有实际店铺
        });

        this.shopInput = ''; // 清空输入框
        this.shopSuggestions = []; // 清空建议
        this.showNotification(`已添加"${shopName}"到探店列表`, 'success');
      } catch (error) {
        console.error('添加店铺失败:', error);
        this.showNotification('添加店铺失败，请重试', 'error');
      }
    },

    // 店铺输入处理
    async onShopInput() {
      if (this.shopInput.trim().length < 2) {
        this.shopSuggestions = [];
        return;
      }
      
      try {
        const payload = {
          keywords: this.shopInput.trim(),
        };
        
        if (this.selectedCity) {
          payload.city = this.selectedCity;
        }
        
        console.log('搜索店铺参数:', payload);
        const response = await axios.post('/api/shops/find', payload);
        
        if (response.data.shops && response.data.shops.length > 0) {
          // 返回前8个建议
          this.shopSuggestions = response.data.shops.slice(0, 8);
          console.log('店铺建议:', this.shopSuggestions);
        } else {
          this.shopSuggestions = [];
          this.showNotification(`未找到"${this.shopInput}"相关店铺，请尝试其他关键词`, 'warning');
        }
      } catch (error) {
        console.error('Error fetching shop suggestions:', error);
        this.shopSuggestions = [];
        this.showNotification('搜索失败，请检查网络连接', 'error');
      }
    },

    // 选择店铺建议
    selectShopSuggestion(suggestion) {
      this.addShopByName(suggestion.name);
      this.shopSuggestions = [];
      this.shopInput = '';
    },

    

    // 显示指定的路线
    displayRoute(routeInfo) {
      if (!routeInfo || !routeInfo.route) {
        return;
      }
      
      const mapDisplay = this.$refs.mapDisplayRef;
      if (!mapDisplay) {
        return;
      }
      
      // 清除现有路线
      mapDisplay.clearRoute();
      
      // 显示新路线
      mapDisplay.displayRoute(routeInfo.route);
      
      // 更新路线信息
      this.routeInfo = routeInfo.route;
      this.currentRouteShops = routeInfo.shops;
      
      // 计算总时间和距离
      this.routeSummary = {
        totalTime: this.formatDuration(routeInfo.totalTime),
        totalDistance: this.formatDistance(routeInfo.totalDistance),
        mode: this.travelMode
      };
      
      // 显示路线信息
      this.showRouteInfo = true;
    },

    // 切换到指定的路线组合
    switchToRoute(index) {
      if (this.routeCombinations && this.routeCombinations.length > index) {
        this.displayRoute(this.routeCombinations[index]);
        this.showNotification(`已切换到路线 ${index + 1}`, 'info');
      }
    },

    // 获取路段图标
    getSegmentIcon(segmentType) {
      const iconMap = {
        'walking': '🚶',
        'bus': '🚌',
        'subway': '🚇',
        'railway': '🚇',
        'taxi': '🚕',
        'driving': '🚗'
      };
      return iconMap[segmentType] || '🚶';
    },

    // 计算公交车站数
    calculateStopsCount(line) {
      if (!line) return 0;
      
      // 计算站数：途径站点数 + 1（到达站）
      const viaStops = line.via_stops ? line.via_stops.length : 0;
      return viaStops + 1;
    },

    // 计算地铁站数
    calculateSubwayStops(railway) {
      if (!railway) return 0;
      
      // 计算站数：途径站点数 + 1（到达站）
      const viaStops = railway.via_stops ? railway.via_stops.length : 0;
      return viaStops + 1;
    },

    // 格式化公交路线的站点信息
    formatStopsInfo(line) {
      if (!line) return '';
      
      const departure = line.departure_stop ? line.departure_stop.name : '起点';
      const arrival = line.arrival_stop ? line.arrival_stop.name : '终点';
      const stopsCount = this.calculateStopsCount(line);
      
      return `${departure} → ${arrival} (${stopsCount}站)`;
    },

    // 格式化地铁路线的站点信息
    formatSubwayStopsInfo(railway) {
      if (!railway) return '';
      
      const departure = railway.departure_stop ? railway.departure_stop.name : '起点';
      const arrival = railway.arrival_stop ? railway.arrival_stop.name : '终点';
      const stopsCount = this.calculateSubwayStops(railway);
      
      return `${departure} → ${arrival} (${stopsCount}站)`;
    },

    // 处理公交路线数据，确保正确的数据结构
    processTransitSegment(segment) {
      if (!segment) return segment;
      
      // 确保segment有正确的类型
      if (segment.bus && segment.bus.lines) {
        segment.type = 'bus';
        segment.lines = segment.bus.lines;
      } else if (segment.railway) {
        segment.type = 'railway';
      } else if (segment.walking) {
        segment.type = 'walking';
        segment.steps = segment.walking.steps || [];
      }
      
      return segment;
    },

    // 处理后端返回的公交路线段数据，转换为前端模板可用的格式
    processTransitSegments(segments) {
      if (!segments || !Array.isArray(segments)) {
        console.warn('processTransitSegments: 无效的segments参数', segments);
        return [];
      }

      // 将每个公交segment转换为适合前端显示的steps格式
      const processedSteps = [];

      segments.forEach((segment, segmentIndex) => {
        // 防护：确保segment对象存在
        if (!segment) {
          console.warn(`processTransitSegments: 第${segmentIndex}个segment为空`);
          return;
        }
        // 步行段
        if (segment.walking && segment.walking.steps) {
          segment.walking.steps.forEach(step => {
            // 防护：确保step对象存在
            if (!step) return;
            processedSteps.push({
              type: 'walk',
              instruction: step.instruction || `步行 ${step.distance || 0}米，约${Math.round((step.duration || 0) / 60)}分钟`,
              distance: step.distance || 0,
              duration: step.duration || 0
            });
          });
        }

        // 公交段
        if (segment.bus && segment.bus.lines) {
          segment.bus.lines.forEach(line => {
            // 防护：确保line对象存在
            if (!line) return;
            const departureStop = line.departure_stop?.name || '起点站';
            const arrivalStop = line.arrival_stop?.name || '终点站';
            const lineName = line.name || '未知线路';
            const viaStops = line.via_stops || [];
            const stopsCount = viaStops.length + 1;
            
            let instruction = `乘坐${lineName}，从${departureStop}到${arrivalStop}`;
            if (stopsCount > 1) {
              instruction += `（${stopsCount}站）`;
            }
            if (viaStops.length > 0) {
              const viaStopNames = viaStops.filter(stop => stop && stop.name).map(stop => stop.name).join('、');
              instruction += `，途经：${viaStopNames}`;
            }

            processedSteps.push({
              type: 'bus',
              instruction: instruction,
              line_name: lineName,
              departure_stop: departureStop,
              arrival_stop: arrivalStop,
              via_stops: viaStops,
              distance: line.distance || 0,
              duration: line.duration || 0
            });
          });
        }

        // 地铁段
        if (segment.railway) {
          const railway = segment.railway.alters ? segment.railway.alters[0] : segment.railway;
          // 防护：确保railway对象存在
          if (!railway) return;
          const departureStop = railway.departure_stop?.name || '起点站';
          const arrivalStop = railway.arrival_stop?.name || '终点站';
          const lineName = railway.name || '未知线路';
          const trip = railway.trip || '';
          const viaStops = railway.via_stops || [];
          const stopsCount = viaStops.length + 1;
          
          let instruction = `乘坐${lineName}`;
          if (trip) {
            instruction += `(${trip})`;
          }
          instruction += `，从${departureStop}到${arrivalStop}`;
          if (stopsCount > 1) {
            instruction += `（${stopsCount}站）`;
          }
          if (viaStops.length > 0) {
            const viaStopNames = viaStops.filter(stop => stop && stop.name).map(stop => stop.name).join('、');
            instruction += `，途经：${viaStopNames}`;
          }

          processedSteps.push({
            type: 'railway',
            instruction: instruction,
            line_name: lineName,
            trip: trip,
            departure_stop: departureStop,
            arrival_stop: arrivalStop,
            via_stops: viaStops,
            distance: railway.distance || 0,
            duration: railway.duration || 0
          });
        }

        // 出租车段
        if (segment.taxi) {
          const distance = segment.taxi.distance || 0;
          const duration = segment.taxi.duration || 0;
          processedSteps.push({
            type: 'taxi',
            instruction: `乘坐出租车${distance > 0 ? `，约${(distance / 1000).toFixed(2)}公里` : ''}${duration > 0 ? `，约${Math.round(duration / 60)}分钟` : ''}`,
            distance: distance,
            duration: duration
          });
        }
      });

      return [{
        from_name: '起点',
        to_name: '终点',
        mode: 'public_transit',
        steps: processedSteps,
        distance: segments.reduce((total, seg) => total + (seg.distance || 0), 0),
        duration: segments.reduce((total, seg) => total + (seg.duration || 0), 0)
      }];
    },

    // 解析路线数据中的交通方式类型
    parseTransitSegmentType(segment) {
      if (!segment) return 'unknown';
      
      if (segment.walking || segment.type === 'walking') return 'walking';
      if (segment.bus || segment.type === 'bus') return 'bus';
      if (segment.railway || segment.subway || segment.type === 'railway' || segment.type === 'subway') return 'subway';
      if (segment.taxi || segment.type === 'taxi') return 'taxi';
      
      return 'other';
    },

    // 提取并格式化公交车次信息
    formatBusLineInfo(line) {
      if (!line) return {};
      
      return {
        number: this.extractBusNumber(line.name),
        fullName: line.name,
        departure: line.departure_stop ? line.departure_stop.name : '未知站点',
        arrival: line.arrival_stop ? line.arrival_stop.name : '未知站点',
        stopsCount: this.calculateStopsCount(line),
        viaStops: line.via_stops || []
      };
    },

    // 提取并格式化地铁线路信息
    formatSubwayLineInfo(railway) {
      if (!railway) return {};
      
      return {
        lineName: this.extractSubwayLine(railway.name),
        trainNumber: railway.trip || '',
        departure: railway.departure_stop ? railway.departure_stop.name : '未知站点',
        arrival: railway.arrival_stop ? railway.arrival_stop.name : '未知站点',
        stopsCount: this.calculateSubwayStops(railway),
        viaStops: railway.via_stops || []
      };
    }
  },
  
  mounted() {
    // 设置默认值
    this.departureTime = this.getCurrentTime();

    // 加载省市数据和用户选择
    this.loadProvinceCityData();
    
    // 加载保存的家地址
    this.loadHomeLocation();
  }
};

// --- App Component (Root Component) ---
const App = {
  template: `
    <div id="nav">
      <router-link to="/">Dashboard</router-link> |
      <router-link to="/login" v.if="!isLoggedIn">Login</router-link>
      <span v-if="isLoggedIn"> | <a href="#" @click.prevent="logout">Logout</a></span>
      <router-link to="/register" v.if="!isLoggedIn"> | Register</router-link>
    </div>
    <router-view></router-view>
  `,
  computed: {
    isLoggedIn() {
      return !!localStorage.getItem('userToken'); // Check if token exists
    }
  },
  methods: {
    logout() {
      localStorage.removeItem('userToken');
      this.$router.push('/login');
    }
  }
};

// --- Router Configuration ---
const routes = [
  { path: '/login', component: Login, meta: { requiresGuest: true } },
  { path: '/register', component: Register, meta: { requiresGuest: true } },
  { path: '/', component: Dashboard, alias: '/dashboard', meta: { requiresAuth: true } }
];

const router = createRouter({
  history: createWebHashHistory(), // Using hash history for simplicity without server config
  routes,
});

// Navigation Guard
router.beforeEach((to, from, next) => {
  const loggedIn = !!localStorage.getItem('userToken'); // Check for token

  if (to.matched.some(record => record.meta.requiresAuth)) {
    if (!loggedIn) {
      next({ path: '/login' });
    } else {
      next();
    }
  } else if (to.matched.some(record => record.meta.requiresGuest)) {
    if (loggedIn) {
      next({ path: '/' }); // Redirect to dashboard if logged in and trying to access login/register
    } else {
      next();
    }
  }
  else {
    next();
  }
});

// --- Initialize Vue App ---
const app = createApp(App); // Use the App object defined above
app.use(router);

// Make axios globally available to components (optional, components can also import it)
// app.config.globalProperties.$axios = axios;

app.mount('#app');

console.log('Vue app initialized with basic routing and components.');

// Add modern CSS styling
const style = document.createElement('style');
style.textContent = `
/* 全局样式 */
* {
  box-sizing: border-box;
}

body { 
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif; 
  margin: 0; 
  padding: 0; 
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  min-height: 100vh;
  color: #333; 
}

#app { 
  max-width: 1200px; 
  margin: 0 auto; 
  padding: 20px; 
}

#nav { 
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  padding: 15px 20px; 
  border-radius: 12px;
  margin-bottom: 30px; 
  text-align: center;
  box-shadow: 0 4px 20px rgba(0,0,0,0.1);
}

#nav a { 
  font-weight: 600; 
  color: #2c3e50; 
  text-decoration: none; 
  margin: 0 15px;
  padding: 8px 16px;
  border-radius: 8px;
  transition: all 0.3s ease;
}

#nav a:hover {
  background-color: #f8f9fa;
  transform: translateY(-1px);
}

#nav a.router-link-exact-active { 
  color: #667eea; 
  background-color: rgba(102, 126, 234, 0.1);
}

/* 表单样式 */
form div { 
  margin-bottom: 20px; 
}

label { 
  display: block; 
  margin-bottom: 8px; 
  font-weight: 600;
  color: #2c3e50;
}

input[type="text"], input[type="password"] { 
  width: 100%; 
  padding: 15px 20px; 
  border: 2px solid #e9ecef; 
  border-radius: 12px; 
  font-size: 16px;
  transition: all 0.3s ease;
  outline: none;
}

input[type="text"]:focus, input[type="password"]:focus {
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

button { 
  background-color: #42b983; 
  color: white; 
  padding: 10px 15px; 
  border: none; 
  border-radius: 4px; 
  cursor: pointer; 
  font-size: 16px; 
  margin-left: 5px;
  transition: all 0.3s ease;
}

button:hover { 
  background-color: #36a476; 
}

button[type="submit"] { 
  width: 100%; 
  margin-left: 0;
  padding: 15px 25px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  font-weight: 600;
}

button[type="submit"]:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(102, 126, 234, 0.3);
}

.error-message { 
  color: #dc3545; 
  font-size: 0.9rem;
  background: rgba(220, 53, 69, 0.1);
  padding: 10px 15px;
  border-radius: 8px;
  margin-top: 10px;
}

.success-message { 
  color: #28a745; 
  font-size: 0.9rem;
  background: rgba(40, 167, 69, 0.1);
  padding: 10px 15px;
  border-radius: 8px;
  margin-top: 10px;
}

/* Dashboard Container */
.dashboard-container {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  border-radius: 20px;
  padding: 30px;
  box-shadow: 0 20px 40px rgba(0,0,0,0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

/* Header */
.app-header {
  text-align: center;
  margin-bottom: 40px;
  padding-bottom: 20px;
  border-bottom: 2px solid #f1f3f4;
}

.app-header h1 {
  margin: 0;
  font-size: 2.5rem;
  font-weight: 700;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.subtitle {
  margin: 10px 0 0 0;
  font-size: 1.1rem;
  color: #666;
  font-weight: 400;
}

/* Section styling */
.section {
  background: #fff;
  border-radius: 16px;
  padding: 25px;
  margin-bottom: 25px;
  box-shadow: 0 4px 15px rgba(0,0,0,0.05);
  border: 1px solid rgba(0,0,0,0.05);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.section:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0,0,0,0.1);
}

.section h3 {
  margin: 0 0 20px 0;
  font-size: 1.4rem;
  font-weight: 600;
  color: #2c3e50;
  display: flex;
  align-items: center;
  gap: 10px;
}

.icon {
  font-size: 1.2em;
}

/* 城市选择网格 */
.city-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 15px;
  margin-top: 20px;
}

.city-card {
  padding: 20px;
  border: 2px solid #e9ecef;
  border-radius: 12px;
  cursor: pointer;
  text-align: center;
  transition: all 0.3s ease;
  background: #f8f9fa;
}

.city-card:hover {
  border-color: #667eea;
  background: #fff;
  transform: translateY(-3px);
  box-shadow: 0 8px 20px rgba(102, 126, 234, 0.15);
}

.city-card.active {
  border-color: #667eea;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  transform: scale(1.05);
}

.city-name {
  font-weight: 600;
  font-size: 1.1rem;
  margin-bottom: 5px;
}

.city-desc {
  font-size: 0.9rem;
  opacity: 0.8;
}

/* 地图样式 */
.map-display-component {
  width: 100%;
  height: 500px;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 15px rgba(0,0,0,0.1);
}

/* 输入容器 */
.input-container {
  position: relative;
  margin-bottom: 20px;
}

.address-input, .shop-input {
  width: 100%;
  padding: 15px 20px;
  font-size: 16px;
  border: 2px solid #e9ecef;
  border-radius: 12px;
  background: #fff;
  transition: all 0.3s ease;
  outline: none;
}

.address-input:focus, .shop-input:focus {
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

/* 建议下拉框 */
.suggestions-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: #fff;
  border: 1px solid #e9ecef;
  border-top: none;
  border-radius: 0 0 12px 12px;
  max-height: 300px;
  overflow-y: auto;
  z-index: 1000;
  box-shadow: 0 8px 25px rgba(0,0,0,0.15);
}

.suggestion-item {
  padding: 15px 20px;
  cursor: pointer;
  border-bottom: 1px solid #f8f9fa;
  transition: background-color 0.2s ease;
}

.suggestion-item:hover {
  background-color: #f8f9fa;
}

.suggestion-item:last-child {
  border-bottom: none;
}

.suggestion-name {
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 4px;
}

.suggestion-address {
  color: #6c757d;
  font-size: 0.9rem;
}

.suggestion-distance {
  font-size: 0.8rem;
  color: #667eea;
  margin-top: 4px;
  font-weight: 500;
}

/* 位置显示 */
.location-display {
  padding: 15px 20px;
  background: linear-gradient(135deg, #e3f2fd 0%, #f3e5f5 100%);
  border-radius: 12px;
  color: #2c3e50;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 15px;
}

/* 店铺列表 */
.shops-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 20px;
}

.shop-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 12px;
  border: 1px solid #e9ecef;
  transition: all 0.3s ease;
}

.shop-card:hover {
  background: #fff;
  box-shadow: 0 4px 15px rgba(0,0,0,0.1);
  transform: translateY(-2px);
}

.shop-info {
  flex: 1;
}

.shop-name {
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 4px;
  font-size: 1.1rem;
}

.shop-address {
  color: #6c757d;
  font-size: 0.9rem;
}

.remove-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: #dc3545;
  color: white;
  border-radius: 50%;
  cursor: pointer;
  font-size: 20px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
}

.remove-btn:hover {
  background: #c82333;
  transform: scale(1.1);
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: #6c757d;
}

.empty-state .icon {
  font-size: 3rem;
  margin-bottom: 15px;
  display: block;
}

/* 出行方式选择器 */
.travel-mode-selector {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.mode-btn {
  flex: 1;
  padding: 12px 20px;
  border: 2px solid #e9ecef;
  background: #fff;
  border-radius: 12px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.3s ease;
  font-size: 16px;
}

.mode-btn:hover {
  border-color: #667eea;
  background: rgba(102, 126, 234, 0.05);
}

.mode-btn.active {
  border-color: #667eea;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

/* 获取路线按钮 */
.get-route-btn {
  width: 100%;
  padding: 15px 25px;
  background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  margin-bottom: 20px;
}

.get-route-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(40, 167, 69, 0.3);
}

.get-route-btn:disabled {
  background: #6c757d;
  cursor: not-allowed;
  opacity: 0.6;
}

/* 路线信息 */
.route-info {
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  border-radius: 16px;
  padding: 25px;
  margin-top: 20px;
}

.route-info h4 {
  margin: 0 0 20px 0;
  color: #2c3e50;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 1.2rem;
}

.route-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 15px;
  margin-bottom: 25px;
}

.stat-item {
  background: #fff;
  padding: 20px;
  border-radius: 12px;
  text-align: center;
  box-shadow: 0 2px 10px rgba(0,0,0,0.05);
}

.stat-label {
  font-size: 0.9rem;
  color: #6c757d;
  margin-bottom: 8px;
  font-weight: 500;
}

.stat-value {
  font-size: 1.3rem;
  font-weight: 700;
  color: #2c3e50;
}

.route-description {
  background: #fff;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.05);
}

.route-description p {
  margin: 8px 0;
  line-height: 1.6;
}

.highlight {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  font-weight: 600;
}

.note {
  font-style: italic;
  color: #6c757d;
  font-size: 0.9rem;
  margin-top: 15px !important;
  padding-top: 15px;
  border-top: 1px solid #e9ecef;
}

/* 路线摘要网格样式 */
.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 15px;
  margin-bottom: 20px;
}

.summary-item {
  background: #fff;
  padding: 15px;
  border-radius: 12px;
  text-align: center;
  box-shadow: 0 2px 10px rgba(0,0,0,0.05);
  transition: all 0.3s ease;
}

.summary-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(0,0,0,0.1);
}

.summary-label {
  font-size: 0.85rem;
  color: #6c757d;
  margin-bottom: 8px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.summary-value {
  font-size: 1.1rem;
  font-weight: 700;
  color: #2c3e50;
}

/* 退出登录按钮 */
.logout-btn {
  width: 100%;
  padding: 15px 25px;
  background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  margin-top: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.logout-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(220, 53, 69, 0.3);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .dashboard-container {
    margin: 10px;
    padding: 20px;
  }
  
  .city-grid {
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 10px;
  }
  
  .city-card {
    padding: 15px;
  }
  
  .app-header h1 {
    font-size: 2rem;
  }
  
  .route-stats {
    grid-template-columns: 1fr;
  }
  
  .travel-mode-selector {
    flex-direction: column;
  }
}

/* 优化路线显示 */
.optimized-route {
  background: #fff;
  padding: 20px;
  border-radius: 12px;
  margin-bottom: 20px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.05);
}

.optimized-route h5 {
  margin: 0 0 15px 0;
  color: #2c3e50;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 1.1rem;
}

.shop-sequence {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sequence-item {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 12px 15px;
  background: #f8f9fa;
  border-radius: 10px;
  transition: all 0.3s ease;
}

.sequence-item:hover {
  background: #e9ecef;
  transform: translateX(5px);
}

.sequence-item.start, .sequence-item.end {
  background: linear-gradient(135deg, #e3f2fd 0%, #f3e5f5 100%);
  font-weight: 600;
}

.sequence-number {
  width: 30px;
  height: 30px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.9rem;
  flex-shrink: 0;
}

.sequence-item.start .sequence-number,
.sequence-item.end .sequence-number {
  background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
  font-size: 1rem;
}

.sequence-info {
  flex: 1;
}

.sequence-name {
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 2px;
}

.sequence-address {
  font-size: 0.9rem;
  color: #6c757d;
}

/* 详细指导 */
.route-instructions {
  background: #fff;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.05);
}

.route-instructions h5 {
  margin: 0 0 15px 0;
  color: #2c3e50;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 1.1rem;
}

.instruction-list {
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  padding: 10px;
}

.instruction-item {
  padding: 8px 12px;
  margin-bottom: 5px;
  background: #f8f9fa;
  border-radius: 6px;
  border-left: 3px solid #667eea;
  font-size: 0.95rem;
  line-height: 1.4;
}

.instruction-item:last-child {
  margin-bottom: 0;
}

.estimation-note {
  margin-top: 15px;
  padding: 10px 15px;
  background: rgba(255, 193, 7, 0.1);
  border: 1px solid rgba(255, 193, 7, 0.3);
  border-radius: 8px;
  color: #856404;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 连锁店提示 */
.chain-store-indicator {
  background: linear-gradient(135deg, #17a2b8 0%, #138496 100%);
  color: white;
  padding: 8px 12px;
  border-radius: 20px;
  font-size: 0.8rem;
  margin-bottom: 10px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

/* 建议列表增强 */
.suggestion-item.chain-store {
  border-left: 4px solid #17a2b8;
  background: linear-gradient(135deg, #e1f5fe 0%, #f0f9ff 100%);
}

.suggestion-item.optimal {
  border-left: 4px solid #28a745;
  background: linear-gradient(135deg, #e8f5e8 0%, #f1f8e9 100%);
}

.suggestion-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 5px;
}

.chain-badge {
  background: #17a2b8;
  color: white;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 0.7rem;
  font-weight: 500;
}

.optimal-badge {
  background: #28a745;
  color: white;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 0.7rem;
  font-weight: 500;
}

.route-time-badge {
  background: #6f42c1;
  color: white;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 0.7rem;
  font-weight: 500;
}

.suggestion-item.multi-brand {
  border-left: 4px solid #fd7e14;
  background: linear-gradient(135deg, #fff3cd 0%, #fef5e7 100%);
  box-shadow: 0 2px 8px rgba(253, 126, 20, 0.15);
}

.suggestion-item.multi-brand .suggestion-name {
  color: #e36209;
  font-weight: 700;
}

.chain-store-indicator {
  background: linear-gradient(135deg, #e3f2fd 0%, #f3e5f5 100%);
  color: #1565c0;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 0.9rem;
  margin-bottom: 5px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  border-left: 4px solid #667eea;
}

/* 店铺类型样式 */
.shop-card.chain-shop {
  border-left: 4px solid #17a2b8;
  background: linear-gradient(135deg, #e1f5fe 0%, #f0f9ff 100%);
}

.shop-card.private-shop {
  border-left: 4px solid #28a745;
  background: linear-gradient(135deg, #e8f5e8 0%, #f1f8e9 100%);
}

.shop-type-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
  margin-left: 8px;
}

.shop-type-badge.chain {
  background: #17a2b8;
  color: white;
}

.shop-type-badge.private {
  background: #28a745;
  color: white;
}

.chain-note {
  font-size: 0.8rem;
  color: #6c757d;
  font-style: italic;
  margin-top: 4px;
}

/* 多路线结果样式 */
.multiple-routes-container {
  background: #fff;
  border-radius: 16px;
  padding: 25px;
  margin-top: 20px;
}

.optimization-summary {
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 25px;
}

.summary-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 15px;
}

.route-category {
  margin-bottom: 30px;
}

.route-category h5 {
  margin: 0 0 15px 0;
  color: #2c3e50;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 1.1rem;
  border-bottom: 2px solid #e9ecef;
  padding-bottom: 10px;
}

.candidate-route {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 15px;
  margin-bottom: 15px;
  border: 1px solid #e9ecef;
  transition: all 0.3s ease;
}

.candidate-route:hover {
  background: #fff;
  box-shadow: 0 4px 15px rgba(0,0,0,0.1);
  transform: translateY(-2px);
}

.route-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.route-rank {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: 600;
}

.route-stats {
  color: #6c757d;
  font-weight: 500;
  font-size: 0.9rem;
}

.select-route-btn {
  background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  margin-left: 10px;
}

.select-route-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(40, 167, 69, 0.3);
}

.route-stores {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.store-tag {
  background: #fff;
  color: #495057;
  padding: 6px 12px;
  border-radius: 16px;
  font-size: 0.8rem;
  border: 1px solid #dee2e6;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.brand-tag {
  background: #667eea;
  color: white;
  padding: 2px 6px;
  border-radius: 8px;
  font-size: 0.7rem;
  margin-left: 4px;
}

/* 时间设置样式 */
.time-settings {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
}

.time-setting-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.time-label {
  font-size: 0.9rem;
  font-weight: 600;
  color: #495057;
  display: flex;
  align-items: center;
  gap: 6px;
}

.time-input {
  padding: 10px 12px;
  border: 2px solid #e9ecef;
  border-radius: 8px;
  font-size: 16px;
  background: #fff;
  transition: border-color 0.3s ease;
}

.time-input:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.duration-input-group, .stay-input-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.duration-input, .stay-input {
  padding: 8px 12px;
  border: 2px solid #e9ecef;
  border-radius: 8px;
  font-size: 14px;
  width: 80px;
  text-align: center;
  background: #fff;
  transition: border-color 0.3s ease;
}

.duration-input:focus, .stay-input:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.duration-unit, .stay-unit {
  font-size: 0.9rem;
  color: #6c757d;
  font-weight: 500;
}

/* 店铺停留时间设置 */
.stay-duration-setting {
  margin-top: 12px;
  padding: 10px 0;
  border-top: 1px solid #e9ecef;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.stay-label {
  font-size: 0.85rem;
  color: #6c757d;
  display: flex;
  align-items: center;
  gap: 4px;
}

/* 时间安排时间轴样式 */
.time-schedule {
  background: #fff;
  padding: 20px;
  border-radius: 12px;
  margin-bottom: 20px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.05);
}

.timeline {
  position: relative;
  padding: 10px 0;
}

.timeline::before {
  content: '';
  position: absolute;
  left: 80px;
  top: 0;
  bottom: 0;
  width: 2px;
  background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
}

.timeline-item {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 20px;
  margin-bottom: 25px;
  padding-left: 10px;
}

.timeline-item::before {
  content: '';
  position: absolute;
  left: 74px;
  top: 8px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #667eea;
  border: 3px solid #fff;
  box-shadow: 0 0 0 3px #667eea;
  z-index: 1;
}

.timeline-item.departure::before {
  background: #28a745;
  box-shadow: 0 0 0 3px #28a745;
}

.timeline-item.return::before {
  background: #dc3545;
  box-shadow: 0 0 0 3px #dc3545;
}

.timeline-time {
  width: 60px;
  font-size: 1.1rem;
  font-weight: 700;
  color: #2c3e50;
  text-align: right;
  padding-top: 2px;
}

.timeline-content {
  flex: 1;
  background: #f8f9fa;
  padding: 15px;
  border-radius: 10px;
  border-left: 4px solid #667eea;
}

.timeline-item.departure .timeline-content {
  border-left-color: #28a745;
  background: linear-gradient(135deg, #e8f5e8 0%, #f1f8e9 100%);
}

.timeline-item.return .timeline-content {
  border-left-color: #dc3545;
  background: linear-gradient(135deg, #fce8e8 0%, #fdf2f2 100%);
}

.timeline-location {
  font-size: 1.1rem;
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 4px;
}

.timeline-address {
  font-size: 0.9rem;
  color: #6c757d;
  margin-bottom: 6px;
}

.timeline-description {
  font-size: 0.95rem;
  color: #495057;
  margin-bottom: 6px;
}

.timeline-departure {
  font-size: 0.85rem;
  color: #28a745;
  font-weight: 600;
}

/* 响应式优化 */
@media (max-width: 768px) {
  .route-header {
    flex-direction: column;
    gap: 10px;
    align-items: stretch;
  }
  
  .select-route-btn {
    width: 100%;
  }
  
  .summary-stats {
    grid-template-columns: 1fr;
  }
  
  .time-settings {
    grid-template-columns: 1fr;
  }
  
  .timeline::before {
    left: 60px;
  }
  
  .timeline-item::before {
    left: 54px;
  }
  
  .timeline-time {
    width: 50px;
    font-size: 1rem;
  }
  
  .stay-duration-setting {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
}

/* 筛选面板样式 */
.filter-controls {
  margin-top: 20px;
  text-align: center;
}

.filter-toggle-btn {
  background: linear-gradient(135deg, #6c757d 0%, #495057 100%);
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 20px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.filter-toggle-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(108, 117, 125, 0.3);
}

.filter-panel {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 20px;
  margin-top: 15px;
  border: 1px solid #e9ecef;
}

.filter-panel h6 {
  margin: 0 0 15px 0;
  color: #2c3e50;
  font-size: 1rem;
  display: flex;
  align-items: center;
  gap: 8px;
}

.brand-filter-group {
  margin-bottom: 20px;
  background: #fff;
  border-radius: 8px;
  padding: 15px;
  border: 1px solid #dee2e6;
}

.brand-filter-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e9ecef;
}

.brand-name {
  font-weight: 600;
  color: #495057;
  font-size: 1rem;
}

.brand-actions {
  display: flex;
  gap: 8px;
}

.filter-action-btn {
  background: #6c757d;
  color: white;
  border: none;
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.filter-action-btn:hover {
  background: #495057;
  transform: scale(1.05);
}

.store-checkboxes {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 10px;
}

.store-checkbox {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px;
  background: #f8f9fa;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.store-checkbox:hover {
  background: #e9ecef;
}

.store-checkbox input[type="checkbox"] {
  margin-top: 2px;
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.store-checkbox-label {
  flex: 1;
}

.store-checkbox-name {
  font-weight: 500;
  color: #2c3e50;
  font-size: 0.9rem;
  margin-bottom: 2px;
}

.store-checkbox-address {
  font-size: 0.8rem;
  color: #6c757d;
  line-height: 1.3;
}

/* 响应式优化筛选面板 */
@media (max-width: 768px) {
  .brand-filter-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  
  .store-checkboxes {
    grid-template-columns: 1fr;
  }
  
  .filter-panel {
    padding: 15px;
  }
}

/* 驾车路线详细显示样式 */
.driving-route-details {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  margin-top: 15px;
}

.driving-route-details .route-segment {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
  border-left: 4px solid #28a745;
  transition: all 0.3s ease;
}

.driving-route-details .route-segment:hover {
  background: #fff;
  box-shadow: 0 4px 15px rgba(0,0,0,0.1);
  transform: translateX(5px);
}

/* 路线顺序样式 */
.route-order {
  background: #fff;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.05);
  margin-top: 15px;
}

.route-order h4 {
  margin: 0 0 15px 0;
  color: #2c3e50;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 1.1rem;
}

.order-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.order-item {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 12px 15px;
  background: #f8f9fa;
  border-radius: 10px;
  transition: all 0.3s ease;
}

.order-item:hover {
  background: #e9ecef;
  transform: translateX(5px);
}

.order-number {
  width: 30px;
  height: 30px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.9rem;
  flex-shrink: 0;
}

.order-info {
  flex: 1;
}

.order-name {
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 2px;
}

.order-address {
  font-size: 0.9rem;
  color: #6c757d;
}

.no-route-details {
  text-align: center;
  padding: 40px 20px;
  color: #6c757d;
}

.no-route-details p {
  margin: 10px 0;
  line-height: 1.5;
}

/* 添加路线分类显示样式 */
.route-categories {
  display: flex;
  flex-direction: row;
  gap: 20px;
}

.route-category {
  background: #fff;
  border-radius: 12px;
  padding: 15px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.05);
  flex: 1;
}

.route-category h4 {
  margin: 0 0 15px 0;
  color: #2c3e50;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid #e9ecef;
  padding-bottom: 10px;
}

.route-type-badge.time {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: 600;
}

.route-type-badge.distance {
  background: linear-gradient(135deg, #20c997 0%, #28a745 100%);
  color: white;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: 600;
}

.time-value {
  color: #764ba2;
  font-weight: 600;
}

.distance-value {
  color: #28a745;
  font-weight: 600;
}

.route-info-badge {
  background: #f8f9fa;
  color: #6c757d;
  font-size: 0.8rem;
  padding: 4px 10px;
  border-radius: 10px;
  margin-left: 10px;
  font-weight: normal;
}

/* 公交路线详细显示样式 */
.transit-route-details {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  margin-top: 15px;
}

.transit-segment {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
  border-left: 4px solid #667eea;
  transition: all 0.3s ease;
}

.transit-segment:hover {
  background: #fff;
  box-shadow: 0 4px 15px rgba(0,0,0,0.1);
  transform: translateX(5px);
}

.segment-title {
  font-weight: 600;
  color: #2c3e50;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 1.1rem;
}

.segment-content {
  margin-top: 15px;
}

.segment-stats {
  display: flex;
  gap: 20px;
  margin-bottom: 15px;
  padding: 10px 15px;
  background: rgba(102, 126, 234, 0.1);
  border-radius: 8px;
}

.stat-time, .stat-distance, .stat-cost {
  font-size: 0.9rem;
  font-weight: 500;
  color: #495057;
  display: flex;
  align-items: center;
  gap: 4px;
}

/* 步行指导样式 */
.walking-instructions {
  background: linear-gradient(135deg, #e8f5e8 0%, #f1f8e9 100%);
  border-radius: 10px;
  padding: 15px;
  border-left: 4px solid #28a745;
}

.instruction-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-weight: 600;
  color: #28a745;
  font-size: 1rem;
}

.instruction-steps {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.instruction-step {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 6px;
}

.step-content {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.step-icon {
  color: #28a745;
  font-weight: bold;
}

.step-text {
  color: #495057;
  line-height: 1.4;
}

.step-meta {
  display: flex;
  gap: 10px;
  font-size: 0.8rem;
  color: #6c757d;
  margin-left: 10px;
}

.step-distance, .step-duration {
  background: #28a745;
  color: white;
  padding: 2px 6px;
  border-radius: 10px;
  font-size: 0.75rem;
}

/* 公交指导样式 */
.bus-instructions {
  background: linear-gradient(135deg, #e3f2fd 0%, #f0f9ff 100%);
  border-radius: 10px;
  padding: 15px;
  border-left: 4px solid #2196f3;
}

.bus-instructions .instruction-header {
  color: #1976d2;
}

.bus-lines {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.bus-line {
  background: rgba(255, 255, 255, 0.8);
  border-radius: 8px;
  padding: 15px;
  border: 1px solid rgba(33, 150, 243, 0.2);
}

.line-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.line-number {
  background: #2196f3;
  color: white;
  padding: 4px 12px;
  border-radius: 20px;
  font-weight: bold;
  font-size: 0.9rem;
}

.line-name {
  color: #1976d2;
  font-weight: 600;
  font-size: 1rem;
}

.line-route {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
  margin-bottom: 10px;
}

.station-info {
  flex: 1;
  text-align: center;
}

.station-label {
  display: block;
  font-size: 0.8rem;
  color: #6c757d;
  margin-bottom: 4px;
}

.station-name {
  font-weight: 600;
  color: #2c3e50;
  font-size: 0.95rem;
  background: rgba(255, 255, 255, 0.8);
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px solid rgba(33, 150, 243, 0.3);
}

.route-arrow {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #1976d2;
  font-weight: 600;
  padding: 8px 12px;
  background: rgba(33, 150, 243, 0.1);
  border-radius: 20px;
  font-size: 0.9rem;
}

.stops-count {
  color: #1976d2;
  font-weight: bold;
}

.via-stops {
  margin-top: 10px;
  padding: 8px 12px;
  background: rgba(33, 150, 243, 0.05);
  border-radius: 6px;
  font-size: 0.9rem;
}

.via-label {
  color: #6c757d;
  font-weight: 500;
}

.via-stations {
  color: #495057;
  margin-left: 8px;
}

/* 地铁指导样式 */
.subway-instructions {
  background: linear-gradient(135deg, #fff3e0 0%, #fef9c3 100%);
  border-radius: 10px;
  padding: 15px;
  border-left: 4px solid #ff9800;
}

.subway-instructions .instruction-header {
  color: #f57c00;
}

.subway-lines {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.subway-line {
  background: rgba(255, 255, 255, 0.8);
  border-radius: 8px;
  padding: 15px;
  border: 1px solid rgba(255, 152, 0, 0.2);
}

.subway-line-number {
  background: #ff9800;
  color: white;
  padding: 4px 12px;
  border-radius: 20px;
  font-weight: bold;
  font-size: 0.9rem;
}

.train-number {
  background: #f57c00;
  color: white;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 0.8rem;
  margin-left: 8px;
}

.subway-instructions .route-arrow {
  background: rgba(255, 152, 0, 0.1);
  color: #f57c00;
}

.subway-instructions .stops-count {
  color: #f57c00;
}

.subway-instructions .station-name {
  border: 1px solid rgba(255, 152, 0, 0.3);
}

.subway-instructions .via-stops {
  background: rgba(255, 152, 0, 0.05);
}

/* 其他交通方式样式 */
.other-instructions {
  background: linear-gradient(135deg, #f3e5f5 0%, #fce4ec 100%);
  border-radius: 10px;
  padding: 15px;
  border-left: 4px solid #9c27b0;
}

.other-instructions .instruction-header {
  color: #7b1fa2;
}

/* 简单指导样式 */
.simple-instruction {
  color: #495057;
  font-style: italic;
  padding: 10px 15px;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 6px;
  text-align: center;
}

/* 响应式优化 */
@media (max-width: 768px) {
  .line-route {
    flex-direction: column;
    gap: 10px;
  }
  
  .route-arrow {
    order: 2;
  }
  
  .station-info.departure {
    order: 1;
  }
  
  .station-info.arrival {
    order: 3;
  }
  
  .segment-stats {
    flex-direction: column;
    gap: 8px;
  }
  
  .transit-segment {
    padding: 15px;
  }
}

/* 通知组件样式 */
.notification-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 10000;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: 400px;
}

.notification {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px 20px;
  border-radius: 12px;
  box-shadow: 0 8px 25px rgba(0,0,0,0.15);
  backdrop-filter: blur(10px);
  cursor: pointer;
  transition: all 0.3s ease;
  animation: slideIn 0.3s ease-out;
  border: 1px solid rgba(255,255,255,0.2);
}

@keyframes slideIn {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

.notification:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 30px rgba(0,0,0,0.2);
}

.notification.success {
  background: linear-gradient(135deg, rgba(40, 167, 69, 0.95) 0%, rgba(32, 201, 151, 0.95) 100%);
  color: white;
  border-color: rgba(40, 167, 69, 0.3);
}

.notification.error {
  background: linear-gradient(135deg, rgba(220, 53, 69, 0.95) 0%, rgba(200, 35, 51, 0.95) 100%);
  color: white;
  border-color: rgba(220, 53, 69, 0.3);
}

.notification.warning {
  background: linear-gradient(135deg, rgba(255, 193, 7, 0.95) 0%, rgba(248, 209, 47, 0.95) 100%);
  color: #212529;
  border-color: rgba(255, 193, 7, 0.3);
}

.notification.info {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.95) 0%, rgba(118, 75, 162, 0.95) 100%);
  color: white;
  border-color: rgba(102, 126, 234, 0.3);
}

.notification-icon {
  width: 24px;
  height: 24px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 14px;
  flex-shrink: 0;
  margin-top: 2px;
}

.notification-content {
  flex: 1;
  min-width: 0;
}

.notification-title {
  font-weight: 600;
  font-size: 15px;
  margin-bottom: 4px;
  line-height: 1.2;
}

.notification-message {
  font-size: 14px;
  line-height: 1.4;
  opacity: 0.95;
}

.notification-close {
  width: 20px;
  height: 20px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
  margin-top: 2px;
}

.notification-close:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: scale(1.1);
}

/* 移动端优化 */
@media (max-width: 768px) {
  .notification-container {
    left: 10px;
    right: 10px;
    max-width: none;
  }
  
  .notification {
    padding: 12px 16px;
  }
  
  .notification-title {
    font-size: 14px;
  }
  
  .notification-message {
    font-size: 13px;
  }
}

/* 加载指示器样式 */
.loading-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  background: #f8f9fa;
  border-radius: 12px;
  margin-top: 20px;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #e9ecef;
  border-top: 4px solid #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 15px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.loading-indicator p {
  color: #6c757d;
  margin: 0;
  font-weight: 500;
}

h2 { color: #333; text-align: center; }
h3 { color: #444; margin-top: 20px; margin-bottom: 15px; }
p { color: #666; }
#map-container-js { /* Ensure this ID is unique if multiple maps were ever on one page */ }

.shop-suggestions {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: white;
  border: 1px solid #ddd;
  border-radius: 4px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  z-index: 1000;
  max-height: 300px;
  overflow-y: auto;
}

.suggestion-item {
  padding: 10px;
  cursor: pointer;
  border-bottom: 1px solid #eee;
}

.suggestion-item:hover {
  background-color: #f5f5f5;
}

.suggestion-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.suggestion-name {
  font-weight: bold;
  color: #333;
}

.suggestion-address {
  font-size: 0.9em;
  color: #666;
}

.suggestion-distance {
  font-size: 0.9em;
  color: #007bff;
}

.route-info {
  margin-top: 20px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.route-summary {
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #dee2e6;
}

.route-summary h3 {
  color: #333;
  margin-bottom: 10px;
}

.route-summary p {
  margin: 5px 0;
  color: #666;
}

.route-details h3 {
  color: #333;
  margin-bottom: 15px;
}

.route-segment {
  margin-bottom: 15px;
  padding: 10px;
  background: white;
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.segment-header {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.segment-number {
  width: 24px;
  height: 24px;
  background: #007bff;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 10px;
  font-size: 14px;
}

.segment-name {
  font-weight: bold;
  color: #333;
}

.segment-details p {
  margin: 5px 0;
  color: #666;
  font-size: 14px;
}

/* 添加路线选择界面 */
.route-options {
  margin-top: 20px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.route-options h3 {
  color: #333;
  margin-bottom: 15px;
}

.route-list {
  max-height: 300px;
  overflow-y: auto;
}

.route-item {
  display: flex;
  align-items: center;
  padding: 10px;
  margin-bottom: 10px;
  background: white;
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  justify-content: space-between;
}

.route-item.active {
  background: #e3f2fd;
  border-left: 4px solid #007bff;
}

.route-number {
  width: 24px;
  height: 24px;
  background: #007bff;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 15px;
  font-size: 14px;
}

.route-details {
  flex: 1;
}

.route-shops {
  font-weight: bold;
  color: #333;
  margin-bottom: 5px;
}

.route-summary {
  font-size: 0.9em;
  color: #666;
}

.separator {
  margin: 0 8px;
  color: #ccc;
}

/* 城市选择表单 */
.city-selection-form {
  display: flex;
  gap: 20px;
  align-items: center;
}

.form-group {
  flex: 1;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: #495057;
}

.form-group select {
  width: 100%;
  padding: 12px 15px;
  border: 2px solid #e9ecef;
  border-radius: 12px;
  font-size: 16px;
  background-color: #fff;
  cursor: pointer;
  transition: all 0.3s ease;
  outline: none;
}

.form-group select:focus {
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

/* 新增样式 */
.badge {
  display: inline-block;
  padding: 2px 8px;
  font-size: 0.75em;
  font-weight: bold;
  border-radius: 10px;
  color: white;
  margin-left: 8px;
}
.badge.chain {
  background-color: #007bff;
}
.suggestion-status {
  font-size: 0.8em;
  color: #ff9800;
  font-style: italic;
  margin-top: 4px;
}
`;
document.head.appendChild(style);