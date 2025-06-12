# 智能行程规划助手 (Intelligent Travel Planning Assistant)

本项目是一款基于Web的智能行程规划助手，旨在帮助用户高效管理地点列表、发现感兴趣的店铺，并为多点行程规划最优路线，同时提供详细的出行方式指引。

## 主要功能

*   **用户认证 (User Authentication):**
    *   用户注册 (User Registration)
    *   用户登录 (User Login)
    *   用户登出 (User Logout)
*   **住址管理 (Home Location Management):**
    *   设置和查看用户家庭住址。
    *   支持手动输入地址或通过地图拾取器精确选择位置。
*   **店铺搜索与管理 (Shop Search & Management):**
    *   通过关键词、城市搜索店铺，输入时提供实时建议列表 (最多显示10条)。
    *   结合用户住址（或其他指定地点）进行周边店铺搜索。
    *   搜索结果列表（明确搜索后）支持按距离排序 (客户端排序)。
    *   将感兴趣的店铺添加至待访问列表。
    *   为列表中的店铺设置预计停留时间。
*   **智能路线规划 (Intelligent Route Optimization):**
    *   基于用户住址和待访问店铺列表（包含停留时间），自动规划“家 -> 店铺1 -> 店铺2 ... -> 家”的闭环优化路线。
    *   支持多种出行模式：
        *   **驾车模式 (Driving Mode):**
            *   提供考虑实时路况的预估行驶时间，使行程用时更准确。
            *   在地图上展示规划的驾车路线。
        *   **公交模式 (Public Transit Mode):**
            *   提供详尽的、分段式的公交指引，包含步行、公交线路、地铁线路等。
            *   每一段指引均包含具体操作（如“步行至XX站”）、线路名称（如“乘坐公交5路”）、出发/到达站点、预估耗时和距离。
            *   在地图上以不同颜色和样式清晰展示不同交通方式的路线段（如步行段虚线，公交/地铁段实线）。
*   **行程时间表生成 (Schedule Generation):**
    *   根据规划出的最优路线（包括各路段交通时间）和用户为各店铺设置的停留时间，自动生成一份详细的行程时间安排表。
*   **高德地图API集成 (Amap API Integration):**
    *   深度集成高德地图服务，用于地址解析、POI（兴趣点）搜索、驾车路线规划、公交路径规划等核心功能。

## 技术栈

*   **后端 (Backend):** Flask (Python)
*   **前端 (Frontend):** Vue.js (JavaScript)
*   **数据库 (Database):** SQLite (通过Flask-SQLAlchemy管理)
*   **API服务 (API Service):** 高德地图API (Amap API)
*   **容器化 (Containerization):** Docker & Docker Compose

## 本地运行指南

本项目推荐使用 Docker 和 Docker Compose 进行容器化部署。

1.  **环境准备 (Prerequisites):**
    *   确保您的系统中已安装 Docker 和 Docker Compose。
    *   访问 [高德开放平台](https://lbs.amap.com/) 注册并申请Web服务API Key (选择服务平台为 "Web服务")。

2.  **配置API Key:**
    *   在 `backend/app.py` 文件中，找到以下行并替换为您申请的高德API Key:
        ```python
        app.config['AMAP_API_KEY'] = '您的高德API Key' # 将引号内的占位符替换为您的真实Key
        ```

3.  **构建和启动服务 (Build and Run):**
    *   在项目的根目录下，打开终端或命令行工具，执行以下命令：
        ```bash
        # 构建Docker镜像 (首次运行或代码更改后执行)
        docker-compose build

        # 启动所有服务 (后台模式)
        docker-compose up -d
        ```

4.  **访问应用 (Access Application):**
    *   **前端应用 (Frontend):** 打开浏览器访问 `http://localhost:8080` (端口号基于 `docker-compose.yml` 文件中的 `frontend` 服务配置)。
    *   **后端API (Backend API):** 后端服务运行在 `http://localhost:5000` (端口号基于 `docker-compose.yml` 文件中的 `backend` 服务配置)，前端应用会自动调用。

5.  **停止服务 (Stop Services):**
    *   在项目根目录下执行：
        ```bash
        docker-compose down
        ```

## 注意事项

*   后端服务首次启动时，会在 `backend` 目录下自动创建名为 `travel_planner.db` 的SQLite数据库文件。
*   如果您修改了前端或后端的代码，为了使更改生效，您需要重新构建Docker镜像 (`docker-compose build`)，然后重启服务 (`docker-compose down && docker-compose up -d`)。
*   请确保高德API Key具有足够的配额，特别是对于路线规划和POI搜索功能。

## 项目结构 (Simplified)

```
.
├── backend/         # 后端Flask应用
│   ├── app.py       # Flask主应用文件和API接口定义
│   └── ...          # 其他后端文件
├── frontend/        # 前端Vue.js应用
│   ├── src/
│   │   ├── components/ # Vue组件
│   │   │   ├── Dashboard.vue # 主要仪表盘组件
│   │   │   └── MapDisplay.vue  # 地图显示组件
│   │   └── ...       # 其他前端源码
│   └── ...
├── docker-compose.yml # Docker编排文件
└── README.md          # 项目说明文件 (本文档)
```

## 贡献 (Contributing)

欢迎对本项目进行改进和贡献！如果您有任何建议或发现问题，请通过创建 Issue 或 Pull Request 的方式参与。

## 许可证 (License)

本项目默认使用 MIT 许可证（请根据实际情况添加或修改）。