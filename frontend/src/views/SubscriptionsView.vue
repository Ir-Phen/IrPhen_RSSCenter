<!-- 此视图将处理添加、查看和删除订阅。 -->
<script setup>
import { ref, onMounted } from 'vue';
import { getSubscriptions, addSubscription, deleteSubscription, fetchPostsForSubscription } from '@/api';

const subscriptions = ref([]);
const newSubscription = ref({
  platform: '',
  user_id: '',
  user_name: '',
  category: 'Default',
});

const loadSubscriptions = async () => {
  subscriptions.value = await getSubscriptions();
};

const handleAddSubscription = async () => {
  if (newSubscription.value.platform && newSubscription.value.user_id) {
    await addSubscription(newSubscription.value);
    newSubscription.value = { platform: '', user_id: '', user_name: '', category: 'Default' };
    await loadSubscriptions(); // Refresh list
  }
};

const handleDeleteSubscription = async (id) => {
  await deleteSubscription(id);
  await loadSubscriptions(); // Refresh list
};

const handleFetchPosts = async (subscriptionId) => {
  try {
    await fetchPostsForSubscription(subscriptionId);
    alert('Posts fetched successfully!');
  } catch (error) {
    alert('Error fetching posts: ' + error.message);
  }
};

onMounted(loadSubscriptions);
</script>

<template>
  <div class="subscriptions-view">
    <h1>Manage Subscriptions</h1>

    <div class="add-subscription">
      <h2>Add New Subscription</h2>
      <form @submit.prevent="handleAddSubscription">
        <input v-model="newSubscription.platform" placeholder="Platform (e.g., bilibili)" required />
        <input v-model="newSubscription.user_id" placeholder="User ID" required />
        <input v-model="newSubscription.user_name" placeholder="User Name (optional)" />
        <button type="submit">Add Subscription</button>
      </form>
    </div>

    <div class="current-subscriptions">
      <h2>Your Subscriptions</h2>
      <ul v-if="subscriptions.length">
        <li v-for="sub in subscriptions" :key="sub.id">
          {{ sub.user_name || sub.user_id }} ({{ sub.platform }}) - {{ sub.category }}
          <button @click="handleFetchPosts(sub.id)">Fetch Now</button>
          <button @click="handleDeleteSubscription(sub.id)">Delete</button>
        </li>
      </ul>
      <p v-else>No subscriptions yet. Add one above!</p>
    </div>
  </div>
</template>

<style scoped>
.subscriptions-view {
  max-width: 800px;
  margin: 20px auto;
  padding: 20px;
  border: 1px solid #eee;
  border-radius: 8px;
}
.add-subscription, .current-subscriptions {
  margin-bottom: 30px;
  padding: 15px;
  border: 1px solid #ddd;
  border-radius: 5px;
}
input {
  margin-right: 10px;
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
}
button {
  padding: 8px 12px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  margin-left: 5px;
}
button:hover {
  background-color: #0056b3;
}
ul {
  list-style: none;
  padding: 0;
}
li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px dashed #eee;
}
li:last-child {
  border-bottom: none;
}
</style>