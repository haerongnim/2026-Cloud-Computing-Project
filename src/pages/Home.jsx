import { useCallback, useState, useEffect } from 'react'
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
  <div className="min-h-screen flex items-center justify-center p-6">
    <div className="flex flex-col xl:flex-row items-center gap-12 max-w-7xl w-full">

      <div className="w-full max-w-sm xl:w-64 flex-shrink-0">
        {sessionReady && <SidePanel onAuthChange={handleAuthChange} />}
      </div>

      <div className="w-full max-w-3xl">
        <Calendar
          entries={entries}
          onDateClick={handleDateClick}
          onMonthChange={handleMonthChange}
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