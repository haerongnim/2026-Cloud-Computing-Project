import { useState, useRef } from 'react'
import { createDiaryEntry } from '../../api'

export default function UploadModal({ date, onDone, onClose }) {
  const [mode, setMode] = useState(null)
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)

  const fileInputRef = useRef(null)
  const videoRef = useRef(null)
  const streamRef = useRef(null)

  async function startCamera() {
    setMode('camera')
    const stream = await navigator.mediaDevices.getUserMedia({ video: true })
    streamRef.current = stream
    if (videoRef.current) videoRef.current.srcObject = stream
  }

  function stopCamera() {
    streamRef.current?.getTracks().forEach(t => t.stop())
  }

  function capturePhoto() {
    const canvas = document.createElement('canvas')
    canvas.width = videoRef.current.videoWidth
    canvas.height = videoRef.current.videoHeight
    canvas.getContext('2d').drawImage(videoRef.current, 0, 0)
    setPreview(canvas.toDataURL('image/jpeg'))
    stopCamera()
  }

  function handleFileChange(e) {
    const file = e.target.files[0]
    if (!file) return
    setMode('file')
    const reader = new FileReader()
    reader.onload = () => setPreview(reader.result)
    reader.readAsDataURL(file)
  }

  async function handleAnalyze() {
    if (!preview) return
    setLoading(true)

    try {
      const res = await fetch(preview)
      const blob = await res.blob()

      const result = await createDiaryEntry({ blob, date })
      onDone({ ...result, albumCover: result.albumCover ?? preview })
    } catch (error) {
      console.error(error)
      alert('분석 중 오류가 발생했습니다.')
    } finally {
      setLoading(false)
    }
  }

  const btnBase = 'w-full py-3 rounded-xl border border-[#d4c9b0] bg-white text-[#5c3d1e] text-sm font-medium hover:bg-[#fdf6e3] transition-colors'

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
      onClick={() => { stopCamera(); onClose() }}
    >
      <div
        className="bg-[#fdf6e3] rounded-2xl border border-[#d4c9b0] w-full max-w-sm p-6 relative shadow-xl"
        onClick={e => e.stopPropagation()}
      >
        <button
          onClick={() => { stopCamera(); onClose() }}
          className="absolute top-4 right-4 text-[#9c7c4a] hover:text-[#5c3d1e] text-xl leading-none"
        >
          ×
        </button>

        <p className="text-xs text-[#9c7c4a] tracking-widest mb-4">{date}</p>
        <p className="text-base font-medium text-[#5c3d1e] mb-5" style={{ fontFamily: 'var(--font-gmarket)' }}>
          오늘의 셀카를 올려봐요
        </p>

        {!mode && !preview && (
          <div className="flex flex-col gap-3">
            <button className={btnBase} onClick={startCamera}>📷 카메라로 촬영</button>
            <button className={btnBase} onClick={() => fileInputRef.current.click()}>🖼 파일에서 선택</button>
            <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleFileChange} />
          </div>
        )}

        {mode === 'camera' && !preview && (
          <div className="flex flex-col items-center gap-3">
            <video ref={videoRef} autoPlay playsInline className="w-full rounded-xl" />
            <button className={btnBase} onClick={capturePhoto}>촬영</button>
          </div>
        )}

        {preview && (
          <div className="flex flex-col items-center gap-4">
            <img src={preview} alt="preview" className="w-full rounded-xl object-cover max-h-52" />
            <button
              className="w-full py-3 rounded-xl bg-[#a0714f] text-white text-sm font-medium hover:bg-[#8a5e3f] transition-colors disabled:opacity-50"
              onClick={handleAnalyze}
              disabled={loading}
            >
              {loading ? '분석 중...' : '감정 분석하기'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}