export default function DateCell({ day, entry, isToday, onClick }) {
  return (
    <div
      onClick={onClick}
      className={[
        'group relative aspect-square rounded-lg border cursor-pointer overflow-hidden',
        'flex flex-col items-center justify-center transition-all duration-150',
        entry
          ? 'border-[#c9a96e] bg-white'
          : isToday
          ? 'border-[#a0714f] bg-[#fff8ee]'
          : 'border-[#e0d5c0] bg-[#fffef9] hover:border-[#c9a96e] hover:bg-[#fdf6e3]',
      ].join(' ')}
    >
      {entry ? (
        <>
          {/* 앨범 커버 (위 65%) */}
          <div className="absolute inset-0 bottom-[30%]">
            {entry.albumCover ? (
              <img
                src={entry.albumCover}
                alt="album"
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="w-full h-full bg-gradient-to-br from-[#e8c49a] to-[#c47c5a]" />
            )}
          </div>
          {/* 날짜 숫자 (아래) */}
          <span className="absolute bottom-1 text-[11px] font-medium text-[#5c3d1e]">
            {day}
          </span>
        </>
      ) : (
        <>
          <span className={[
            'text-xs transition-all duration-150 text-[#9c7c4a]',
            isToday ? 'font-semibold text-[#a0714f]' : '',
            'group-hover:opacity-0',
          ].join(' ')}>
            {day}
          </span>
          {/* hover 시 + */}
          <span className="absolute text-xl text-[#a0714f] opacity-0 group-hover:opacity-100 transition-opacity duration-150">
            +
          </span>
        </>
      )}
    </div>
  )
}