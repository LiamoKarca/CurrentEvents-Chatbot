// Import the functions you need from the SDKs you need
import { initializeApp } from "firebase/app";
import { getAnalytics } from "firebase/analytics";
import { connectAuthEmulator } from "firebase/auth";

// TODO: Add SDKs for Firebase products that you want to use
// https://firebase.google.com/docs/web/setup#available-libraries

// Your web app's Firebase configuration
// For Firebase JS SDK v7.20.0 and later, measurementId is optional
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID,
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const analytics = getAnalytics(app);

// 開始設置 GoogleAuthProvider
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut,
  sendEmailVerification,
  type User,
} from "firebase/auth";

export const auth = getAuth(app);
auth.useDeviceLanguage();
export const googleProvider = new GoogleAuthProvider();

export default app;

const hostedLoginUrl = import.meta.env.VITE_HOSTED_LOGIN_URL as string | undefined;

const fallbackUrl =
  (import.meta.env.VITE_FIREBASE_EMAIL_CONTINUE_URL as string | undefined) ||
  hostedLoginUrl ||
  (typeof window !== "undefined" ? `${window.location.origin}/login` : undefined);

const verificationActionSettings = fallbackUrl ? { url: fallbackUrl } : undefined;

// 使用 Google 帳號登入。
export function signInWithGoogle() {
  return signInWithPopup(auth, googleProvider);
}

// 使用電子郵件登入。
export function signInWithEmail(email: string, password: string) {
  return signInWithEmailAndPassword(auth, email, password);
}


// 使用電子郵件註冊新帳號。
export function registerWithEmail(email: string, password: string) {
  return createUserWithEmailAndPassword(auth, email, password);
}

// 登出目前使用者。
export function logout() {
  return signOut(auth);
}

// 傳送驗證電子郵件（非 gmail 註冊或登入的使用者）
export function sendVerificationEmail(user?: User | null) {
  const target = user ?? auth.currentUser;
  if (!target) {
    return Promise.reject(new Error("尚未登入使用者"));
  }
  if (verificationActionSettings) {
    return sendEmailVerification(target, verificationActionSettings);
  }
  return sendEmailVerification(target);
}


// 如果在本地開發環境中，連接到 Auth Emulator。
if (import.meta.env.VITE_USE_AUTH_EMULATOR === "true") {
  connectAuthEmulator(auth, "http://localhost:9099", { disableWarnings: true });
}