import { createRouter, createWebHistory } from 'vue-router';
import Login from '../views/auth/Login.vue';
import Register from '../views/auth/Register.vue';
import Pending from '../views/Pending.vue';
import UserLayout from '../layouts/UserLayout.vue';
import UserDashboard from '../views/user/Dashboard.vue';
import UserBooking from '../views/user/Booking.vue';
import UserReservations from '../views/user/Reservations.vue';
import UserScenarios from '../views/user/Scenarios.vue';
import UserProfile from '../views/user/Profile.vue';
import { isLoggedIn, isAdmin, useAuth } from '../composables/useAuth.js';

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', name: 'login', component: Login },
  { path: '/register', name: 'register', component: Register },

  {
    path: '/user',
    component: UserLayout,
    children: [
      { path: 'dashboard', component: UserDashboard },
      { path: 'booking', component: UserBooking },
      { path: 'reservations', component: UserReservations },
      { path: 'scenarios', component: UserScenarios },
      { path: 'profile', component: UserProfile },
    ],
  },

  {
    path: '/merchant',
    children: [
      { path: 'dashboard', component: Pending, props: { title: '数据概览' } },
      { path: 'bookings', component: Pending, props: { title: '预约管理' } },
      { path: 'resources', component: Pending, props: { title: '资源管理' } },
      { path: 'rules', component: Pending, props: { title: '预约规则' } },
      { path: 'scenarios', component: Pending, props: { title: '预约场景' } },
      { path: 'profile', component: Pending, props: { title: '个人中心' } },
    ],
  },

  { path: '/:pathMatch(.*)*', redirect: '/login' },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to) => {
  const auth = useAuth();
  const logged = isLoggedIn();

  if (to.path === '/login' || to.path === '/register') {
    if (logged && auth.user) {
      return auth.user.role === 'admin' ? '/merchant/dashboard' : '/user/dashboard';
    }
    return true;
  }

  if (!logged) return '/login';

  if (to.path.startsWith('/merchant') && !isAdmin()) {
    return '/user/dashboard';
  }

  return true;
});

export default router;
