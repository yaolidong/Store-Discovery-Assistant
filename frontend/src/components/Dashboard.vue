<template>
  <div class="dashboard-container">
    <h2>Welcome to your Dashboard!</h2>
    <p>This is where your amazing trip planning features will reside.</p>
    <p>Plan new trips, view existing ones, and manage your travel itineraries.</p>

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
        <div class="form-group">
          <label for="homeAddress">Home Address:</label>
          <input type="text" id="homeAddress" v-model="homeAddressInput" placeholder="Enter your home address" />
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
        <div class="form-group">
          <label for="shopInput">Shop Name:</label>
          <input type="text" id="shopInput" v-model="shopInput" placeholder="Enter a shop name" />
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
        <input type="text" id="homeCityName" v-model="homeCityName" placeholder="Enter city for transit" />
        <small v-if="!homeCityName" class="text-danger">City is required for public transit mode.</small>
      </div>

      <button
        @click="calculateOptimizedRoute"
        :disabled="!canCalculateRoute || isCalculatingRoute || (selectedTravelMode === 'public_transit' && !homeCityName)"
        class="btn-primary btn-large"
      >
        {{ isCalculatingRoute ? 'Calculating Route...' : 'Plan My Day! (Optimized Route)' }}
      </button>
      <p v-if="!canCalculateRoute && !isCalculatingRoute" class="route-calculation-condition">
        Please set your home location, confirm at least one shop, and specify city if using transit, to enable route calculation.
      </p>

      <div v-if="optimizedRouteData" class="optimized-route-details">
        <h4>Optimized Itinerary:</h4>
        <p>
          <strong>Total Distance:</strong> {{ (optimizedRouteData.total_distance / 1000).toFixed(2) }} km<br>
          <strong>Total Duration:</strong> {{ Math.round(optimizedRouteData.total_duration / 60) }} minutes
        </p>
        <h5>Route:</h5>
        <ul class="route-steps-list">
          <li v-for="(point, index) in optimizedRouteData.optimized_order" :key="point.id + '-' + index" class="route-step">
            <strong>{{ index + 1 }}. {{ point.name }}</strong>
            <div v-if="index < optimizedRouteData.route_segments.length" class="segment-details">
              &nbsp;&nbsp;&nbsp;&nbsp;⇩ To {{ optimizedRouteData.route_segments[index].to_name }}:
              {{ (optimizedRouteData.route_segments[index].distance / 1000).toFixed(2) }} km,
              {{ Math.round(optimizedRouteData.route_segments[index].duration / 60) }} min
            </div>
          </li>
        </ul>
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

    <div>
      <input type="text" v-model="storeAddress" placeholder="Store Location (for manual directions)" />
    </div>
    <button @click="getDirections" class="directions-button">Get Directions</button>
    <!-- Map display for both directions and picking -->
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
      homeAddressInput: '',
      homeLatitudeInput: '',
      homeLongitudeInput: '',
      currentHomeLocation: {
        address: null,
        latitude: null,
        longitude: null,
      },
      storeAddress: '', // Existing property
      showMap: false,    // Existing property
      mapPickModeEnabled: false, // For controlling map pick mode

      // Shops to visit
      shopInput: '',
      shopsToVisit: [], // Array of { id: Date.now(), name: 'Shop Name', address?, lat?, lon?, status? }

      // Shop Search & Disambiguation
      searchResults: [], // Stores results from /api/shops/find
      selectedShopForSearch: { id: null, name: '' }, // Shop from shopsToVisit being searched
      isLoadingShops: false, // Loading indicator for shop search

      // Optimized Route
      optimizedRouteData: null, // Stores response from /api/route/optimize
      isCalculatingRoute: false, // Loading indicator for route calculation
      selectedTravelMode: 'driving', // 'driving' or 'public_transit'
      homeCityName: '', // Placeholder for city name/code for transit.

      // Schedule Display
      defaultStartTime: '09:00:00', // e.g., 9 AM
      displayableSchedule: null, // Array of schedule items
    };
  },
  computed: {
    pickHomeButtonText() {
      return this.mapPickModeEnabled ? 'Cancel Picking on Map' : 'Pick Home on Map';
    },
    canCalculateRoute() {
      // Check if home location is set and there's at least one confirmed shop
      const homeSet = this.currentHomeLocation && this.currentHomeLocation.latitude && this.currentHomeLocation.longitude;
      const confirmedShopsExist = this.shopsToVisit.some(shop => shop.status === 'confirmed');
      return homeSet && confirmedShopsExist;
    }
  },
  methods: {
    async fetchHomeLocation() {
      try {
        const response = await axios.get('/api/user/home'); // Assumes cookie-based auth
        this.currentHomeLocation = response.data;
        // Pre-fill input fields if needed, or keep them separate
        this.homeAddressInput = response.data.home_address || '';
        this.homeLatitudeInput = response.data.home_latitude || '';
        this.homeLongitudeInput = response.data.home_longitude || '';
      } catch (error) {
        console.error('Error fetching home location:', error);
        // Handle error (e.g., show a message to the user)
        if (error.response && error.response.status === 401) {
          // Unauthorized, perhaps redirect to login or show a message
          alert('Session expired or not authenticated. Please login again.');
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
        // Filter out null latitude/longitude if empty strings before sending
        if (this.homeLatitudeInput === '') payload.latitude = null;
        if (this.homeLongitudeInput === '') payload.longitude = null;


        const response = await axios.post('/api/user/home', payload); // Assumes cookie-based auth
        this.currentHomeLocation = { // Update current home location display
            address: payload.address,
            latitude: payload.latitude,
            longitude: payload.longitude
        };
        alert(response.data.message || 'Home location updated successfully!');
        this.fetchHomeLocation(); // Re-fetch to confirm and get any backend-processed values
      } catch (error) {
        console.error('Error saving home location:', error);
        alert('Failed to save home location. ' + (error.response?.data?.message || ''));
      }
    },
    pickHomeOnMap() {
      if (this.mapPickModeEnabled) {
        // If already in pick mode, cancel it
        this.mapPickModeEnabled = false;
        // Optionally, hide the map if it was only shown for picking
        // For now, let's assume the map might be used for other things too (like getDirections)
        // so we don't automatically hide it unless specifically designed.
      } else {
        // Enter pick mode
        this.mapPickModeEnabled = true;
        this.showMap = true; // Ensure map is visible for picking
        alert('Map picking mode activated. Click on the map to select your home location.');
      }
    },
    handleLocationPicked(locationData) {
      this.homeAddressInput = locationData.address;
      this.homeLatitudeInput = locationData.latitude.toString();
      this.homeLongitudeInput = locationData.longitude.toString();
      this.mapPickModeEnabled = false; // Deactivate pick mode
      alert(`Location picked: ${locationData.address}. Review and click "Set Home Location" to save.`);
      // Optionally, you could scroll to the form or highlight the save button.
    },
    getDirections() { // Existing method
      // Note: The original homeAddress model is now homeAddressInput or part of currentHomeLocation
      console.log('Home Address for directions:', this.currentHomeLocation.address || this.homeAddressInput);
      console.log('Store Address:', this.storeAddress);
      this.showMap = true; // Ensure map is visible for directions
      this.mapPickModeEnabled = false; // Ensure pick mode is off if directions are requested
    },
    logoutUser() { // Existing method
      localStorage.removeItem('userToken');
      alert('You have been logged out.');
      this.$router.push('/login');
    },
    // Methods for Shops to Visit
    addShop() {
      if (this.shopInput.trim() !== '') {
        this.shopsToVisit.push({
          id: Date.now(), // Simple unique ID
          name: this.shopInput.trim(),
          // address: null, // Future enhancement
          // latitude: null, // Future enhancement
          // longitude: null, // Future enhancement
          // status: 'pending' // Future enhancement (e.g., pending, found, not_found)
        });
        this.shopInput = ''; // Clear input
      } else {
        alert('Please enter a shop name.');
      }
    },
    removeShop(shopId) {
      this.shopsToVisit = this.shopsToVisit.filter(shop => shop.id !== shopId);
      // If the shop being removed was the one selected for search, clear search results
      if (this.selectedShopForSearch && this.selectedShopForSearch.id === shopId) {
        this.searchResults = [];
        this.selectedShopForSearch = { id: null, name: '' };
      }
    },
    async findShopOnMap(shop) {
      this.isLoadingShops = true;
      this.selectedShopForSearch = shop;
      this.searchResults = []; // Clear previous results

      const payload = {
        keywords: shop.name,
      };

      if (this.currentHomeLocation && this.currentHomeLocation.latitude && this.currentHomeLocation.longitude) {
        payload.latitude = this.currentHomeLocation.latitude;
        payload.longitude = this.currentHomeLocation.longitude;
        // payload.radius = 10000; // Optional: backend has a default
      }
      // Optionally, add city if available from user input or home location (requires parsing city from home_address or a separate field)
      // payload.city = this.currentHomeLocation.city; // Example

      try {
        const response = await axios.post('/api/shops/find', payload);
        if (response.data.shops && response.data.shops.length > 0) {
          this.searchResults = response.data.shops;
        } else {
          alert(`No shops found for "${shop.name}". You can try a different name or add details manually.`);
          this.searchResults = []; // Ensure it's empty
        }
      } catch (error) {
        console.error('Error searching for shops:', error);
        let errorMessage = `Error searching for shops for "${shop.name}".`;
        if (error.response && error.response.data && error.response.data.message) {
          errorMessage += ` ${error.response.data.message}`;
        }
        alert(errorMessage);
        this.searchResults = []; // Ensure it's empty on error
      } finally {
        this.isLoadingShops = false;
      }
    },
    confirmShopSelection(selectedCandidate) {
      const shopIndex = this.shopsToVisit.findIndex(s => s.id === this.selectedShopForSearch.id);
      if (shopIndex !== -1) {
        // Create a new object for reactivity if shopsToVisit items are complex
        // or directly update if simple and Vue detects changes.
        // For safety and reactivity, creating a new object or using Vue.set for new properties is good.
        const updatedShop = {
          ...this.shopsToVisit[shopIndex], // Keep original id and any other properties
          name: selectedCandidate.name,    // Amap might return a more formal name
          address: selectedCandidate.address,
          latitude: selectedCandidate.latitude,
          longitude: selectedCandidate.longitude,
          status: 'confirmed',
          amap_id: selectedCandidate.id, // Store Amap POI ID if needed
          stayDurationMinutes: 0 // Initialize stay duration
        };
        this.shopsToVisit.splice(shopIndex, 1, updatedShop); // Replace item reactively

        alert(`Shop "${updatedShop.name}" confirmed with address: ${updatedShop.address}.`);
      } else {
        alert("Error: Could not find the original shop in your list to update.");
      }
      // Clear search state
      this.searchResults = [];
      this.selectedShopForSearch = { id: null, name: '' };
    },
    async calculateOptimizedRoute() {
      if (!this.canCalculateRoute) {
        alert("Please set your home location and confirm at least one shop before calculating the route.");
        return;
      }

      this.isCalculatingRoute = true;
      this.optimizedRouteData = null; // Clear previous route data
      this.displayableSchedule = null; // Clear previous schedule
      if (this.$refs.mapDisplay) { // Clear previous route from map
         this.$refs.mapDisplay.clearMapElements();
      }


      const confirmedShops = this.shopsToVisit
        .filter(shop => shop.status === 'confirmed')
        .map(shop => {
          const shopPayload = {
            id: shop.id, // Keep original client-side ID for reference if needed
            name: shop.name,
            latitude: shop.latitude,
            longitude: shop.longitude,
            amap_id: shop.amap_id // Include Amap ID if available and useful for backend
          };
          // Add stay_duration in seconds if stayDurationMinutes is positive
          if (shop.stayDurationMinutes && shop.stayDurationMinutes > 0) {
            shopPayload.stay_duration = shop.stayDurationMinutes * 60;
          }
          return shopPayload;
        });

      if (confirmedShops.length === 0) {
          alert("No shops have been confirmed with a location yet. Please search and select shops first.");
          this.isCalculatingRoute = false;
          return;
      }

      const payload = {
        home_location: {
          latitude: this.currentHomeLocation.latitude,
          longitude: this.currentHomeLocation.longitude,
        },
        shops: confirmedShops,
        // mode: "driving" // Default in backend, can be added if mode selection is implemented
      };

      // Add mode and city if public transit
      payload.mode = this.selectedTravelMode;
      if (this.selectedTravelMode === 'public_transit') {
        if (!this.homeCityName.trim()) {
          alert("Please provide the city name for public transit calculations.");
          this.isCalculatingRoute = false;
          return;
        }
        payload.city = this.homeCityName.trim();
      }

      try {
        const response = await axios.post('/api/route/optimize', payload);
        this.optimizedRouteData = response.data;
        if (this.optimizedRouteData) {
          this.displayableSchedule = this.generateDisplaySchedule(this.optimizedRouteData);
          if (this.$refs.mapDisplay) {
            this.showMap = true; // Ensure map is visible
            this.$refs.mapDisplay.drawOptimizedRoute(this.optimizedRouteData);
          } else {
            console.warn("MapDisplay component not available via ref to draw route.");
          }
        } else {
            alert("Route calculation did not return any data, though the request was successful.");
            this.displayableSchedule = null; // Ensure schedule is cleared if route data is unexpectedly null
        }

      } catch (error) {
        console.error('Error calculating optimized route:', error);
        let errorMessage = "Error calculating optimized route.";
        if (error.response && error.response.data && error.response.data.message) {
          errorMessage += ` ${error.response.data.message}`;
        }
        alert(errorMessage);
        this.optimizedRouteData = null; // Clear data on error
        this.displayableSchedule = null; // Clear schedule on error
      } finally {
        this.isCalculatingRoute = false;
      }
    },
    generateDisplaySchedule(routeData) {
      if (!routeData || !routeData.optimized_order || !routeData.route_segments) {
        return [];
      }

      const displayScheduleItems = [];
      let scheduleTime = new Date();
      const [hours, minutes, seconds] = this.defaultStartTime.split(':').map(Number);
      scheduleTime.setHours(hours, minutes, seconds, 0);

      // First item is Home departure
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
        // const fromLocationName = segment.from_name; // Not directly used in item creation for this loop
        const toLocationName = segment.to_name;
        const toLocationId = segment.to_id; // This is the original client-side ID

        // Add travel time to current scheduleTime
        scheduleTime.setSeconds(scheduleTime.getSeconds() + travelDurationSeconds);

        displayScheduleItems.push({
          type: 'arrival',
          location: toLocationName,
          time: new Date(scheduleTime.getTime()),
          travel_duration_seconds: travelDurationSeconds
        });

        // Handle stay duration if it's a shop (not Home)
        // The last segment brings us back home, so toLocationName could be "Home"
        if (toLocationName !== "Home") {
          // The toLocation for segment `i` is `routeData.optimized_order[i+1]`
          const currentRoutePoint = routeData.optimized_order[i+1];
          const stayDurationSeconds = currentRoutePoint.stay_duration || 0; // Already in seconds from backend

          if (stayDurationSeconds > 0) {
            displayScheduleItems.push({
              type: 'stay',
              location: toLocationName, // or currentRoutePoint.name
              duration_seconds: stayDurationSeconds
            });

            // Add stay time to current scheduleTime
            scheduleTime.setSeconds(scheduleTime.getSeconds() + stayDurationSeconds);

            // Add departure from this shop
            displayScheduleItems.push({
              type: 'departure',
              location: toLocationName, // or currentRoutePoint.name
              time: new Date(scheduleTime.getTime())
            });
          } else { // No stay duration or stay_duration is 0
            // If no stay, departure is immediate (same time as arrival).
            displayScheduleItems.push({
              type: 'departure',
              location: toLocationName, // or currentRoutePoint.name
              time: new Date(scheduleTime.getTime()) // Same as arrival time
            });
          }
        }
      }
      return displayScheduleItems;
    },
    formatTime(dateObject) {
      if (!dateObject || !(dateObject instanceof Date)) return '';
      return dateObject.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    },
    formatDuration(totalSeconds) {
      if (totalSeconds === undefined || totalSeconds === null || totalSeconds < 0) return 'N/A';
      const minutes = Math.round(totalSeconds / 60);
      return `${minutes}`; // Template will add " min"
    }
  },
  mounted() {
    this.fetchHomeLocation();
    // Original mounted content:
    // if (!localStorage.getItem('userToken')) {
    //   this.$router.push('/login');
    // }
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
  max-height: 300px; /* Limit height and make scrollable if too many results */
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
.search-result-item div { /* Container for name and address */
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
  margin-bottom: 10px; /* Smaller margin for tighter layout */
}
.add-shop-form label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
}
.add-shop-form input[type="text"] {
  /* Using global style, but can be overridden */
  margin-bottom: 10px; /* Ensure space before button if it wraps */
}
/* AddShop button is btn-primary, already styled */

.shops-list {
  list-style: none;
  padding: 0;
  margin-top: 20px;
}

.shop-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start; /* Align items to the top */
  padding: 10px;
  border: 1px solid #eee;
  border-radius: 4px;
  margin-bottom: 8px;
  background-color: #fdfdfd;
}

.shop-info {
  flex-grow: 1;
  display: flex;
  flex-direction: column; /* Stack shop name, address, and stay duration input vertically */
}
.shop-name {
  font-weight: bold;
  margin-bottom: 4px;
}
.shop-address-confirmed {
  font-size: 0.9em;
  color: #555;
  margin-bottom: 5px; /* Space before stay duration input */
}
.shop-stay-duration {
  display: flex;
  align-items: center;
  margin-top: 5px; /* Space above the stay duration input */
}
.stay-duration-label {
  font-size: 0.85em;
  margin-right: 5px;
  color: #333;
}
.stay-duration-input {
  width: 70px; /* Adjust width as needed */
  padding: 4px 6px;
  font-size: 0.9em;
  border: 1px solid #ccc;
  border-radius: 3px;
}


.shop-item-actions button {
  margin-left: 8px;
  align-self: flex-start; /* Align buttons to the top of their container if shop-info grows tall */
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
/* btn-danger is already styled */

.no-shops-message {
  color: #777;
  font-style: italic;
  text-align: center;
  margin-top: 15px;
}


.dashboard-container {
  max-width: 800px; /* Increased width for more content */
  margin: 30px auto; /* Reduced top margin */
  padding: 25px;
  text-align: left; /* Align text to left for forms */
  background-color: #f9f9f9;
  border: 1px solid #eee;
  border-radius: 8px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
}
h2 {
  text-align: center; /* Center main heading */
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
  width: calc(100% - 22px); /* Adjust width for padding and border */
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  box-sizing: border-box;
}

.btn-primary, .btn-secondary, .directions-button, .logout-button {
  padding: 10px 18px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
  margin-right: 10px; /* Spacing between buttons */
  margin-top: 10px; /* Spacing above buttons */
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

.directions-button {
  background-color: #28a745; /* Green */
  color: white;
}
.directions-button:hover {
  background-color: #1e7e34;
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

/* Ensure existing styles for other elements are not negatively impacted */
input[type="text"] { /* More general styling for text inputs */
  width: calc(100% - 22px);
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  box-sizing: border-box;
  margin-bottom: 10px; /* Add some space below inputs */
}

/* Styles for Schedule Display */
.schedule-display-section {
  background-color: #f0f8ff; /* AliceBlue, a very light blue */
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
  border-bottom: 1px dashed #cce0ff; /* Light blue dashed border */
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
  color: #0056b3; /* Dark blue for time */
  margin-right: 15px;
  min-width: 70px; /* Ensure alignment */
}
.event-description {
  color: #333;
}
.event-stay-description {
  padding-left: calc(70px + 15px); /* Align with descriptions of timed events */
  font-style: italic;
  color: #555;
}
.departure-event .event-description strong,
.arrival-event .event-description strong {
  color: #007bff; /* Primary blue for location names */
}

</style>
