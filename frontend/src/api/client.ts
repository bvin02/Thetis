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
