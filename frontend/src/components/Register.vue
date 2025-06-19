<template>
  <div class="dashboard-container">
    <div class="app-header">
      <h1>智能商店寻路助手</h1>
      <p class="subtitle">创建新账户</p>
    </div>
    
    <div class="section">
      <h3><span class="icon">👤</span>用户注册</h3>
      <form @submit.prevent="registerUser" class="auth-form">
        <div class="form-group">
          <label for="username">用户名:</label>
          <input type="text" id="username" v-model="username" required placeholder="请输入用户名">
        </div>
        <div class="form-group">
          <label for="password">密码:</label>
          <input type="password" id="password" v-model="password" required placeholder="请输入密码">
        </div>
        <button type="submit" class="btn-primary">注册</button>
      </form>
      <p v-if="successMessage" class="success-message">{{ successMessage }}</p>
      <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>
      <p class="auth-link">已有账户? <router-link to="/login">点击登录</router-link></p>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'Register',
  data() {
    return {
      username: '',
      password: '',
      successMessage: '',
      errorMessage: ''
    };
  },
  methods: {
    async registerUser() {
      this.successMessage = '';
      this.errorMessage = '';
      try {
        const response = await axios.post('/api/register', {
          username: this.username,
          password: this.password
        });
        this.successMessage = response.data.message;
        this.$router.push('/login');
        
        // 使用更简洁的通知方式
        this.$nextTick(() => {
          console.log('注册成功！请登录');
        });
      } catch (error) {
        this.errorMessage = (error.response && error.response.data && error.response.data.message) || 'Registration failed. Please try again.';
        console.error('Registration error:', error);
      }
    }
  }
};
</script>

<style scoped>
/* Scoped styles from the original component can be added here if any */
.register-container {
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
