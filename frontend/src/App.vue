<script setup>
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <header>
    <nav>
      <RouterLink to="/">Home</RouterLink>
      <RouterLink to="/subscriptions">Subscriptions</RouterLink>
    </nav>
  </header>

  <main>
    <RouterView />
  </main>
</template>

<style scoped>
header {
  line-height: 1.5;
  max-height: 100vh;
  padding: 20px;
  background-color: #f8f8f8;
  border-bottom: 1px solid #eee;
  text-align: center;
}

nav {
  width: 100%;
  font-size: 1rem;
  text-align: center;
  margin-top: 1rem;
}

nav a {
  display: inline-block;
  padding: 0 1rem;
  border-left: 1px solid var(--color-border);
  text-decoration: none;
  color: #333;
}

nav a.router-link-exact-active {
  color: #007bff; /* Highlight active link */
  font-weight: bold;
}

nav a:first-of-type {
  border: 0;
}

main {
  padding: 20px;
}
</style>