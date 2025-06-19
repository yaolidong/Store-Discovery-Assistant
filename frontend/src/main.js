// 导入 Vue 和 Vue Router
import { createApp } from 'vue';
import { createRouter, createWebHashHistory } from 'vue-router';

// 导入全局样式
import './styles.css';

// 导入所有Vue组件
import Dashboard from './components/Dashboard.vue';
import Login from './components/Login.vue';
import Register from './components/Register.vue';
import NotificationComp from './components/NotificationComp.vue';
import MapDisplay from './components/MapDisplay.vue';
import App from './App.vue';

// 导入工具类
import { DataValidator, RouteState } from './utils/index.js';

// 使全局可用（如果其他组件需要）
window.DataValidator = DataValidator;
window.RouteState = RouteState;

// --- Router Configuration ---
const routes = [
  { path: '/login', component: Login, meta: { requiresGuest: true } },
  { path: '/register', component: Register, meta: { requiresGuest: true } },
  { path: '/', component: Dashboard, alias: '/dashboard', meta: { requiresAuth: true } }
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

// Navigation Guard
router.beforeEach((to, from, next) => {
  const loggedIn = !!localStorage.getItem('userToken');

  if (to.matched.some(record => record.meta.requiresAuth)) {
    if (!loggedIn) {
      next({ path: '/login' });
    } else {
      next();
    }
  } else if (to.matched.some(record => record.meta.requiresGuest)) {
    if (loggedIn) {
      next({ path: '/' });
    } else {
      next();
    }
  }
  else {
    next();
  }
});

// --- Initialize Vue App ---
const app = createApp(App);
app.use(router);

// 注册全局组件
app.component('NotificationComp', NotificationComp);
app.component('MapDisplay', MapDisplay);

app.mount('#app');

console.log('Vue app initialized with modular components.');