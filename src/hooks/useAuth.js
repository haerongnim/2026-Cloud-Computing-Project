import { useState } from 'react'

export function useAuth() {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('user')
    return saved ? JSON.parse(saved) : null
  })

  function login(email, password) {
    const users = JSON.parse(localStorage.getItem('users') || '[]')
    const found = users.find(u => u.email === email && u.password === password)
    if (!found) throw new Error('이메일 또는 비밀번호가 틀렸어요')
    localStorage.setItem('user', JSON.stringify(found))
    setUser(found)
  }

  function signup(email, password, nickname) {
    const users = JSON.parse(localStorage.getItem('users') || '[]')
    if (users.find(u => u.email === email)) throw new Error('이미 사용 중인 이메일이에요')
    const newUser = { email, password, nickname }
    localStorage.setItem('users', JSON.stringify([...users, newUser]))
    localStorage.setItem('user', JSON.stringify(newUser))
    setUser(newUser)
  }

  function logout() {
    localStorage.removeItem('user')
    setUser(null)
  }

  return { user, login, signup, logout }
}