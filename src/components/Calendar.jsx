import { useState } from 'react'
import DateCell from './DateCell'

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTHS = [
  'January','February','March','April','May','June',
  'July','August','September','October','November','December'
]

export default function Calendar({ entries, onDateClick }) {
  const now = new Date()
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth())

  const todayYear = now.getFullYear()
  const todayMonth = now.getMonth()
  const todayDate = now.getDate()

  const firstDay = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()

  function prevMonth() {
    if (month === 0) { setYear(y => y - 1); setMonth(11) }
    else setMonth(m => m - 1)
  }
  function nextMonth() {
    if (month === 11) { setYear(y => y + 1); setMonth(0) }
    else setMonth(m => m + 1)
  }

  const cells = []
  for (let i = 0; i < firstDay; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(d)

  return (
    <div className="w-full max-w-3xl rounded-2xl shadow-xl border border-[#d4c9b0] bg-[#fdf6e3]">
      <div className="px-10 py-8">

        {/* 헤더 */}
        <div className="flex items-center justify-between mb-8">
          <button
            onClick={prevMonth}
            className="w-8 h-8 flex items-center justify-center rounded-full text-lg text-[#9c7c4a] hover:bg-[#f0e8d5] transition-colors"
          >‹</button>

          <div className="text-center">
            <h1
              className="text-4xl tracking-[0.25em] text-[#5c3d1e]"
              style={{ fontFamily: 'var(--font-gmarket)', fontWeight: 700 }}
            >
              {MONTHS[month].toUpperCase()}
            </h1>
            <p className="text-sm mt-1 tracking-[0.3em] text-[#9c7c4a]">{year}</p>
          </div>

          <button
            onClick={nextMonth}
            className="w-8 h-8 flex items-center justify-center rounded-full text-lg text-[#9c7c4a] hover:bg-[#f0e8d5] transition-colors"
          >›</button>
        </div>

        {/* 요일 헤더 */}
        <div className="grid grid-cols-7 mb-3">
          {WEEKDAYS.map(d => (
            <div key={d} className="text-center text-xs font-medium py-1 tracking-wider text-[#9c7c4a]">
              {d}
            </div>
          ))}
        </div>

        {/* 날짜 그리드 — 다크 배경으로 감쌈 */}
        <div className="rounded-xl overflow-hidden p-3">
          <div className="grid grid-cols-7 gap-2">
            {cells.map((day, i) => {
              if (!day) return <div key={`empty-${i}`} />

              const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
              const entry = entries[dateStr] ?? null
              const isToday = day === todayDate && month === todayMonth && year === todayYear

              return (
                <DateCell
                  key={dateStr}
                  day={day}
                  entry={entry}
                  isToday={isToday}
                  onClick={() => onDateClick(dateStr, !!entry)}
                />
              )
            })}
          </div>
        </div>

      </div>
    </div>
  )
}