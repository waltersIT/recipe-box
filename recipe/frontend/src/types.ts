export type ImportMethod = 'manual' | 'url' | 'browser' | 'pdf' | 'image'
export type Parser = 'schema.org' | 'claude' | 'text'

export interface RecipeFields {
  title: string
  description: string
  /** One item per line; items starting with "# " are section headings. */
  ingredients: string[]
  instructions: string[]
  notes: string
  servings: string
  prep_time: number | null
  cook_time: number | null
  total_time: number | null
  source_url: string
  source_name: string
  author: string
  tags: string[]
  nutrition: Record<string, string>
}

export interface UserBrief {
  username: string
  name: string
  avatar: string | null
}

export interface Profile extends UserBrief {
  display_name: string
  bio: string
  recipe_count: number
  follower_count: number
  following_count: number
  is_following: boolean
  is_me: boolean
  created_at: string
}

export interface Me {
  username: string
  email: string
  profile: Profile
}

export interface Comment {
  id: number
  author: UserBrief
  body: string
  /** The comment this answers; null for a top-level one. Threads are one deep. */
  parent: number | null
  /** Only ever filled in on a top-level comment. */
  replies: Comment[]
  edited: boolean
  edited_at: string | null
  /** Whether the person reading may rewrite it (its author). */
  can_edit: boolean
  /** Its author, and the owner of the recipe it's on. */
  can_delete: boolean
  created_at: string
}

export interface Attachment {
  id: number
  url: string
  original_name: string
  content_type: string
  created_at: string
}

export interface Recipe extends RecipeFields {
  id: number
  image: string | null
  rating: number
  like_count: number
  view_count: number
  /** Whether the person reading has liked it. */
  liked: boolean
  owner: UserBrief | null
  import_method: ImportMethod
  attachments: Attachment[]
  created_at: string
  updated_at: string
}

export interface RecipeSummary {
  id: number
  title: string
  image: string | null
  total_time: number | null
  prep_time: number | null
  cook_time: number | null
  servings: string
  rating: number
  like_count: number
  view_count: number
  liked: boolean
  owner: UserBrief | null
  tags: string[]
  source_name: string
  created_at: string
}

export interface HomeFeed {
  /** Recipes from the people you follow, newest first. */
  following: RecipeSummary[]
  following_count: number
  /** Most viewed and liked. */
  recommended: RecipeSummary[]
  recipe_count: number
}

export interface LikeResult {
  id: number
  like_count: number
  liked: boolean
}

export interface RecipeDraft extends RecipeFields {
  image_url: string
}

export interface ImportResult {
  draft: RecipeDraft
  method: ImportMethod
  parser: Parser
  warnings: string[]
}

export interface ImportConfig {
  llm_enabled: boolean
  llm_model: string | null
  ocr_engine: string | null
  max_files: number
  max_file_mb: number
}

export interface TagCount {
  name: string
  count: number
}

export type RecipeInput = Partial<RecipeFields> & {
  rating?: number
  import_method?: ImportMethod
  /** A remote photo (from an import) for the server to download. */
  image_url?: string
}
