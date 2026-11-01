export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function readError(res: Response): Promise<string> {
  try {
    const body = await res.json()
    if (typeof body?.detail === 'string') return body.detail
    if (Array.isArray(body?.detail)) return body.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join(' ')
  } catch {
    /* not JSON */
  }
  return `The server answered ${res.status}.`
}

async function send<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(url, init)
  } catch {
    throw new ApiError(0, "Can't reach the Thetis server. Is npm run dev running?")
  }
  if (!res.ok) throw new ApiError(res.status, await readError(res))
  return res.json() as Promise<T>
}

export function getJSON<T>(url: string): Promise<T> {
  return send<T>(url)
}

export function postJSON<T>(url: string, body?: unknown, method: 'POST' | 'PATCH' = 'POST'): Promise<T> {
  return send<T>(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export function postFile<T>(url: string, file: File): Promise<T> {
  const form = new FormData()
  form.append('file', file)
  return send<T>(url, { method: 'POST', body: form })
}

/** POST, then read server-sent events until the stream ends. A failure before the stream starts throws, as send() does. */
export async function postStream<T>(url: string, body: unknown, onEvent: (event: T) => void, signal?: AbortSignal): Promise<void> {
  let res: Response
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
  } catch (error) {
    if (signal?.aborted) throw error
    throw new ApiError(0, "Can't reach the Thetis server. Is npm run dev running?")
  }
  if (!res.ok) throw new ApiError(res.status, await readError(res))
  if (!res.body) throw new ApiError(0, 'The server sent nothing back.')
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) return
    buffer += value
    let end = buffer.indexOf('\n\n')
    while (end !== -1) {
      const line = buffer.slice(0, end)
      buffer = buffer.slice(end + 2)
      if (line.startsWith('data: ')) onEvent(JSON.parse(line.slice(6)) as T)
      end = buffer.indexOf('\n\n')
    }
  }
}
