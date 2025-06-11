<template>
  <div class="dashboard-container">
    <h2>Welcome to your Dashboard!</h2>
    <p>This is where your amazing trip planning features will reside.</p>
    <p>Plan new trips, view existing ones, and manage your travel itineraries.</p>
    <button @click="logoutUser" class="logout-button">Logout</button>
  </div>
</template>

<script>
export default {
  name: 'Dashboard',
  methods: {
    logoutUser() {
      // Clear user session/token (e.g., from localStorage)
      localStorage.removeItem('userToken');
      alert('You have been logged out.');
      // Redirect to login page
      this.$router.push('/login');
    }
  },
  mounted() {
    // Example: Fetch user-specific data or check authentication
    // if (!localStorage.getItem('userToken')) {
    //   this.$router.push('/login');
    // }
  }
};
</script>

<style scoped>
.dashboard-container {
  max-width: 600px;
  margin: 50px auto;
  padding: 30px;
  text-align: center;
  background-color: #f9f9f9;
  border: 1px solid #eee;
  border-radius: 8px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
}
h2 {
  color: #333;
  margin-bottom: 20px;
}
p {
  color: #555;
  line-height: 1.6;
  margin-bottom: 10px;
}
.logout-button {
  margin-top: 20px;
  padding: 10px 20px;
  background-color: #d9534f;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}
.logout-button:hover {
  background-color: #c9302c;
}
</style>
