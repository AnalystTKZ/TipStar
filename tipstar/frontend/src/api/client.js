import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// Posts
export const getPendingPosts  = () => api.get('/posts/pending')
export const getApprovedPosts = () => api.get('/posts/approved')
export const getPostHistory   = () => api.get('/posts/history')
export const approvePost      = (id) => api.patch(`/posts/${id}/approve`)
export const rejectPost       = (id) => api.patch(`/posts/${id}/reject`)
export const editPost         = (id, content) => api.patch(`/posts/${id}/edit`, { content })
export const deletePost       = (id) => api.delete(`/posts/${id}`)

// News
export const getNewsFeed   = (page = 1, size = 20) => api.get('/news', { params: { page, size } })
export const getNewsDetail = (id) => api.get(`/news/${id}`)

// Knowledge Base
export const getPlayers    = () => api.get('/players')
export const getPlayer     = (id) => api.get(`/players/${id}`)
export const createPlayer  = (data) => api.post('/players', data)
export const updatePlayer  = (id, data) => api.patch(`/players/${id}`, data)
export const syncPlayers   = () => api.post('/players/sync')
export const scrapePlayer  = (data) => api.post('/players/scrape', data)

export const getTeams      = () => api.get('/teams')
export const getTeam       = (id) => api.get(`/teams/${id}`)
export const createTeam    = (data) => api.post('/teams', data)
export const updateTeam    = (id, data) => api.patch(`/teams/${id}`, data)
export const syncTeams     = () => api.post('/teams/sync')
export const scrapeTeam    = (data) => api.post('/teams/scrape', data)

export const getMatches    = () => api.get('/matches')
export const getMatch      = (id) => api.get(`/matches/${id}`)
export const createMatch   = (data) => api.post('/matches', data)

export const getDrama      = () => api.get('/drama')
export const getDramaItem  = (id) => api.get(`/drama/${id}`)
export const createDrama   = (data) => api.post('/drama', data)

// Analytics
export const getAnalyticsSummary  = () => api.get('/analytics/summary')
export const getPostsOverTime     = () => api.get('/analytics/posts')
export const getCoverageRatio     = () => api.get('/analytics/coverage')
export const getPostTypeBreakdown = () => api.get('/analytics/types')
export const getTopPlayers        = () => api.get('/analytics/players')

export default api
