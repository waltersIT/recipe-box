import type {
  Attachment,
  ImportConfig,
  ImportResult,
  Recipe,
  RecipeInput,
  RecipeSummary,
  TagCount,
} from './types'

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

function firstFieldError(data: unknown): string | null {
  if (!data || typeof data !== 'object') return null
  for (const [field, value] of Object.entries(data)) {
    const message = Array.isArray(value) ? value[0] : value
    if (typeof message === 'string') return field === 'non_field_errors' ? message : `${field}: ${message}`
  }
  return null
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, init)
  } catch {
    throw new ApiError("Can't reach the Recipe Box server. Is the backend running?", 0)
  }
  if (!response.ok) {
    let message = `Something went wrong (HTTP ${response.status}).`
    try {
      const data = await response.json()
      message = (typeof data.detail === 'string' && data.detail) || firstFieldError(data) || message
    } catch {
      if (response.status >= 500) message = 'The server hit an error. Check the backend logs.'
    }
    throw new ApiError(message, response.status)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

function sendJson(method: string, body: unknown): RequestInit {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
}

function sendFiles(field: string, files: File[]): RequestInit {
  const form = new FormData()
  for (const file of files) form.append(field, file)
  return { method: 'POST', body: form }
}

export interface RecipeQuery {
  search?: string
  tag?: string
  favorite?: boolean
  ordering?: string
}

export const api = {
  listRecipes(query: RecipeQuery = {}) {
    const params = new URLSearchParams()
    if (query.search) params.set('search', query.search)
    if (query.tag) params.set('tag', query.tag)
    if (query.favorite) params.set('favorite', '1')
    if (query.ordering) params.set('ordering', query.ordering)
    return request<RecipeSummary[]>(`/recipes/?${params}`)
  },
  getRecipe: (id: number | string) => request<Recipe>(`/recipes/${id}/`),
  createRecipe: (data: RecipeInput) => request<Recipe>('/recipes/', sendJson('POST', data)),
  updateRecipe: (id: number | string, data: RecipeInput) => request<Recipe>(`/recipes/${id}/`, sendJson('PATCH', data)),
  deleteRecipe: (id: number | string) => request<void>(`/recipes/${id}/`, { method: 'DELETE' }),
  uploadImage: (id: number, file: File) => request<Recipe>(`/recipes/${id}/image/`, sendFiles('image', [file])),
  deleteImage: (id: number) => request<Recipe>(`/recipes/${id}/image/`, { method: 'DELETE' }),
  uploadAttachments: (id: number, files: File[]) =>
    request<Attachment[]>(`/recipes/${id}/attachments/`, sendFiles('file', files)),
  deleteAttachment: (recipeId: number, attachmentId: number) =>
    request<void>(`/recipes/${recipeId}/attachments/${attachmentId}/`, { method: 'DELETE' }),
  tags: () => request<TagCount[]>('/tags/'),
  importConfig: () => request<ImportConfig>('/import/config/'),
  importUrl: (url: string) => request<ImportResult>('/import/url/', sendJson('POST', { url })),
  importHtml: (url: string, html: string) => request<ImportResult>('/import/html/', sendJson('POST', { url, html })),
  importFiles: (files: File[]) => request<ImportResult>('/import/files/', sendFiles('files', files)),
}
