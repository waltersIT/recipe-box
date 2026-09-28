import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { timeAgo } from '../lib/format'
import type { Comment, Me } from '../types'
import Avatar from './Avatar'

/** The box you type a comment or a reply into. */
function CommentForm({
  user,
  value,
  onChange,
  onSubmit,
  onCancel,
  busy,
  placeholder,
  submitLabel,
  autoFocus,
}: {
  user: Me
  value: string
  onChange: (value: string) => void
  onSubmit: () => Promise<void>
  onCancel?: () => void
  busy: boolean
  placeholder: string
  submitLabel: string
  autoFocus?: boolean
}) {
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (value.trim()) await onSubmit()
  }

  return (
    <form className="comment-form" onSubmit={submit}>
      <Avatar user={user.profile} size={34} />
      <div>
        <textarea
          rows={value ? 3 : 2}
          maxLength={2000}
          placeholder={placeholder}
          aria-label={placeholder}
          value={value}
          autoFocus={autoFocus}
          // Pick up where the text left off, not in front of it.
          onFocus={(event) => event.currentTarget.setSelectionRange(value.length, value.length)}
          onChange={(event) => onChange(event.target.value)}
        />
        <div className="button-row">
          <button type="submit" className="button primary small" disabled={busy || !value.trim()}>
            {busy ? 'Posting…' : submitLabel}
          </button>
          {onCancel && (
            <button type="button" className="button small" disabled={busy} onClick={onCancel}>
              Cancel
            </button>
          )}
        </div>
      </div>
    </form>
  )
}

function CommentRow({
  comment,
  onSaved,
  onDeleted,
  onReply,
}: {
  comment: Comment
  onSaved: (updated: Comment) => void
  onDeleted: () => void
  /** Missing on a reply: a reply's Reply button belongs to its thread. */
  onReply?: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(comment.body)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!draft.trim()) return
    setBusy(true)
    setError('')
    try {
      onSaved(await api.updateComment(comment.id, draft.trim()))
      setEditing(false)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    const replies = comment.replies.length
    const question = replies
      ? `Delete this comment and its ${replies} ${replies === 1 ? 'reply' : 'replies'}?`
      : 'Delete this comment?'
    if (!confirm(question)) return
    setBusy(true)
    try {
      await api.deleteComment(comment.id)
      onDeleted()
    } catch (err) {
      setError((err as Error).message)
      setBusy(false)
    }
  }

  return (
    <div className="comment">
      <Link to={`/u/${comment.author.username}`} aria-label={comment.author.name}>
        <Avatar user={comment.author} size={34} />
      </Link>
      <div className="comment-body">
        <p className="comment-head">
          <Link to={`/u/${comment.author.username}`} className="comment-author">
            {comment.author.name}
          </Link>
          <span className="muted small">
            <time dateTime={comment.created_at}>{timeAgo(comment.created_at)}</time>
            {comment.edited && ' · edited'}
          </span>
        </p>
        {editing ? (
          <form onSubmit={save}>
            <textarea
              rows={3}
              maxLength={2000}
              value={draft}
              autoFocus
              onFocus={(event) => event.currentTarget.setSelectionRange(draft.length, draft.length)}
              onChange={(event) => setDraft(event.target.value)}
            />
            <div className="button-row">
              <button type="submit" className="button small primary" disabled={busy || !draft.trim()}>
                {busy ? 'Saving…' : 'Save'}
              </button>
              <button
                type="button"
                className="button small"
                disabled={busy}
                onClick={() => {
                  setDraft(comment.body)
                  setEditing(false)
                  setError('')
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <p className="comment-text">{comment.body}</p>
        )}
        {error && <div className="alert error">{error}</div>}
        {!editing && (
          <div className="comment-actions">
            {onReply && (
              <button type="button" className="link-button" onClick={onReply}>
                Reply
              </button>
            )}
            {comment.can_edit && (
              <button type="button" className="link-button" disabled={busy} onClick={() => setEditing(true)}>
                Edit
              </button>
            )}
            {comment.can_delete && (
              <button type="button" className="link-button danger-text" disabled={busy} onClick={remove}>
                Delete
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

/** The conversation under a recipe. Open to read, signed in to join. */
export default function Comments({ recipeId }: { recipeId: number }) {
  const { user } = useAuth()
  const { pathname } = useLocation()
  const [comments, setComments] = useState<{ id: number; items: Comment[] } | null>(null)
  const [draft, setDraft] = useState('')
  const [replyTo, setReplyTo] = useState<number | null>(null)
  const [replyDraft, setReplyDraft] = useState('')
  const [posting, setPosting] = useState(false)
  const [error, setError] = useState('')
  const signInLink = `/login?next=${encodeURIComponent(pathname)}`

  const items = comments?.id === recipeId ? comments.items : null
  const total = items?.reduce((count, thread) => count + 1 + thread.replies.length, 0) ?? 0

  useEffect(() => {
    let cancelled = false
    api
      .comments(recipeId)
      .then((data) => !cancelled && setComments({ id: recipeId, items: data }))
      .catch((err: Error) => !cancelled && setError(err.message))
    return () => {
      cancelled = true
    }
    // Signing in or out changes which Edit and Delete links come back.
  }, [recipeId, user])

  function replace(update: (list: Comment[]) => Comment[]) {
    setComments((prev) => (prev ? { ...prev, items: update(prev.items) } : prev))
  }

  /** Applies a change to one comment wherever it sits in a thread. */
  function replaceOne(id: number, update: (comment: Comment) => Comment | null) {
    replace((list) =>
      list.flatMap((thread) => {
        if (thread.id === id) {
          const next = update(thread)
          return next ? [next] : []
        }
        if (!thread.replies.some((reply) => reply.id === id)) return [thread]
        return [
          {
            ...thread,
            replies: thread.replies.flatMap((reply) => {
              if (reply.id !== id) return [reply]
              const next = update(reply)
              return next ? [next] : []
            }),
          },
        ]
      }),
    )
  }

  async function post() {
    setPosting(true)
    setError('')
    try {
      const comment = await api.addComment(recipeId, draft.trim())
      replace((list) => [...list, comment])
      setDraft('')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setPosting(false)
    }
  }

  async function postReply(parent: number) {
    setPosting(true)
    setError('')
    try {
      const reply = await api.addComment(recipeId, replyDraft.trim(), parent)
      replace((list) =>
        list.map((thread) => (thread.id === parent ? { ...thread, replies: [...thread.replies, reply] } : thread)),
      )
      setReplyDraft('')
      setReplyTo(null)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setPosting(false)
    }
  }

  function startReply(thread: Comment, mention?: string) {
    if (!user) return
    setReplyTo(thread.id)
    setReplyDraft(mention ? `@${mention} ` : '')
  }

  return (
    <section className="comments">
      <h2>
        Comments{total > 0 && <span className="muted"> ({total})</span>}
      </h2>

      {user ? (
        <CommentForm
          user={user}
          value={draft}
          onChange={setDraft}
          onSubmit={post}
          busy={posting && replyTo === null}
          placeholder="Did you make it? Say how it went."
          submitLabel="Post comment"
        />
      ) : (
        <p className="muted">
          <Link to={signInLink}>Sign in</Link> to leave a comment.
        </p>
      )}

      {error && <div className="alert error">{error}</div>}

      {items === null && !error && <p className="muted">Loading…</p>}
      {items?.length === 0 && <p className="muted">No comments yet.</p>}
      {items && items.length > 0 && (
        <ul className="comment-list">
          {items.map((thread) => (
            <li key={thread.id}>
              <CommentRow
                comment={thread}
                onSaved={(updated) => replaceOne(updated.id, (previous) => ({ ...updated, replies: previous.replies }))}
                onDeleted={() => replaceOne(thread.id, () => null)}
                onReply={user ? () => startReply(thread) : undefined}
              />

              {(thread.replies.length > 0 || replyTo === thread.id) && (
                <ul className="reply-list">
                  {thread.replies.map((reply) => (
                    <li key={reply.id}>
                      <CommentRow
                        comment={reply}
                        onSaved={(updated) => replaceOne(updated.id, () => updated)}
                        onDeleted={() => replaceOne(reply.id, () => null)}
                        onReply={user ? () => startReply(thread, reply.author.username) : undefined}
                      />
                    </li>
                  ))}
                  {replyTo === thread.id && user && (
                    <li>
                      <CommentForm
                        user={user}
                        value={replyDraft}
                        onChange={setReplyDraft}
                        onSubmit={() => postReply(thread.id)}
                        onCancel={() => {
                          setReplyTo(null)
                          setReplyDraft('')
                        }}
                        busy={posting && replyTo === thread.id}
                        placeholder={`Reply to ${thread.author.name}`}
                        submitLabel="Reply"
                        autoFocus
                      />
                    </li>
                  )}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}

      {!user && items && items.length > 0 && (
        <p className="muted small">
          <Link to={signInLink}>Sign in</Link> to reply.
        </p>
      )}
    </section>
  )
}
