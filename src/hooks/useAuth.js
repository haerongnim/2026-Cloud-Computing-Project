import { useEffect, useState } from 'react'
import { loadAuthSession, loginAccount, logoutAccount, signupAccount } from '../api'

export function useAuth(onAuthChange) {
  const [user, setUser] = useState(null)

  useEffect(() => {
    loadAuthSession().then(({ user: sessionUser }) => setUser(sessionUser)).catch(console.error)
  }, [])

  async function login(email, password) {
    const { user: sessionUser } = await loginAccount(email, password)
    setUser(sessionUser)
    onAuthChange?.()
  }

  async function signup(email, password, nickname) {
    const { user: sessionUser } = await signupAccount(email, password, nickname)
    setUser(sessionUser)
    onAuthChange?.()
  }

  async function logout() {
    await logoutAccount()
    setUser(null)
    onAuthChange?.()
  }

  return { user, login, signup, logout }
}