export default function ResultModal({ date, data, onSave, onClose }) {
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

        {data?.albumCover && (
          <img src={data.albumCover} alt="selfie" className="w-full rounded-xl mb-4 object-cover max-h-48" />
        )}

        <div className="mb-4">
          <p className="text-xs text-[#9c7c4a] mb-1">감지된 감정</p>
          <p className="text-lg font-medium text-[#5c3d1e]" style={{ fontFamily: 'var(--font-gmarket)' }}>
            {data?.emotion}
          </p>
        </div>

        <div className="mb-6">
          <p className="text-xs text-[#9c7c4a] mb-2">추천 플레이리스트</p>
          {data?.playlist?.length > 0 ? (
            <ul className="space-y-2">
              {data.playlist.map((track, i) => (
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
            <p className="text-sm text-[#c9b99a]">추천 결과가 없어요</p>
          )}
        </div>

        <button
          onClick={onSave}
          className="w-full py-3 rounded-xl bg-[#a0714f] text-white text-sm font-medium hover:bg-[#8a5e3f] transition-colors"
        >
          저장하고 닫기
        </button>
      </div>
    </div>
  )
}