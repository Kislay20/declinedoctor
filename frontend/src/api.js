import axios from 'axios';

const api = axios.create({
  baseURL: 'http://127.0.0.1:8000/api',
});

// Attach role-aware authorization header to every request
api.interceptors.request.use((config) => {
  const role = localStorage.getItem('declinedoctor_user_role') || 'OPERATOR';
  config.headers['X-User-Role'] = role;
  return config;
});

export default api;