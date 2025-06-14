import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000'; // Ensure this matches your backend URL

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getSubscriptions = async () => {
  const response = await api.get('/subscriptions');
  return response.data;
};

export const addSubscription = async (subscriptionData) => {
  const response = await api.post('/subscriptions', subscriptionData);
  return response.data;
};

export const deleteSubscription = async (id) => {
  await api.delete(`/subscriptions/${id}`);
};

export const getAllPosts = async () => {
  const response = await api.get('/posts');
  return response.data;
};

export const fetchPostsForSubscription = async (subscriptionId) => {
  const response = await api.post(`/posts/fetch_and_store/${subscriptionId}`);
  return response.data;
};