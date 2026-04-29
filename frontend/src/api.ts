import axios from 'axios'

const baseURL = import.meta.env.DEV
  ? 'http://127.0.0.1:8000'
  : 'https://graphtool-bk.ruiyuan.me/'

const api = axios.create({
  baseURL,
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

export async function exportRawTableDocx(payload: any) {
  const { data } = await api.post('/api/export-raw-table-docx', payload, {
    responseType: 'blob',
  })
  return data
}
