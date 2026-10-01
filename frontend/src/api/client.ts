import axios from "axios";

// Locally the Vite dev server proxies /api to the backend. In production the
// frontend and backend live on different hosts, so the build is given the
// backend's address through VITE_API_BASE_URL (e.g. https://api.example.com/api).
const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("campusone_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err?.response?.status === 401) {
      localStorage.removeItem("campusone_token");
      localStorage.removeItem("campusone_user");
      if (!window.location.pathname.includes("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);

export default client;
