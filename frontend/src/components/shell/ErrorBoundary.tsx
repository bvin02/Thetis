import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'

/** The last line of defence: an unexpected error shows a way out instead of a blank page. */
export class ErrorBoundary extends Component<{ children: ReactNode; resetKey: string }, { failed: boolean; shownFor: string }> {
  state = { failed: false, shownFor: '' }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  static getDerivedStateFromProps(props: { resetKey: string }, state: { failed: boolean; shownFor: string }) {
    // Moving to another page clears the error
    if (state.shownFor !== props.resetKey) return { failed: false, shownFor: props.resetKey }
    return null
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Thetis hit an unexpected error', error, info.componentStack)
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div role="alert" className="flex flex-col items-start gap-3 px-7 py-10 max-[660px]:px-4">
        <span className="text-[15px] font-semibold">Something went wrong on this page</span>
        <p className="m-0 max-w-[60ch] text-[13px] leading-normal text-ink-2">Your saved checks and decisions are safe. Reload the page to carry on.</p>
        <button type="button" className="ghost" onClick={() => window.location.reload()}>Reload</button>
      </div>
    )
  }
}
