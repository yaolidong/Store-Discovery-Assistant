// 处理路线结果
processRouteResults(routesData) {
    if (!routesData || !routesData.route_candidates || routesData.route_candidates.length === 0) {
        this.showNotification('未能计算出有效路线', 'warning');
        return;
    }

    const allRoutes = routesData.route_candidates;

    // 按时间从短到长排序
    const timeRoutes = [...allRoutes]
        .sort((a, b) => a.total_overall_duration - b.total_overall_duration)
        .slice(0, 5);

    // 按距离从短到长排序
    const distanceRoutes = [...allRoutes]
        .sort((a, b) => a.total_distance - b.total_distance)
        .slice(0, 5);
    
    const formatRoute = (route, index, type) => ({
        id: `route_${type}_${index}`,
        type: type,
        optimizationType: type === 'time' ? '时间最短' : '距离最短',
        rank: index + 1,
        combination: route.optimized_order || [],
        totalTime: Math.round(route.total_overall_duration),
        totalDistance: Math.round(route.total_distance),
        routeData: route,
        originalIndex: index
    });
    
    this.routeCombinations = [
        ...timeRoutes.map((route, index) => formatRoute(route, index, 'time')),
        ...distanceRoutes.map((route, index) => formatRoute(route, index, 'distance'))
    ];
    
    if (this.routeCombinations.length === 0) {
        this.showNotification('未能计算出有效路线', 'warning');
        return;
    }
    
    this.routeInfo = null;
    this.showRouteInfo = false;
    
    this.showNotification(`🎉 成功获取候选路线! 时间优化(${timeRoutes.length}条), 距离优化(${distanceRoutes.length}条)`, 'success');
},

// 错误处理方法 