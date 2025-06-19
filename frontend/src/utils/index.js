// 数据验证工具类
export class DataValidator {
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
export class RouteState {
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