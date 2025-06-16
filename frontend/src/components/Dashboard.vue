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
        {{ isCalculatingRoute ? 'Calculating Route...' : 'Plan My Day! (Optimized Route)' }}
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
                  <div class="stat-secondary">
                    <span class="stat-value">{{ (route.total_distance / 1000).toFixed(2) }}</span> 公里
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
              <p>未找到时间最优路线</p>
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
                  <div class="stat-secondary">
                    <span class="stat-value">{{ Math.round(route.total_overall_duration / 60) }}</span> 分钟
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
              <p>未找到距离最优路线</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <hr class="separator"/>

    <!-- Generated Schedule Display -->
    <div v-if="displayableSchedule && displayableSchedule.length > 0" class="schedule-display-section">
      <h3>Generated Schedule (Starts at {{ formatTime(new Date(new Date().setHours(...defaultStartTime.split(':').map(Number)))) }})</h3>
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
      currentSelectedRoute: null, // The full object of the selected route
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
    getDirections() {
      if (this.isCalculatingRoute || !this.canCalculateRoute) return;
      this.isCalculatingRoute = true;
      // Reset state for new results
      this.routesByTime = [];
      this.routesByDistance = [];
      this.selectedRouteId = null;
      this.currentSelectedRoute = null;
      this.displayableSchedule = null;
      if (this.$refs.mapDisplay) {
         this.$refs.mapDisplay.clearMapElements();
      }
      const confirmedShops = this.shopsToVisit
        .filter(shop => shop.status === 'confirmed')
        .map(shop => ({
            id: shop.id,
            name: shop.name,
            latitude: shop.latitude,
            longitude: shop.longitude,
            amap_id: shop.amap_id,
            stay_duration: (shop.stayDurationMinutes || 0) * 60
        }));
      const payload = {
        home_location: {
          latitude: this.currentHomeLocation.latitude,
          longitude: this.currentHomeLocation.longitude,
        },
        shops: confirmedShops,
        mode: this.selectedTravelMode,
        city: this.selectedTravelMode === 'public_transit' ? this.homeCityName.trim() : this.selectedCity
      };
      
      axios.post('/api/route/optimize', payload)
        .then(response => {
          console.log("API Response received:", response.data);

          const timeRoutes = (response.data.routes?.fastest_travel_time_routes || []).map((route, index) => ({ ...route, id: `time-${index}` }));
          const distanceRoutes = (response.data.routes?.shortest_distance_routes || []).map((route, index) => ({ ...route, id: `distance-${index}` }));

          // Use this.$set to ensure reactivity
          this.$set(this, 'routesByTime', timeRoutes);
          this.$set(this, 'routesByDistance', distanceRoutes);
          
          console.log("Data assigned to component state. Forcing UI update...", {
            routesByTime: this.routesByTime,
            routesByDistance: this.routesByDistance
          });

          // Force Vue to re-render the component.
          this.$forceUpdate();

          // Set a default selection if routes are found
          if (this.routesByTime.length > 0) {
            console.log("Defaulting to first TIME-optimized route.");
            this.selectRoute(this.routesByTime[0]);
          } else if (this.routesByDistance.length > 0) {
            console.log("Defaulting to first DISTANCE-optimized route.");
            this.selectRoute(this.routesByDistance[0]);
          } else {
            alert("No valid routes found.");
          }
        })
        .catch(error => {
          console.error('Error calculating optimized route:', error);
          alert('Error calculating route: ' + (error.response?.data?.message || 'Server error'));
        })
        .finally(() => {
          this.isCalculatingRoute = false;
        });
    },
    selectRoute(route) {
      console.log("Attempting to select route:", route);
      if (!route || !route.id) {
        console.error("Invalid route object passed to selectRoute.", route);
        return;
      }
      this.selectedRouteId = route.id;
      this.currentSelectedRoute = route;
      console.log("State after selecting route:", {
        selectedRouteId: this.selectedRouteId,
      });
      this.displayRouteOnMap(route);
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
/* Add styling for .map-display-component if needed, e.g., margin */
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
.dashboard-container {
  max-width: 800px;
  margin: 30px auto;
  padding: 25px;
  text-align: left;
  background-color: #f9f9f9;
  border: 1px solid #eee;
  border-radius: 8px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
}
h2 {
  text-align: center;
  color: #333;
  margin-bottom: 25px;
}
h3 {
  color: #444;
  margin-top: 20px;
  margin-bottom: 15px;
}
p {
  color: #555;
  line-height: 1.6;
  margin-bottom: 10px;
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
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.shop-badge {
  background: #e9ecef;
  color: #495057;
  padding: 3px 8px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 500;
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
</style>
