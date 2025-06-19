<template>
  <div class="dashboard-container">
    <h2>Welcome to your Dashboard!</h2>
    <p>This is where your amazing trip planning features will reside.</p>
    <p>Plan new trips, view existing ones, and manage your travel itineraries.</p>

    <!-- 城市选择部分 -->
    <div class="city-selection-section">
      <h3>选择您的城市</h3>
      <div class="form-group">
        <label for="citySelect">城市选择:</label>
        <select id="citySelect" v-model="selectedCity" @change="onCityChange" class="city-select">
          <option value="">请选择城市</option>
          <option value="北京">北京</option>
          <option value="上海">上海</option>
          <option value="广州">广州</option>
          <option value="深圳">深圳</option>
          <option value="杭州">杭州</option>
          <option value="南京">南京</option>
          <option value="成都">成都</option>
          <option value="武汉">武汉</option>
          <option value="西安">西安</option>
          <option value="重庆">重庆</option>
          <option value="天津">天津</option>
          <option value="苏州">苏州</option>
        </select>
        <p v-if="selectedCity" class="selected-city-display">
          当前选择: <strong>{{ selectedCity }}</strong>
        </p>
      </div>
    </div>

    <hr class="separator"/>

    <div class="home-location-section">
      <h3>Manage Home Location</h3>
      <div v-if="currentHomeLocation && currentHomeLocation.address" class="current-home-display">
        Current Home: {{ currentHomeLocation.address }}
        <span v-if="currentHomeLocation.latitude && currentHomeLocation.longitude">
          (Lat: {{ currentHomeLocation.latitude }}, Lon: {{ currentHomeLocation.longitude }})
        </span>
      </div>
      <div v-else class="current-home-display">
        No home location set.
      </div>
      <form @submit.prevent="saveHomeLocation" class="home-form">
        <div class="form-group address-input-container">
          <label for="homeAddress">Home Address:</label>
          <input 
            type="text" 
            id="homeAddress" 
            v-model="homeAddressInput" 
            @input="onAddressInput"
            @focus="showAddressSuggestions = true"
            @blur="hideAddressSuggestions"
            placeholder="Enter your home address" 
            autocomplete="off"
          />
          <!-- 地址建议下拉框 -->
          <div v-if="showAddressSuggestions && addressSuggestions.length > 0" class="address-suggestions">
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
        <div class="form-group">
          <label for="homeLatitude">Latitude (Optional):</label>
          <input type="text" id="homeLatitude" v-model="homeLatitudeInput" placeholder="Enter latitude" />
        </div>
        <div class="form-group">
          <label for="homeLongitude">Longitude (Optional):</label>
          <input type="text" id="homeLongitude" v-model="homeLongitudeInput" placeholder="Enter longitude" />
        </div>
        <button type="submit" class="btn-primary">Set Home Location</button>
        <button type="button" @click="pickHomeOnMap" :class="{'btn-danger': mapPickModeEnabled, 'btn-secondary': !mapPickModeEnabled}">
          {{ pickHomeButtonText }}
        </button>
      </form>
    </div>

    <hr class="separator"/>

    <div class="shops-to-visit-section">
      <h3>Shops to Visit</h3>
      <form @submit.prevent="addShop" class="add-shop-form">
        <div class="form-group shop-input-container">
          <label for="shopInput">Shop Name:</label>
          <input 
            type="text" 
            id="shopInput" 
            v-model="shopInput" 
            @input="onShopInput"
            @focus="showShopSuggestions = true"
            @blur="hideShopSuggestions"
            placeholder="Enter a shop name" 
            autocomplete="off"
          />
          <!-- 店铺建议下拉框 -->
          <div v-if="showShopSuggestions && shopSuggestions.length > 0" class="shop-suggestions">
            <div 
              v-for="suggestion in shopSuggestions" 
              :key="suggestion.id"
              @mousedown="selectShopSuggestion(suggestion)"
              class="suggestion-item"
            >
              <div class="suggestion-name">{{ suggestion.name }}</div>
              <div class="suggestion-address">{{ suggestion.address }}</div>
              <div class="suggestion-distance" v-if="suggestion.distance">{{ Math.round(suggestion.distance) }}m</div>
            </div>
          </div>
        </div>
        <button type="submit" class="btn-primary">Add Shop</button>
      </form>

      <ul v-if="shopsToVisit.length > 0" class="shops-list">
        <li v-for="shop in shopsToVisit" :key="shop.id" class="shop-item">
          <div class="shop-info">
            <span class="shop-name">{{ shop.name }}</span>
            <span v-if="shop.status === 'confirmed'" class="shop-address-confirmed">
              📍 {{ shop.address }} (Confirmed)
            </span>
            <div v-if="shop.status === 'confirmed'" class="shop-stay-duration">
              <label :for="'stayDuration-' + shop.id" class="stay-duration-label">Stay (minutes):</label>
              <input
                type="number"
                :id="'stayDuration-' + shop.id"
                v-model.number="shop.stayDurationMinutes"
                min="0"
                placeholder="0"
                class="stay-duration-input"
              />
            </div>
          </div>
          <div class="shop-item-actions">
            <button
              @click="findShopOnMap(shop)"
              :class="{'btn-success': shop.status === 'confirmed', 'btn-info': shop.status !== 'confirmed'}"
              class="btn-small"
              :disabled="isLoadingShops && selectedShopForSearch.id === shop.id"
            >
              {{ isLoadingShops && selectedShopForSearch.id === shop.id ? 'Searching...' : (shop.status === 'confirmed' ? 'Re-Search' : 'Search/Find') }}
            </button>
            <button @click="removeShop(shop.id)" class="btn-danger btn-small" :disabled="isLoadingShops">Remove</button>
          </div>
        </li>
      </ul>
      <p v-else class="no-shops-message">No shops added yet. Add some above!</p>

      <!-- Search Results / Disambiguation Section -->
      <div v-if="isLoadingShops && searchResults.length === 0 && selectedShopForSearch.id" class="loading-shops-indicator">
        <p>Searching for "{{selectedShopForSearch.name}}"... Please wait.</p>
      </div>
      <div v-if="!isLoadingShops && searchResults.length > 0 && selectedShopForSearch.id" class="search-results-section">
        <h4>Select the correct shop for: "{{ selectedShopForSearch.name }}"</h4>
        <ul class="search-results-list">
          <li v-for="candidate in searchResults" :key="candidate.id" class="search-result-item">
            <div>
              <strong>{{ candidate.name }}</strong><br>
              <small>{{ candidate.address }}</small>
              <small v-if="candidate.distance"> (Distance: {{ candidate.distance }}m)</small>
            </div>
            <button @click="confirmShopSelection(candidate)" class="btn-success btn-small">Select</button>
          </li>
        </ul>
        <button @click="searchResults = []; selectedShopForSearch = {id: null, name: ''};" class="btn-secondary btn-small">Cancel Search</button>
      </div>
    </div>

    <hr class="separator"/>

    <div class="route-optimization-section">
      <h3>Route Optimization</h3>

      <div class="form-group travel-mode-selection">
        <label>Travel Mode:</label>
        <label for="modeDriving">
          <input type="radio" id="modeDriving" value="driving" v-model="selectedTravelMode"> Driving
        </label>
        <label for="modeTransit">
          <input type="radio" id="modeTransit" value="public_transit" v-model="selectedTravelMode"> Public Transit
        </label>
      </div>

      <div v-if="selectedTravelMode === 'public_transit'" class="form-group">
        <label for="homeCityName">Origin City for Transit (e.g., "Beijing" or city code):</label>
        <input type="text" id="homeCityName" v-model="homeCityName" :placeholder="selectedCity || '请输入城市名'" />
        <small v-if="!homeCityName" class="text-danger">City is required for public transit mode.</small>
      </div>

      <button
        @click="getDirections"
        :disabled="!canCalculateRoute || isCalculatingRoute || (selectedTravelMode === 'public_transit' && !homeCityName)"
        class="btn-primary btn-large"
      >
        {{ getButtonText }}
      </button>
      <p v-if="!canCalculateRoute && !isCalculatingRoute" class="route-calculation-condition">
        Please set your home location, confirm at least one shop, and specify city if using transit, to enable route calculation.
      </p>

      <!-- NEW DUAL COLUMN DISPLAY -->
      <div v-if="routesByTime.length > 0 || routesByDistance.length > 0" class="dual-routes-container">
        <h3>
          可选路线对比
          <span class="route-summary-badge">
            找到 {{ routesByTime.length }} (时间) + {{ routesByDistance.length }} (距离) 方案
          </span>
        </h3>
        
        <div class="routes-columns">
          <!-- Time Optimized Column -->
          <div class="route-column time-column">
            <div class="column-header">
              <h4>⏱️ 时间最短 <span class="column-count">{{ routesByTime.length }}</span></h4>
              <p class="column-description">优先考虑总耗时最短的方案</p>
            </div>
            <div class="route-candidates" v-if="routesByTime.length > 0">
              <div 
                v-for="(route, index) in routesByTime" 
                :key="route.id" 
                class="route-candidate"
                :class="{ selected: selectedRouteId === route.id }"
                @click="selectRoute(route)"
              >
                <div class="candidate-header">
                  <span class="candidate-rank">方案 #{{ index + 1 }}</span>
                </div>
                <div class="candidate-stats">
                  <div class="stat-primary">
                    <span class="stat-value">{{ Math.round(route.total_overall_duration / 60) }}</span> 分钟
                  </div>
                  <div class="stat-secondary" v-if="route.cost">
                    <span class="stat-icon">💰</span>
                    <span class="stat-value">{{ route.cost }}</span> 元
                  </div>
                </div>
                <div class="candidate-route">
                  <p class="route-path">
                    {{ route.optimized_order.map(p => p.name).join(' → ') }}
                  </p>
                </div>
              </div>
            </div>
            <div v-else class="no-routes">
              <span class="icon">☹️</span>
              <p>未能找到按时间优化的路线。</p>
            </div>
          </div>

          <!-- Distance Optimized Column -->
          <div class="route-column distance-column">
            <div class="column-header">
              <h4>📏 距离最短 <span class="column-count">{{ routesByDistance.length }}</span></h4>
              <p class="column-description">优先考虑总里程最短的方案</p>
            </div>
            <div class="route-candidates" v-if="routesByDistance.length > 0">
              <div 
                v-for="(route, index) in routesByDistance" 
                :key="route.id" 
                class="route-candidate"
                :class="{ selected: selectedRouteId === route.id }"
                @click="selectRoute(route)"
              >
                <div class="candidate-header">
                  <span class="candidate-rank">方案 #{{ index + 1 }}</span>
                </div>
                <div class="candidate-stats">
                  <div class="stat-primary">
                    <span class="stat-value">{{ (route.total_distance / 1000).toFixed(2) }}</span> 公里
                  </div>
                  <div class="stat-secondary" v-if="route.cost">
                    <span class="stat-icon">💰</span>
                    <span class="stat-value">{{ route.cost }}</span> 元
                  </div>
                </div>
                <div class="candidate-route">
                  <p class="route-path">
                    {{ route.optimized_order.map(p => p.name).join(' → ') }}
                  </p>
                </div>
              </div>
            </div>
            <div v-else class="no-routes">
              <span class="icon">☹️</span>
              <p>未能找到按距离优化的路线。</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Loading indicator -->
      <div v-if="isCalculatingRoute" class="loading-routes-indicator">
        <p>正在为您寻找最佳路线，请稍候...</p>
      </div>

    </div>

    <hr class="separator"/>

    <div v-if="(routesByTime.length > 0 || routesByDistance.length > 0) && (!displayableSchedule || displayableSchedule.length === 0)" class="placeholder-message-section">
      <p>请从上方列表中选择一条路线以查看详细行程及地图。</p>
    </div>

    <!-- Generated Schedule Display -->
    <div v-if="displayableSchedule && displayableSchedule.length > 0" class="schedule-display-section">
      <h3>Generated Schedule (Starts at {{ formatTime(new Date(new Date().setHours(...departureTime.split(':').map(Number)))) }})</h3>
      <ul class="schedule-list">
        <li v-for="(item, index) in displayableSchedule" :key="index" class="schedule-item">
          <div v-if="item.type === 'departure'" class="schedule-event departure-event">
            <span class="event-time">{{ formatTime(item.time) }}</span>
            <span class="event-description">Depart from <strong>{{ item.location }}</strong></span>
          </div>
          <div v-else-if="item.type === 'arrival'" class="schedule-event arrival-event">
            <span class="event-time">{{ formatTime(item.time) }}</span>
            <span class="event-description">
              Arrive at <strong>{{ item.location }}</strong>
              (Travel: {{ formatDuration(item.travel_duration_seconds) }} min)
            </span>
          </div>
          <div v-else-if="item.type === 'stay'" class="schedule-event stay-event">
            <!-- No time for stay, it's a duration at the arrival location -->
            <span class="event-description event-stay-description">
              Stay at <strong>{{ item.location }}</strong> for {{ formatDuration(item.duration_seconds) }} min
            </span>
          </div>
        </li>
      </ul>
    </div>

    <!-- 详细路线指导显示 - 优化版 -->
    <div v-if="selectedRoute && (selectedRoute.route_segments || selectedRoute.steps)" class="route-guidance-section">
      <h3>📍 详细路线指导</h3>
      
      <!-- 路线概览信息 -->
      <div class="route-overview">
        <div class="overview-stats">
          <div class="stat-item">
            <span class="stat-icon">⏱️</span>
            <span class="stat-label">总用时</span>
            <span class="stat-value">{{ Math.round((selectedRoute.total_overall_duration || selectedRoute.duration || 0) / 60) }}分钟</span>
          </div>
          <div class="stat-item">
            <span class="stat-icon">📏</span>
            <span class="stat-label">总距离</span>
            <span class="stat-value">{{ ((selectedRoute.total_distance || selectedRoute.distance || 0) / 1000).toFixed(2) }}公里</span>
          </div>
          <div v-if="selectedRoute.cost" class="stat-item">
            <span class="stat-icon">💰</span>
            <span class="stat-label">预估费用</span>
            <span class="stat-value">{{ selectedRoute.cost }}元</span>
          </div>
        </div>
      </div>

      <!-- 多段路线的详细指导 -->
      <div v-if="selectedRoute.route_segments" class="route-segments">
        <div v-for="(segment, segmentIndex) in selectedRoute.route_segments" :key="segmentIndex" class="route-segment">
          <div class="segment-header">
            <div class="segment-title">
              <span class="segment-number">{{ segmentIndex + 1 }}</span>
              <h4>{{ segment.from_name }} → {{ segment.to_name }}</h4>
              <span v-if="segment.mode" class="segment-mode" :class="segment.mode">
                {{ segment.mode === 'public_transit' ? '🚌 公交' : '🚗 驾车' }}
              </span>
            </div>
            <div class="segment-meta">
              <span class="segment-distance">{{ (segment.distance / 1000).toFixed(2) }}公里</span>
              <span class="segment-duration">{{ Math.round(segment.duration / 60) }}分钟</span>
            </div>
          </div>
          
          <!-- 公交详细步骤 -->
          <div v-if="segment.mode === 'public_transit' && segment.steps && segment.steps.length > 0" class="transit-steps">
            <div v-for="(step, stepIndex) in segment.steps" :key="stepIndex" class="transit-step" :class="step.type">
              <div class="step-number">{{ stepIndex + 1 }}</div>
              <div class="step-icon">
                <span v-if="step.type === 'walk'">🚶‍♂️</span>
                <span v-else-if="step.type === 'bus'">🚌</span>
                <span v-else-if="step.type === 'railway'">🚇</span>
                <span v-else-if="step.type === 'taxi'">🚕</span>
                <span v-else-if="step.type === 'fallback'">⚠️</span>
                <span v-else-if="step.type === 'unavailable'">❌</span>
                <span v-else>🔄</span>
              </div>
              <div class="step-content">
                <p class="step-instruction">{{ step.instruction }}</p>
                <div v-if="step.duration || step.distance" class="step-meta">
                  <span v-if="step.duration" class="step-duration">{{ Math.round(step.duration / 60) }}分钟</span>
                  <span v-if="step.distance" class="step-distance">{{ step.distance }}米</span>
                </div>
              </div>
            </div>
          </div>
          
          <!-- 驾车备选路线提示 -->
          <div v-else-if="segment.mode === 'driving_fallback'" class="fallback-steps">
            <div class="fallback-notice">
              <div class="notice-icon">⚠️</div>
              <div class="notice-content">
                <p class="notice-title">公交路线不可达</p>
                <p class="notice-text">未找到可用的公交路线，以下为驾车路线作为参考：</p>
              </div>
            </div>
            <div v-for="(step, stepIndex) in segment.steps" :key="stepIndex" class="driving-step fallback-step">
              <div class="step-number">{{ stepIndex + 1 }}</div>
              <div class="step-icon">🚗</div>
              <div class="step-content">
                <p class="step-instruction">{{ step.instruction || step.action }}</p>
                <div v-if="step.distance || step.duration" class="step-meta">
                  <span v-if="step.distance" class="step-distance">{{ step.distance }}米</span>
                  <span v-if="step.duration" class="step-duration">{{ Math.round(step.duration) }}秒</span>
                </div>
              </div>
            </div>
          </div>
          
          <!-- 驾车详细步骤 -->
          <div v-else-if="segment.mode === 'driving' && segment.steps && segment.steps.length > 0" class="driving-steps">
            <div v-for="(step, stepIndex) in segment.steps" :key="stepIndex" class="driving-step">
              <div class="step-number">{{ stepIndex + 1 }}</div>
              <div class="step-icon">🚗</div>
              <div class="step-content">
                <p class="step-instruction">{{ step.instruction || step.action }}</p>
                <div v-if="step.distance || step.duration" class="step-meta">
                  <span v-if="step.distance" class="step-distance">{{ step.distance }}米</span>
                  <span v-if="step.duration" class="step-duration">{{ Math.round(step.duration) }}秒</span>
                </div>
              </div>
            </div>
          </div>
          
          <!-- 如果没有详细步骤，显示基本信息 -->
          <div v-else class="basic-segment-info">
            <div class="basic-info-content">
              <p class="route-description">从 <strong>{{ segment.from_name }}</strong> 到 <strong>{{ segment.to_name }}</strong></p>
              <div class="basic-stats">
                <span class="basic-stat">📏 {{ (segment.distance / 1000).toFixed(2) }}公里</span>
                <span class="basic-stat">⏱️ {{ Math.round(segment.duration / 60) }}分钟</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 单段路线的详细指导 -->
      <div v-else-if="selectedRoute.steps" class="route-steps">
        <div v-for="(step, stepIndex) in selectedRoute.steps" :key="stepIndex" class="route-step" :class="step.type">
          <div class="step-number">{{ stepIndex + 1 }}</div>
          <div class="step-icon">
            <span v-if="step.type === 'walk'">🚶‍♂️</span>
            <span v-else-if="step.type === 'bus'">🚌</span>
            <span v-else-if="step.type === 'railway'">🚇</span>
            <span v-else-if="step.type === 'taxi'">🚕</span>
            <span v-else>🔄</span>
          </div>
          <div class="step-content">
            <p class="step-instruction">{{ step.instruction }}</p>
            <div v-if="step.duration || step.distance" class="step-meta">
              <span v-if="step.duration" class="step-duration">{{ Math.round(step.duration / 60) }}分钟</span>
              <span v-if="step.distance" class="step-distance">{{ step.distance }}米</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <hr class="separator"/>

    <map-display
      v-if="showMap"
      ref="mapDisplay"
      :is-pick-mode-active="mapPickModeEnabled"
      @location-picked="handleLocationPicked"
      class="map-display-component"
    ></map-display>
    <button @click="logoutUser" class="logout-button">Logout</button>
  </div>
</template>
<script>
import MapDisplay from './MapDisplay.vue';
import axios from 'axios';
import { debounce } from 'lodash';

export default {
  name: 'Dashboard',
  components: {
    MapDisplay,
  },
  data() {
    return {
      // UI Status
      isLoading: false,
      isCalculatingRoute: false,

      // Map
      mapDisplayRef: null,
      mapPickModeEnabled: false,
      
      // City & Home Location
      selectedCity: '',
      currentHomeLocation: null,
      homeAddressInput: '',
      homeLatitudeInput: '',
      homeLongitudeInput: '',
      showAddressSuggestions: false,
      addressSuggestions: [],
      
      // Shop Search
      shopInput: '',
      shopSuggestions: [],
      showShopSuggestions: false,
      isLoadingShops: false,
      searchResults: [],
      selectedShopForSearch: {id: null, name: ''},
      
      // Shops to Visit List
      shopsToVisit: [],
      
      // --- UNIFIED ROUTE PLANNING STATE ---
      selectedTravelMode: 'driving', // Unified travel mode
      homeCityName: '', // For public transit
      departureTime: '09:00:00', // Replaces defaultStartTime
      defaultStayDuration: 30,
      
      // Route results for the new dual-column UI
      routesByDistance: [], // Array for distance-optimized candidates
      routesByTime: [],     // Array for time-optimized candidates
      
      // UI state for selected route
      selectedRouteId: null,      // The ID of the currently selected route candidate
      selectedRoute: null,        // The full object of the selected route
      displayableSchedule: null,  // The schedule for the selected route
      
      showMap: false,
    };
  },
  computed: {
    pickHomeButtonText() {
      return this.mapPickModeEnabled ? 'Cancel Picking on Map' : 'Pick Home on Map';
    },
    canCalculateRoute() {
      const homeSet = this.currentHomeLocation && this.currentHomeLocation.latitude && this.currentHomeLocation.longitude;
      const confirmedShopsExist = this.shopsToVisit.some(shop => shop.status === 'confirmed');
      return homeSet && confirmedShopsExist;
    },
    mapCenter() {
      if (this.currentHomeLocation && this.currentHomeLocation.latitude && this.currentHomeLocation.longitude) {
        return [this.currentHomeLocation.longitude, this.currentHomeLocation.latitude];
      }
      return [121.4737, 31.2304]; // Default to Shanghai
    },
    mapMarkers() {
      const markers = [];

      // Add home marker if location is set
      if (this.currentHomeLocation && this.currentHomeLocation.latitude && this.currentHomeLocation.longitude) {
        markers.push({
          id: 'home',
          position: [this.currentHomeLocation.longitude, this.currentHomeLocation.latitude],
          label: 'Home',
          color: 'blue'
        });
      }

      // Add markers for confirmed shops
      this.shopsToVisit.forEach(shop => {
        if (shop.status === 'confirmed' && shop.latitude && shop.longitude) {
          markers.push({
            id: shop.id,
            position: [shop.longitude, shop.latitude],
            label: shop.name,
            color: 'red'
          });
        }
      });
      
      return markers;
    },
    routePolyline() {
      if (this.selectedRoute && this.selectedRoute.polyline) {
        return this.selectedRoute.polyline;
      }
      return '';
    },
    routeSteps() {
      if (this.selectedRoute && this.selectedRoute.steps) {
        return this.selectedRoute.steps;
      }
      return [];
    }
  },
  methods: {
    async fetchHomeLocation() {
      try {
        const response = await axios.get('/api/user/home');
        this.currentHomeLocation = response.data;
        this.homeAddressInput = response.data.home_address || '';
        this.homeLatitudeInput = response.data.home_latitude || '';
        this.homeLongitudeInput = response.data.home_longitude || '';
      } catch (error) {
        console.error('Error fetching home location:', error);
        if (error.response && error.response.status === 401) {
          alert('Session expired. Please login again.');
          this.$router.push('/login');
        }
      }
    },
    async saveHomeLocation() {
      try {
        const payload = {
          address: this.homeAddressInput,
          latitude: this.homeLatitudeInput ? parseFloat(this.homeLatitudeInput) : null,
          longitude: this.homeLongitudeInput ? parseFloat(this.homeLongitudeInput) : null,
        };
        const response = await axios.post('/api/user/home', payload);
        this.currentHomeLocation = response.data; // Update with response from server
        alert(response.data.message || 'Home location updated successfully!');
      } catch (error) {
        console.error('Error saving home location:', error);
        alert('Failed to save home location. ' + (error.response?.data?.message || ''));
      }
    },
    pickHomeOnMap() {
      this.mapPickModeEnabled = !this.mapPickModeEnabled;
      if (this.mapPickModeEnabled) {
          this.showMap = true;
          alert('Map picking mode activated. Click on the map to select your home location.');
      }
    },
    handleLocationPicked(locationData) {
      this.homeAddressInput = locationData.address;
      this.homeLatitudeInput = locationData.latitude.toString();
      this.homeLongitudeInput = locationData.longitude.toString();
      this.mapPickModeEnabled = false;
      alert(`Location picked: ${locationData.address}. Review and click "Set Home Location" to save.`);
    },
    logoutUser() {
      localStorage.removeItem('userToken');
      alert('You have been logged out.');
      this.$router.push('/login');
    },
    addShop() {
      if (!this.shopInput.trim()) {
        alert('请输入店铺名称。');
        return;
      }
      const newShop = {
        id: Date.now(),
        name: this.shopInput.trim(),
        status: 'pending_confirmation' 
      };
      // If a suggestion matches, add it directly as confirmed
      const matchingSuggestion = this.shopSuggestions.find(s => s.name.toLowerCase() === this.shopInput.trim().toLowerCase());
      if (matchingSuggestion) {
        this.selectShopSuggestion(matchingSuggestion);
      } else {
        this.shopsToVisit.push(newShop);
        this.shopInput = '';
      }
    },
    removeShop(shopId) {
      this.shopsToVisit = this.shopsToVisit.filter(shop => shop.id !== shopId);
      if (this.selectedShopForSearch && this.selectedShopForSearch.id === shopId) {
        this.searchResults = [];
        this.selectedShopForSearch = { id: null, name: '' };
      }
    },
    async findShopOnMap(shop) {
      this.isLoadingShops = true;
      this.selectedShopForSearch = shop;
      this.searchResults = [];
      const payload = {
        keywords: shop.name,
        city: this.selectedCity || '',
      };
      if (this.currentHomeLocation?.latitude) {
        payload.latitude = this.currentHomeLocation.latitude;
        payload.longitude = this.currentHomeLocation.longitude;
      }
      try {
        const response = await axios.post('/api/shops/find', payload);
        this.searchResults = response.data.shops || [];
        if (this.searchResults.length === 0) {
          alert(`No shops found for "${shop.name}".`);
        }
      } catch (error) {
        console.error('Error searching for shops:', error);
        alert(`Error searching for shops: ` + (error.response?.data?.message || 'Unknown error'));
      } finally {
        this.isLoadingShops = false;
      }
    },
    confirmShopSelection(selectedCandidate) {
      const shopIndex = this.shopsToVisit.findIndex(s => s.id === this.selectedShopForSearch.id);
      if (shopIndex !== -1) {
        const updatedShop = {
          ...this.shopsToVisit[shopIndex],
          name: selectedCandidate.name,
          address: selectedCandidate.address,
          latitude: selectedCandidate.latitude,
          longitude: selectedCandidate.longitude,
          status: 'confirmed',
          amap_id: selectedCandidate.id,
          stayDurationMinutes: 30
        };
        this.shopsToVisit.splice(shopIndex, 1, updatedShop);
      }
      this.searchResults = [];
      this.selectedShopForSearch = { id: null, name: '' };
    },
    displayRouteOnMap(routeData) {
      if (!routeData) {
        console.warn("No route data to display on map.");
        return;
      }
      this.displayableSchedule = this.generateDisplaySchedule(routeData);
      this.showMap = true;
      this.$nextTick(() => {
          if (this.$refs.mapDisplay) {
              this.$refs.mapDisplay.drawOptimizedRoute(routeData);
          } else {
              console.warn("MapDisplay component ref not available.");
          }
      });
    },
    getButtonText() {
      const confirmedShops = this.shopsToVisit.filter(s => s.status === 'confirmed').length;
      if (this.isCalculatingRoute || this.isFetchingDetails) {
        return "Calculating...";
      }
      if (confirmedShops === 1) {
        return "获取路线";
      }
      return "规划我的行程 (多站优化)";
    },
    async getDirections() {
      if (!this.canCalculateRoute || this.isCalculatingRoute) return;

      // Reset previous results
      this.routesByTime = [];
      this.routesByDistance = [];
      this.selectedRoute = null;
      this.selectedRouteId = null;
      this.routeCandidates = [];

      const confirmedShops = this.shopsToVisit.filter(s => s.status === 'confirmed');
      
      this.isCalculatingRoute = true;

      // 修复：即使是单个店铺，也使用route/optimize接口来规划完整的往返路线
      if (confirmedShops.length === 1) {
        try {
          const destination = confirmedShops[0];
          // 使用optimize接口确保获得完整的往返路线（家->店铺->家）
          const payload = {
            home_location: {
              latitude: this.currentHomeLocation.latitude,
              longitude: this.currentHomeLocation.longitude,
            },
            shops: [{
              id: destination.id,
              name: destination.name,
              latitude: destination.latitude,
              longitude: destination.longitude,
              stay_duration: (destination.stayDurationMinutes || 30) * 60, // Convert to seconds
            }],
            mode: this.selectedTravelMode,
            city: this.selectedTravelMode === 'public_transit' ? this.homeCityName : undefined,
            top_n: 5, // Request top 5 for both time and distance
          };

          const response = await fetch('http://localhost:5000/api/route/optimize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          });

          if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || 'Failed to calculate optimized route.');
          }

          const result = await response.json();
          
          // 处理返回的数据结构
          if (result.route_candidates && result.route_candidates.length > 0) {
            this.processRouteResults(result.route_candidates);
          } else if (result.routes && (result.routes.fastest_travel_time_routes || result.routes.shortest_distance_routes)) {
            // 兼容旧的数据结构
            this.routesByTime = this.processRoutes(result.routes.fastest_travel_time_routes || []);
            this.routesByDistance = this.processRoutes(result.routes.shortest_distance_routes || []);
          } else {
            throw new Error('未收到有效的路线数据');
          }
          
          const totalRoutes = this.routesByTime.length + this.routesByDistance.length;
          this.showNotification(`🎉 成功获取 ${totalRoutes} 条往返路线! 请从下方列表中选择一条路线`, 'success');
          
          // 自动选择第一条路线
          if (this.routesByTime.length > 0) {
            this.selectRoute(this.routesByTime[0]);
          } else if (this.routesByDistance.length > 0) {
            this.selectRoute(this.routesByDistance[0]);
          }

        } catch (error) {
          console.error('Error getting directions:', error);
          alert(`获取路线失败: ${error.message}`);
        } finally {
          this.isCalculatingRoute = false;
        }
      } else {
        // Fallback to existing TSP logic for multiple shops
        this.optimizeRoute();
      }
    },

    async optimizeRoute() {
      // This method now contains the original logic for multi-stop optimization
      if (!this.canCalculateRoute || this.isCalculatingRoute) return;

      this.isCalculatingRoute = true;
      this.routesByTime = [];
      this.routesByDistance = [];
      this.selectedRoute = null;
      this.selectedRouteId = null;

      const confirmedShops = this.shopsToVisit.filter(s => s.status === 'confirmed').map(shop => ({
        id: shop.id,
        name: shop.name,
        latitude: shop.latitude,
        longitude: shop.longitude,
        stay_duration: (shop.stayDurationMinutes || 0) * 60, // Convert to seconds
      }));

      const payload = {
        home_location: {
          latitude: this.currentHomeLocation.latitude,
          longitude: this.currentHomeLocation.longitude,
        },
        shops: confirmedShops,
        mode: this.selectedTravelMode,
        city: this.selectedTravelMode === 'public_transit' ? this.homeCityName : undefined,
        top_n: 5, // Request top 5 for both time and distance
      };
      
      try {
        const response = await fetch('http://localhost:5000/api/route/optimize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.message || 'Failed to calculate optimized route.');
        }

        const result = await response.json();
        
        // 修复：处理后端返回的route_candidates数据结构
        if (result.route_candidates && result.route_candidates.length > 0) {
          this.processRouteResults(result.route_candidates);
        } else if (result.routes && (result.routes.fastest_travel_time_routes || result.routes.shortest_distance_routes)) {
          // 兼容旧的数据结构
          this.routesByTime = this.processRoutes(result.routes.fastest_travel_time_routes || []);
          this.routesByDistance = this.processRoutes(result.routes.shortest_distance_routes || []);
        } else {
          throw new Error('未收到有效的路线数据');
        }
        
        // 不自动选择路线，让用户从候选列表中选择
        this.selectedRoute = null;
        this.selectedRouteId = null;
        this.displayableSchedule = null;
      
        const totalRoutes = this.routesByTime.length + this.routesByDistance.length;
        this.showNotification(`🎉 成功获取 ${totalRoutes} 条候选路线! 请从下方列表中选择一条路线`, 'success');
        if (this.routesByTime.length > 0) {
          this.selectRoute(this.routesByTime[0]);
        } else if (this.routesByDistance.length > 0) {
          this.selectRoute(this.routesByDistance[0]);
        }

      } catch (error) {
        console.error('Error optimizing route:', error);
        alert(`Error: ${error.message}`);
      } finally {
        this.isCalculatingRoute = false;
      }
    },
    processRoutes(routes) {
      return routes.map(route => {
        if (route.optimized_order && route.route_segments) {
          route.optimized_order = route.optimized_order.map(p => ({
            ...p,
            stay_duration: route.route_segments.find(s => s.to_name === p.name)?.duration || 0
          }));
        }
        return route; // Return the original object if no processing is needed
      });
    },
    // 处理路线结果 - 从main.js移植的正确逻辑
    processRouteResults(routesData) {
      if (!routesData || routesData.length === 0) {
        this.showNotification('未能计算出有效路线', 'warning');
        return;
      }

      const allRoutes = routesData;
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
        ...route, // 保留原始路线数据
        combination: route.optimized_order || [],
        totalTime: Math.round(route.total_overall_duration),
        totalDistance: Math.round(route.total_distance),
        routeData: route,
        originalIndex: index
      });
      
      // 设置路线数组
      this.routesByTime = timeRoutes.map((route, index) => formatRoute(route, index, 'time'));
      this.routesByDistance = distanceRoutes.map((route, index) => formatRoute(route, index, 'distance'));
      
      console.log('🚗 最终生成的时间路线:', this.routesByTime);
      console.log('🚗 最终生成的距离路线:', this.routesByDistance);
      
      if (this.routesByTime.length === 0 && this.routesByDistance.length === 0) {
        this.showNotification('未能计算出有效路线', 'warning');
        return;
      }
      
      this.showNotification(`🎉 成功获取候选路线! 时间优化(${this.routesByTime.length}条), 距离优化(${this.routesByDistance.length}条)`, 'success');
    },
    // 显示通知方法
    showNotification(message, type = 'info', title = '') {
      // 这里可以使用简单的alert或者集成更复杂的通知组件
      if (type === 'success') {
        console.log('✅', title || '成功', message);
      } else if (type === 'error') {
        console.error('❌', title || '错误', message);
      } else if (type === 'warning') {
        console.warn('⚠️', title || '警告', message);
      } else {
        console.info('ℹ️', title || '提示', message);
      }
      // 可以在这里添加更复杂的通知UI逻辑
    },
    selectRoute(route) {
      console.log('选择路线:', route);
      this.selectedRoute = route;
      this.selectedRouteId = route.id;
      
      // 生成可显示的行程
      if (route.optimized_order && route.route_segments) {
        this.displayableSchedule = this.generateDisplaySchedule(route);
      }
      
      // 在地图上显示路线
      this.displayRouteOnMap(route);
      
      // 滚动到路线详情区域
      this.$nextTick(() => {
        const routeGuidanceSection = document.querySelector('.route-guidance-section');
        if (routeGuidanceSection) {
          routeGuidanceSection.scrollIntoView({ behavior: 'smooth' });
        }
      });
    },
    generateDisplaySchedule(routeData) {
      if (!routeData || !routeData.optimized_order || !routeData.route_segments) return [];
      const displayScheduleItems = [];
      let scheduleTime = new Date();
      const [hours, minutes, seconds] = this.departureTime.split(':').map(Number);
      scheduleTime.setHours(hours, minutes, seconds, 0);
      if (routeData.optimized_order.length > 0 && routeData.optimized_order[0].name === "Home") {
        displayScheduleItems.push({
          type: 'departure',
          location: 'Home',
          time: new Date(scheduleTime.getTime())
        });
      }

      for (let i = 0; i < routeData.route_segments.length; i++) {
        const segment = routeData.route_segments[i];
        const travelDurationSeconds = segment.duration;
        const toLocationName = segment.to_name;
        scheduleTime.setSeconds(scheduleTime.getSeconds() + travelDurationSeconds);
        displayScheduleItems.push({
          type: 'arrival',
          location: toLocationName,
          time: new Date(scheduleTime.getTime()),
          travel_duration_seconds: travelDurationSeconds
        });

        if (toLocationName !== "Home") {
          const currentRoutePoint = routeData.optimized_order[i+1];
          const stayDurationSeconds = currentRoutePoint.stay_duration || 0;
          if (stayDurationSeconds > 0) {
            displayScheduleItems.push({ type: 'stay', location: toLocationName, duration_seconds: stayDurationSeconds });
            scheduleTime.setSeconds(scheduleTime.getSeconds() + stayDurationSeconds);
          }
          displayScheduleItems.push({ type: 'departure', location: toLocationName, time: new Date(scheduleTime.getTime())});
        }
      }
      return displayScheduleItems;
    },
    formatTime(dateObject) {
      if (!(dateObject instanceof Date)) return '';
      return dateObject.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    },
    formatDuration(totalSeconds) {
      return `${Math.round(totalSeconds / 60)}`;
    },
    async onAddressInput() {
      if (this.homeAddressInput.trim().length < 2) {
        this.addressSuggestions = [];
        return;
      }
      try {
        const payload = { keywords: this.homeAddressInput.trim(), city: this.selectedCity };
        const response = await axios.post('/api/shops/find', payload);
        this.addressSuggestions = response.data.shops?.slice(0, 5) || [];
      } catch (error) {
        console.error('Error fetching address suggestions:', error);
        this.addressSuggestions = [];
      }
    },
    hideAddressSuggestions() {
      setTimeout(() => { this.showAddressSuggestions = false; }, 200);
    },
    selectAddressSuggestion(suggestion) {
      this.homeAddressInput = suggestion.address || suggestion.name;
      this.homeLatitudeInput = suggestion.latitude?.toString() || '';
      this.homeLongitudeInput = suggestion.longitude?.toString() || '';
      this.showAddressSuggestions = false;
    },
    async onShopInput() {
      if (this.shopInput.trim().length < 2) {
        this.shopSuggestions = [];
        return;
      }
      try {
        const payload = {
          keywords: this.shopInput.trim(),
          city: this.selectedCity,
        };
        if(this.currentHomeLocation?.latitude) {
            payload.latitude = this.currentHomeLocation.latitude;
            payload.longitude = this.currentHomeLocation.longitude;
            payload.radius = 20000;
        }
        const response = await axios.post('/api/shops/find', payload);
        this.shopSuggestions = response.data.shops?.slice(0, 8) || [];
      } catch (error) {
        console.error('Error fetching shop suggestions:', error);
        this.shopSuggestions = [];
      }
    },
    hideShopSuggestions() {
      setTimeout(() => { this.showShopSuggestions = false; }, 200);
    },
    selectShopSuggestion(suggestion) {
      const newShop = {
        id: suggestion.id || Date.now(),
        name: suggestion.name,
        address: suggestion.address,
        latitude: suggestion.latitude,
        longitude: suggestion.longitude,
        status: 'confirmed',
        amap_id: suggestion.id,
        stayDurationMinutes: 30
      };
      this.shopsToVisit.push(newShop);
      this.shopInput = '';
      this.showShopSuggestions = false;
    },
    onCityChange() {
      if (this.selectedCity) {
        this.homeCityName = this.selectedCity;
        localStorage.setItem('selectedCity', this.selectedCity);
        if (this.$refs.mapDisplay) {
          const coords = this.getCityCoordinates(this.selectedCity);
          if (coords) this.$refs.mapDisplay.setCenterToCity(coords.longitude, coords.latitude);
        }
      }
    },
    getCityCoordinates(cityName) {
      const cityCoordinates = {
        '北京': { longitude: 116.4074, latitude: 39.9042 },
        '上海': { longitude: 121.4737, latitude: 31.2304 },
        '广州': { longitude: 113.2644, latitude: 23.1291 },
        '深圳': { longitude: 114.0579, latitude: 22.5431 },
        '杭州': { longitude: 120.1551, latitude: 30.2741 },
        '南京': { longitude: 118.7969, latitude: 32.0603 },
        '成都': { longitude: 104.0668, latitude: 30.5728 },
        '武汉': { longitude: 114.3055, latitude: 30.5928 },
        '西安': { longitude: 108.9402, latitude: 34.3416 },
        '重庆': { longitude: 106.5516, latitude: 29.5630 },
        '天津': { longitude: 117.2010, latitude: 39.0842 },
        '苏州': { longitude: 120.5853, latitude: 31.2989 }
      };
      return cityCoordinates[cityName];
    },
  },
  created() {
    const savedCity = localStorage.getItem('selectedCity');
    if (savedCity) this.selectedCity = savedCity;
  },
  mounted() {
    this.fetchHomeLocation();
  }
};
</script>
<style scoped>
.dashboard-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
  font-family: 'Avenir', Helvetica, Arial, sans-serif;
  color: #2c3e50;
  display: grid;
  grid-template-columns: 1fr 2fr;
  grid-gap: 30px;
}
.placeholder-message-section {
  background-color: #f0f8ff; /* Light Alice Blue, similar to schedule display */
  padding: 20px;
  border-radius: 6px;
  margin-bottom: 25px; /* Consistent with other sections */
  box-shadow: 0 1px 3px rgba(0,0,0,0.03);
  text-align: center;
  color: #555; /* Subdued text color */
  font-style: italic;
}
.map-display-component {
  margin-top: 20px;
  margin-bottom: 20px;
}
.route-optimization-section {
  background-color: #fff;
  padding: 20px;
  border-radius: 6px;
  margin-bottom: 25px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.03);
}
.route-optimization-section h3 {
  margin-top: 0;
}
.travel-mode-selection label {
  margin-right: 15px;
  font-weight: normal;
}
.travel-mode-selection input[type="radio"] {
  margin-right: 5px;
}
.text-danger {
  color: #dc3545;
  font-size: 0.85em;
}
.btn-large {
  padding: 12px 24px;
  font-size: 1.1em;
  display: block; /* Make it block to center it or control width */
  margin: 0 auto 15px auto; /* Center button and add margin below */
}
.route-calculation-condition {
  font-size: 0.9em;
  color: #777;
  text-align: center;
  margin-bottom: 15px;
}
.optimized-route-details {
  margin-top: 20px;
  padding: 15px;
  background-color: #e9f5ff; /* Light blue background for itinerary */
  border: 1px solid #b3d7ff;
  border-radius: 4px;
}
.optimized-route-details h4, .optimized-route-details h5 {
  color: #0056b3; /* Darker blue for headings */
}
.optimized-route-details h5 {
  margin-top: 15px;
  margin-bottom: 8px;
}
.route-steps-list {
  list-style-type: none;
  padding-left: 0;
}
.route-step {
  padding: 8px 0;
  border-bottom: 1px dashed #b3d7ff;
}
.route-step:last-child {
  border-bottom: none;
}
.segment-details {
  font-size: 0.9em;
  color: #333;
  padding-left: 10px; /* Indent segment details */
}
.loading-shops-indicator {
  margin-top: 15px;
  padding: 10px;
  background-color: #eef7ff;
  border: 1px solid #cce0ff;
  border-radius: 4px;
  text-align: center;
  font-style: italic;
}
.search-results-section {
  margin-top: 20px;
  padding: 15px;
  background-color: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 6px;
}
.search-results-section h4 {
  margin-top: 0;
  margin-bottom: 15px;
}
.search-results-list {
  list-style: none;
  padding: 0;
  max-height: 300px;
  overflow-y: auto;
  margin-bottom: 15px;
}
.search-result-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  border-bottom: 1px solid #eee;
}
.search-result-item:last-child {
  border-bottom: none;
}
.search-result-item div {
  flex-grow: 1;
  margin-right: 10px;
}
.search-result-item small {
  color: #555;
}
.shops-to-visit-section {
  background-color: #fff;
  padding: 20px;
  border-radius: 6px;
  margin-bottom: 25px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.03);
}
.add-shop-form .form-group {
  margin-bottom: 10px;
}
.add-shop-form label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
}
.add-shop-form input[type="text"] {
  margin-bottom: 10px;
}
.shops-list {
  list-style: none;
  padding: 0;
  margin-top: 20px;
}
.shop-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 10px;
  border: 1px solid #eee;
  border-radius: 4px;
  margin-bottom: 8px;
  background-color: #fdfdfd;
}
.shop-info {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
}
.shop-name {
  font-weight: bold;
  margin-bottom: 4px;
}
.shop-address-confirmed {
  font-size: 0.9em;
  color: #555;
  margin-bottom: 5px;
}
.shop-stay-duration {
  display: flex;
  align-items: center;
  margin-top: 5px;
}
.stay-duration-label {
  font-size: 0.85em;
  margin-right: 5px;
  color: #333;
}
.stay-duration-input {
  width: 70px;
  padding: 4px 6px;
  font-size: 0.9em;
  border: 1px solid #ccc;
  border-radius: 3px;
}
.shop-item-actions button {
  margin-left: 8px;
  align-self: flex-start;
}
.btn-small {
  padding: 5px 10px;
  font-size: 0.9em;
}
.btn-info {
  background-color: #17a2b8;
  color: white;
}
.btn-info:hover {
  background-color: #117a8b;
}
.btn-success {
  background-color: #28a745;
  color: white;
}
.btn-success:hover {
  background-color: #1e7e34;
}
.no-shops-message {
  color: #777;
  font-style: italic;
  text-align: center;
  margin-top: 15px;
}
.home-location-section {
  background-color: #fff;
  padding: 20px;
  border-radius: 6px;
  margin-bottom: 25px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.03);
}
.current-home-display {
  padding: 10px;
  background-color: #eef7ff;
  border: 1px solid #cce0ff;
  border-radius: 4px;
  margin-bottom: 15px;
  font-style: italic;
}
.home-form .form-group {
  margin-bottom: 15px;
}
.home-form label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
  color: #333;
}
.home-form input[type="text"] {
  width: calc(100% - 22px);
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  box-sizing: border-box;
}
.btn-primary, .btn-secondary, .logout-button {
  padding: 10px 18px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
  margin-right: 10px;
  margin-top: 10px;
}
.btn-primary {
  background-color: #007bff;
  color: white;
}
.btn-primary:hover {
  background-color: #0056b3;
}
.btn-secondary {
  background-color: #6c757d;
  color: white;
}
.btn-secondary:hover {
  background-color: #545b62;
}
.btn-danger {
  background-color: #dc3545;
  color: white;
}
.btn-danger:hover {
  background-color: #c82333;
}
.logout-button {
  margin-top: 20px;
  padding: 10px 20px;
  background-color: #d9534f;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}
.logout-button:hover {
  background-color: #c9302c;
}
.separator {
  margin-top: 30px;
  margin-bottom: 30px;
  border: 0;
  border-top: 1px solid #eee;
}
input[type="text"] {
  width: calc(100% - 22px);
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  box-sizing: border-box;
  margin-bottom: 10px;
}
.schedule-display-section {
  background-color: #f0f8ff;
  padding: 20px;
  border-radius: 6px;
  margin-bottom: 25px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.03);
}
.schedule-display-section h3 {
  margin-top: 0;
  color: #333;
  text-align: center;
  margin-bottom: 15px;
}
.schedule-list {
  list-style-type: none;
  padding: 0;
}
.schedule-item {
  padding: 8px 0;
  border-bottom: 1px dashed #cce0ff;
}
.schedule-item:last-child {
  border-bottom: none;
}
.schedule-event {
  display: flex;
  align-items: center;
}
.event-time {
  font-weight: bold;
  color: #0056b3;
  margin-right: 15px;
  min-width: 70px;
}
.event-description {
  color: #333;
}
.event-stay-description {
  padding-left: calc(70px + 15px);
  font-style: italic;
  color: #555;
}
.departure-event .event-description strong,
.arrival-event .event-description strong {
  color: #007bff;
}
.city-selection-section {
  background-color: #fff;
  padding: 20px;
  border-radius: 6px;
  margin-bottom: 25px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.03);
}
.city-selection-section h3 {
  margin-top: 0;
  margin-bottom: 15px;
}
.city-select {
  width: 100%;
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 16px;
  margin-bottom: 10px;
  background-color: #fff;
}
.city-select:focus {
  outline: none;
  border-color: #007bff;
  box-shadow: 0 0 0 2px rgba(0,123,255,0.25);
}
.selected-city-display {
  margin-top: 10px;
  color: #28a745;
  font-size: 0.9em;
}
.address-input-container, .shop-input-container {
  position: relative;
}
.address-suggestions, .shop-suggestions {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background-color: #fff;
  border: 1px solid #ccc;
  border-top: none;
  border-radius: 0 0 4px 4px;
  max-height: 200px;
  overflow-y: auto;
  z-index: 1000;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
.suggestion-item {
  padding: 12px;
  cursor: pointer;
  border-bottom: 1px solid #f0f0f0;
  transition: background-color 0.2s;
}
.suggestion-item:hover {
  background-color: #f8f9fa;
}
.suggestion-item:last-child {
  border-bottom: none;
}
.suggestion-name {
  font-weight: bold;
  color: #333;
  margin-bottom: 2px;
}
.suggestion-address {
  color: #666;
  font-size: 0.9em;
}
.suggestion-distance {
  font-size: 0.8em;
  color: #888;
  margin-top: 2px;
}
.shop-suggestions {
  position: absolute;
  background-color: #fff;
  border: 1px solid #ccc;
  border-radius: 4px;
  max-height: 200px;
  overflow-y: auto;
  z-index: 1000;
}
.shop-suggestions .suggestion-item {
  padding: 10px;
  cursor: pointer;
}
.shop-suggestions .suggestion-item:hover {
  background-color: #f0f0f0;
}
.shop-suggestions .suggestion-name {
  font-weight: bold;
}
.shop-suggestions .suggestion-address {
  color: #555;
}
.shop-suggestions .suggestion-distance {
  font-size: 0.8em;
  color: #777;
}
.route-results-container {
  display: flex;
  gap: 20px;
  margin-top: 20px;
  flex-wrap: wrap;
}
.route-option-card {
  flex: 1;
  min-width: 300px;
  padding: 15px;
  background-color: #e9f5ff;
  border: 1px solid #b3d7ff;
  border-radius: 6px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
.route-option-card h4 {
  color: #0056b3;
  margin-top: 0;
  border-bottom: 2px solid #b3d7ff;
  padding-bottom: 8px;
  margin-bottom: 12px;
}
.route-option-card button {
  margin-top: 15px;
  width: 100%;
}
/* 双列路线展示样式 - 添加到现有CSS中 */

.dual-routes-container {
  background: #fff;
  border-radius: 16px;
  padding: 25px;
  margin-top: 20px;
  box-shadow: 0 4px 15px rgba(0,0,0,0.05);
  border: 1px solid rgba(0,0,0,0.05);
}

.dual-routes-container h3 {
  margin: 0 0 25px 0;
  color: #2c3e50;
  font-size: 1.4rem;
  display: flex;
  align-items: center;
  gap: 10px;
}

.route-summary-badge {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: 500;
}

/* 双列布局 */
.routes-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 30px;
  margin-bottom: 25px;
}

.route-column {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 20px;
  min-height: 400px;
}

.distance-column {
  border-left: 4px solid #28a745;
}

.time-column {
  border-left: 4px solid #667eea;
}

/* 列标题 */
.column-header {
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 2px solid #e9ecef;
}

.column-header h4 {
  margin: 0 0 8px 0;
  color: #2c3e50;
  font-size: 1.2rem;
  display: flex;
  align-items: center;
  gap: 8px;
}

.column-count {
  background: rgba(0,0,0,0.1);
  color: #6c757d;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 0.8rem;
  font-weight: 500;
}

.column-description {
  color: #6c757d;
  font-size: 0.9rem;
  margin: 0;
}

/* 路线候选项容器 */
.route-candidates {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 单个路线候选项 */
.route-candidate {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.3s ease;
  border: 2px solid transparent;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

.route-candidate:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0,0,0,0.1);
  border-color: #e9ecef;
}

.route-candidate.selected {
  border-color: #667eea;
  background: linear-gradient(135deg, #f8f9ff 0%, #f0f4ff 100%);
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(102, 126, 234, 0.2);
}

.distance-column .route-candidate.selected {
  border-color: #28a745;
  background: linear-gradient(135deg, #f8fff8 0%, #f0fff0 100%);
  box-shadow: 0 8px 25px rgba(40, 167, 69, 0.2);
}

/* 候选项头部 */
.candidate-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.candidate-rank {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.8rem;
  font-weight: 600;
}

.distance-column .candidate-rank {
  background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
}

.candidate-type {
  color: #6c757d;
  font-size: 0.85rem;
  font-weight: 500;
}

/* 统计数据 */
.candidate-stats {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}

.stat-primary, .stat-secondary {
  display: flex;
  align-items: center;
  gap: 6px;
}

.stat-primary .stat-value {
  font-weight: 700;
  color: #2c3e50;
  font-size: 1.1rem;
}

.stat-secondary .stat-value {
  color: #6c757d;
  font-size: 0.9rem;
}

.stat-icon {
  font-size: 1rem;
}

/* 路线路径 */
.candidate-route {
  margin-bottom: 12px;
}

.route-path {
  color: #495057;
  font-size: 0.9rem;
  line-height: 1.4;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

/* 店铺标签 */
.candidate-shops {
  display: none;
}

.route-candidate.selected .shop-badge {
  background: rgba(102, 126, 234, 0.1);
  color: #667eea;
}

.distance-column .route-candidate.selected .shop-badge {
  background: rgba(40, 167, 69, 0.1);
  color: #28a745;
}

/* 无路线状态 */
.no-routes {
  text-align: center;
  padding: 40px 20px;
  color: #6c757d;
}

.no-routes .icon {
  font-size: 2.5rem;
  margin-bottom: 10px;
  display: block;
  opacity: 0.5;
}

.no-routes p {
  margin: 0;
  font-style: italic;
}

/* 路线对比统计 */
.routes-comparison {
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  border-radius: 12px;
  padding: 20px;
  margin-top: 20px;
}

.routes-comparison h4 {
  margin: 0 0 15px 0;
  color: #2c3e50;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 1.1rem;
}

.comparison-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 15px;
}

.comparison-item {
  background: #fff;
  padding: 15px;
  border-radius: 10px;
  text-align: center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

.comparison-label {
  display: block;
  font-size: 0.85rem;
  color: #6c757d;
  margin-bottom: 5px;
  font-weight: 500;
}

.comparison-value {
  display: block;
  font-size: 1.2rem;
  font-weight: 700;
  color: #2c3e50;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .routes-columns {
    grid-template-columns: 1fr;
    gap: 20px;
  }
  
  .candidate-stats {
    flex-direction: column;
    gap: 8px;
  }
  
  .candidate-shops {
    justify-content: center;
  }
  
  .comparison-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 480px) {
  .dual-routes-container {
    padding: 15px;
  }
  
  .route-column {
    padding: 15px;
  }
  
  .comparison-grid {
    grid-template-columns: 1fr;
  }
}

/* --- Route Candidate Specific Styles --- */
.route-candidates-container {
  margin-top: 20px;
  border: 1px solid #ddd;
  padding: 15px;
  border-radius: 8px;
  background-color: #f9f9f9;
}

.route-candidates-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.route-candidate-item {
  padding: 15px;
  border: 1px solid #eee;
  border-radius: 8px;
  margin-bottom: 10px;
  cursor: pointer;
  background-color: #fff;
  transition: all 0.2s ease-in-out;
}

.route-candidate-item:hover {
  border-color: #007bff;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}

.route-candidate-item.selected {
  border-color: #28a745;
  background-color: #e9f5ec;
  box-shadow: 0 0 10px rgba(40, 167, 69, 0.3);
}

.candidate-item-header {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}

.candidate-rank {
  background-color: #007bff;
  color: white;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.9em;
  margin-right: 10px;
}

.candidate-summary {
  font-weight: bold;
}

.candidate-item-stats {
  display: flex;
  gap: 20px;
  font-size: 0.95em;
  color: #555;
}

.stat-primary, .stat-secondary {
  display: flex;
  align-items: center;
  gap: 5px;
}

.stat-icon {
  font-size: 1.1em;
}

.loading-routes-indicator {
  text-align: center;
  padding: 20px;
  font-size: 1.2em;
  color: #555;
}

/* Add some spacing and alignment to buttons in a row */
.home-form .form-group + .btn-primary,
.home-form .btn-primary + .btn-secondary {
  margin-left: 10px;
}

.shop-item-actions button + button {
  margin-left: 8px;
}

/* 强制隐藏所有路线卡片中的店铺标签 */
.candidate-shops,
.candidate-item-tags {
  display: none !important;
}

/* 路线指导样式 */
.route-guidance-section {
  margin-top: 25px;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 12px;
  border: 1px solid #e9ecef;
}

.route-guidance-section h3 {
  margin: 0 0 20px 0;
  color: #2c3e50;
  font-size: 1.3rem;
  font-weight: 600;
}

.route-segments {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.route-segment {
  background: #fff;
  border-radius: 10px;
  padding: 18px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  border: 1px solid #e9ecef;
}

.segment-header {
  margin-bottom: 15px;
  border-bottom: 1px solid #e9ecef;
  padding-bottom: 12px;
}

.segment-header h4 {
  margin: 0 0 8px 0;
  color: #2c3e50;
  font-size: 1.1rem;
  font-weight: 600;
}

.segment-meta {
  display: flex;
  gap: 15px;
  align-items: center;
  flex-wrap: wrap;
}

.segment-distance,
.segment-duration {
  background: #e3f2fd;
  color: #1976d2;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 500;
}

.segment-mode {
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 500;
}

.segment-mode.public_transit {
  background: #e8f5e8;
  color: #2e7d32;
}

.segment-mode.driving {
  background: #fff3e0;
  color: #f57c00;
}

.transit-steps,
.driving-steps,
.route-steps {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.transit-step,
.driving-step,
.route-step {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
  border-left: 4px solid transparent;
}

.transit-step.walk,
.route-step.walk {
  border-left-color: #6c757d;
  background: #f1f3f4;
}

.transit-step.bus,
.route-step.bus {
  border-left-color: #28a745;
  background: #e8f5e8;
}

.transit-step.railway,
.route-step.railway {
  border-left-color: #007bff;
  background: #e3f2fd;
}

.transit-step.taxi,
.route-step.taxi {
  border-left-color: #ffc107;
  background: #fff8e1;
}

.driving-step {
  border-left-color: #f57c00;
  background: #fff3e0;
}

.step-icon {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.2rem;
}

.step-content {
  flex: 1;
  min-width: 0;
}

.step-instruction {
  margin: 0 0 6px 0;
  color: #2c3e50;
  font-size: 0.95rem;
  line-height: 1.4;
}

.step-meta {
  display: flex;
  gap: 12px;
  font-size: 0.8rem;
  color: #6c757d;
}

.step-distance,
.step-duration {
  background: #e9ecef;
  padding: 2px 6px;
  border-radius: 4px;
}

.basic-segment-info {
  padding: 15px;
  background: #f8f9fa;
  border-radius: 8px;
  color: #6c757d;
  font-style: italic;
}

.basic-segment-info p {
  margin: 0 0 8px 0;
}

.basic-segment-info p:last-child {
  margin: 0;
}

/* 新增：路线概览样式 */
.route-overview {
  margin-bottom: 25px;
  padding: 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  color: white;
}

.overview-stats {
  display: flex;
  justify-content: space-around;
  gap: 20px;
  flex-wrap: wrap;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 120px;
}

.stat-item .stat-icon {
  font-size: 1.5rem;
}

.stat-item .stat-label {
  font-size: 0.9rem;
  opacity: 0.9;
  text-align: center;
}

.stat-item .stat-value {
  font-size: 1.2rem;
  font-weight: 600;
  text-align: center;
}

/* 新增：段落标题优化 */
.segment-title {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.segment-number {
  background: #667eea;
  color: white;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.85rem;
  font-weight: 600;
  flex-shrink: 0;
}

/* 新增：步骤编号样式 */
.step-number {
  background: #e9ecef;
  color: #495057;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.8rem;
  font-weight: 600;
  flex-shrink: 0;
}

/* 优化：基础段落信息样式 */
.basic-info-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.route-description {
  margin: 0;
  font-size: 1rem;
  color: #2c3e50;
  font-weight: 500;
}

.basic-stats {
  display: flex;
  gap: 15px;
  flex-wrap: wrap;
}

.basic-stat {
  background: #e3f2fd;
  color: #1976d2;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 0.9rem;
  font-weight: 500;
}

/* 新增：备选路线和警告样式 */
.fallback-steps {
  background: #fff8e1;
  border: 1px solid #ffcc02;
  border-radius: 8px;
  padding: 15px;
  margin-top: 10px;
}

.fallback-notice {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 15px;
  padding: 12px;
  background: #fff3e0;
  border-radius: 6px;
  border-left: 4px solid #ff9800;
}

.notice-icon {
  font-size: 1.2rem;
  flex-shrink: 0;
}

.notice-content {
  flex: 1;
}

.notice-title {
  margin: 0 0 4px 0;
  font-weight: 600;
  color: #f57c00;
  font-size: 0.9rem;
}

.notice-text {
  margin: 0;
  color: #ef6c00;
  font-size: 0.85rem;
  line-height: 1.4;
}

.fallback-step {
  background: #fff3e0 !important;
  border-left-color: #ff9800 !important;
}

.transit-step.fallback,
.transit-step.unavailable {
  background: #ffebee;
  border-left-color: #f44336;
}

.transit-step.unavailable .step-instruction {
  color: #d32f2f;
  font-weight: 500;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .route-guidance-section {
    padding: 15px;
  }
  
  .route-overview {
    padding: 15px;
  }
  
  .overview-stats {
    gap: 15px;
  }
  
  .stat-item {
    min-width: 100px;
  }
  
  .segment-title {
    gap: 8px;
  }
  
  .segment-meta {
    gap: 10px;
  }
  
  .transit-step,
  .driving-step,
  .route-step {
    gap: 10px;
    padding: 10px;
  }
  
  .step-meta {
    flex-direction: column;
    gap: 6px;
  }
  
  .basic-stats {
    gap: 10px;
  }
}
</style>
