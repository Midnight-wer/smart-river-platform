import { reactive, ref } from 'vue'
import type { PageQuery, PageResult } from '@/types'

/**
 * 列表页通用逻辑：分页、关键字查询、加载状态与异常兜底
 * @param fetcher 数据请求方法，入参为分页查询条件
 */
export function useTable<T extends Record<string, any>>(
  fetcher: (query: PageQuery) => Promise<PageResult<T>>,
  defaultQuery: Record<string, unknown> = {},
) {
  const loading = ref(false)
  const list = ref<T[]>([])
  const total = ref(0)

  const query = reactive<PageQuery>({
    page: 1,
    pageSize: 10,
    keyword: '',
    ...defaultQuery,
  })

  /** 加载数据，异常时保持列表为空并记录日志 */
  async function load(): Promise<void> {
    loading.value = true
    try {
      const result = await fetcher({ ...query })
      list.value = result?.list ?? []
      total.value = result?.total ?? 0
    } catch (error) {
      console.error('[useTable] 数据加载失败', error)
      list.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  /** 条件查询（回到第一页） */
  function search(): Promise<void> {
    query.page = 1
    return load()
  }

  /** 重置查询条件 */
  async function reset(): Promise<void> {
    Object.keys(query).forEach((key) => {
      if (key === 'page' || key === 'pageSize') return
      query[key] = ''
    })
    query.page = 1
    await load()
  }

  /** 切换页码 */
  function changePage(page: number): Promise<void> {
    query.page = page
    return load()
  }

  /** 切换每页条数 */
  function changePageSize(size: number): Promise<void> {
    query.pageSize = size
    query.page = 1
    return load()
  }

  /** 刷新当前页 */
  function refresh(): Promise<void> {
    return load()
  }

  return { loading, list, total, query, load, search, reset, changePage, changePageSize, refresh }
}
