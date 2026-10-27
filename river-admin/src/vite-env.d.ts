/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 是否启用内置 mock 服务，默认 true */
  readonly VITE_USE_MOCK?: string
  /** 接口基础路径 */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
