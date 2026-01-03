import { useState, useEffect, useCallback } from 'react'

export type Theme = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

interface UseThemeOptions {
  defaultTheme?: Theme
  storageKey?: string
}

/**
 * Hook to manage theme with system preference detection
 *
 * Follows the system theme when set to 'system' mode,
 * otherwise uses the user's explicit preference.
 */
export function useTheme(options: UseThemeOptions = {}) {
  const { defaultTheme = 'system', storageKey = 'empire-theme' } = options

  const [userTheme, setUserTheme] = useState<Theme>(() => {
    const stored = localStorage.getItem(storageKey)
    return (stored as Theme) || defaultTheme
  })

  const [systemTheme, setSystemTheme] = useState<ResolvedTheme>(() => {
    // Initialize with system preference
    if (typeof window !== 'undefined') {
      return window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'
    }
    return 'dark'
  })

  // Get the resolved theme (what's actually applied)
  const resolvedTheme: ResolvedTheme =
    userTheme === 'system' ? systemTheme : userTheme

  // Listen for system theme changes via media query
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')

    const handleChange = (e: MediaQueryListEvent) => {
      setSystemTheme(e.matches ? 'dark' : 'light')
    }

    mediaQuery.addEventListener('change', handleChange)
    return () => mediaQuery.removeEventListener('change', handleChange)
  }, [])

  // Apply theme to document
  useEffect(() => {
    const root = document.documentElement

    // Remove previous theme class
    root.classList.remove('light', 'dark')

    // Add new theme class
    root.classList.add(resolvedTheme)

    // Update meta theme-color for macOS title bar
    const metaThemeColor = document.querySelector('meta[name="theme-color"]')
    if (metaThemeColor) {
      metaThemeColor.setAttribute(
        'content',
        resolvedTheme === 'dark' ? '#0a0a0a' : '#ffffff'
      )
    }
  }, [resolvedTheme])

  // Persist theme preference
  useEffect(() => {
    localStorage.setItem(storageKey, userTheme)
  }, [userTheme, storageKey])

  const setTheme = useCallback((newTheme: Theme) => {
    setUserTheme(newTheme)
  }, [])

  const toggleTheme = useCallback(() => {
    setUserTheme((current) => {
      if (current === 'dark') return 'light'
      if (current === 'light') return 'system'
      return 'dark'
    })
  }, [])

  return {
    theme: userTheme,
    resolvedTheme,
    systemTheme,
    setTheme,
    toggleTheme,
    isDark: resolvedTheme === 'dark',
    isLight: resolvedTheme === 'light',
    isSystem: userTheme === 'system',
  }
}

export default useTheme
