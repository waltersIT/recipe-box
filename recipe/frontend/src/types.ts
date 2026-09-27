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
  is_favorite: boolean
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
  is_favorite: boolean
  tags: string[]
  source_name: string
  created_at: string
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
  is_favorite?: boolean
  import_method?: ImportMethod
  /** A remote photo (from an import) for the server to download. */
  image_url?: string
}
