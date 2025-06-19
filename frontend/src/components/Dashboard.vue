<template>
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
         
         <!-- 详细路线步骤省略，内容太长 -->
         <!-- ... 这里省略了大量的路线详情模板代码 ... -->
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
</template>

<script>
import MapDisplay from './MapDisplay.vue';
import Notification from './NotificationComp.vue';

export default {
  components: {
    MapDisplay,
    Notification
  },
  name: 'Dashboard',
  data() {
    return {
      // 城市和省份数据
      provinces: [],
      selectedProvince: '',
      selectedCity: '',
      availableCities: [],
      
      // 家的位置相关
      homeAddress: '',
      homeLocation: null,
      addressSuggestions: [],
      showAddressSuggestions: false,
      
      // 店铺相关
      shopInput: '',
      shopsToVisit: [],
      shopSuggestions: [],
      showShopSuggestions: false,
      stayDurations: {},
      defaultStayDuration: 30,
      
      // 路线规划相关
      departureTime: '09:00',
      travelMode: 'DRIVING',
      routeCombinations: [],
      selectedRouteId: null,
      routeInfo: null,
      showRouteInfo: false,
      routeSummary: null,
      isLoading: false,
      
      // 连锁店品牌列表
      chainStoreBrands: [
        '肯德基', 'KFC', '麦当劳', "McDonald's", '星巴克', 'Starbucks',
        '必胜客', 'Pizza Hut', '德克士', '华莱士', '正新鸡排',
        '蜜雪冰城', '喜茶', '奈雪的茶', '茶百道', '古茗',
        '瑞幸咖啡', 'Luckin Coffee', '7-Eleven', '全家', 'FamilyMart',
        '便利蜂', '罗森', 'Lawson', '好利来', '面包新语'
      ]
    }
  },
  computed: {
    canGetRoute() {
      return this.homeLocation && 
             this.shopsToVisit.length > 0 && 
             this.selectedCity && 
             !this.isLoading;
    },
    
    routeButtonText() {
      if (this.isLoading) return '正在规划路线...';
      if (!this.homeLocation) return '请先设置家的位置';
      if (this.shopsToVisit.length === 0) return '请先添加要探访的店铺';
      if (!this.selectedCity) return '请先选择城市';
      return '开始规划路线';
    },
    
    homeLocationStatus() {
      if (!this.homeLocation) {
        return {
          status: 'pending',
          message: '请设置家的位置',
          icon: '📍'
        };
      }
      return {
        status: 'completed',
        message: `已设置: ${this.homeAddress}`,
        icon: '✅'
      };
    },
    
    shopsStatus() {
      const chainStores = this.shopsToVisit.filter(shop => shop.type === 'chain');
      const privateStores = this.shopsToVisit.filter(shop => shop.type === 'private');
      
      if (this.shopsToVisit.length === 0) {
        return {
          status: 'pending',
          message: '请添加要探访的店铺',
          icon: '🛍️'
        };
      }
      
      let message = `已添加 ${this.shopsToVisit.length} 家店铺`;
      if (chainStores.length > 0) {
        message += ` (${chainStores.length} 家连锁店, ${privateStores.length} 家私人店铺)`;
      }
      
      return {
        status: 'completed',
        message: message,
        icon: '✅'
      };
    }
  },
  methods: {
    // 通知相关方法
    showNotification(message, type = 'info', title = '') {
      if (this.$refs.notification) {
        const methods = {
          'success': 'success',
          'error': 'error', 
          'warning': 'warning',
          'info': 'info'
        };
        const method = methods[type] || 'info';
        this.$refs.notification[method](message, title);
      }
    },

    // 登出方法
    async logoutUser() {
      try {
        const response = await fetch('/api/logout', {
          method: 'POST',
          credentials: 'include'
        });
        
        if (response.ok) {
          window.location.href = '/';
        }
      } catch (error) {
        console.error('登出失败:', error);
        this.showNotification('登出失败，请重试', 'error');
      }
    },

    // 省市数据加载
    loadProvinceCityData() {
      this.provinces = [
        // 直辖市
        {
          name: '北京市',
          cities: [{ name: '北京市', adcode: '110100' }]
        },
        {
          name: '上海市', 
          cities: [{ name: '上海市', adcode: '310100' }]
        },
        {
          name: '天津市',
          cities: [{ name: '天津市', adcode: '120100' }]
        },
        {
          name: '重庆市',
          cities: [{ name: '重庆市', adcode: '500100' }]
        },
        
        // 华北地区
        {
          name: '河北省',
          cities: [
            { name: '石家庄市', adcode: '130100' },
            { name: '唐山市', adcode: '130200' },
            { name: '秦皇岛市', adcode: '130300' },
            { name: '邯郸市', adcode: '130400' },
            { name: '邢台市', adcode: '130500' },
            { name: '保定市', adcode: '130600' },
            { name: '张家口市', adcode: '130700' },
            { name: '承德市', adcode: '130800' },
            { name: '沧州市', adcode: '130900' },
            { name: '廊坊市', adcode: '131000' },
            { name: '衡水市', adcode: '131100' }
          ]
        },
        {
          name: '山西省',
          cities: [
            { name: '太原市', adcode: '140100' },
            { name: '大同市', adcode: '140200' },
            { name: '阳泉市', adcode: '140300' },
            { name: '长治市', adcode: '140400' },
            { name: '晋城市', adcode: '140500' },
            { name: '朔州市', adcode: '140600' },
            { name: '晋中市', adcode: '140700' },
            { name: '运城市', adcode: '140800' },
            { name: '忻州市', adcode: '140900' },
            { name: '临汾市', adcode: '141000' },
            { name: '吕梁市', adcode: '141100' }
          ]
        },
        {
          name: '内蒙古自治区',
          cities: [
            { name: '呼和浩特市', adcode: '150100' },
            { name: '包头市', adcode: '150200' },
            { name: '乌海市', adcode: '150300' },
            { name: '赤峰市', adcode: '150400' },
            { name: '通辽市', adcode: '150500' },
            { name: '鄂尔多斯市', adcode: '150600' },
            { name: '呼伦贝尔市', adcode: '150700' },
            { name: '巴彦淖尔市', adcode: '150800' },
            { name: '乌兰察布市', adcode: '150900' },
            { name: '兴安盟', adcode: '152200' },
            { name: '锡林郭勒盟', adcode: '152500' },
            { name: '阿拉善盟', adcode: '152900' }
          ]
        },
        
        // 东北地区
        {
          name: '辽宁省',
          cities: [
            { name: '沈阳市', adcode: '210100' },
            { name: '大连市', adcode: '210200' },
            { name: '鞍山市', adcode: '210300' },
            { name: '抚顺市', adcode: '210400' },
            { name: '本溪市', adcode: '210500' },
            { name: '丹东市', adcode: '210600' },
            { name: '锦州市', adcode: '210700' },
            { name: '营口市', adcode: '210800' },
            { name: '阜新市', adcode: '210900' },
            { name: '辽阳市', adcode: '211000' },
            { name: '盘锦市', adcode: '211100' },
            { name: '铁岭市', adcode: '211200' },
            { name: '朝阳市', adcode: '211300' },
            { name: '葫芦岛市', adcode: '211400' }
          ]
        },
        {
          name: '吉林省',
          cities: [
            { name: '长春市', adcode: '220100' },
            { name: '吉林市', adcode: '220200' },
            { name: '四平市', adcode: '220300' },
            { name: '辽源市', adcode: '220400' },
            { name: '通化市', adcode: '220500' },
            { name: '白山市', adcode: '220600' },
            { name: '松原市', adcode: '220700' },
            { name: '白城市', adcode: '220800' },
            { name: '延边朝鲜族自治州', adcode: '222400' }
          ]
        },
        {
          name: '黑龙江省',
          cities: [
            { name: '哈尔滨市', adcode: '230100' },
            { name: '齐齐哈尔市', adcode: '230200' },
            { name: '鸡西市', adcode: '230300' },
            { name: '鹤岗市', adcode: '230400' },
            { name: '双鸭山市', adcode: '230500' },
            { name: '大庆市', adcode: '230600' },
            { name: '伊春市', adcode: '230700' },
            { name: '佳木斯市', adcode: '230800' },
            { name: '七台河市', adcode: '230900' },
            { name: '牡丹江市', adcode: '231000' },
            { name: '黑河市', adcode: '231100' },
            { name: '绥化市', adcode: '231200' },
            { name: '大兴安岭地区', adcode: '232700' }
          ]
        },
        
        // 华东地区
        {
          name: '江苏省',
          cities: [
            { name: '南京市', adcode: '320100' },
            { name: '无锡市', adcode: '320200' },
            { name: '徐州市', adcode: '320300' },
            { name: '常州市', adcode: '320400' },
            { name: '苏州市', adcode: '320500' },
            { name: '南通市', adcode: '320600' },
            { name: '连云港市', adcode: '320700' },
            { name: '淮安市', adcode: '320800' },
            { name: '盐城市', adcode: '320900' },
            { name: '扬州市', adcode: '321000' },
            { name: '镇江市', adcode: '321100' },
            { name: '泰州市', adcode: '321200' },
            { name: '宿迁市', adcode: '321300' }
          ]
        },
        {
          name: '浙江省',
          cities: [
            { name: '杭州市', adcode: '330100' },
            { name: '宁波市', adcode: '330200' },
            { name: '温州市', adcode: '330300' },
            { name: '嘉兴市', adcode: '330400' },
            { name: '湖州市', adcode: '330500' },
            { name: '绍兴市', adcode: '330600' },
            { name: '金华市', adcode: '330700' },
            { name: '衢州市', adcode: '330800' },
            { name: '舟山市', adcode: '330900' },
            { name: '台州市', adcode: '331000' },
            { name: '丽水市', adcode: '331100' }
          ]
        },
        {
          name: '安徽省',
          cities: [
            { name: '合肥市', adcode: '340100' },
            { name: '芜湖市', adcode: '340200' },
            { name: '蚌埠市', adcode: '340300' },
            { name: '淮南市', adcode: '340400' },
            { name: '马鞍山市', adcode: '340500' },
            { name: '淮北市', adcode: '340600' },
            { name: '铜陵市', adcode: '340700' },
            { name: '安庆市', adcode: '340800' },
            { name: '黄山市', adcode: '341000' },
            { name: '滁州市', adcode: '341100' },
            { name: '阜阳市', adcode: '341200' },
            { name: '宿州市', adcode: '341300' },
            { name: '六安市', adcode: '341500' },
            { name: '亳州市', adcode: '341600' },
            { name: '池州市', adcode: '341700' },
            { name: '宣城市', adcode: '341800' }
          ]
        },
        {
          name: '福建省',
          cities: [
            { name: '福州市', adcode: '350100' },
            { name: '厦门市', adcode: '350200' },
            { name: '莆田市', adcode: '350300' },
            { name: '三明市', adcode: '350400' },
            { name: '泉州市', adcode: '350500' },
            { name: '漳州市', adcode: '350600' },
            { name: '南平市', adcode: '350700' },
            { name: '龙岩市', adcode: '350800' },
            { name: '宁德市', adcode: '350900' }
          ]
        },
        {
          name: '江西省',
          cities: [
            { name: '南昌市', adcode: '360100' },
            { name: '景德镇市', adcode: '360200' },
            { name: '萍乡市', adcode: '360300' },
            { name: '九江市', adcode: '360400' },
            { name: '新余市', adcode: '360500' },
            { name: '鹰潭市', adcode: '360600' },
            { name: '赣州市', adcode: '360700' },
            { name: '吉安市', adcode: '360800' },
            { name: '宜春市', adcode: '360900' },
            { name: '抚州市', adcode: '361000' },
            { name: '上饶市', adcode: '361100' }
          ]
        },
        {
          name: '山东省',
          cities: [
            { name: '济南市', adcode: '370100' },
            { name: '青岛市', adcode: '370200' },
            { name: '淄博市', adcode: '370300' },
            { name: '枣庄市', adcode: '370400' },
            { name: '东营市', adcode: '370500' },
            { name: '烟台市', adcode: '370600' },
            { name: '潍坊市', adcode: '370700' },
            { name: '济宁市', adcode: '370800' },
            { name: '泰安市', adcode: '370900' },
            { name: '威海市', adcode: '371000' },
            { name: '日照市', adcode: '371100' },
            { name: '临沂市', adcode: '371300' },
            { name: '德州市', adcode: '371400' },
            { name: '聊城市', adcode: '371500' },
            { name: '滨州市', adcode: '371600' },
            { name: '菏泽市', adcode: '371700' }
          ]
        },
        
        // 华中地区
        {
          name: '河南省',
          cities: [
            { name: '郑州市', adcode: '410100' },
            { name: '开封市', adcode: '410200' },
            { name: '洛阳市', adcode: '410300' },
            { name: '平顶山市', adcode: '410400' },
            { name: '安阳市', adcode: '410500' },
            { name: '鹤壁市', adcode: '410600' },
            { name: '新乡市', adcode: '410700' },
            { name: '焦作市', adcode: '410800' },
            { name: '濮阳市', adcode: '410900' },
            { name: '许昌市', adcode: '411000' },
            { name: '漯河市', adcode: '411100' },
            { name: '三门峡市', adcode: '411200' },
            { name: '南阳市', adcode: '411300' },
            { name: '商丘市', adcode: '411400' },
            { name: '信阳市', adcode: '411500' },
            { name: '周口市', adcode: '411600' },
            { name: '驻马店市', adcode: '411700' },
            { name: '济源市', adcode: '419001' }
          ]
        },
        {
          name: '湖北省',
          cities: [
            { name: '武汉市', adcode: '420100' },
            { name: '黄石市', adcode: '420200' },
            { name: '十堰市', adcode: '420300' },
            { name: '宜昌市', adcode: '420500' },
            { name: '襄阳市', adcode: '420600' },
            { name: '鄂州市', adcode: '420700' },
            { name: '荆门市', adcode: '420800' },
            { name: '孝感市', adcode: '420900' },
            { name: '荆州市', adcode: '421000' },
            { name: '黄冈市', adcode: '421100' },
            { name: '咸宁市', adcode: '421200' },
            { name: '随州市', adcode: '421300' },
            { name: '恩施土家族苗族自治州', adcode: '422800' },
            { name: '仙桃市', adcode: '429004' },
            { name: '潜江市', adcode: '429005' },
            { name: '天门市', adcode: '429006' },
            { name: '神农架林区', adcode: '429021' }
          ]
        },
        {
          name: '湖南省',
          cities: [
            { name: '长沙市', adcode: '430100' },
            { name: '株洲市', adcode: '430200' },
            { name: '湘潭市', adcode: '430300' },
            { name: '衡阳市', adcode: '430400' },
            { name: '邵阳市', adcode: '430500' },
            { name: '岳阳市', adcode: '430600' },
            { name: '常德市', adcode: '430700' },
            { name: '张家界市', adcode: '430800' },
            { name: '益阳市', adcode: '430900' },
            { name: '郴州市', adcode: '431000' },
            { name: '永州市', adcode: '431100' },
            { name: '怀化市', adcode: '431200' },
            { name: '娄底市', adcode: '431300' },
            { name: '湘西土家族苗族自治州', adcode: '433100' }
          ]
        },
        
        // 华南地区
        {
          name: '广东省',
          cities: [
            { name: '广州市', adcode: '440100' },
            { name: '韶关市', adcode: '440200' },
            { name: '深圳市', adcode: '440300' },
            { name: '珠海市', adcode: '440400' },
            { name: '汕头市', adcode: '440500' },
            { name: '佛山市', adcode: '440600' },
            { name: '江门市', adcode: '440700' },
            { name: '湛江市', adcode: '440800' },
            { name: '茂名市', adcode: '440900' },
                         { name: '肇庆市', adcode: '441200' },
            { name: '惠州市', adcode: '441300' },
            { name: '梅州市', adcode: '441400' },
            { name: '汕尾市', adcode: '441500' },
            { name: '河源市', adcode: '441600' },
            { name: '阳江市', adcode: '441700' },
            { name: '清远市', adcode: '441800' },
            { name: '东莞市', adcode: '441900' },
            { name: '中山市', adcode: '442000' },
            { name: '潮州市', adcode: '445100' },
            { name: '揭阳市', adcode: '445200' },
            { name: '云浮市', adcode: '445300' }
          ]
        },
        {
          name: '广西壮族自治区',
          cities: [
            { name: '南宁市', adcode: '450100' },
            { name: '柳州市', adcode: '450200' },
            { name: '桂林市', adcode: '450300' },
            { name: '梧州市', adcode: '450400' },
            { name: '北海市', adcode: '450500' },
            { name: '防城港市', adcode: '450600' },
            { name: '钦州市', adcode: '450700' },
            { name: '贵港市', adcode: '450800' },
            { name: '玉林市', adcode: '450900' },
            { name: '百色市', adcode: '451000' },
            { name: '贺州市', adcode: '451100' },
            { name: '河池市', adcode: '451200' },
            { name: '来宾市', adcode: '451300' },
            { name: '崇左市', adcode: '451400' }
          ]
        },
        {
          name: '海南省',
          cities: [
            { name: '海口市', adcode: '460100' },
            { name: '三亚市', adcode: '460200' },
            { name: '三沙市', adcode: '460300' },
            { name: '儋州市', adcode: '460400' },
            { name: '五指山市', adcode: '469001' },
            { name: '琼海市', adcode: '469002' },
            { name: '文昌市', adcode: '469005' },
            { name: '万宁市', adcode: '469006' },
            { name: '东方市', adcode: '469007' },
            { name: '定安县', adcode: '469021' },
            { name: '屯昌县', adcode: '469022' },
            { name: '澄迈县', adcode: '469023' },
            { name: '临高县', adcode: '469024' },
            { name: '白沙黎族自治县', adcode: '469025' },
            { name: '昌江黎族自治县', adcode: '469026' },
            { name: '乐东黎族自治县', adcode: '469027' },
            { name: '陵水黎族自治县', adcode: '469028' },
            { name: '保亭黎族苗族自治县', adcode: '469029' },
            { name: '琼中黎族苗族自治县', adcode: '469030' }
          ]
        },
        
        // 西南地区
        {
          name: '四川省',
          cities: [
            { name: '成都市', adcode: '510100' },
            { name: '自贡市', adcode: '510300' },
            { name: '攀枝花市', adcode: '510400' },
            { name: '泸州市', adcode: '510500' },
            { name: '德阳市', adcode: '510600' },
            { name: '绵阳市', adcode: '510700' },
            { name: '广元市', adcode: '510800' },
            { name: '遂宁市', adcode: '510900' },
            { name: '内江市', adcode: '511000' },
            { name: '乐山市', adcode: '511100' },
            { name: '南充市', adcode: '511300' },
            { name: '眉山市', adcode: '511400' },
            { name: '宜宾市', adcode: '511500' },
            { name: '广安市', adcode: '511600' },
            { name: '达州市', adcode: '511700' },
            { name: '雅安市', adcode: '511800' },
            { name: '巴中市', adcode: '511900' },
            { name: '资阳市', adcode: '512000' },
            { name: '阿坝藏族羌族自治州', adcode: '513200' },
            { name: '甘孜藏族自治州', adcode: '513300' },
            { name: '凉山彝族自治州', adcode: '513400' }
          ]
        },
        {
          name: '贵州省',
          cities: [
            { name: '贵阳市', adcode: '520100' },
            { name: '六盘水市', adcode: '520200' },
            { name: '遵义市', adcode: '520300' },
            { name: '安顺市', adcode: '520400' },
            { name: '毕节市', adcode: '520500' },
            { name: '铜仁市', adcode: '520600' },
            { name: '黔西南布依族苗族自治州', adcode: '522300' },
            { name: '黔东南苗族侗族自治州', adcode: '522600' },
            { name: '黔南布依族苗族自治州', adcode: '522700' }
          ]
        },
        {
          name: '云南省',
          cities: [
            { name: '昆明市', adcode: '530100' },
            { name: '曲靖市', adcode: '530300' },
            { name: '玉溪市', adcode: '530400' },
            { name: '保山市', adcode: '530500' },
            { name: '昭通市', adcode: '530600' },
            { name: '丽江市', adcode: '530700' },
            { name: '普洱市', adcode: '530800' },
            { name: '临沧市', adcode: '530900' },
            { name: '楚雄彝族自治州', adcode: '532300' },
            { name: '红河哈尼族彝族自治州', adcode: '532500' },
            { name: '文山壮族苗族自治州', adcode: '532600' },
            { name: '西双版纳傣族自治州', adcode: '532800' },
            { name: '大理白族自治州', adcode: '532900' },
            { name: '德宏傣族景颇族自治州', adcode: '533100' },
            { name: '怒江傈僳族自治州', adcode: '533300' },
            { name: '迪庆藏族自治州', adcode: '533400' }
          ]
        },
        {
          name: '西藏自治区',
          cities: [
            { name: '拉萨市', adcode: '540100' },
            { name: '日喀则市', adcode: '540200' },
            { name: '昌都市', adcode: '540300' },
            { name: '林芝市', adcode: '540400' },
            { name: '山南市', adcode: '540500' },
            { name: '那曲市', adcode: '540600' },
            { name: '阿里地区', adcode: '542500' }
          ]
        },
        
        // 西北地区
        {
          name: '陕西省',
          cities: [
            { name: '西安市', adcode: '610100' },
            { name: '铜川市', adcode: '610200' },
            { name: '宝鸡市', adcode: '610300' },
            { name: '咸阳市', adcode: '610400' },
            { name: '渭南市', adcode: '610500' },
            { name: '延安市', adcode: '610600' },
            { name: '汉中市', adcode: '610700' },
            { name: '榆林市', adcode: '610800' },
            { name: '安康市', adcode: '610900' },
            { name: '商洛市', adcode: '611000' }
          ]
        },
        {
          name: '甘肃省',
          cities: [
            { name: '兰州市', adcode: '620100' },
            { name: '嘉峪关市', adcode: '620200' },
            { name: '金昌市', adcode: '620300' },
            { name: '白银市', adcode: '620400' },
            { name: '天水市', adcode: '620500' },
            { name: '武威市', adcode: '620600' },
            { name: '张掖市', adcode: '620700' },
            { name: '平凉市', adcode: '620800' },
            { name: '酒泉市', adcode: '620900' },
            { name: '庆阳市', adcode: '621000' },
            { name: '定西市', adcode: '621100' },
            { name: '陇南市', adcode: '621200' },
            { name: '临夏回族自治州', adcode: '622900' },
            { name: '甘南藏族自治州', adcode: '623000' }
          ]
        },
        {
          name: '青海省',
          cities: [
            { name: '西宁市', adcode: '630100' },
            { name: '海东市', adcode: '630200' },
            { name: '海北藏族自治州', adcode: '632200' },
            { name: '黄南藏族自治州', adcode: '632300' },
            { name: '海南藏族自治州', adcode: '632500' },
            { name: '果洛藏族自治州', adcode: '632600' },
            { name: '玉树藏族自治州', adcode: '632700' },
            { name: '海西蒙古族藏族自治州', adcode: '632800' }
          ]
        },
        {
          name: '宁夏回族自治区',
          cities: [
            { name: '银川市', adcode: '640100' },
            { name: '石嘴山市', adcode: '640200' },
            { name: '吴忠市', adcode: '640300' },
            { name: '固原市', adcode: '640400' },
            { name: '中卫市', adcode: '640500' }
          ]
        },
        {
          name: '新疆维吾尔自治区',
          cities: [
            { name: '乌鲁木齐市', adcode: '650100' },
            { name: '克拉玛依市', adcode: '650200' },
            { name: '吐鲁番市', adcode: '650400' },
            { name: '哈密市', adcode: '650500' },
            { name: '昌吉回族自治州', adcode: '652300' },
            { name: '博尔塔拉蒙古自治州', adcode: '652700' },
            { name: '巴音郭楞蒙古自治州', adcode: '652800' },
            { name: '阿克苏地区', adcode: '652900' },
            { name: '克孜勒苏柯尔克孜自治州', adcode: '653000' },
            { name: '喀什地区', adcode: '653100' },
            { name: '和田地区', adcode: '653200' },
            { name: '伊犁哈萨克自治州', adcode: '654000' },
            { name: '塔城地区', adcode: '654200' },
            { name: '阿勒泰地区', adcode: '654300' },
            { name: '石河子市', adcode: '659001' },
            { name: '阿拉尔市', adcode: '659002' },
            { name: '图木舒克市', adcode: '659003' },
            { name: '五家渠市', adcode: '659004' },
            { name: '北屯市', adcode: '659005' },
            { name: '铁门关市', adcode: '659006' },
            { name: '双河市', adcode: '659007' },
            { name: '可克达拉市', adcode: '659008' },
            { name: '昆玉市', adcode: '659009' },
            { name: '胡杨河市', adcode: '659010' },
            { name: '新星市', adcode: '659011' }
          ]
        },
        
        // 特别行政区
        {
          name: '香港特别行政区',
          cities: [{ name: '香港特别行政区', adcode: '810000' }]
        },
        {
          name: '澳门特别行政区',
          cities: [{ name: '澳门特别行政区', adcode: '820000' }]
        },
        {
          name: '台湾省',
          cities: [
            { name: '台北市', adcode: '710100' },
            { name: '高雄市', adcode: '710200' },
            { name: '台中市', adcode: '710300' },
            { name: '台南市', adcode: '710400' },
            { name: '新北市', adcode: '710500' },
            { name: '桃园市', adcode: '710600' }
          ]
        }
      ];
    },

    updateAvailableCities() {
      const selectedProvince = this.provinces.find(p => p.name === this.selectedProvince);
      this.availableCities = selectedProvince ? selectedProvince.cities : [];
      this.selectedCity = '';
    },

    onProvinceChange() {
      this.updateAvailableCities();
      
      // 清除地图上现有的标记和路线
      if (this.$refs.mapDisplayRef) {
        this.$refs.mapDisplayRef.clearAllMarkersAndRoutes();
      }
      
      // 重置相关状态
      this.homeLocation = null;
      this.homeAddress = '';
      this.shopsToVisit = [];
      this.routeCombinations = [];
      this.showRouteInfo = false;
    },

    onCityChange() {
      if (this.selectedCity && this.$refs.mapDisplayRef) {
        // 获取选中城市的信息
        const cityInfo = this.availableCities.find(city => city.name === this.selectedCity);
        if (cityInfo) {
          // 通过高德地图API获取城市中心坐标
          this.getCityCenter(cityInfo.adcode);
        }
        
        // 清除之前的数据
        this.homeLocation = null;
        this.homeAddress = '';
        this.shopsToVisit = [];
        this.routeCombinations = [];
        this.showRouteInfo = false;
      }
    },

    // 地址输入处理
    async onAddressInput() {
      if (!this.homeAddress.trim() || !this.selectedCity) {
        this.addressSuggestions = [];
        return;
      }

      try {
        const response = await fetch(`/api/search-address?query=${encodeURIComponent(this.homeAddress)}&city=${encodeURIComponent(this.selectedCity)}`);
        if (response.ok) {
          const data = await response.json();
          this.addressSuggestions = data.suggestions || [];
        }
      } catch (error) {
        console.error('地址搜索错误:', error);
        this.addressSuggestions = [];
      }
    },

    hideAddressSuggestions() {
      setTimeout(() => {
        this.showAddressSuggestions = false;
      }, 200);
    },

    selectAddressSuggestion(suggestion) {
      this.homeAddress = suggestion.name;
      this.homeLocation = {
        longitude: parseFloat(suggestion.location.split(',')[0]),
        latitude: parseFloat(suggestion.location.split(',')[1])
      };
      this.showAddressSuggestions = false;
      
      // 通知地图组件设置家的位置
      if (this.$refs.mapDisplayRef) {
        this.$refs.mapDisplayRef.setHomeLocation(
          this.homeLocation.longitude,
          this.homeLocation.latitude,
          this.homeAddress
        );
      }
      
      this.showNotification('家的位置设置成功', 'success');
    },

    // 店铺输入处理
    async onShopInput() {
      if (!this.shopInput.trim() || !this.selectedCity) {
        this.shopSuggestions = [];
        return;
      }

      try {
        const response = await fetch(`/api/search-shops?query=${encodeURIComponent(this.shopInput)}&city=${encodeURIComponent(this.selectedCity)}`);
        if (response.ok) {
          const data = await response.json();
          this.shopSuggestions = data.suggestions || [];
        }
      } catch (error) {
        console.error('店铺搜索错误:', error);
        this.shopSuggestions = [];
      }
    },

    hideShopSuggestions() {
      setTimeout(() => {
        this.showShopSuggestions = false;
      }, 200);
    },

    selectShopSuggestion(suggestion) {
      // 检查是否已经添加过这个店铺
      const exists = this.shopsToVisit.some(shop => shop.id === suggestion.id);
      if (!exists) {
        this.shopsToVisit.push({
          ...suggestion,
          type: this.isChainStore(suggestion.name) ? 'chain' : 'private'
        });
        this.showNotification(`已添加店铺: ${suggestion.name}`, 'success');
      } else {
        this.showNotification('该店铺已在列表中', 'warning');
      }
      
      this.shopInput = '';
      this.showShopSuggestions = false;
    },

    removeShop(shopId) {
      const index = this.shopsToVisit.findIndex(shop => shop.id === shopId);
      if (index > -1) {
        const removedShop = this.shopsToVisit.splice(index, 1)[0];
        this.showNotification(`已移除店铺: ${removedShop.name}`, 'info');
        
        // 清除路线信息
        this.routeCombinations = [];
        this.showRouteInfo = false;
        this.selectedRouteId = null;
      }
    },

    // 连锁店判断
    isChainStore(shopName) {
      return this.chainStoreBrands.some(brand => 
        shopName.toLowerCase().includes(brand.toLowerCase()) ||
        brand.toLowerCase().includes(shopName.toLowerCase())
      );
    },

    // 停留时间管理
    getStayDuration(shopId) {
      return this.stayDurations[shopId] || this.defaultStayDuration;
    },

    setStayDuration(shopId, duration) {
      this.$set(this.stayDurations, shopId, duration);
    },

    // 路线规划
    async getDirections() {
      if (!this.canGetRoute) return;
      
      this.isLoading = true;
      this.routeCombinations = [];
      this.showRouteInfo = false;
      
      try {
        const response = await fetch('/api/optimize-route', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            homeLocation: this.homeLocation,
            shops: this.shopsToVisit,
            travelMode: this.travelMode,
            departureTime: this.departureTime,
            stayDurations: this.stayDurations,
            defaultStayDuration: this.defaultStayDuration,
            city: this.selectedCity
          })
        });

        if (response.ok) {
          const result = await response.json();
          this.processRouteResults(result);
        } else {
          throw new Error('路线规划请求失败');
        }
      } catch (error) {
        console.error('路线规划错误:', error);
        this.showNotification('路线规划失败，请重试', 'error');
      } finally {
        this.isLoading = false;
      }
    },

    processRouteResults(result) {
      if (result.success && result.routes) {
        this.routeCombinations = result.routes;
        this.showNotification(`找到 ${result.routes.length} 个可选路线方案`, 'success');
      } else {
        this.showNotification('未找到合适的路线方案', 'warning');
      }
    },

    // 路线选择
    async selectRoute(routeOption) {
      this.selectedRouteId = routeOption.id;
      this.routeInfo = routeOption;
      this.showRouteInfo = true;
      
      // 在地图上显示路线
      if (this.$refs.mapDisplayRef) {
        await this.$refs.mapDisplayRef.drawOptimizedRoute(routeOption);
      }
      
      this.showNotification('已选择路线方案', 'success');
    },

    onRouteCalculated(routeData) {
      this.routeInfo = routeData;
      this.showRouteInfo = true;
    },

    // 格式化工具方法
    formatDistance(distance) {
      if (distance >= 1000) {
        return `${(distance / 1000).toFixed(1)}km`;
      }
      return `${Math.round(distance)}m`;
    },

    formatDuration(minutes) {
      if (minutes >= 60) {
        const hours = Math.floor(minutes / 60);
        const remainingMinutes = Math.round(minutes % 60);
        return remainingMinutes > 0 ? `${hours}小时${remainingMinutes}分钟` : `${hours}小时`;
      }
      return `${Math.round(minutes)}分钟`;
    },

    // 获取城市中心坐标
    async getCityCenter(adcode) {
      try {
        // 使用高德地图API获取城市中心坐标
        const response = await fetch(`/api/get-city-center?adcode=${adcode}`);
        if (response.ok) {
          const data = await response.json();
          if (data.success && data.center) {
            // 设置地图中心
            if (this.$refs.mapDisplayRef && this.$refs.mapDisplayRef.map) {
              const center = new AMap.LngLat(data.center.longitude, data.center.latitude);
              this.$refs.mapDisplayRef.map.setCenter(center);
              this.$refs.mapDisplayRef.map.setZoom(12);
            }
          }
        }
      } catch (error) {
        console.error('获取城市中心坐标失败:', error);
        // 如果API失败，使用默认的城市坐标映射
        this.setDefaultCityCenter();
      }
    },

    // 设置默认城市中心（备用方案）
    setDefaultCityCenter() {
      const cityCoordinates = {
        '北京市': [116.405285, 39.904989],
        '上海市': [121.472644, 31.231706],
        '广州市': [113.280637, 23.125178],
        '深圳市': [114.085947, 22.547],
        '杭州市': [120.153576, 30.287459],
        '南京市': [118.767413, 32.041544],
        '成都市': [104.065735, 30.659462],
        '武汉市': [114.298572, 30.584355]
      };

      const coordinates = cityCoordinates[this.selectedCity];
      if (coordinates && this.$refs.mapDisplayRef && this.$refs.mapDisplayRef.map) {
        const center = new AMap.LngLat(coordinates[0], coordinates[1]);
        this.$refs.mapDisplayRef.map.setCenter(center);
        this.$refs.mapDisplayRef.map.setZoom(12);
      }
    }
  },

  mounted() {
    this.loadProvinceCityData();
  }
}
</script>