export default function DiaryModal({ date, entry, onClose }) {
  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-[#fdf6e3] rounded-2xl border border-[#d4c9b0] w-full max-w-sm p-6 relative shadow-xl"
        onClick={e => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-[#9c7c4a] hover:text-[#5c3d1e] text-xl leading-none"
        >
          ×
        </button>

        <p className="text-xs text-[#9c7c4a] tracking-widest mb-4">{date}</p>

        {entry?.albumCover && (
          <img src={entry.albumCover} alt="selfie" className="w-full rounded-xl mb-4 object-cover max-h-48" />
        )}

        <div className="mb-4">
          <p className="text-xs text-[#9c7c4a] mb-1">감정</p>
          <p className="text-lg font-medium text-[#5c3d1e]" style={{ fontFamily: 'var(--font-gmarket)' }}>
            {entry?.emotion ?? '—'}
          </p>
        </div>

        <div>
          <p className="text-xs text-[#9c7c4a] mb-2">플레이리스트</p>
          {entry?.playlist?.length > 0 ? (
            <ul className="space-y-2">
              {entry.playlist.map((track, i) => (
                <li key={i} className="flex items-center gap-3 bg-white rounded-lg p-2 border border-[#e0d5c0]">
                  {track.albumCover && <img src={track.albumCover} alt="" className="w-10 h-10 rounded object-cover" />}
                  <div>
                    <p className="text-sm font-medium text-[#5c3d1e]">{track.name}</p>
                    <p className="text-xs text-[#9c7c4a]">{track.artist}</p>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-[#c9b99a]">저장된 플레이리스트가 없어요</p>
          )}
        </div>
      </div>
    </div>
  )
}