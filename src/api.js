async function jsonRequest(url, options = {}) {
  const response = await fetch(url, options)
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.error?.message ?? 'Request failed')
  return data
}

export async function loadAuthSession() {
  return jsonRequest("/api/v1/auth/session")
}

export async function loginAccount(email, password) {
  return jsonRequest("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  })
}

export async function signupAccount(email, password, nickname) {
  return jsonRequest("/api/v1/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, nickname }),
  })
}

export async function logoutAccount() {
  await jsonRequest("/api/v1/auth/logout", { method: "POST" })
}

export async function createDiaryEntry({ blob, date }) {
  const contentType = blob.type === 'image/png' ? 'image/png' : 'image/jpeg'
  const filename = contentType === 'image/png' ? 'upload.png' : 'upload.jpg'
  const presign = await jsonRequest('/api/v1/uploads/presign', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, contentType }),
  })

  const formData = new FormData()
  Object.entries(presign.fields).forEach(([key, value]) => formData.append(key, value))
  formData.append('file', blob, filename)
  const upload = await fetch(presign.uploadUrl, { method: 'POST', body: formData })
  if (!upload.ok) throw new Error('Image upload failed')

  const accepted = await jsonRequest('/api/v1/entries', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ date, s3Key: presign.s3Key }),
  })
  return pollDiaryEntry(accepted.entryId)
}

export async function loadMonth(month) {
  const query = new URLSearchParams({ month })
  const data = await jsonRequest(`/api/v1/entries?${query}`)
  return Object.fromEntries(data.entries.map(entry => [entry.date, toCalendarEntry(entry)]))
}

async function pollDiaryEntry(entryId) {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const entry = await jsonRequest(`/api/v1/entries/${entryId}`)
    console.log('폴링 결과:', entry) 
    if (entry.status === 'FAILED') throw new Error('Emotion analysis failed')
    if (['PLAYLIST_READY', 'EMAIL_SENDING', 'EMAIL_SENT'].includes(entry.status)) return toCalendarEntry(entry)
    await new Promise(resolve => setTimeout(resolve, 1000))
  }
  throw new Error('Emotion analysis timed out')
}

function toCalendarEntry(entry) {
  return {
    albumCover: entry.imageUrl ?? null,
    emotion: entry.emotion ? `${entry.emotion} (${entry.confidence}%)` : 'Processing',
    playlist: entry.playlist ?? [],
  }
}
