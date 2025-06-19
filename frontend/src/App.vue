<template>
  <div id="nav">
    <router-link to="/">主页</router-link> |
    <router-link to="/login" v-if="!isLoggedIn">登录</router-link>
    <span v-if="isLoggedIn"> | <a href="#" @click.prevent="logout">登出</a></span>
    <router-link to="/register" v-if="!isLoggedIn"> | 注册</router-link>
  </div>
  <router-view></router-view>
  <notification-comp ref="notification"></notification-comp>
</template>

<script>
import NotificationComp from './components/NotificationComp.vue';

export default {
  name: 'App',
  components: {
    NotificationComp
  },
  computed: {
    isLoggedIn() {
      // Check local storage for a token or user session
      return !!localStorage.getItem('userToken');
    }
  },
  methods: {
    logout() {
      localStorage.removeItem('userToken'); // Clear token/session
      this.$router.push('/login'); // Redirect to login
    }
  }
};
</script>

<style>
/* Basic styles, can be expanded or moved to a global CSS file */
#app { /* This would target the div in index.html if App.vue is the root component */
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
}

#nav {
  padding: 30px;
}

#nav a {
  font-weight: bold;
  color: #2c3e50;
  margin: 0 5px;
}

#nav a.router-link-exact-active {
  color: #42b983;
}
</style>
