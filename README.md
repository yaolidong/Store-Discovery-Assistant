# 门店发现助手 (Store Discovery Assistant)

本项目是一个基于Web的门店发现助手，旨在帮助用户发现附近的店铺，并规划最优的出行路线。

## 功能模块

*   **用户认证 (User Authentication):**
    *   注册 (Register)
    *   登录 (Login)
    *   登出 (Logout)
*   **用户住址管理 (User Home Address Management):**
    *   设置和查看用户住址 (Set and view user home address)
*   **店铺搜索 (Shop Search):**
    *   通过关键词、位置、城市搜索店铺 (Search shops by keywords, location, city)
*   **路线规划 (Route Planning):**
    *   规划从家出发，通过优化店铺的访问顺序，访问多个店铺并返回家中的最优驾车或公交路线。系统会尝试计算最短总距离或最少总时间的路线。也支持基础的公交路线查询（当前版本主要支持点对点查询，多点连续公交行程规划能力有限）。
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
    *   后端API: `http://localhost:5001` (具体端口请查看 `docker-compose.yml` 中 `backend` 服务的端口映射)

## 关于当前版本

本项目通过 Docker 运行的版本提供了一套核心的门店发现和路线规划功能。前端界面基于 `frontend/src/main.js` 文件中的 Vue 组件定义，实现了基础的用户交互。

代码库中 `frontend/src/components/` 目录下包含了更为完整和功能丰富的 Vue 单文件组件（SFCs），这些组件设计用于实现更高级的功能，例如：
*   全自动的最优路线计算（TSP优化，区分最短距离和最快时间）。
*   详细的行程时间安排表。
*   更完善的店铺搜索与筛选界面。

这些高级组件需要Vue的构建工具链（如 Vue CLI 或 Vite）进行编译和打包才能在生产环境中使用。当前默认的 Docker 配置直接使用 Nginx 托管基于 `main.js` 的简化版前端，未包含此构建步骤。若您希望体验或开发这些高级功能，请自行配置Vue的开发和构建环境。

## 注意事项
*   首次启动后端服务时，会自动在 `backend` 目录下创建 `travel_planner.db` SQLite数据库文件。
*   如果修改了前后端代码，需要重新执行 `docker-compose build` 来构建新的镜像，然后重启服务 `docker-compose down && docker-compose up -d`。