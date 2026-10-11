import { useEffect, useRef, useState } from 'react'
import './App.css'

const sampleAnswer = 'The study found that regular walking can improve cardiovascular health. Participants who walked for at least 30 minutes a day had a 20% lower risk of heart disease, and the benefits were seen across all age groups.'

function Icon({ name, size = 20, className = '' }) {
  const shared = { className, width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true }
  const paths = {
    spark: <><path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z" /><path d="m19 15 .9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15Z" /></>,
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" /><path d="M14 2v6h6M8 13h8M8 17h8" /></>,
    upload: <><path d="M12 16V4m-4 4 4-4 4 4" /><path d="M20 16.5v2A1.5 1.5 0 0 1 18.5 20h-13A1.5 1.5 0 0 1 4 18.5v-2" /></>,
    check: <><path d="m5 12 4 4L19 6" /></>,
    close: <><path d="m18 6-12 12M6 6l12 12" /></>,
    arrow: <><path d="M5 12h14m-6-6 6 6-6 6" /></>,
    shield: <><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z" /><path d="m9 12 2 2 4-4" /></>,
    book: <><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" /></>,
    inspect: <><path d="M5 3.75h9.5L19 8.2v11.05A1.75 1.75 0 0 1 17.25 21h-10.5A1.75 1.75 0 0 1 5 19.25V3.75Z" /><path d="M14 4v4.5h4.5M8.5 12h5M8.5 15.5h3" /><circle cx="16.5" cy="16.5" r="3.2" /><path d="m18.8 18.8 2.2 2.2" /></>,
  }
  return <svg {...shared}>{paths[name]}</svg>
}

function formatSize(bytes) {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

function sanitizeErrorText(value) {
  return String(value ?? '')
    .replace(/\bBearer\s+[^\s,;]+/gi, 'Bearer [redacted]')
    .replace(/\b(?:gsk|sk)-[A-Za-z0-9_-]{8,}\b/g, '[redacted key]')
    .replace(/\b(api[_ -]?key|authorization)\s*[:=]\s*[^\s,;]+/gi, '$1 [redacted]')
    .replace(/\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\b/g, '[redacted token]')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 800)
}

function getBackendErrorText(value) {
  if (typeof value === 'string') return value
  if (!value || typeof value !== 'object') return ''
  for (const key of ['error', 'detail']) {
    const field = value[key]
    if (typeof field === 'string' && field.trim()) return field
    if (field && typeof field === 'object') {
      const nested = field.message || field.detail || field.error
      if (typeof nested === 'string' && nested.trim()) return nested
      try { return JSON.stringify(field) } catch { return '' }
    }
  }
  return ''
}

function isFailureStatus(value) {
  if (typeof value === 'number') return value >= 400
  return typeof value === 'string' && (/^(error|failed|failure|unsuccessful|rate[ _-]?limited|quota[ _-]?exceeded)$/i.test(value.trim()) || /^\d{3}$/.test(value.trim()) && Number(value) >= 400)
}

function isRateLimitFailure(status, detail, applicationStatus) {
  return status === 429 || Number(applicationStatus) === 429 || /\b429\b|rate[ -]?limit|quota|resource[_ -]?exhausted/i.test(detail)
}

function hasClaimError(claim) {
  return typeof claim?.error === 'string' ? Boolean(claim.error.trim()) : Boolean(claim?.error)
}

function isProviderQuotaError(claim) {
  let errorText = claim?.error
  if (typeof errorText !== 'string') {
    try { errorText = JSON.stringify(errorText) } catch { errorText = '' }
  }
  return /token.per.day|quota|rate[ -]?limit|429|resource[_ -]?exhausted|too many requests/i.test(errorText || '')
}

function displayValue(value) {
  if (value == null) return ''
  if (typeof value === 'string') return value
  try { return JSON.stringify(value) } catch { return '' }
}

function evidenceQuote(item) {
  if (typeof item === 'string') return item
  return typeof item?.quote === 'string' ? item.quote : ''
}

function evidencePage(item) {
  return item && typeof item === 'object' ? item.page ?? item.page_number : undefined
}

function claimKey(claim, index) {
  return String(claim?.id ?? index)
}

function verdictTone(verdict) {
  const value = String(verdict || '').toLowerCase()
  if (/support|verified|true|correct/.test(value)) return 'verdict-positive'
  if (/contradict|false|incorrect|unsupported/.test(value)) return 'verdict-negative'
  if (/ambiguous|unclear|partial|mixed/.test(value)) return 'verdict-caution'
  return ''
}

function App() {
  const [pdf, setPdf] = useState(null)
  const [answer, setAnswer] = useState('')
  const [question, setQuestion] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [fileError, setFileError] = useState('')
  const [auditMessage, setAuditMessage] = useState(false)
  const [auditState, setAuditState] = useState('idle')
  const [auditError, setAuditError] = useState('')
  const [auditData, setAuditData] = useState(null)
  const [selectedClaimKey, setSelectedClaimKey] = useState('')
  const [verdictFilter, setVerdictFilter] = useState('all')
  const [copyStatus, setCopyStatus] = useState('')
  const [pdfUrl, setPdfUrl] = useState('')
  const inputRef = useRef(null)
  const pdfUrlRef = useRef('')
  const wordCount = answer.trim() ? answer.trim().split(/\s+/).length : 0
  const isDemo = auditData?.demo_mode === true || auditData?.demo === true || auditData?.mode === 'demo' || auditData?.llm === 'fallback'
  const auditClaims = Array.isArray(auditData?.claims) ? auditData.claims.filter((claim) => claim && typeof claim === 'object') : []
  const failedClaims = auditClaims.filter(hasClaimError)
  const verifiedClaims = auditClaims.filter((claim) => {
  const verdict = String(claim.verdict || '').trim().toLowerCase()
  return !hasClaimError(claim) &&
    ['supported', 'contradicted'].includes(verdict)
})
  const allClaimsFailed = auditClaims.length > 0 && failedClaims.length === auditClaims.length
  const hasPartialClaimFailures = failedClaims.length > 0 && !allClaimsFailed
  const quotaFailure = failedClaims.some(isProviderQuotaError)
  const claimEntries = auditClaims.map((claim, index) => ({ claim, index, key: claimKey(claim, index), failed: hasClaimError(claim) }))
  const verdictOptions = [...new Set(verifiedClaims.map((claim) => String(claim.verdict || '').trim()).filter(Boolean))]
  const visibleClaimEntries = claimEntries.filter(({ claim, failed }) => verdictFilter === 'all'
    || verdictFilter === 'not-verified' && failed
    || !failed && String(claim.verdict || '').toLowerCase() === verdictFilter.toLowerCase())
  const selectedClaimEntry = claimEntries.find(({ key }) => key === selectedClaimKey) || null
  const selectedClaim = selectedClaimEntry?.claim || null
  const selectedEvidence = Array.isArray(selectedClaim?.evidence) ? selectedClaim.evidence : []

  useEffect(() => {
    return () => {
      if (pdfUrlRef.current) URL.revokeObjectURL(pdfUrlRef.current)
    }
  }, [])

  function acceptFile(file) {
    if (!file) return
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      setFileError('Please choose a PDF file to continue.')
      return
    }
    setFileError('')
    if (pdfUrlRef.current) URL.revokeObjectURL(pdfUrlRef.current)
    const url = URL.createObjectURL(file)
    pdfUrlRef.current = url
    setPdfUrl(url)
    setPdf(file)
    setAuditMessage(false)
    setAuditData(null)
    setSelectedClaimKey('')
  }

  function clearFile() {
    if (pdfUrlRef.current) URL.revokeObjectURL(pdfUrlRef.current)
    pdfUrlRef.current = ''
    setPdfUrl('')
    setPdf(null)
    setFileError('')
    setAuditMessage(false)
    setAuditData(null)
    setSelectedClaimKey('')
    if (inputRef.current) inputRef.current.value = ''
  }

  function handleDrop(event) {
    event.preventDefault()
    setIsDragging(false)
    acceptFile(event.dataTransfer.files?.[0])
  }

  const canAudit = Boolean(pdf && answer.trim())

  async function copyQuotation(quotation) {
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard is unavailable')
      await navigator.clipboard.writeText(quotation)
      setCopyStatus('Quotation copied')
    } catch {
      setCopyStatus('Copy is unavailable in this browser')
    }
  }

  async function submitAudit() {
    if (!canAudit || auditState === 'loading') return
    if (!API_BASE_URL) {
      setAuditState('error')
      setAuditError('API base URL is not configured. Set VITE_API_BASE_URL in frontend/.env.local and restart Vite.')
      return
    }
    setAuditState('loading')
    setAuditError('')
    setAuditData(null)
    const formData = new FormData()
    formData.append('pdf', pdf)
    formData.append('answer', answer.trim())
    if (question.trim()) formData.append('question', question.trim())
    const endpoint = `${API_BASE_URL}/api/audit`
    try {
      const response = await fetch(endpoint, { method: 'POST', body: formData })
      const rawBody = await response.text()
      let body = null
      let isJson = false
      if (rawBody.trim()) {
        try {
          body = JSON.parse(rawBody)
          isJson = true
        } catch {
          body = rawBody
        }
      }

      const backendError = sanitizeErrorText(getBackendErrorText(body))
      const statusFailure = isJson && isFailureStatus(body?.status)
      const applicationFailure = isJson && (body?.success === false || statusFailure || Boolean(backendError))
      const failureDetail = backendError || (applicationFailure ? sanitizeErrorText(body?.message) : '')
      const httpFailure = !response.ok
      if (httpFailure || applicationFailure) {
        const category = isRateLimitFailure(response.status, failureDetail, body?.status)
          ? 'rate_limit_or_quota'
          : applicationFailure ? 'application_failure' : 'http_failure'
        const message = category === 'rate_limit_or_quota'
          ? `The audit service is rate limited or its API quota is exhausted.${failureDetail ? ` ${failureDetail}` : ''}`
          : failureDetail || (httpFailure
            ? `Audit failed with HTTP ${response.status}${rawBody.trim() ? `: ${sanitizeErrorText(rawBody)}` : '; the service returned no error details.'}`
            : 'The audit service reported a failure.')
        console.error('[Second Opinion] Audit request failed', {
          endpoint,
          httpStatus: response.status,
          category,
          error: sanitizeErrorText(failureDetail || rawBody || message),
        })
        throw new Error(message)
      }

      if (!isJson || !body || typeof body !== 'object' || Array.isArray(body)) {
        const category = rawBody.trim() ? 'unexpected_response' : 'empty_response'
        const message = category === 'empty_response'
          ? 'The audit service returned an empty response. No results were displayed.'
          : 'The audit service returned a non-JSON response. No results were displayed.'
        console.error('[Second Opinion] Audit response could not be used', {
          endpoint,
          httpStatus: response.status,
          category,
          error: sanitizeErrorText(rawBody) || '(empty response)',
        })
        throw new Error(message)
      }
      const responseClaims = Array.isArray(body.claims) ? body.claims.filter((claim) => claim && typeof claim === 'object') : []
      const responseFailedClaims = responseClaims.filter(hasClaimError)
      const responseVerifiedClaims = responseClaims.filter((claim) => {
        const verdict = String(claim.verdict || '').trim().toLowerCase()
        return !hasClaimError(claim) &&
          ['supported', 'contradicted'].includes(verdict)
      })
      const responseHasQuotaFailure = responseFailedClaims.some(isProviderQuotaError)
      const firstClaim = responseClaims.find((claim) => !hasClaimError(claim)) || responseClaims[0]
      setSelectedClaimKey(firstClaim ? claimKey(firstClaim, responseClaims.indexOf(firstClaim)) : '')
      setVerdictFilter('all')
      setCopyStatus('')
      if (responseFailedClaims.length > 0) {
        console.warn('[Second Opinion] Audit contains claims that were not verified', {
          endpoint,
          httpStatus: response.status,
          category: responseHasQuotaFailure ? 'provider_quota_or_rate_limit' : 'claim_verification_failure',
          failedClaims: responseFailedClaims.length,
          verifiedClaims: responseVerifiedClaims.length,
        })
      } else {
        console.info('[Second Opinion] Audit response received', {
          endpoint,
          httpStatus: response.status,
          category: 'audit_response',
          claims: responseClaims.length,
        })
      }
      setAuditData(body)
      setAuditState('success')
    } catch (error) {
      const isNetworkError = error instanceof TypeError
      const category = isNetworkError ? 'network_or_cors' : 'request_or_response_error'
      const detail = sanitizeErrorText(error?.message || 'Unknown audit request error')
      if (category === 'network_or_cors') {
        console.error('[Second Opinion] Audit request could not be read by the browser', {
          endpoint,
          httpStatus: null,
          category,
          error: detail,
        })
      }
      setAuditState('error')
      setAuditError(isNetworkError
        ? 'The browser could not access the audit response because of a network or CORS issue. The server-side error could not be read.'
        : detail || 'The audit request failed. Please try again.')
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Second Opinion home">
          <span className="brand-mark"><Icon name="inspect" size={23} /></span>
          <span className="brand-lockup"><span className="brand-name">Second Opinion</span><span className="brand-descriptor">AI EVIDENCE LAB</span></span>
        </a>
        <nav className="main-nav" aria-label="Main navigation">
          <a className="nav-link active" href="#workspace"><span className="nav-index">01</span>Audit workspace</a>
          <a className="nav-link" href="#how-it-works"><span className="nav-index">02</span>Method</a>
        </nav>
        <div className="topbar-right"><div className="prototype-pill"><span className="status-dot" /> SOURCE-LED REVIEW</div></div>
      </header>

      <main id="top">
        <section className="hero-section" aria-labelledby="hero-title">
          <div className="hero-copy-block">
            <div className="eyebrow"><span className="eyebrow-line" /> INDEPENDENT VERIFICATION / 001</div>
            <h1 id="hero-title">Not every answer<br /><em>survives scrutiny.</em></h1>
            <p className="hero-copy">Trace AI-generated claims back to their sources. Find the evidence, expose contradictions, and identify what remains unverified.</p>
            <div className="hero-note"><Icon name="shield" size={17} /><span>One answer. One source. Evidence kept in view.</span></div>
            <a className="hero-cta" href="#workspace">Prepare an audit <Icon name="arrow" size={17} /></a>
          </div>
          <div className="evidence-visual" aria-label="Illustration of a source document under review">
            <div className="visual-coordinate">FIELD NOTE <span>01—A</span></div>
            <svg className="visual-contours" viewBox="0 0 600 400" fill="none" aria-hidden="true"><path d="M-20 325C96 305 111 192 223 190s105 115 206 88 107-118 191-148" /><path d="M-25 349C90 326 119 217 227 214s106 112 205 83 113-112 193-141" /><path d="M84 20c81 67 98 125 87 179s-54 92-39 155 67 73 128 71" /><path d="M115 4c78 72 92 130 75 191s-48 92-25 143 73 74 132 61" /></svg>
            <div className="visual-document"><div className="document-topline"><Icon name="file" size={16} /><span>PRIMARY SOURCE</span><span className="document-page">PDF</span></div><div className="document-rule wide" /><div className="document-rule" /><div className="document-rule short" /><div className="document-quote"><span>“</span><i /><i /><i /></div><div className="document-rule" /><div className="document-rule wide" /><div className="document-rule short" /><div className="document-footer"><span>REFERENCE / SOURCE</span><span>● ● ●</span></div></div>
            <div className="visual-stamp"><span className="stamp-ring"><Icon name="inspect" size={24} /></span><span>CHECK THE<br />SOURCE</span></div>
            <div className="visual-caption"><span className="caption-line" /> EVIDENCE BEFORE CONFIDENCE</div>
          </div>
        </section>

        <section className="workspace" id="workspace" aria-label="Audit workspace">
          <div className="workspace-heading">
            <div><span className="section-kicker">01 / SUBMISSION</span><h2>Start with the source.</h2></div>
            <span className="step-count"><span className="step-live" /> PDF + answer required</span>
          </div>
          <div className="workspace-grid">
            <div className="panel source-panel">
              <div className="panel-title-row">
                <span className="panel-icon"><Icon name="file" size={18} /></span>
                <div><h3>Source document</h3><p>01 — Add the material claims will be checked against</p></div>
                <span className="required-tag">REQUIRED</span>
              </div>
              <input ref={inputRef} className="visually-hidden" type="file" accept="application/pdf,.pdf" aria-label="Choose a PDF source document" onChange={(event) => acceptFile(event.target.files?.[0])} />
              {pdf ? (
                <div className="file-ready">
                  <span className="pdf-badge">PDF</span>
                  <div className="file-info"><strong>{pdf.name}</strong><span>{formatSize(pdf.size)} · Ready to review</span></div>
                  <span className="file-check"><Icon name="check" size={15} /></span>
                  <button className="icon-button remove-file" type="button" onClick={clearFile} aria-label="Remove uploaded PDF"><Icon name="close" size={17} /></button>
                  <button className="replace-link" type="button" onClick={() => inputRef.current?.click()}>Replace</button>
                </div>
              ) : (
                <button className={`dropzone ${isDragging ? 'dragging' : ''}`} type="button" onClick={() => inputRef.current?.click()} onDragOver={(event) => { event.preventDefault(); setIsDragging(true) }} onDragLeave={() => setIsDragging(false)} onDrop={handleDrop}>
                  <span className="upload-icon"><Icon name="upload" size={22} /></span>
                  <span className="drop-title">Drop your PDF here, or <span>browse</span></span>
                  <span className="drop-hint">PDF files only <i /> Add your source document to begin</span>
                </button>
              )}
              {fileError && <p className="inline-error" role="alert">{fileError}</p>}
              <div className="privacy-note"><Icon name="shield" size={15} /><span>Your document is only used as the source for this review.</span></div>
            </div>

            <div className="panel answer-panel">
              <div className="panel-title-row">
                <span className="panel-icon"><Icon name="spark" size={18} /></span>
                <div><h3>Answer under review</h3><p>02 — Paste the answer you want to verify</p></div>
                <span className="required-tag">REQUIRED</span>
              </div>
              <div className="answer-field-wrap">
                <label className="visually-hidden" htmlFor="answer">AI-generated answer</label>
                <textarea id="answer" value={answer} onChange={(event) => { setAnswer(event.target.value); setAuditMessage(false) }} placeholder="Paste an AI-generated answer here..." />
                {!answer && <div className="textarea-hint"><span className="hint-mark">↳</span> Include the full response so each claim can be reviewed.</div>}
              </div>
              <div className="answer-toolbar">
                <span className="word-count">{wordCount} {wordCount === 1 ? 'word' : 'words'}</span>
                <div className="text-actions"><button type="button" className="text-button" onClick={() => { setAnswer(''); setAuditMessage(false) }} disabled={!answer}>Clear</button><span className="action-divider" /><button type="button" className="text-button sample-button" onClick={() => { setAnswer(sampleAnswer); setAuditMessage(false) }}>Use sample answer <Icon name="arrow" size={14} /></button></div>
              </div>
            </div>
          </div>

          <div className="question-row">
            <label htmlFor="question"><span className="optional-icon">?</span><span><strong>Have a question in mind?</strong><small>Optional · Give the review a little more context</small></span></label>
            <input id="question" type="text" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="e.g. Does the study support this conclusion?" />
          </div>

          <div className="audit-footer">
            <div className="footer-guidance"><span className="mini-lock"><Icon name="shield" size={16} /></span><span>We’ll compare claims to the source, one by one.</span></div>
            <button className="audit-button" type="button" disabled={!canAudit || auditState === 'loading'} onClick={submitAudit}>{auditState === 'loading' ? 'Auditing…' : 'Audit answer'} <Icon name="arrow" size={17} /></button>
          </div>
          {auditMessage && <div className="api-notice" role="status"><span className="notice-icon"><Icon name="book" size={18} /></span><span><strong>Audit status</strong><small>{auditMessage}</small></span><button type="button" className="icon-button" aria-label="Dismiss message" onClick={() => setAuditMessage(false)}><Icon name="close" size={17} /></button></div>}
          {auditError && <div className="api-notice" role="alert"><span className="notice-icon"><Icon name="book" size={18} /></span><span><strong>Audit could not be completed</strong><small>{auditError}</small></span></div>}
          {auditState === 'success' && (allClaimsFailed
            ? <div className="api-notice" role="alert"><span className="notice-icon"><Icon name="book" size={18} /></span><span><strong>Verification unavailable</strong><small>{quotaFailure ? "The backend's AI provider quota has been exceeded. Please ask the backend team to resolve the quota issue before retrying." : 'The backend could not verify any claims. Please ask the backend team to resolve the verification errors before retrying.'}</small></span></div>
            : hasPartialClaimFailures
              ? <div className="api-notice" role="status"><span className="notice-icon"><Icon name="book" size={18} /></span><span><strong>Some claims were not verified</strong><small>{quotaFailure ? 'The backend AI provider quota or rate limit was reached. Failed claims are excluded from verified results.' : 'Failed claims are marked Not verified and excluded from verified results.'}</small></span></div>
              : <div className="api-notice" role="status"><span className="notice-icon"><Icon name="book" size={18} /></span><span><strong>{isDemo ? 'Demo audit response' : 'Audit results received'}</strong><small>{isDemo ? 'The backend reported demo mode. ' : ''}{verifiedClaims.length} claim{verifiedClaims.length === 1 ? '' : 's'} returned without verification errors.</small></span></div>)}
          <div className="analysis-heading"><div><span className="section-kicker">02 / INVESTIGATION</span><h2>What the source supports.</h2></div><span className="analysis-locked"><Icon name="shield" size={15} />{auditState === 'success' && auditClaims.length > 0 ? allClaimsFailed ? 'Verification unavailable' : `${verifiedClaims.length} verified · ${failedClaims.length} not verified` : 'Awaiting submission'}</span></div>
          <div className="analysis-grid">
            <section className="analysis-panel source-viewer" aria-labelledby="source-viewer-heading">
              <div className="analysis-panel-head"><span className="panel-icon"><Icon name="file" size={18} /></span><div><h3 id="source-viewer-heading">Source document</h3><p>{pdf ? pdf.name : 'Your PDF will appear here'}</p></div>{pdf && <button className="replace-link viewer-change" type="button" onClick={() => inputRef.current?.click()}>Change</button>}</div>
              {pdf && pdfUrl ? <><p className="pdf-control-note">Use your browser’s PDF toolbar for available page and zoom controls. Text selection depends on browser support.</p><div className="pdf-frame"><object data={pdfUrl} type="application/pdf" aria-label={`Preview of ${pdf.name}`}><div className="pdf-fallback"><Icon name="file" size={24} /><span>PDF preview isn’t available in this browser.</span><a href={pdfUrl} target="_blank" rel="noreferrer">Open document</a></div></object></div></> : <div className="analysis-empty source-empty"><span className="empty-illustration"><Icon name="file" size={25} /></span><strong>Your source, in view</strong><p>Upload a PDF above to keep the original document close while you review.</p><span className="empty-rule" /></div>}
              {pdf && <div className="document-meta"><span className="pdf-badge mini">PDF</span><span>{formatSize(pdf.size)}</span><span className="meta-dot" /> <span>Source document</span></div>}
            </section>
            <section className="analysis-panel claim-map" aria-labelledby="claim-map-heading">
              <div className="analysis-panel-head"><span className="panel-icon"><Icon name="spark" size={18} /></span><div><h3 id="claim-map-heading">Claims under review</h3><p>{auditState === 'success' ? auditClaims.length + ' claims from this audit' : 'Claim map'}</p></div></div>
              {auditState === 'success' && auditData?.overall && failedClaims.length === 0 && <div className="overall-strip"><span className="section-kicker">OVERALL ASSESSMENT</span>{auditData.overall.summary && <p>{displayValue(auditData.overall.summary)}</p>}{auditData.overall.counts != null && <small>Counts · {displayValue(auditData.overall.counts)}</small>}{auditData.overall.source_coverage != null && <small>Source coverage · {displayValue(auditData.overall.source_coverage)}</small>}{auditData.overall.score != null && <small>Score · {displayValue(auditData.overall.score)}</small>}</div>}
              {auditState === 'success' && auditClaims.length > 0 ? <>
                <div className="claim-tools"><span className="claim-list-label">CLAIM REGISTER</span><label className="filter-label">Filter <select className="verdict-filter" value={verdictFilter} onChange={(event) => {
                  const nextFilter = event.target.value
                  setVerdictFilter(nextFilter)
                  const nextEntry = claimEntries.find(({ claim, failed }) => nextFilter === 'all' || nextFilter === 'not-verified' && failed || !failed && String(claim.verdict || '').toLowerCase() === nextFilter.toLowerCase())
                  if (nextEntry) setSelectedClaimKey(nextEntry.key)
                }}><option value="all">All claims</option>{verdictOptions.map((verdict) => <option value={verdict} key={verdict}>{verdict}</option>)}{failedClaims.length > 0 && <option value="not-verified">Not verified</option>}</select></label></div>
                <div className="claim-list" aria-label="Audit claims">{visibleClaimEntries.map(({ claim, index, key, failed }) => {
                  const evidence = Array.isArray(claim.evidence) ? claim.evidence : []
                  return <button type="button" className={'claim-row' + (selectedClaimKey === key ? ' selected' : '') + (failed ? ' claim-failed' : '')} aria-pressed={selectedClaimKey === key} onClick={() => { setSelectedClaimKey(key); setCopyStatus('') }} key={key}>
                    <span className="claim-row-index">{claim.id ?? String(index + 1).padStart(2, '0')}</span>
                    <span className="claim-row-content"><span className="claim-row-text">{displayValue(claim.text) || 'Claim text not provided'}</span><span className="claim-row-meta"><span className={'verdict-tag' + (failed ? ' verdict-failed' : ` ${verdictTone(claim.verdict)}`)}>{failed ? 'Not verified' : displayValue(claim.verdict) || 'Verdict not provided'}</span>{!failed && claim.confidence != null && <span className="claim-confidence">{displayValue(claim.confidence)} confidence</span>}<span className="evidence-count">{failed ? 'Verification failed' : evidence.length + (evidence.length === 1 ? ' evidence' : ' evidence')}</span></span></span>
                    <span className="claim-select-mark" aria-hidden="true">↗</span>
                  </button>
                })}</div>
              </> : <div className="claim-empty"><div className="empty-trace" aria-hidden="true"><span className="trace-source"><Icon name="file" size={20} /></span><span className="trace-rule" /><span className="trace-claim">C</span><span className="trace-rule" /><span className="trace-evidence"><Icon name="book" size={18} /></span></div><strong>{auditState === 'success' ? 'No claims were returned' : 'Claims appear after an audit'}</strong><p>{auditState === 'success' ? 'The audit response contained no claim objects.' : 'Submit an answer with its source document to see each claim connected to its evidence.'}</p></div>}
              <div className="map-legend"><span><i className="legend-dot supported" /> Supported</span><span><i className="legend-dot contradicted" /> Contradicted</span><span><i className="legend-dot unclear" /> Ambiguous</span></div>
            </section>
            <section className="analysis-panel evidence-panel" aria-labelledby="evidence-heading">
              <div className="analysis-panel-head"><span className="panel-icon"><Icon name="book" size={18} /></span><div><h3 id="evidence-heading">Evidence inspector</h3><p>{selectedClaim ? 'Selected claim source material' : 'Evidence is tied to a selected claim'}</p></div></div>
              {!selectedClaim ? <div className="evidence-empty"><span className="empty-illustration"><Icon name="book" size={23} /></span><strong>Select a claim</strong><p>Choose a claim from the register to inspect its source quotation, explanation, and page reference.</p></div> : <div className="evidence-detail">
                <div className="evidence-claim-ref"><span>CLAIM REFERENCE</span><strong>{selectedClaim.id ?? String(selectedClaimEntry.index + 1).padStart(2, '0')}</strong></div>
                <div className="selected-claim-copy">{displayValue(selectedClaim.text)}</div>
                <div className="selected-verdict"><span className={'verdict-tag' + (selectedClaimEntry.failed ? ' verdict-failed' : ` ${verdictTone(selectedClaim.verdict)}`)}>{selectedClaimEntry.failed ? 'Not verified' : displayValue(selectedClaim.verdict) || 'Verdict not provided'}</span>{!selectedClaimEntry.failed && selectedClaim.confidence != null && <span className="claim-confidence">{displayValue(selectedClaim.confidence)} confidence</span>}</div>
                {selectedClaimEntry.failed ? <div className="evidence-state evidence-failure"><strong>Verification unavailable</strong><p>{isProviderQuotaError(selectedClaim) ? 'The backend AI provider quota or rate limit was exceeded. This claim has no verified result.' : 'The backend could not verify this claim. It is excluded from verified results.'}</p></div> : <>
                  {selectedClaim.explanation && <div className="claim-explanation"><span className="evidence-label">EXPLANATION</span><p>{displayValue(selectedClaim.explanation)}</p></div>}
                  <div className="evidence-quotes"><span className="evidence-label">SOURCE EVIDENCE</span>{selectedEvidence.length === 0 ? <div className="evidence-state"><strong>No supporting evidence returned</strong><p>The backend returned no evidence quotation for this claim.</p></div> : selectedEvidence.map((item, index) => {
                    const quote = evidenceQuote(item)
                    const page = evidencePage(item)
                    return <div className="evidence-quote-card" key={index}>{quote ? <><blockquote>{quote}</blockquote><div className="quote-actions">{page != null && <span className="page-reference">SOURCE PAGE {displayValue(page)}</span>}<button className="copy-quote" type="button" title="Copy quotation" aria-label="Copy quotation" onClick={() => copyQuotation(quote)}>Copy quote</button></div></> : <div className="evidence-state"><strong>Evidence quotation unavailable</strong><p>An evidence item was returned, but it did not include a readable quotation.</p>{page != null && <span className="page-reference">SOURCE PAGE {displayValue(page)}</span>}</div>}</div>
                  })}</div>
                  {copyStatus && <p className="copy-status" role="status">{copyStatus}</p>}
                </>}
              </div>}
              <div className="evidence-foot"><Icon name="shield" size={14} /> Only backend-provided evidence is shown.</div>
            </section>
          </div>
          <div className="workspace-bottom"><span>SECOND OPINION <i /> A MORE THOUGHTFUL WAY TO REVIEW AI</span><span>Built for careful readers <span className="tiny-spark">✳</span></span></div>
        </section>

        <section className="how-section" id="how-it-works">
          <div className="how-heading"><span className="section-kicker">A SIMPLE SECOND LOOK</span><h2>From confident answer<br />to <em>grounded understanding.</em></h2></div>
          <div className="how-steps">
            <div className="how-step"><span className="step-number">01</span><span className="step-icon"><Icon name="file" size={19} /></span><h3>Bring the source</h3><p>Start with the PDF you trust, whether it’s a paper, report, or article.</p></div>
            <div className="step-connector" aria-hidden="true">··········→</div>
            <div className="how-step"><span className="step-number">02</span><span className="step-icon"><Icon name="spark" size={19} /></span><h3>Add the answer</h3><p>Paste an AI response and a question you’d like the review to consider.</p></div>
            <div className="step-connector" aria-hidden="true">··········→</div>
            <div className="how-step"><span className="step-number">03</span><span className="step-icon"><Icon name="shield" size={19} /></span><h3>See what holds up</h3><p>Claims are checked against the source, so you can decide with more context.</p></div>
          </div>
        </section>
      </main>
      <footer className="page-footer"><a className="footer-brand" href="#top"><span className="brand-mark small"><Icon name="spark" size={15} /></span> second<span>opinion</span></a><span>Less guesswork. More ground truth.</span><span className="footer-proto">A thoughtful little prototype <span>✳</span></span></footer>
    </div>
  )
}

export default App
