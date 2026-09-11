import { defineStore } from 'pinia'
import { callApi } from '../api/cloud'

export const useSnap = defineStore('snap', {
  state: () => ({
    loading: false,
    error: '',
    snap: null,
    updatedAt: '',
    prevCoreCodes: null, // 昨日核心池代码集合（用于"新晋"信号，不覆盖当前快照）
  }),
  getters: {
    date: (s) => (s.snap && s.snap.date) || '',
    market: (s) => (s.snap && s.snap.market) || [],
    sentiment: (s) => (s.snap && s.snap.sentiment) || null,
    series: (s) => (s.snap && s.snap.series) || [],
    cycle: (s) => (s.snap && s.snap.cycle) || null,
    cores: (s) => (s.snap && s.snap.cores) || [],
    themes: (s) => (s.snap && s.snap.themes) || [],
    actions: (s) => (s.snap && s.snap.actions) || null,
    // 分析系统·实验室（Lab）：价值框架蒸馏 × 当日候选池（题材成分∪核心池）
    lab: (s) => (s.snap && s.snap.lab) || null,
    // 双线粘合突破（MA7/MA21）形态扫描：候选池同 Lab（涨停∪核心池）
    pattern: (s) => (s.snap && s.snap.pattern) || null,
    // 首板（连板==1，更前置的"刚启动"信号）：按首封时间升序
    firstboards: (s) => (s.snap && s.snap.firstboards) || [],
    firstboardsIndustries: (s) => (s.snap && s.snap.firstboards_industry) || [],
    // 新晋：在今日核心池、但不在昨日核心池
    freshCodes: (s) => {
      if (!s.prevCoreCodes || !s.snap || !s.snap.cores) return new Set()
      const today = new Set(s.snap.cores.map((c) => c.code))
      const fresh = new Set()
      today.forEach((code) => {
        if (!s.prevCoreCodes.has(code)) fresh.add(code)
      })
      return fresh
    },
  },
  actions: {
    async load(date) {
      this.loading = true
      this.error = ''
      try {
        const r = await callApi(date ? 'day' : 'latest', date ? { date } : {})
        if (r && r.ok && r.snapshot) {
          this.snap = r.snapshot
          this.updatedAt = new Date().toLocaleTimeString('zh-CN', { hour12: false })
        } else {
          this.error = (r && r.error) || '加载失败'
        }
      } catch (e) {
        this.error = e.message || String(e)
      } finally {
        this.loading = false
      }
    },
    async refresh(date) {
      this.loading = true
      this.error = ''
      try {
        const r = await callApi('refresh', date ? { date } : {})
        if (r && r.ok) await this.load(r.date)
        else this.error = (r && r.error) || '刷新失败'
      } catch (e) {
        this.error = e.message || String(e)
      } finally {
        this.loading = false
      }
    },
    // 取昨日核心池代码（仅用于"新晋"对比，不替换当前快照）；无昨日数据则置空
    async fetchPrevCores() {
      const today = this.date
      if (!today) return
      const y = new Date(Date.parse(today) - 86400000).toISOString().slice(0, 10)
      if (y === today) return
      try {
        const r = await callApi('day', { date: y })
        const cores = (r && r.ok && r.snapshot && r.snapshot.cores) || []
        this.prevCoreCodes = new Set(cores.map((c) => c.code))
      } catch {
        this.prevCoreCodes = null // 取不到不阻断，仅不显示新晋信号
      }
    },
  },
})
