import axios from 'axios'

const api = axios.create({
  baseURL: 'http://127.0.0.1:8000',
  timeout: 30000,
})

export async function analyze(payload: any) {
  const { data } = await api.post('/api/analyze', payload)
  return data
}

export async function importCmbl(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await api.post('/api/import-cmbl', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function exportCmbl(payload: any) {
  const { data } = await api.post('/api/export-cmbl', payload)
  return data
}