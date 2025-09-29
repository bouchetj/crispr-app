import axios from 'axios'

export const apiBase = import.meta.env.VITE_API_URL ?? ''
export const api = axios.create({ baseURL: apiBase })

export async function post<T>(url: string, data: any): Promise<T> {
  const res = await api.post<T>(url, data)
  return res.data
}
export async function get<T>(url: string): Promise<T> {
  const res = await api.get<T>(url)
  return res.data
}
