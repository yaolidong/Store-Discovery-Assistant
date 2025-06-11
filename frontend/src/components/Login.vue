<template>
  <div class="login-container">
    <h2>Login</h2>
    <form @submit.prevent="loginUser">
      <div class="form-group">
        <label for="username">Username:</label>
        <input type="text" id="username" v-model="username" required>
      </div>
      <div class="form-group">
        <label for="password">Password:</label>
        <input type="password" id="password" v-model="password" required>
      </div>
      <button type="submit">Login</button>
    </form>
    <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>
    <p class="register-link">
      Don't have an account? <router-link to="/register">Register here</router-link>
    </p>
  </div>
</template>

<script>
// import axios from 'axios'; // Assuming axios is globally available or configured in main.js

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
        // Adjust the URL to where your backend is running, e.g., http://localhost:5000/login
        // Or use a base URL if configured with axios globally e.g. axios.defaults.baseURL = 'http://localhost:5000/api';
        const response = await axios.post('/api/login', {
          username: this.username,
          password: this.password
        });
        // Assuming the backend returns a token or session confirmation
        // Store token or session info (e.g., in localStorage)
        localStorage.setItem('userToken', response.data.token || 'fakeToken'); // Replace 'fakeToken' with actual token from response
        // console.log('Login successful:', response.data);
        alert('Login successful!');
        this.$router.push('/'); // Redirect to dashboard or home page
      } catch (error) {
        if (error.response && error.response.data && error.response.data.message) {
          this.errorMessage = error.response.data.message;
        } else if (error.request) {
          this.errorMessage = 'No response from server. Please check your connection or backend.';
        } else {
          this.errorMessage = 'Login failed. Please try again.';
        }
        console.error('Login error:', error);
      }
    }
  }
};
</script>

<style scoped>
.login-container {
  max-width: 400px;
  margin: 50px auto;
  padding: 20px;
  border: 1px solid #ddd;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
h2 {
  text-align: center;
  color: #333;
}
.form-group {
  margin-bottom: 15px;
}
.form-group label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
}
.form-group input[type="text"],
.form-group input[type="password"] {
  width: calc(100% - 22px);
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
}
button[type="submit"] {
  width: 100%;
  padding: 10px;
  background-color: #42b983;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}
button[type="submit"]:hover {
  background-color: #36a476;
}
.error-message {
  color: red;
  margin-top: 10px;
  text-align: center;
}
.register-link {
  margin-top: 15px;
  text-align: center;
}
</style>
