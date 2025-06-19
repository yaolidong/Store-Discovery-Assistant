<template>
  <div id="map-container" style="width: 100%; height: 500px; border: 1px solid #ccc; border-radius: 8px;"></div>
  <div v-if="showRouteInfo && routeInfo" class="route-info">
    <div class="route-summary">
      <h3>路线摘要</h3>
      <p>总时间: {{ routeSummary.totalTime }}</p>
      <p>总距离: {{ routeSummary.totalDistance }}</p>
      <p>出行方式: {{ travelMode === 'TRANSIT' ? '公交' : travelMode === 'DRIVING' ? '驾车' : '步行' }}</p>
    </div>
    
    <div class="route-details">
      <h3>详细路线</h3>
      <div v-for="(segment, index) in routeInfo.segments" :key="index" class="route-segment">
        <div class="segment-header">
          <span class="segment-number">{{ index + 1 }}</span>
          <span class="segment-name">{{ segment.name }}</span>
        </div>
        <div class="segment-details">
          <p v-if="segment.duration">时间: {{ formatDuration(segment.duration) }}</p>
          <p v-if="segment.distance">距离: {{ formatDistance(segment.distance) }}</p>
          <p v-if="segment.instructions">{{ segment.instructions }}</p>
        </div>
      </div>
    </div>
  </div>
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
      currentRoutePolylines: [], // Stores objects like { id: segmentId, polyline: AMap.Polyline, originalSegment: segment }
      currentRouteMarkers: [],   // Stores AMap.Marker objects for the optimized route
      showRouteInfo: false,
      routeInfo: null,
      routeSummary: null,
      travelMode: 'DRIVING',
      highlightedPolylineRef: null, // Stores the currently highlighted AMap.Polyline instance
      defaultPolylineStyle: { strokeColor: "#3366FF", strokeOpacity: 0.8, strokeWeight: 6 },
      isInitialized: false
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
  async mounted() {
    await this.initializeMap();
  },
  methods: {
    async initializeMap() {
      if (window.AMap) {
        this.map = new AMap.Map('map-container', {
          zoom: 11,
          center: [116.397428, 39.90923],
          resizeEnable: true
        });
        
        // 加载工具栏和比例尺插件
        AMap.plugin(['AMap.ToolBar', 'AMap.Scale'], () => {
          this.map.addControl(new AMap.ToolBar());
          this.map.addControl(new AMap.Scale());
        });
        
        this.isInitialized = true;
        console.log("地图初始化成功");

        // Initialize Geocoder
        AMap.plugin('AMap.Geocoder', () => {
          this.geocoder = new AMap.Geocoder({
            // city: "全国" // default, or specify city for accuracy
          });
        });
      } else {
        console.error("高德地图API未加载");
      }
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
        // If polylines are stored as {id, polyline, ...}, iterate and remove polyline property
        this.currentRoutePolylines.forEach(pEntry => this.map.remove(pEntry.polyline));
        this.currentRoutePolylines = [];
      }
      if (this.currentRouteMarkers && this.currentRouteMarkers.length > 0) {
        this.map.remove(this.currentRouteMarkers);
        this.currentRouteMarkers = [];
      }
      if (this.highlightedPolylineRef) { // Ensure any lingering highlight reference is cleared
        // Its style would have been reset or it was removed with currentRoutePolylines
        this.highlightedPolylineRef = null;
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
              strokeWeight: this.defaultPolylineStyle.strokeWeight,
              // borderWeight: 1, // Optional: Add a border to the polyline
              // strokeStyle: "solid", // "solid" or "dashed"
            });
            this.map.add(polyline);
            // Store with an ID and the polyline instance
            const segmentId = segment.from_id + '_' + segment.to_id; // Create a unique ID for the segment
            this.currentRoutePolylines.push({
              id: segmentId,
              polyline: polyline,
              originalSegment: segment // Store original segment for reference if needed
            });
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
        const allOverlaysForFitView = this.currentRoutePolylines.map(pEntry => pEntry.polyline).concat(this.currentRouteMarkers);
        if (allOverlaysForFitView.length > 0) {
          this.map.setFitView(allOverlaysForFitView, false, [60, 60, 60, 60], 18); // false for immediate, 60px padding, maxZoom 18
        }
      }
    },
    highlightSegment(segmentToHighlight, stepIndex) { // stepIndex is currently unused but available
      // Reset previously highlighted polyline (if any)
      if (this.highlightedPolylineRef) {
        this.highlightedPolylineRef.setOptions(this.defaultPolylineStyle);
        this.highlightedPolylineRef = null;
      }

      // Find and highlight the new segment
      // The ID for the segment was created as from_id + '_' + to_id in drawOptimizedRoute
      const segmentIdToMatch = segmentToHighlight.from_id + '_' + segmentToHighlight.to_id;
      const polylineEntry = this.currentRoutePolylines.find(p => p.id === segmentIdToMatch);

      if (polylineEntry && polylineEntry.polyline) {
        polylineEntry.polyline.setOptions({
          strokeColor: '#FF0000', // Highlight color (e.g., red)
          strokeOpacity: 1,
          strokeWeight: 8, // Thicker
        });
        this.highlightedPolylineRef = polylineEntry.polyline;
        // Optionally zoom/pan to the highlighted segment
        // This might be too aggressive if user is just clicking through steps quickly
        // this.map.setFitView([polylineEntry.polyline], false, [100,100,100,100], 16);
        console.log(`Highlighted segment: ${segmentIdToMatch}, step: ${stepIndex}`);
      } else {
        console.warn(`Polyline for segment ${segmentIdToMatch} not found to highlight.`);
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
    },
    async planDrivingRoute(waypoints) {
      return new Promise((resolve, reject) => {
        if (!this.map) {
          reject(new Error('地图未初始化'));
          return;
        }

        AMap.plugin('AMap.Driving', () => {
          const driving = new AMap.Driving({
            map: this.map,
            policy: AMap.DrivingPolicy.LEAST_TIME
          });

          const start = waypoints[0].location;
          const end = waypoints[waypoints.length - 1].location;
          const waypointsList = waypoints.slice(1, -1).map(wp => wp.location);

          driving.search(start, end, {
            waypoints: waypointsList
          }, (status, result) => {
            if (status === 'complete' && result.info === 'OK') {
              const route = result.routes[0];
              const segments = route.steps.map((step, index) => ({
                name: waypoints[index]?.name || `路段 ${index + 1}`,
                duration: step.time,
                distance: step.distance,
                instructions: step.instruction
              }));

              this.routeInfo = {
                segments,
                totalDistance: route.distance,
                totalTime: route.time
              };

              this.routeSummary = {
                totalTime: this.formatDuration(route.time),
                totalDistance: this.formatDistance(route.distance),
                mode: 'DRIVING'
              };

              this.showRouteInfo = true;
              resolve(this.routeInfo);
            } else {
              reject(new Error(result?.info || '路线规划失败'));
            }
          });
        });
      });
    },
    async planTransitRoute(waypoints) {
      return new Promise((resolve, reject) => {
        if (!this.map) {
          reject(new Error('地图未初始化'));
          return;
        }

        AMap.plugin('AMap.Transit', () => {
          const transit = new AMap.Transit({
            map: this.map,
            policy: AMap.TransitPolicy.LEAST_TIME
          });

          const start = waypoints[0].location;
          const end = waypoints[waypoints.length - 1].location;
          const waypointsList = waypoints.slice(1, -1).map(wp => wp.location);

          transit.search(start, end, {
            waypoints: waypointsList
          }, (status, result) => {
            if (status === 'complete' && result.info === 'OK') {
              const route = result.routes[0];
              const segments = route.transits.map((transit, index) => ({
                name: waypoints[index]?.name || `路段 ${index + 1}`,
                duration: transit.time,
                distance: transit.distance,
                instructions: transit.instructions
              }));

              this.routeInfo = {
                segments,
                totalDistance: route.distance,
                totalTime: route.time
              };

              this.routeSummary = {
                totalTime: this.formatDuration(route.time),
                totalDistance: this.formatDistance(route.distance),
                mode: 'TRANSIT'
              };

              this.showRouteInfo = true;
              resolve(this.routeInfo);
            } else {
              reject(new Error(result?.info || '路线规划失败'));
            }
          });
        });
      });
    },
    async planWalkingRoute(waypoints) {
      return new Promise((resolve, reject) => {
        if (!this.map) {
          reject(new Error('地图未初始化'));
          return;
        }

        AMap.plugin('AMap.Walking', () => {
          const walking = new AMap.Walking({
            map: this.map,
            policy: AMap.WalkingPolicy.LEAST_TIME
          });

          const start = waypoints[0].location;
          const end = waypoints[waypoints.length - 1].location;
          const waypointsList = waypoints.slice(1, -1).map(wp => wp.location);

          walking.search(start, end, {
            waypoints: waypointsList
          }, (status, result) => {
            if (status === 'complete' && result.info === 'OK') {
              const route = result.routes[0];
              const segments = route.steps.map((step, index) => ({
                name: waypoints[index]?.name || `路段 ${index + 1}`,
                duration: step.time,
                distance: step.distance,
                instructions: step.instruction
              }));

              this.routeInfo = {
                segments,
                totalDistance: route.distance,
                totalTime: route.time
              };

              this.routeSummary = {
                totalTime: this.formatDuration(route.time),
                totalDistance: this.formatDistance(route.distance),
                mode: 'WALKING'
              };

              this.showRouteInfo = true;
              resolve(this.routeInfo);
            } else {
              reject(new Error(result?.info || '路线规划失败'));
            }
          });
        });
      });
    },
    formatDuration(seconds) {
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      if (hours > 0) {
        return `${hours}小时${minutes}分钟`;
      }
      return `${minutes}分钟`;
    },
    formatDistance(meters) {
      if (meters >= 1000) {
        return `${(meters / 1000).toFixed(1)}公里`;
      }
      return `${meters}米`;
    },
    
    // 添加缺失的方法
    clearAllMarkersAndRoutes() {
      this.clearMapElements();
    },
    
    setHomeLocation(longitude, latitude, address) {
      console.log('=== 设置家的位置标记 ===');
      console.log('接收到的参数:');
      console.log('  经度 (longitude):', longitude, typeof longitude);
      console.log('  纬度 (latitude):', latitude, typeof latitude);
      console.log('  地址:', address);
      console.log('地图对象:', this.map);
      console.log('地图是否已初始化:', !!this.map);
      
      if (!this.map) {
        console.error('地图未初始化');
        return;
      }
      
      // 验证坐标数值
      const lng = parseFloat(longitude);
      const lat = parseFloat(latitude);
      
      if (isNaN(lng) || isNaN(lat)) {
        console.error('坐标数值无效:', { longitude, latitude, lng, lat });
        return;
      }
      
      console.log('最终使用的坐标:', { lng, lat });
      console.log('创建AMap.LngLat对象...');
      
      const center = new AMap.LngLat(lng, lat);
      console.log('AMap.LngLat对象:', center);
      console.log('center.getLng():', center.getLng());
      console.log('center.getLat():', center.getLat());
      
      console.log('设置地图中心...');
      this.map.setCenter(center);
      this.map.setZoom(16);
      
      // 强制等待地图渲染后再次确认中心位置
      setTimeout(() => {
        console.log('延迟确认地图中心...');
        this.map.setCenter(center);  // 再次设置确保生效
        console.log('最终地图中心:', this.map.getCenter());
        console.log('目标中心坐标:', center);
      }, 100);
      
      console.log('当前地图中心:', this.map.getCenter());
      console.log('当前地图缩放级别:', this.map.getZoom());
      
      // 清除之前的标记
      if (this.currentMarker) {
        console.log('移除之前的标记');
        this.map.remove(this.currentMarker);
        this.currentMarker = null;
      }
      
      try {
        // 创建家的位置标记，使用简单的默认图标和红色样式
        this.currentMarker = new AMap.Marker({
          position: center,
          title: `家: ${address}`,
          // 使用高德地图的默认图标，但设置为红色
          icon: '//a.amap.com/jsapi_demos/static/demo-center/icons/poi-marker-red.png',
          // 移除offset，让标记准确显示在坐标位置
          anchor: 'center'  // 设置为中心对齐，这样标记的中心就在坐标点上
        });
        
        console.log('标记位置坐标:', this.currentMarker.getPosition());
        console.log('地图中心坐标:', this.map.getCenter());
        
        console.log('标记对象创建成功:', this.currentMarker);
        
        // 添加标记到地图
        this.map.add(this.currentMarker);
        console.log('标记已添加到地图');
        
        // 创建信息窗口
        const infoWindow = new AMap.InfoWindow({
          content: `<div style="padding: 10px; min-width: 200px;">
            <h4 style="margin: 0 0 8px 0; color: #333; font-size: 16px;">🏠 家的位置</h4>
            <p style="margin: 0; color: #666; font-size: 14px; line-height: 1.4;">${address}</p>
          </div>`,
          offset: new AMap.Pixel(0, -35)
        });
        
        // 点击标记时显示信息窗口
        this.currentMarker.on('click', () => {
          console.log('标记被点击，显示信息窗口');
          infoWindow.open(this.map, this.currentMarker.getPosition());
        });
        
        // 验证标记和地图中心位置是否一致
        setTimeout(() => {
          if (this.currentMarker) {
            const markerPos = this.currentMarker.getPosition();
            const mapCenter = this.map.getCenter();
            
            console.log('=== 位置验证 ===');
            console.log('标记坐标:', markerPos.getLng(), markerPos.getLat());
            console.log('地图中心:', mapCenter.getLng(), mapCenter.getLat());
            
            // 计算偏差
            const lngDiff = Math.abs(markerPos.getLng() - mapCenter.getLng());
            const latDiff = Math.abs(markerPos.getLat() - mapCenter.getLat());
            
            console.log('坐标偏差:', { lngDiff, latDiff });
            
                         if (lngDiff > 0.001 || latDiff > 0.001) {
               console.warn('标记位置与地图中心存在明显偏差!');
               // 重新对齐地图中心到标记位置
               this.map.setCenter(markerPos);
               console.log('已重新对齐地图中心到标记位置');
               
               // 再次验证对齐
               setTimeout(() => {
                 const newCenter = this.map.getCenter();
                 console.log('重新对齐后的地图中心:', newCenter.getLng(), newCenter.getLat());
               }, 200);
             } else {
               console.log('✅ 标记位置与地图中心已对齐');
             }
             
             // 最终强制对齐到标记位置（无论如何都执行）
             this.map.setCenter(markerPos);
             console.log('🎯 执行最终强制对齐到标记位置');
            
            infoWindow.open(this.map, this.currentMarker.getPosition());
            console.log('自动显示信息窗口');
          }
        }, 500);
        
        console.log('家的位置标记设置完成');
        
        // 创建持续监控和对齐机制
        let alignmentAttempts = 0;
        const ensureAlignment = () => {
          if (alignmentAttempts >= 5) return; // 最多尝试5次
          
          alignmentAttempts++;
          if (this.currentMarker && this.map) {
            const markerPos = this.currentMarker.getPosition();
            this.map.setCenter(markerPos);
            console.log(`🔄 对齐尝试 ${alignmentAttempts}: 重新设置地图中心到标记位置`);
            
            setTimeout(ensureAlignment, 300); // 每300ms检查一次
          }
        };
        
        // 开始对齐监控
        setTimeout(ensureAlignment, 200);
        
      } catch (error) {
        console.error('创建标记时出错:', error);
        
        // 备用方案：使用更简单的标记
        this.currentMarker = new AMap.Marker({
          position: center,
          title: `家: ${address}`
        });
        
        this.map.add(this.currentMarker);
        console.log('使用备用标记方案');
      }
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
</style>
