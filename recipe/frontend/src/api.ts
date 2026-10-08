import type {
  Attachment,
  Comment,
  HomeFeed,
  ImportConfig,
  ImportResult,
  LikeResult,
  Me,
  Profile,
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

function cookie(name: string): string {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : ''
}

/** Django sets the CSRF cookie on the first GET; unsafe requests echo it back. */
async function csrfToken(): Promise<string> {
  const token = cookie('csrftoken')
  if (token) return token
  await fetch('/api/auth/me/', { credentials: 'same-origin' })
  return cookie('csrftoken')
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = init?.method ?? 'GET'
  const options: RequestInit = { credentials: 'same-origin', ...init }
  if (method !== 'GET' && method !== 'HEAD') {
    options.headers = { ...init?.headers, 'X-CSRFToken': await csrfToken() }
  }
  let response: Response
  try {
    response = await fetch(`/api${path}`, options)
  } catch {
    throw new ApiError("Can't reach the Recipe Box server. Is the backend running?", 0)
  }
  if (!response.ok) {
    let message =
      response.status === 403
        ? 'You need to be signed in to do that.'
        : `Something went wrong (HTTP ${response.status}).`
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
  /** Only recipes you've liked. */
  liked?: boolean
  /** Only recipes you uploaded. */
  mine?: boolean
  /** Only recipes from the people you follow. */
  following?: boolean
  /** Only recipes uploaded by this username. */
  user?: string
  ordering?: string
}

export const api = {
  listRecipes(query: RecipeQuery = {}) {
    const params = new URLSearchParams()
    if (query.search) params.set('search', query.search)
    if (query.tag) params.set('tag', query.tag)
    if (query.liked) params.set('liked', '1')
    if (query.mine) params.set('mine', '1')
    if (query.following) params.set('following', '1')
    if (query.user) params.set('user', query.user)
    if (query.ordering) params.set('ordering', query.ordering)
    return request<RecipeSummary[]>(`/recipes/?${params}`)
  },
  home: () => request<HomeFeed>('/home/'),
  getRecipe: (id: number | string) => request<Recipe>(`/recipes/${id}/`),
  comments: (recipeId: number | string) => request<Comment[]>(`/recipes/${recipeId}/comments/`),
  addComment: (recipeId: number, body: string, parent?: number) =>
    request<Comment>(`/recipes/${recipeId}/comments/`, sendJson('POST', { body, parent: parent ?? null })),
  updateComment: (id: number, body: string) => request<Comment>(`/comments/${id}/`, sendJson('PATCH', { body })),
  deleteComment: (id: number) => request<void>(`/comments/${id}/`, { method: 'DELETE' }),
  like: (id: number, liked: boolean) =>
    request<LikeResult>(`/recipes/${id}/like/`, { method: liked ? 'POST' : 'DELETE' }),
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

  // --- Accounts ---
  me: () => request<Me | null>('/auth/me/'),
  register: (data: {
    username: string
    password: string
    email?: string
    display_name?: string
    accept_terms: boolean
  }) =>
    request<Me>('/auth/register/', sendJson('POST', data)),
  login: (username: string, password: string) => request<Me>('/auth/login/', sendJson('POST', { username, password })),
  logout: () => request<void>('/auth/logout/', { method: 'POST' }),
  updateProfile: (data: { display_name?: string; bio?: string }) => request<Me>('/users/me/', sendJson('PATCH', data)),
  deleteAccount: (password: string) => request<void>('/users/me/', sendJson('DELETE', { password })),
  uploadAvatar: (file: File) => request<Me>('/users/me/avatar/', sendFiles('avatar', [file])),
  deleteAvatar: () => request<Me>('/users/me/avatar/', { method: 'DELETE' }),
  profile: (username: string) => request<Profile>(`/users/${encodeURIComponent(username)}/`),
  profileRecipes: (username: string, ordering?: string) =>
    request<RecipeSummary[]>(`/users/${encodeURIComponent(username)}/recipes/?ordering=${ordering ?? ''}`),
  follow: (username: string, following: boolean) =>
    request<Profile>(`/users/${encodeURIComponent(username)}/follow/`, { method: following ? 'POST' : 'DELETE' }),
  following: (username: string) => request<Profile[]>(`/users/${encodeURIComponent(username)}/following/`),
  followers: (username: string) => request<Profile[]>(`/users/${encodeURIComponent(username)}/followers/`),
  importConfig: () => request<ImportConfig>('/import/config/'),
  importUrl: (url: string) => request<ImportResult>('/import/url/', sendJson('POST', { url })),
  importHtml: (url: string, html: string) => request<ImportResult>('/import/html/', sendJson('POST', { url, html })),
  importFiles: (files: File[]) => request<ImportResult>('/import/files/', sendFiles('files', files)),
}
