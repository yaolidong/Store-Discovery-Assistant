<template>
  <div v-if="notifications.length > 0" class="notification-container">
    <div 
      v-for="notification in notifications" 
      :key="notification.id"
      :class="['notification', notification.type]"
      @click="removeNotification(notification.id)"
    >
      <div class="notification-icon">
        <span v-if="notification.type === 'success'">✓</span>
        <span v-else-if="notification.type === 'error'">✗</span>
        <span v-else-if="notification.type === 'warning'">⚠</span>
        <span v-else>ℹ</span>
      </div>
      <div class="notification-content">
        <div class="notification-title" v-if="notification.title">{{ notification.title }}</div>
        <div class="notification-message">{{ notification.message }}</div>
      </div>
      <div class="notification-close">&times;</div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'Notification',
  data() {
    return {
      notifications: []
    };
  },
  methods: {
    show(message, type = 'info', title = '', duration = 4000) {
      const id = Date.now();
      const notification = { id, message, type, title };
      
      this.notifications.push(notification);
      
      if (duration > 0) {
        setTimeout(() => {
          this.removeNotification(id);
        }, duration);
      }
      
      return id;
    },
    
    removeNotification(id) {
      const index = this.notifications.findIndex(n => n.id === id);
      if (index > -1) {
        this.notifications.splice(index, 1);
      }
    },
    
    success(message, title = '成功') {
      return this.show(message, 'success', title);
    },
    
    error(message, title = '错误') {
      return this.show(message, 'error', title, 6000);
    },
    
    warning(message, title = '警告') {
      return this.show(message, 'warning', title, 5000);
    },
    
    info(message, title = '提示') {
      return this.show(message, 'info', title);
    }
  }
};
</script>

<style scoped>
.notification-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 10000;
  width: 320px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.notification {
  background-color: #fff;
  color: #333;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  display: flex;
  align-items: flex-start;
  padding: 15px;
  cursor: pointer;
  transition: all 0.3s ease;
  border-left: 5px solid #666;
}

.notification:hover {
  box-shadow: 0 6px 16px rgba(0,0,0,0.2);
  transform: translateY(-2px);
}

.notification.success { border-color: #4CAF50; }
.notification.error { border-color: #F44336; }
.notification.warning { border-color: #FFC107; }
.notification.info { border-color: #2196F3; }

.notification-icon {
  margin-right: 15px;
  font-size: 24px;
  line-height: 1;
}

.notification.success .notification-icon { color: #4CAF50; }
.notification.error .notification-icon { color: #F44336; }
.notification.warning .notification-icon { color: #FFC107; }
.notification.info .notification-icon { color: #2196F3; }

.notification-content {
  flex-grow: 1;
}

.notification-title {
  font-weight: bold;
  margin-bottom: 5px;
}

.notification-message {
  font-size: 14px;
  line-height: 1.4;
}

.notification-close {
  font-size: 20px;
  color: #aaa;
  align-self: flex-start;
  line-height: 0.8;
  padding-left: 10px;
}

.notification-close:hover {
  color: #333;
}
</style> 