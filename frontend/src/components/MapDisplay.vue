<template>
  <div id="map-container" style="width: 100%; height: 500px;"></div>
</template>

<script>
export default {
  name: 'MapDisplay',
  data() {
    return {
      map: null,
      currentMarker: null, // To keep track of the current marker
    };
  },
  mounted() {
    if (window.AMap) {
      this.initMap();
    } else {
      console.error("Gaode Maps API not loaded. Ensure the script tag is in index.html and the key is valid.");
      // You might want to add a retry mechanism or a callback if AMap loads later.
      // For now, we'll assume AMap is available globally when mounted.
      // If it's loaded asynchronously, this might need adjustment.
      // A common pattern is to have the AMap script load call a global init function.
    }
  },
  methods: {
    initMap() {
      // Initialize map
      this.map = new AMap.Map('map-container', {
        zoom: 11,
        center: [116.397428, 39.90923], // Default to Beijing
        resizeEnable: true,
      });

      // Add controls
      this.map.addControl(new AMap.ToolBar());
      this.map.addControl(new AMap.Scale());

      // You can emit an event if needed, to let parent know map is ready
      // this.$emit('map-ready', this.map);
    },
    setCenterAndMarker(longitude, latitude, address) {
      if (!this.map) {
        console.error("Map not initialized yet.");
        return;
      }

      // Clear existing marker
      if (this.currentMarker) {
        this.map.remove(this.currentMarker);
        this.currentMarker = null;
      }

      const newCenter = new AMap.LngLat(longitude, latitude);
      this.map.setCenter(newCenter);

      this.currentMarker = new AMap.Marker({
        position: newCenter,
        title: address,
        // You can customize the marker further, e.g., icon, label
      });
      this.map.add(this.currentMarker);

      // Optionally, open an info window
      // const infoWindow = new AMap.InfoWindow({
      //   content: address || 'Selected Location',
      //   offset: new AMap.Pixel(0, -30)
      // });
      // infoWindow.open(this.map, this.currentMarker.getPosition());
    }
  },
  beforeUnmount() {
    // Destroy the map instance when the component is unmounted
    if (this.map) {
      this.map.destroy();
      this.map = null;
    }
  }
};
</script>

<style scoped>
#map-container {
  border: 1px solid #ccc;
  border-radius: 4px;
}
</style>
