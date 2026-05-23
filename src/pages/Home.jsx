import { useState } from 'react'
import Calendar from '../components/Calendar'
import DiaryModal from '../components/modals/DiaryModal'
import UploadModal from '../components/modals/UploadModal'
import ResultModal from '../components/modals/ResultModal'
import SidePanel from '../components/SidePanel'

const DUMMY_ENTRIES = {
  '2026-05-01': { albumCover: null, emotion: 'Happy (82%)', playlist: [{ name: 'Good as Hell', artist: 'Lizzo', albumCover: '' }] },
  '2026-05-03': { albumCover: null, emotion: 'Calm (74%)', playlist: [] },
  '2026-05-07': { albumCover: null, emotion: 'Sad (61%)', playlist: [] },
  '2026-05-10': { albumCover: null, emotion: 'Surprised (55%)', playlist: [] },
  '2026-05-15': { albumCover: null, emotion: 'Happy (90%)', playlist: [] },
  '2026-05-19': { albumCover: null, emotion: 'Calm (68%)', playlist: [] },
}

export default function Home() {
  const [selectedDate, setSelectedDate] = useState(null)
  const [modalType, setModalType] = useState(null)
  const [resultData, setResultData] = useState(null)
  const [entries, setEntries] = useState(DUMMY_ENTRIES)

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
        <SidePanel />
      </div>

      <Calendar entries={entries} onDateClick={handleDateClick} />

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