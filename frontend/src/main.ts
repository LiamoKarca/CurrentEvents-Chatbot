import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')

// 前端更新時，需要重新部署到 Firebase Hosting
// % cd/frontend
// % yarn install
// % yarn run build
// % firebase deploy --only hosting