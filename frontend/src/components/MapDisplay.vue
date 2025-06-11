<template>
  <div id="map-container" style="width: 100%; height: 500px;"></div>
</template>

<script>
export default {
  name: 'MapDisplay',
  props: {
    isPickModeActive: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      map: null,
      currentMarker: null, // To keep track of the current marker
      driving: null, // To store the AMap.Driving instance
      geocoder: null, // To store AMap.Geocoder instance
      mapClickListener: null, // To store the map click listener function
      currentRoutePolylines: [], // Stores AMap.Polyline objects for the optimized route
      currentRouteMarkers: [],   // Stores AMap.Marker objects for the optimized route
    };
  },
  watch: {
    isPickModeActive(newVal) {
      if (newVal) {
        this.enableMapPicking();
      } else {
        this.disableMapPicking();
      }
    }
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

      // Initialize Geocoder
      AMap.plugin('AMap.Geocoder', () => {
        this.geocoder = new AMap.Geocoder({
          // city: "全国" // default, or specify city for accuracy
        });
      });
    },
    enableMapPicking() {
      if (!this.map) return;
      // Remove previous listener if any to avoid duplicates
      if (this.mapClickListener) {
        this.map.off('click', this.mapClickListener);
      }
      this.mapClickListener = (e) => {
        const lngLat = e.lnglat;
        if (this.geocoder) {
          this.geocoder.getAddress(lngLat, (status, result) => {
            if (status === 'complete' && result.info === 'OK') {
              const address = result.regeocode.formattedAddress;
              this.$emit('location-picked', {
                address: address,
                latitude: lngLat.getLat(),
                longitude: lngLat.getLng(),
              });
              this.setCenterAndMarker(lngLat.getLng(), lngLat.getLat(), address); // Show marker at picked location
            } else {
              console.error('Reverse geocoding failed:', result);
              // Emit with coordinates only if geocoding fails? Or show error?
              this.$emit('location-picked', { // Emit with null address if geocoding fails
                address: 'N/A (Geocoding failed)',
                latitude: lngLat.getLat(),
                longitude: lngLat.getLng(),
              });
              this.setCenterAndMarker(lngLat.getLng(), lngLat.getLat(), 'Picked Location (Geocoding failed)');
            }
          });
        } else {
          // Geocoder not ready, emit with coordinates only
           this.$emit('location-picked', {
            address: 'N/A (Geocoder not ready)',
            latitude: lngLat.getLat(),
            longitude: lngLat.getLng(),
          });
          this.setCenterAndMarker(lngLat.getLng(), lngLat.getLat(), 'Picked Location (Geocoder not ready)');
          console.warn("Geocoder not initialized yet. Emitting coordinates only.");
        }
      };
      this.map.on('click', this.mapClickListener);
      this.map.getContainer().style.cursor = 'crosshair'; // Change cursor
      console.log('Map picking enabled.');
    },
    disableMapPicking() {
      if (!this.map || !this.mapClickListener) return;
      this.map.off('click', this.mapClickListener);
      this.map.getContainer().style.cursor = ''; // Reset cursor
      this.mapClickListener = null; // Clear the stored listener
      console.log('Map picking disabled.');
    },
    clearMapElements() { // Renamed from clearPreviousRoute and enhanced
      if (this.driving) {
        this.driving.clear();
      }
      if (this.currentMarker) {
        this.map.remove(this.currentMarker);
        this.currentMarker = null;
      }
      if (this.currentRoutePolylines && this.currentRoutePolylines.length > 0) {
        this.map.remove(this.currentRoutePolylines);
        this.currentRoutePolylines = [];
      }
      if (this.currentRouteMarkers && this.currentRouteMarkers.length > 0) {
        this.map.remove(this.currentRouteMarkers);
        this.currentRouteMarkers = [];
      }
      // console.log('Cleared all map elements (driving route, markers, optimized route polylines)');
    },
    drawOptimizedRoute(routeData) {
      if (!this.map || !routeData) {
        console.error("Map not initialized or no route data provided.");
        return;
      }
      this.clearMapElements(); // Clear previous routes, markers etc.

      // Draw polylines for each segment
      routeData.route_segments.forEach(segment => {
        if (segment.polyline) {
          // Assuming polyline is a string like "lng1,lat1;lng2,lat2;..."
          const path = segment.polyline.split(';').map(coordStr => {
            const parts = coordStr.split(',');
            return new AMap.LngLat(parseFloat(parts[0]), parseFloat(parts[1]));
          });

          if (path.length > 0) {
            const polyline = new AMap.Polyline({
              path: path,
              strokeColor: "#3366FF", // Default color
              strokeOpacity: 0.8,
              strokeWeight: 6,
              // borderWeight: 1, // Optional: Add a border to the polyline
              // strokeStyle: "solid", // "solid" or "dashed"
            });
            this.map.add(polyline);
            this.currentRoutePolylines.push(polyline);
          }
        }
      });

      // Add markers for each point in the optimized order
      routeData.optimized_order.forEach((point, index) => {
        const marker = new AMap.Marker({
          position: new AMap.LngLat(point.longitude, point.latitude),
          title: point.name,
          label: { // Display index number on marker
            content: (index + 1).toString(), // Start numbering from 1
            offset: new AMap.Pixel(0, 0), // Adjust as needed
            direction: 'center'
          },
          // You can customize markers further (e.g., different icon for home vs shops)
          // icon: point.id === 'home' ? 'path/to/home_icon.png' : 'path/to/shop_icon.png',
        });
        this.map.add(marker);
        this.currentRouteMarkers.push(marker);
      });

      // Adjust map view to fit all new polylines and markers
      if (this.currentRoutePolylines.length > 0 || this.currentRouteMarkers.length > 0) {
         // Create a new AMap.OverlayGroup with all polylines and markers to easily setFitView
        const overlayGroup = new AMap.OverlayGroup([...this.currentRoutePolylines, ...this.currentRouteMarkers]);
        this.map.setFitView(overlayGroup.getOverlays(), false, [60, 60, 60, 60], 18); // false for immediate, 60px padding, maxZoom 18
      }
    },
    displayRoute(originAddress, destinationAddress) {
      if (!this.map) {
        alert("Map is not initialized yet. Please wait.");
        console.error("Map not initialized yet.");
        return;
      }

      this.clearMapElements(); // Use the enhanced clearing function

      AMap.plugin('AMap.Driving', () => { // Load AMap.Driving plugin
        const geocoder = new AMap.Geocoder({
          // city: "全国" // default
        });

        let originLngLat, destinationLngLat;

        geocoder.getLocation(originAddress, (status, result) => {
          if (status === 'complete' && result.info === 'OK' && result.geocodes.length) {
            originLngLat = result.geocodes[0].location;
            checkAndProceed();
          } else {
            alert(`Geocoding failed for origin: ${originAddress}. ${result.info}`);
            console.error("Geocoding failed for origin:", originAddress, status, result);
          }
        });

        geocoder.getLocation(destinationAddress, (status, result) => {
          if (status === 'complete' && result.info === 'OK' && result.geocodes.length) {
            destinationLngLat = result.geocodes[0].location;
            checkAndProceed();
          } else {
            alert(`Geocoding failed for destination: ${destinationAddress}. ${result.info}`);
            console.error("Geocoding failed for destination:", destinationAddress, status, result);
          }
        });

        const checkAndProceed = () => {
          if (originLngLat && destinationLngLat) {
            if (!this.driving) {
              this.driving = new AMap.Driving({
                map: this.map,
                // panel: "panel" // Optional: Specify ID of a div to display text directions
                policy: AMap.DrivingPolicy.LEAST_TIME // Example policy
              });
            }

            this.driving.search(originLngLat, destinationLngLat, (status, result) => {
              if (status === 'complete' && result.info === 'OK') {
                // Route will be drawn on the map automatically by the plugin
                console.log("Route search successful:", result);
              } else {
                alert(`Failed to get directions. Status: ${status}, Info: ${result.info}`);
                console.error("Route search failed:", status, result);
              }
            });
          }
        };
      });
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
      this.disableMapPicking(); // Ensure listener is removed
      this.map.destroy();
      this.map = null;
    }
    if (this.driving) {
      this.driving.clear(); // Clear routes
      this.driving = null;
    }
    // Clear any drawn optimized routes as well
    this.clearMapElements();
    this.geocoder = null;
  }
};
</script>

<style scoped>
#map-container {
  border: 1px solid #ccc;
  border-radius: 4px;
}
</style>
