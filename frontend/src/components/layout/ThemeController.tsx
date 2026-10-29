import { useEffect } from 'react'
import { useConfig } from '@/api/config'
import i18n from '@/i18n'

export function accentForeground(hex: string) {
  const channels = hex.slice(1).match(/.{2}/g)?.map(value => parseInt(value, 16) / 255) ?? [0.5, 0.5, 0.5]
  const [r, g, b] = channels.map(value => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4)
  const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
  return 1.05 / (luminance + 0.05) > (luminance + 0.05) / 0.05 ? '#ffffff' : '#111827'
}

export function ThemeController() {
  const { data } = useConfig()
  const theme = data?.theme ?? 'auto'
  const accent = data?.accent_color ?? '#808b9d'
  const language = data?.interface_language_setting ?? '简中'
  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const apply = () => {
      const dark = theme === 'dark' || (theme === 'auto' && media.matches)
      document.documentElement.classList.toggle('dark', dark)
      document.documentElement.style.colorScheme = dark ? 'dark' : 'light'
    }
    apply()
    media.addEventListener('change', apply)
    return () => media.removeEventListener('change', apply)
  }, [theme])
  useEffect(() => {
    document.documentElement.style.setProperty('--primary', accent)
    document.documentElement.style.setProperty('--ring', accent)
    document.documentElement.style.setProperty('--primary-foreground', accentForeground(accent))
  }, [accent])
  useEffect(() => {
    const locale = language === 'English' ? 'en' : 'zh-CN'
    document.documentElement.lang = locale
    void i18n.changeLanguage(locale)
  }, [language])
  return null
}
