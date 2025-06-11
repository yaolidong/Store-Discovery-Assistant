// For this basic setup, we assume .vue files are handled by a build process or an in-browser component loader.
// If running directly in a browser without a build step, .vue files won't be processed as expected.
// We'll proceed by defining components in their respective .vue files and importing them here.

// --- Router Setup ---
// (Component definitions will be imported from .vue files)
// We need to define placeholder components here or ensure .vue files can be loaded.
// For simplicity in this step, we'll assume .vue files can be loaded as modules.
// This usually requires a build setup (like Vite or Vue CLI) or a special script that can handle .vue files in the browser.

// Since we don't have a build system, true .vue SFCs are tricky.
// We'll use Vue's object-based component definition for now within main.js
// and later structure them into .vue files if a build step is introduced.

// Let's adjust the plan slightly for a no-build-step environment using global Vue.
// We will define components as objects and the router directly in this file.
// The .vue files created later will serve as templates for these objects.

const { createApp } = Vue;
const { createRouter, createWebHashHistory } = VueRouter;

// Placeholder for components that will be defined in .vue files.
// In a no-build setup, you might load these as JS objects or use vue3-sfc-loader.
// For now, we will define them inline and then create the .vue files.

const Login = {
  template: `
    <div>
      <h2>Login</h2>
      <form @submit.prevent="loginUser">
        <div>
          <label for="username">Username:</label>
          <input type="text" id="username" v.model="username" required>
        </div>
        <div>
          <label for="password">Password:</label>
          <input type="password" id="password" v.model="password" required>
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
      errorMessage: ''
    };
  },
  methods: {
    async loginUser() {
      this.errorMessage = '';
      try {
        const response = await axios.post('http://localhost:5000/login', {
          username: this.username,
          password: this.password
        });
        // Store token properly if backend sends one, e.g., response.data.token
        localStorage.setItem('userToken', response.data.token || 'fakeToken');
        alert('Login successful!');
        this.$router.push('/');
      } catch (error) {
        this.errorMessage = (error.response && error.response.data && error.response.data.message) || 'Login failed. Please try again.';
        console.error('Login error:', error);
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
          <input type="text" id="username" v.model="username" required>
        </div>
        <div>
          <label for="password">Password:</label>
          <input type="password" id="password" v.model="password" required>
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
        const response = await axios.post('http://localhost:5000/register', {
          username: this.username,
          password: this.password
        });
        this.successMessage = response.data.message;
        alert('Registration successful! Please login.');
        this.$router.push('/login');
      } catch (error) {
        this.errorMessage = (error.response && error.response.data && error.response.data.message) || 'Registration failed. Please try again.';
        console.error('Registration error:', error);
      }
    }
  }
};

const MapDisplayComp = {
  name: 'MapDisplay',
  template: `<div id="map-container-js" style="width: 100%; height: 500px; border: 1px solid #ccc; border-radius: 4px;"></div>`,
  data() {
    return {
      map: null,
      currentMarker: null,
      driving: null, // For route display
    };
  },
  mounted() {
    if (window.AMap) {
      this.initMap();
    } else {
      console.error("Gaode Maps API not loaded for MapDisplayComp. Ensure the script tag is in index.html and the key is valid.");
      // Poll for AMap availability
      let attempts = 0;
      const interval = setInterval(() => {
        attempts++;
        if (window.AMap) {
          this.initMap();
          clearInterval(interval);
        } else if (attempts > 10) { // Try for a few seconds
          clearInterval(interval);
          console.error("Gaode Maps API failed to load after multiple attempts.");
          alert("Error: Could not load map service. Please check your API key and internet connection.");
        }
      }, 500);
    }
  },
  methods: {
    initMap() {
      // Ensure container ID matches the template
      this.map = new AMap.Map('map-container-js', {
        zoom: 11,
        center: [116.397428, 39.90923], // Default to Beijing
        resizeEnable: true,
      });
      this.map.addControl(new AMap.ToolBar());
      this.map.addControl(new AMap.Scale());
      console.log("MapDisplayComp: Map initialized with container 'map-container-js'");
    },
    clearPreviousRoute() {
      if (this.driving) {
        this.driving.clear();
        console.log("MapDisplayComp: Previous route cleared.");
      }
      if (this.currentMarker) {
        this.map.remove(this.currentMarker);
        this.currentMarker = null;
        console.log("MapDisplayComp: Previous marker cleared.");
      }
    },
    displayRoute(originAddress, destinationAddress) {
      if (!this.map) {
        alert("MapDisplayComp: Map is not initialized yet. Please wait.");
        console.error("MapDisplayComp: Map not initialized when displayRoute called.");
        // Attempt to initialize map if it's not, could be due to timing
        if(window.AMap) {
          this.initMap();
          if (!this.map) {
            console.error("MapDisplayComp: Failed to initialize map on demand.");
            return;
          }
          alert("MapDisplayComp: Map was initialized now. Please try getting directions again.");
          return;
        }
        return;
      }

      console.log(`MapDisplayComp: displayRoute called with Origin: ${originAddress}, Destination: ${destinationAddress}`);
      this.clearPreviousRoute();

      // AMap.Geocoder and AMap.Driving should be available globally from index.html
      if (!AMap.Geocoder || !AMap.Driving) {
        alert("MapDisplayComp: Geocoder or Driving service not available. Check AMap loading in index.html.");
        console.error("MapDisplayComp: AMap.Geocoder or AMap.Driving not found.");
        return;
      }

      const geocoder = new AMap.Geocoder();
      let originLngLat, destinationLngLat;
      let geocodeCount = 0;
      const totalGeocodes = 2;

      const checkAndProceed = () => {
        geocodeCount++;
        if (geocodeCount === totalGeocodes) {
          if (originLngLat && destinationLngLat) {
            console.log("MapDisplayComp: Both addresses geocoded. Origin:", originLngLat, "Destination:", destinationLngLat);
            if (!this.driving) {
              this.driving = new AMap.Driving({
                map: this.map,
                policy: AMap.DrivingPolicy.LEAST_TIME // Example policy
                // panel: "panel_id_in_mapdisplaycomp_if_any" // Optional
              });
              console.log("MapDisplayComp: AMap.Driving initialized.");
            }

            this.driving.search(originLngLat, destinationLngLat, (status, result) => {
              if (status === 'complete' && result.info === 'OK') {
                console.log("MapDisplayComp: Route search successful.", result);
                // Route is drawn by the plugin.
              } else {
                alert(`MapDisplayComp: Failed to get directions. Status: ${status}, Info: ${result.info}`);
                console.error("MapDisplayComp: Route search failed:", status, result);
              }
            });
          } else {
            alert("MapDisplayComp: Could not determine coordinates for both locations. Please check addresses.");
            console.error("MapDisplayComp: One or both geocoding attempts failed to return LngLat.");
          }
        }
      };

      geocoder.getLocation(originAddress, (status, result) => {
        if (status === 'complete' && result.info === 'OK' && result.geocodes.length) {
          originLngLat = result.geocodes[0].location;
          console.log("MapDisplayComp: Geocoded origin:", originAddress, "to", originLngLat);
        } else {
          alert(`MapDisplayComp: Geocoding failed for origin: ${originAddress}. ${result.info}`);
          console.error("MapDisplayComp: Geocoding failed for origin:", originAddress, status, result);
        }
        checkAndProceed();
      });

      geocoder.getLocation(destinationAddress, (status, result) => {
        if (status === 'complete' && result.info === 'OK' && result.geocodes.length) {
          destinationLngLat = result.geocodes[0].location;
          console.log("MapDisplayComp: Geocoded destination:", destinationAddress, "to", destinationLngLat);
        } else {
          alert(`MapDisplayComp: Geocoding failed for destination: ${destinationAddress}. ${result.info}`);
          console.error("MapDisplayComp: Geocoding failed for destination:", destinationAddress, status, result);
        }
        checkAndProceed();
      });
    },
    setCenterAndMarker(longitude, latitude, address) {
      if (!this.map) {
        console.error("MapDisplayComp: Map not initialized when setCenterAndMarker called.");
         // Attempt to initialize map if it's not, could be due to timing
        if(window.AMap) {
          this.initMap();
          if (!this.map) {
            console.error("MapDisplayComp: Failed to initialize map on demand for setCenterAndMarker.");
            return;
          }
        } else {
          return;
        }
      }
      if (this.currentMarker) {
        this.map.remove(this.currentMarker);
      }
      const newCenter = new AMap.LngLat(longitude, latitude);
      this.map.setCenter(newCenter);
      this.currentMarker = new AMap.Marker({
        position: newCenter,
        title: address,
      });
      this.map.add(this.currentMarker);
      this.map.setZoom(15); // Zoom in on the marker
    }
  },
  beforeUnmount() {
    if (this.driving) {
      this.driving.clear();
      this.driving = null;
      console.log("MapDisplayComp: Driving instance cleared and destroyed.");
    }
    if (this.map) {
      this.map.destroy();
      this.map = null;
      console.log("MapDisplayComp: Map instance destroyed.");
    }
  }
};

const Dashboard = {
  components: {
    'map-display': MapDisplayComp // Register MapDisplayComp locally
  },
  template: `
    <div>
      <h2>Welcome to your Dashboard, {{ username }}!</h2>

      <div class="directions-controls" style="margin-bottom: 15px;">
        <h3>Get Directions</h3>
        <div>
          <label for="homeAddress">Home Location:</label>
          <input type="text" id="homeAddress" v-model="homeAddress" placeholder="Enter home address">
        </div>
        <div>
          <label for="storeAddress">Store Location:</label>
          <input type="text" id="storeAddress" v-model="storeAddress" placeholder="Enter store address">
        </div>
        <button @click="getDirections" style="margin-top: 10px;">Get Directions</button>
      </div>

      <hr style="margin: 20px 0;">

      <div class="map-controls">
        <h3>Search Location</h3>
        <input type="text" v-model="searchQuery" placeholder="Enter a location to search">
        <button @click="searchLocation">Search and Center</button>
      </div>

      <map-display ref="mapDisplayRef" style="margin-top: 20px;"></map-display>

      <p style="margin-top: 20px;">This is where your trip planning features will be.</p>
      <button @click="logoutUser" class="logout-button">Logout</button>
    </div>
  `,
  data() {
    return {
      username: 'User', // Placeholder
      searchQuery: '',
      homeAddress: '',
      storeAddress: '',
    };
  },
  methods: {
    async logoutUser() {
      localStorage.removeItem('userToken');
      alert('Logged out successfully!');
      this.$router.push('/login');
    },
    fetchUsername() {
      // Placeholder
    },
    getDirections() {
      if (!this.homeAddress.trim() || !this.storeAddress.trim()) {
        alert("Please enter both Home and Store locations.");
        return;
      }
      const mapDisplay = this.$refs.mapDisplayRef;
      if (mapDisplay && typeof mapDisplay.displayRoute === 'function') {
        console.log("Dashboard: Calling displayRoute on MapDisplayComp with:", this.homeAddress, this.storeAddress);
        mapDisplay.displayRoute(this.homeAddress, this.storeAddress);
      } else {
        alert("Map display component is not available or does not support routing.");
        console.error("Dashboard: mapDisplayRef not found or displayRoute method missing.", mapDisplay);
      }
    },
    searchLocation() {
      if (!this.searchQuery.trim()) {
        alert("Please enter a location to search.");
        return;
      }
      // Geocoder and map readiness checks are now more robust within MapDisplayComp
      // and its setCenterAndMarker method.
      const mapDisplayComponent = this.$refs.mapDisplayRef;
      if (!mapDisplayComponent) {
          alert("Map component is not ready yet. Please wait a moment and try again.");
          console.error("Dashboard: mapDisplayRef not found for searchLocation.");
          return;
      }

      // We'll use a global Geocoder here for simplicity, as it's just for finding a point
      // The MapDisplayComp will handle its own geocoding for routes
      if (!window.AMap || !AMap.Geocoder) {
          alert("Map services or Geocoder not available for search. Please check API key and script loading.");
          console.error("Dashboard: AMap.Geocoder not available for searchLocation.");
          return;
      }
      const geocoder = new AMap.Geocoder();
      geocoder.getLocation(this.searchQuery, (status, result) => {
        if (status === 'complete' && result.info === 'OK' && result.geocodes && result.geocodes.length > 0) {
          const geocode = result.geocodes[0];
          const { lng, lat } = geocode.location;
          if (mapDisplayComponent) {
            mapDisplayComponent.setCenterAndMarker(lng, lat, geocode.formattedAddress);
          }
        } else {
          alert('Could not find location: ' + (result.info || 'Unknown error'));
          console.error("Geocoding error/no result:", status, result);
        }
      });
    }
  },
  mounted() {
    this.fetchUsername();
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

// Note: The .vue files (Login.vue, Register.vue, Dashboard.vue, App.vue)
// will be created next, mirroring the structure of these JavaScript component objects.
// To use those .vue files directly, a build system (like Vite or Vue CLI) or
// an in-browser SFC loader (like vue3-sfc-loader) would be needed.
// The current setup uses JS object components for a no-build environment.
// The API calls are placeholders and assume the backend is running and accessible at /api.
// Change /api/login and /api/register to the actual backend URL if different (e.g. http://localhost:5000/login)

// Add basic CSS file, create it if it doesn't exist
const style = document.createElement('style');
style.textContent = `
body { font-family: sans-serif; margin: 0; padding: 0; background-color: #f4f4f4; color: #333; }
#app { max-width: 800px; margin: 20px auto; padding: 20px; background-color: #fff; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
#nav { padding: 10px 0; border-bottom: 1px solid #eee; margin-bottom: 20px; text-align: center; }
#nav a { font-weight: bold; color: #2c3e50; text-decoration: none; margin: 0 10px; }
#nav a.router-link-exact-active { color: #42b983; }
h2 { color: #333; }
form div { margin-bottom: 10px; }
label { display: block; margin-bottom: 5px; }
input[type="text"], input[type="password"] { width: calc(100% - 22px); padding: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
button { background-color: #42b983; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; margin-left: 5px; }
button:hover { background-color: #36a476; }
button[type="submit"] { width: 100%; margin-left: 0; } /* Ensure submit buttons are full width */
.logout-button { background-color: #d9534f; margin-top:15px;}
.logout-button:hover { background-color: #c9302c; }
p { color: #666; }
.error-message { color: red; font-size: 0.9em; }
.success-message { color: green; font-size: 0.9em; }
.map-controls { margin-bottom: 15px; display: flex; align-items: center; }
.map-controls input[type="text"] { flex-grow: 1; padding: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
#map-container-js { /* Ensure this ID is unique if multiple maps were ever on one page */ }
`;
document.head.appendChild(style);
// Removed duplicate .success-message style and extra appendChild(style)
