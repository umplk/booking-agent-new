import { createApp } from 'vue';
import './styles/global.css';
import App from './App.vue';
import router from './router/index.js';
import { restoreSession } from './composables/useAuth.js';

const app = createApp(App);
app.use(router);

restoreSession().finally(() => {
  app.mount('#app');
});
