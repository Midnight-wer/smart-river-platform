<script setup lang="ts">
/**
 * 登录页
 */
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Lock, User } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  username: 'admin',
  password: '',
  remember: true,
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 32, message: '用户名长度为 2 ~ 32 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 32, message: '密码长度为 6 ~ 32 个字符', trigger: 'blur' },
  ],
}

/** 演示账号 */
const demoAccounts = [
  { username: 'admin', label: '超级管理员' },
  { username: 'province', label: '省级河长' },
  { username: 'city', label: '市级河长' },
  { username: 'county', label: '县级河长' },
  { username: 'town', label: '乡镇级河长' },
]

function useDemoAccount(username: string): void {
  form.username = username
  form.password = '123456'
}

async function handleSubmit(): Promise<void> {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await userStore.loginAction({ username: form.username, password: form.password, remember: form.remember })
    ElMessage.success('登录成功，欢迎使用智河通平台')
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.replace(redirect)
  } catch (error) {
    console.error('[login] 登录失败', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (userStore.isLogin) {
    router.replace('/dashboard')
  }
})
</script>

<template>
  <div class="rv-login">
    <div class="rv-login__bg" />
    <div class="rv-login__panel">
      <div class="rv-login__brand">
        <span class="rv-login__mark">智</span>
        <div>
          <h1 class="rv-login__name">智河通</h1>
          <p class="rv-login__slogan">智慧河长协同治理平台</p>
        </div>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" size="large" @keyup.enter="handleSubmit">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" :prefix-icon="User" clearable />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            show-password
            clearable
          />
        </el-form-item>

        <div class="rv-login__options">
          <el-checkbox v-model="form.remember">记住登录状态</el-checkbox>
          <el-link type="primary" @click="ElMessage.info('请联系系统管理员重置密码')">
            忘记密码？
          </el-link>
        </div>

        <el-button type="primary" class="rv-login__submit" :loading="loading" @click="handleSubmit">
          登 录
        </el-button>
      </el-form>

      <div class="rv-login__demo">
        <span class="rv-login__demo-label">演示账号（密码均为 123456）</span>
        <div class="rv-login__demo-list">
          <el-tag
            v-for="item in demoAccounts"
            :key="item.username"
            class="rv-login__demo-tag"
            effect="plain"
            @click="useDemoAccount(item.username)"
          >
            {{ item.label }}
          </el-tag>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.rv-login {
  position: relative;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: linear-gradient(135deg, #0b2557 0%, #123a7d 45%, #1d4ed8 100%);
}

.rv-login__bg {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(circle at 20% 30%, rgba(96, 165, 250, 0.35), transparent 45%),
    radial-gradient(circle at 80% 70%, rgba(37, 99, 235, 0.35), transparent 45%);
  pointer-events: none;
}

.rv-login__panel {
  position: relative;
  width: 400px;
  padding: 34px 36px 28px;
  background: rgba(255, 255, 255, 0.97);
  border-radius: 16px;
  box-shadow: 0 24px 60px rgba(2, 12, 40, 0.4);
}

.rv-login__brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 26px;
}

.rv-login__mark {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  color: #fff;
  font-size: 20px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.rv-login__name {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: var(--rv-text);
  letter-spacing: 2px;
}

.rv-login__slogan {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--rx-text-secondary, var(--rv-text-secondary));
}

.rv-login__options {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: -6px 0 18px;
}

.rv-login__submit {
  width: 100%;
  letter-spacing: 6px;
  font-weight: 600;
}

.rv-login__demo {
  margin-top: 22px;
  padding-top: 16px;
  border-top: 1px dashed var(--rv-border);
}

.rv-login__demo-label {
  font-size: 12px;
  color: var(--rv-text-secondary);
}

.rv-login__demo-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.rv-login__demo-tag {
  cursor: pointer;
}
</style>
