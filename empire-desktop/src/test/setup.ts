import '@testing-library/jest-dom'
import { afterEach } from 'vitest'

// Mock localStorage for zustand persist middleware
const store: Record<string, string> = {}
const localStorageMock: Storage = {
  getItem: (key: string) => store[key] ?? null,
  setItem: (key: string, value: string) => { store[key] = value },
  removeItem: (key: string) => { delete store[key] },
  clear: () => { Object.keys(store).forEach(k => delete store[k]) },
  get length() { return Object.keys(store).length },
  key: (index: number) => Object.keys(store)[index] ?? null,
}

Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock, configurable: true })

// Clean localStorage between tests to prevent leaks
afterEach(() => {
  localStorageMock.clear()
})
