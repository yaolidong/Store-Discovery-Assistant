'便利蜂', '罗森', 'Lawson'
];

return chainBrands.some(brand => 
  shopName.toLowerCase().includes(brand.toLowerCase()) ||
  brand.toLowerCase().includes(shopName.toLowerCase())
);
},

// --- New Methods for Safe Map Interaction ---
onMapInited() {
  console.log('Dashboard: Map component is ready.');
  this.mapReady = true;
  // If home location data was loaded before map was ready, update map now.
  if (this.homeLocation) {
    this.updateHomeOnMap();
  }
},

async updateHomeOnMap() {
  if (!this.mapReady || !this.homeLocation) {
    console.log('updateHomeOnMap skipped: map not ready or no home location.');
    return;
  }
  console.log('Updating home location on map...');
  const mapDisplay = this.$refs.mapDisplayRef;
  if (mapDisplay) {
    try {
      await mapDisplay.setHomeLocation(
        this.homeLocation.longitude, 
        this.homeLocation.latitude, 
        this.homeAddress
      );
      const city = await mapDisplay.getCityFromCoords(this.homeLocation.longitude, this.homeLocation.latitude);
      if (city) {
        this.selectedCity = city;
        localStorage.setItem('selectedCity', city);
        console.log(`城市已根据坐标自动更新为: ${city}`);
      }
    } catch (error) {
      console.error("Error in updateHomeOnMap:", error);
      this.showNotification("在地图上更新家的位置时出错", "error");
    }
  }
},

// --- Refactored Methods ---
async loadHomeLocation() {
  const saved = localStorage.getItem('homeLocation');
  if (saved) {
    try {
      const data = JSON.parse(saved);
      this.homeAddress = data.address;
      this.homeLocation = data.location;
      console.log('已加载保存的家地址:', this.homeAddress);

      // If map is already ready, update it. Otherwise, onMapInited will handle it.
      if (this.mapReady) {
        this.updateHomeOnMap();
      }
    } catch (error) {
      console.error('加载家地址失败:', error);
      localStorage.removeItem('homeLocation');
    }
  }
},

selectAddressSuggestion(suggestion) {
  this.homeAddress = suggestion.address || suggestion.name;
  this.homeLocation = {
    longitude: suggestion.longitude,
    latitude: suggestion.latitude,
    address: suggestion.address || suggestion.name
  };
  this.showAddressSuggestions = false;
  this.addressSuggestions = [];
  this.saveHomeLocation();
  
  // Safely update map
  if (this.mapReady) {
    const mapDisplay = this.$refs.mapDisplayRef;
    if (mapDisplay && suggestion.latitude && suggestion.longitude) {
      mapDisplay.setHomeLocation(suggestion.longitude, suggestion.latitude, this.homeAddress);
    }
  }
},

selectShopSuggestion(suggestion) {
  // ... (logic for adding shop to list)

  // Safely add marker to map
  if (!suggestion.isChainStore && this.mapReady) {
    const mapDisplay = this.$refs.mapDisplayRef;
    if (mapDisplay && suggestion.latitude && suggestion.longitude) {
      mapDisplay.addShopMarker(privateShop);
    }
  }

  // ... (rest of the function)
}, 