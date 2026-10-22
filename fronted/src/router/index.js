import { createRouter, createWebHistory } from 'vue-router';
import Login from '../views/auth/Login.vue';
import Register from '../views/auth/Register.vue';
import UserLayout from '../layouts/UserLayout.vue';
import UserDashboard from '../views/user/Dashboard.vue';
import UserBooking from '../views/user/Booking.vue';
import UserReservations from '../views/user/Reservations.vue';
import UserScenarios from '../views/user/Scenarios.vue';
import UserProfile from '../views/user/Profile.vue';
import MerchantLayout from '../layouts/MerchantLayout.vue';
import MerchantDashboard from '../views/merchant/Dashboard.vue';
import MerchantBookings from '../views/merchant/Bookings.vue';
import MerchantResources from '../views/merchant/Resources.vue';
import MerchantRules from '../views/merchant/Rules.vue';
import MerchantScenarios from '../views/merchant/Scenarios.vue';
import MerchantProfile from '../views/merchant/Profile.vue';
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
    component: MerchantLayout,
    children: [
      { path: 'dashboard', component: MerchantDashboard },
      { path: 'bookings', component: MerchantBookings },
      { path: 'resources', component: MerchantResources },
      { path: 'rules', component: MerchantRules },
      { path: 'scenarios', component: MerchantScenarios },
      { path: 'profile', component: MerchantProfile },
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
