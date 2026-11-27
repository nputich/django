import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { registerSW } from 'virtual:pwa-register'
import './styles/theme.css'
import App from './App.jsx'
import { isNativeApp } from './envFlags'

if (isNativeApp()) {
  import('./nativeApp').then(({ initNativeApp }) => initNativeApp())
} else {
  registerSW({ immediate: true })
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
