import { useState, useEffect } from 'react'
import { loadAuthSession, loadMonth } from '../api'
import Calendar from '../components/Calendar'
import DiaryModal from '../components/modals/DiaryModal'
import UploadModal from '../components/modals/UploadModal'
import ResultModal from '../components/modals/ResultModal'
import SidePanel from '../components/SidePanel'

export default function Home() {
  const [user, setUser] = useState(null)
  const [selectedDate, setSelectedDate] = useState(null)
  const [modalType, setModalType] = useState(null)
  const [resultData, setResultData] = useState(null)
  const [entries, setEntries] = useState({})
  const [currentMonth, setCurrentMonth] = useState(() => {
    const now = new Date()
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  })

  // 인증 상태 갱신
  function refreshAuth() {
    loadAuthSession()
      .then(({ user: sessionUser }) => setUser(sessionUser))
      .catch(() => setUser(null))
  }

  useEffect(() => { refreshAuth() }, [])

  // 월/유저 바뀔 때 entries 불러오기
  useEffect(() => {
    loadMonth(currentMonth)
      .then(setEntries)
      .catch(() => setEntries({}))
  }, [currentMonth, user])

  function handleDateClick(dateStr, hasEntry) {
    if (!user) return
    setSelectedDate(dateStr)
    setModalType(hasEntry ? 'diary' : 'upload')
  }

  function handleUploadDone(data) {
    setResultData(data)
    setModalType('result')
  }

  function handleSave() {
    if (selectedDate && resultData) {
      setEntries(prev => ({ ...prev, [selectedDate]: resultData }))
    }
    closeModal()
    loadMonth(currentMonth).then(setEntries).catch(() => {})
  }

  function closeModal() {
    setSelectedDate(null)
    setModalType(null)
    setResultData(null)
  }

  return (
  <div className="min-h-screen flex items-center justify-center p-6">
    <div className="flex flex-col xl:flex-row items-center gap-12 max-w-7xl w-full">

      <div className="w-full max-w-sm xl:w-64 flex-shrink-0">
        <SidePanel onAuthChange={refreshAuth} />
      </div>

      <div className="w-full max-w-3xl">
        <Calendar
          entries={entries}
          onDateClick={handleDateClick}
          onMonthChange={setCurrentMonth}
        />
      </div>

    </div>

    {modalType === 'diary' && (
      <DiaryModal
        date={selectedDate}
        entry={entries[selectedDate]}
        onClose={closeModal}
      />
    )}

    {modalType === 'upload' && (
      <UploadModal
        date={selectedDate}
        onDone={handleUploadDone}
        onClose={closeModal}
      />
    )}

    {modalType === 'result' && (
      <ResultModal
        date={selectedDate}
        data={resultData}
        onSave={handleSave}
        onClose={closeModal}
      />
    )}
  </div>
)
}