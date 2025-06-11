# 门店发现助手 (Store Discovery Assistant)

本项目是一个基于Web的门店发现助手，旨在帮助用户发现附近的店铺，并规划最优的出行路线。

## 功能模块

*   **用户认证 (User Authentication):**
    *   注册 (Register)
    *   登录 (Login)
    *   登出 (Logout)
*   **行程管理 (Trip Management):**
    *   创建行程 (Create Trip)
    *   查看行程 (View Trips)
*   **用户住址管理 (User Home Address Management):**
    *   设置和查看用户住址 (Set and view user home address)
*   **店铺搜索 (Shop Search):**
    *   通过关键词、位置、城市搜索店铺 (Search shops by keywords, location, city)
*   **路线优化 (Route Optimization):**
    *   计算从家到多个店铺的最优路线 (Calculate optimal route from home to multiple shops)
    *   支持驾车和公交两种模式 (Supports driving and public transit modes)
*   **高德地图API集成 (Amap API Integration):**
    *   用于地理编码、POI搜索、路线规划 (Used for geocoding, POI search, route planning)

## 技术栈

*   **后端 (Backend):** Flask (Python)
*   **前端 (Frontend):** Vue.js (JavaScript)
*   **数据库 (Database):** SQLite
*   **API服务 (API Service):** 高德地图API (Amap API)

## 安装和部署

本项目使用 Docker 和 Docker Compose 进行容器化部署。

1.  **环境准备:**
    *   确保已安装 Docker 和 Docker Compose。
    *   在高德开放平台申请API Key，并在 `backend/app.py` 文件中配置 `AMAP_API_KEY`。
        ```python
        app.config['AMAP_API_KEY'] = '您的高德API Key' # 替换成您申请的Key
        ```

2.  **构建和启动服务:**
    在项目根目录下执行以下命令：
    ```bash
    # 构建镜像
    docker-compose build

    # 启动服务 (后台运行)
    docker-compose up -d
    ```

3.  **访问应用:**
    *   前端应用: `http://localhost:8080` (具体端口请查看 `docker-compose.yml` 中 `frontend` 服务的端口映射)
    *   后端API: `http://localhost:5000` (具体端口请查看 `docker-compose.yml` 中 `backend` 服务的端口映射)

## 注意事项
*   首次启动后端服务时，会自动在 `backend` 目录下创建 `travel_planner.db` SQLite数据库文件。
*   如果修改了前后端代码，需要重新执行 `docker-compose build` 来构建新的镜像，然后重启服务 `docker-compose down && docker-compose up -d`。