<script setup lang="ts">
/**
 * 应用根组件
 * 通过 el-config-provider 注入中文语言包，替代全局 app.use(ElementPlus)。
 */
import zhCn from 'element-plus/es/locale/lang/zh-cn'
</script>

<template>
  <el-config-provider :locale="zhCn">
    <router-view />
  </el-config-provider>
</template>
