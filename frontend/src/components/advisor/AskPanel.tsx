import { ArrowUp, RotateCcw } from 'lucide-react'
import { Fragment, useEffect, useRef, useState } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, postStream } from '../../api/client'
import { Spinner } from '../ui'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

type AskEvent = { type: 'delta'; text: string } | { type: 'done'; cached: boolean; model: string } | { type: 'error'; message: string }

const TOKEN = /(\*\*[^*]+\*\*|\b[A-Z]-\d{2}\b)/g

/** Bold and tank links in one line of Claude's text. Plain React nodes, so nothing it writes can become markup. */
function inline(text: string): ReactNode[] {
  return text.split(TOKEN).map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) return <strong key={index} className="font-semibold text-ink">{inline(part.slice(2, -2))}</strong>
    if (/^[A-Z]-\d{2}$/.test(part)) return <Link key={index} to={`/tanks/${part}`} className="mono font-medium whitespace-nowrap text-ink underline decoration-border-strong underline-offset-2 hover:decoration-ink">{part}</Link>
    return <Fragment key={index}>{part}</Fragment>
  })
}

function Answer({ text }: { text: string }) {
  const blocks: ReactNode[] = []
  let items: string[] = []
  let ordered = false
  const flush = () => {
    if (items.length === 0) return
    const Tag = ordered ? 'ol' : 'ul'
    blocks.push(
      <Tag key={blocks.length} className={`m-0 flex flex-col gap-1 pl-[18px] ${ordered ? 'list-decimal' : 'list-disc'}`}>
        {items.map((item, index) => <li key={index} className="pl-0.5">{inline(item)}</li>)}
      </Tag>,
    )
    items = []
  }
  for (const raw of text.split('\n')) {
    const line = raw.trim()
    const numbered = line.match(/^\d+[.)]\s+(.*)$/)
    const bullet = line.match(/^[-•*]\s+(.*)$/)
    if (numbered || bullet) {
      if (items.length > 0 && ordered !== !!numbered) flush()
      ordered = !!numbered
      items.push((numbered ?? bullet)![1])
    } else if (line) {
      flush()
      blocks.push(<p key={blocks.length} className="m-0">{inline(line)}</p>)
    }
  }
  flush()
  return <div className="flex flex-col gap-2 text-[13px] leading-[1.5] text-ink-2">{blocks}</div>
}

/** Ask anything about the hatchery. Claude answers from the same records the rest of the page reads. */
export function AskPanel({ questions }: { questions: string[] }) {
  const [messages, setMessages] = useState<Message[]>([])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const scroller = useRef<HTMLDivElement | null>(null)
  const abort = useRef<AbortController | null>(null)

  useEffect(() => () => abort.current?.abort(), [])
  useEffect(() => {
    const box = scroller.current
    if (box) box.scrollTop = box.scrollHeight
  }, [messages])

  const send = (text: string) => {
    const question = text.trim()
    if (!question || busy) return
    const history: Message[] = [...messages, { role: 'user', content: question }]
    setMessages([...history, { role: 'assistant', content: '' }])
    setDraft('')
    setBusy(true)
    setError(null)
    const controller = new AbortController()
    abort.current = controller
    let answer = ''
    let finished = false
    let reason: string | null = null
    postStream<AskEvent>('/api/advisor/ask', { messages: history }, (event) => {
      if (event.type === 'delta') {
        answer += event.text
        setMessages([...history, { role: 'assistant', content: answer }])
      } else if (event.type === 'done') {
        finished = true
      } else {
        reason = event.message
      }
    }, controller.signal)
      .catch((failure: unknown) => {
        if (controller.signal.aborted) return
        reason = failure instanceof ApiError ? failure.message : "Claude didn't answer. Try again."
      })
      .finally(() => {
        if (controller.signal.aborted) return
        setBusy(false)
        // Only a finished answer joins the conversation, because it's sent back with the next question
        if (!finished) {
          setError(reason ?? "Claude's answer was cut off. Try again.")
          setMessages(history.slice(0, -1))
          setDraft(question)
        }
      })
  }

  const onKey = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      send(draft)
    }
  }

  const reset = () => {
    abort.current?.abort()
    setMessages([])
    setBusy(false)
    setError(null)
  }

  const empty = messages.length === 0
  return (
    <section aria-label="Ask Thetis" className="flex min-h-0 flex-col rounded-card border border-line">
      <div className="flex items-center justify-between gap-2 border-b border-divider px-4 py-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold">Ask Thetis</h2>
          <span className="tag !border-[#B9D0DD] !text-brand">Claude</span>
        </div>
        {!empty && (
          <button type="button" className="ghost !h-7 !w-7 !p-0 max-[660px]:!h-11 max-[660px]:!w-11" aria-label="Start a new conversation" onClick={reset}>
            <RotateCcw size={12} strokeWidth={2} />
          </button>
        )}
      </div>

      <div ref={scroller} aria-live="polite" className="flex max-h-[min(52vh,520px)] min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4">
        {empty && (
          <>
            <p className="m-0 text-[13px] leading-[1.5] text-ink-3">Ask about any tank, batch or decision. Answers come from your records.</p>
            <div className="flex flex-col items-stretch gap-1.5">
              {questions.map((question) => (
                <button key={question} type="button" className="ghost !h-auto min-h-8 !justify-start !whitespace-normal !py-1.5 text-left !text-[13px] !leading-[1.35] !text-ink-2 max-[660px]:min-h-11" onClick={() => send(question)}>
                  {question}
                </button>
              ))}
            </div>
          </>
        )}
        {messages.map((message, index) => (
          message.role === 'user' ? (
            <p key={index} className="m-0 ml-6 self-end rounded-card bg-muted-bg px-3 py-2 text-[13px] leading-[1.45] whitespace-pre-wrap text-ink">{message.content}</p>
          ) : message.content ? (
            <div key={index} className="appear"><Answer text={message.content} /></div>
          ) : (
            <span key={index} role="status" className="flex items-center gap-2 text-[13px] text-ink-3"><Spinner />Reading your records</span>
          )
        ))}
        {error && <p role="alert" className="m-0 text-[13px] text-critical-text">{error}</p>}
      </div>

      <form className="flex flex-col gap-2 border-t border-divider p-3" onSubmit={(event) => { event.preventDefault(); send(draft) }}>
        <div className="flex items-end gap-2">
          <textarea
            className="field min-h-8 flex-1 !resize-none max-[660px]:min-h-11"
            rows={1}
            value={draft}
            maxLength={2000}
            placeholder="Ask a question"
            aria-label="Ask a question"
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={onKey}
          />
          <button type="submit" className="solid !h-8 !w-8 flex-none !p-0 max-[660px]:!h-11 max-[660px]:!w-11" disabled={busy || !draft.trim()} aria-label="Send">
            {busy ? <Spinner light /> : <ArrowUp size={14} strokeWidth={2} />}
          </button>
        </div>
        <span className="text-[11px] leading-[1.4] text-ink-4">Written by Claude from your records. Check anything you act on.</span>
      </form>
    </section>
  )
}
