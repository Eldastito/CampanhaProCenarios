import { useRef, useState } from 'react'

export default function ScreenRecorder() {
  const [recording, setRecording] = useState(false)
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: { frameRate: 30 },
        audio: false,
      })

      chunksRef.current = []
      const recorder = new MediaRecorder(stream, { mimeType: 'video/webm;codecs=vp9' })

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'video/webm' })
        const url = URL.createObjectURL(blob)
        setVideoUrl(url)
        stream.getTracks().forEach((t) => t.stop())
        setRecording(false)
      }

      stream.getVideoTracks()[0].onended = () => {
        recorder.stop()
      }

      recorder.start(1000)
      mediaRecorderRef.current = recorder
      setRecording(true)
      setVideoUrl(null)
    } catch {
      // User cancelled or denied permission
      setRecording(false)
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop()
  }

  function downloadVideo() {
    if (!videoUrl) return
    const a = document.createElement('a')
    a.href = videoUrl
    a.download = `simulacao-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.webm`
    a.click()
  }

  return (
    <div className="flex items-center gap-2">
      {!recording && !videoUrl && (
        <button
          onClick={startRecording}
          className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg bg-red-600 hover:bg-red-700 text-white transition-colors"
        >
          <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
          Gravar Tela
        </button>
      )}

      {recording && (
        <button
          onClick={stopRecording}
          className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg bg-red-700 text-white border border-red-400 animate-pulse"
        >
          <span className="w-2 h-2 rounded-full bg-white" />
          Parar Gravação
        </button>
      )}

      {videoUrl && !recording && (
        <button
          onClick={downloadVideo}
          className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg bg-green-600 hover:bg-green-700 text-white transition-colors"
        >
          ⬇ Baixar Vídeo
        </button>
      )}

      {videoUrl && (
        <button
          onClick={() => setVideoUrl(null)}
          className="text-xs text-gray-400 hover:text-gray-200"
        >
          Nova gravação
        </button>
      )}
    </div>
  )
}
