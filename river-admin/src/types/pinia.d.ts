import type { PersistedStateOptions } from 'pinia-plugin-persistedstate'

declare module 'pinia' {
  export interface DefineStoreOptionsBase<S extends StateTree, Store> {
    /** 持久化配置，配合 pinia-plugin-persistedstate 使用 */
    persist?: boolean | PersistedStateOptions
  }
}
