<template>
  <div class="dashboard-container">
    <div class="app-header">
      <h1>智能商店寻路助手</h1>
      <p class="subtitle">登录您的账户</p>
    </div>
    
    <div class="section">
      <h3><span class="icon">🔐</span>用户登录</h3>
      <form @submit.prevent="loginUser" class="auth-form">
        <div class="form-group">
          <label for="username">用户名:</label>
          <input type="text" id="username" v-model="username" required placeholder="请输入用户名">
        </div>
        <div class="form-group">
          <label for="password">密码:</label>
          <input type="password" id="password" v-model="password" required placeholder="请输入密码">
        </div>
        <button type="submit" class="btn-primary">登录</button>
      </form>
      <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>
      <p class="auth-link">还没有账户? <router-link to="/register">点击注册</router-link></p>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'Login',
  data() {
    return {
      username: '',
      password: '',
      errorMessage: ''
    };
  },
  methods: {
    async loginUser() {
      this.errorMessage = '';
      try {
        const response = await axios.post('/api/login', {
          username: this.username,
          password: this.password
        });
        localStorage.setItem('userToken', response.data.token || 'fakeToken');
        this.$router.push('/');
        
        // 使用更简洁的通知方式
        this.$nextTick(() => {
          // 可以通过全局事件或其他方式显示通知
          console.log('登录成功！');
        });
      } catch (error) {
        console.error('Login error:', error);
        if (error.response) {
          this.errorMessage = error.response.data.message || '登录失败，请检查用户名和密码';
        } else if (error.request) {
          this.errorMessage = '无法连接到服务器，请检查网络连接或稍后重试';
        } else {
          this.errorMessage = '登录请求出错，请稍后重试';
        }
      }
    }
  }
};
</script>

<style scoped>
/* Scoped styles from the original component can be added here if any */
.login-container {
  max-width: 500px;
  margin: 50px auto;
  padding: 2rem;
  border-radius: 8px;
  box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}
.auth-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
</style>
