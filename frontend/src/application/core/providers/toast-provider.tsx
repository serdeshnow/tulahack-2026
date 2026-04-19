import { Toaster } from 'sonner'

export function ToastProvider() {
  return (
    <Toaster
      toastOptions={{
        style: {
          background: '#242926',
          color: '#FBFAF9',
          gap: '12px',
          borderRadius: '12px',
          fontFamily: "Inter, -apple-system, 'Segoe UI', sans-serif"
        }
      }}
      position={'top-right'}
      duration={1000 * 4}
    />
  )
}
