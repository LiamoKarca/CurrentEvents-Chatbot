// frontend/src/config.ts
// 組件用的 API_BASE：若 .env 有設定就用；否則預設走 /api 交給開發代理
export const API_BASE = import.meta.env.VITE_API_BASE || '/api';
