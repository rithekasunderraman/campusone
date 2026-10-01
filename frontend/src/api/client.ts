import axios from "axios";

const client = axios.create({
  baseURL: "/api",
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
