<!-- 此视图将显示获取的帖子。 -->
<script setup>
import { ref, onMounted } from 'vue';
import { getAllPosts } from '@/api';

const posts = ref([]);

const loadPosts = async () => {
  posts.value = await getAllPosts();
};

const formatDate = (dateString) => {
  return new Date(dateString).toLocaleString();
};

onMounted(loadPosts);
</script>

<template>
  <div class="home-view">
    <h1>Your RSS Feed</h1>
    <button @click="loadPosts">Refresh Posts</button>

    <div class="post-list" v-if="posts.length">
      <div class="post-item" v-for="post in posts" :key="post.id">
        <h2><a :href="post.link" target="_blank">{{ post.title }}</a></h2>
        <p class="meta">
          By {{ post.user_name }} on {{ post.platform }} at {{ formatDate(post.published_at) }}
        </p>
        <p class="content">{{ post.content }}</p>
      </div>
    </div>
    <p v-else>No posts to display yet. Add subscriptions and fetch posts!</p>
  </div>
</template>

<style scoped>
.home-view {
  max-width: 900px;
  margin: 20px auto;
  padding: 20px;
  border: 1px solid #eee;
  border-radius: 8px;
}
.post-list {
  margin-top: 20px;
}
.post-item {
  margin-bottom: 20px;
  padding: 15px;
  border: 1px solid #ddd;
  border-radius: 5px;
  background-color: #f9f9f9;
}
.post-item h2 {
  margin-top: 0;
  font-size: 1.2em;
}
.post-item h2 a {
  text-decoration: none;
  color: #007bff;
}
.post-item h2 a:hover {
  text-decoration: underline;
}
.post-item .meta {
  font-size: 0.85em;
  color: #666;
  margin-bottom: 10px;
}
.post-item .content {
  line-height: 1.6;
  color: #333;
}
</style>