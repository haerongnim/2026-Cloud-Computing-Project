import { useState } from 'react'
import { useAuth } from '../hooks/useAuth'

export default function SidePanel({ onAuthChange }) {
  const { user, login, signup, logout } = useAuth(onAuthChange)
  const [isSignup, setIsSignup] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [nickname, setNickname] = useState('')
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    try {
      if (isSignup) {
        await signup(email, password, nickname)
      } else {
        await login(email, password)
      }
      setEmail('')
      setPassword('')
      setNickname('')
    } catch (err) {
      setError(err.message)
    }
  }

  const inputClass =
    'w-full px-3 py-2 rounded-lg border border-[#d4c9b0] bg-white text-sm text-[#5c3d1e] placeholder:text-[#c9b99a] focus:outline-none focus:border-[#a0714f] transition-colors'

  // ── 로그인 후: 프로필 카드
  if (user) {
    return (
      <div className="bg-[#fdf6e3] rounded-2xl border border-[#d4c9b0] shadow-xl p-6 flex flex-col items-center gap-4">
        {/* 아바타 */}
        <div className="w-16 h-16 rounded-full bg-gradient-to-br from-[#e8c49a] to-[#a0714f] flex items-center justify-center text-white text-2xl font-bold shadow-inner">
          {(user.nickname ?? user.email)[0].toUpperCase()}
        </div>

        <div className="text-center">
          <p className="text-base font-semibold text-[#5c3d1e]" style={{ fontFamily: 'var(--font-gmarket)' }}>
            {user.nickname ?? '사용자'}
          </p>
          <p className="text-xs text-[#9c7c4a] mt-0.5">{user.email}</p>
        </div>

        <div className="w-full border-t border-[#e0d5c0]" />

        <div className="w-full text-center">
          <p className="text-xs text-[#9c7c4a] mb-1">나의 감정 기록</p>
          <p className="text-2xl font-bold text-[#a0714f]" style={{ fontFamily: 'var(--font-gmarket)' }}>
            —
          </p>
          <p className="text-xs text-[#c9b99a]">달력에 기록을 남겨봐요</p>
        </div>

        <button
          onClick={logout}
          className="w-full py-2 rounded-xl border border-[#d4c9b0] text-xs text-[#9c7c4a] hover:bg-[#f0e8d5] hover:text-[#5c3d1e] transition-colors"
        >
          로그아웃
        </button>
      </div>
    )
  }

  // ── 로그인 전: 로그인 / 회원가입 폼
  return (
    <div className="bg-[#fdf6e3] rounded-2xl border border-[#d4c9b0] shadow-xl p-6 flex flex-col gap-4">
      <div>
        <p className="text-base font-semibold text-[#5c3d1e]" style={{ fontFamily: 'var(--font-gmarket)' }}>
          {isSignup ? '회원가입' : '로그인'}
        </p>
        <p className="text-xs text-[#9c7c4a] mt-0.5">
          {isSignup ? '감정 다이어리를 시작해봐요' : '나의 감정 기록을 확인해봐요'}
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-2.5">
        {isSignup && (
          <input
            className={inputClass}
            type="text"
            placeholder="닉네임"
            value={nickname}
            onChange={e => setNickname(e.target.value)}
            required
          />
        )}
        <input
          className={inputClass}
          type="email"
          placeholder="이메일"
          value={email}
          onChange={e => setEmail(e.target.value)}
          required
        />
        <input
          className={inputClass}
          type="password"
          placeholder="비밀번호"
          value={password}
          onChange={e => setPassword(e.target.value)}
          required
        />

        {error && (
          <p className="text-xs text-red-400">{error}</p>
        )}

        <button
          type="submit"
          className="w-full py-2.5 rounded-xl bg-[#a0714f] text-white text-sm font-medium hover:bg-[#8a5e3f] transition-colors mt-1"
        >
          {isSignup ? '가입하기' : '로그인'}
        </button>
      </form>

      <button
        onClick={() => { setIsSignup(v => !v); setError('') }}
        className="text-xs text-[#9c7c4a] hover:text-[#5c3d1e] transition-colors text-center"
      >
        {isSignup ? '이미 계정이 있어요 → 로그인' : '회원가입'}
      </button>
    </div>
  )
}