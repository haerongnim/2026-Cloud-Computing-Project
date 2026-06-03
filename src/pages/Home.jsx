import { useCallback, useEffect, useState } from 'react'
import Calendar from '../components/Calendar'
import DiaryModal from '../components/modals/DiaryModal'
import UploadModal from '../components/modals/UploadModal'
import ResultModal from '../components/modals/ResultModal'
import SidePanel from '../components/SidePanel'
import { loadAuthSession, loadMonth } from '../api'

export default function Home() {
  const [selectedDate, setSelectedDate] = useState(null)
  const [modalType, setModalType] = useState(null)
  const [resultData, setResultData] = useState(null)
  const [entries, setEntries] = useState({})
  const [identityRevision, setIdentityRevision] = useState(0)
  const [sessionReady, setSessionReady] = useState(false)

  useEffect(() => {
    loadAuthSession().then(() => setSessionReady(true)).catch(console.error)
  }, [])

  const handleMonthChange = useCallback(async month => {
    try {
      setEntries(await loadMonth(month))
    } catch (error) {
      console.error(error)
    }
  }, [identityRevision])

  function handleAuthChange() {
    closeModal()
    setEntries({})
    setIdentityRevision(value => value + 1)
  }

  function handleDateClick(dateStr, hasEntry) {
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
  }

  function closeModal() {
    setSelectedDate(null)
    setModalType(null)
    setResultData(null)
  }

  return (
    <div className="min-h-screen w-full flex items-center justify-center p-8 relative">
      <div className="absolute left-20 top-100 -translate-y-1/2 w-64">
        {sessionReady && <SidePanel onAuthChange={handleAuthChange} />}
      </div>

      {sessionReady && (
        <Calendar entries={entries} onDateClick={handleDateClick} onMonthChange={handleMonthChange} />
      )}

      {modalType === 'diary' && (
        <DiaryModal date={selectedDate} entry={entries[selectedDate]} onClose={closeModal} />
      )}
      {modalType === 'upload' && (
        <UploadModal date={selectedDate} onDone={handleUploadDone} onClose={closeModal} />
      )}
      {modalType === 'result' && (
        <ResultModal date={selectedDate} data={resultData} onSave={handleSave} onClose={closeModal} />
      )}
    </div>
  )
}