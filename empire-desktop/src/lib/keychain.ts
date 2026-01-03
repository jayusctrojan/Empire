import { invoke } from '@tauri-apps/api/core'

/**
 * TypeScript bindings for Rust Keychain commands
 * Provides secure JWT storage in macOS Keychain
 */

/**
 * Store JWT token in system keychain
 */
export async function storeJwt(userId: string, jwt: string): Promise<void> {
  await invoke('store_jwt', { userId, jwt })
}

/**
 * Retrieve JWT token from system keychain
 */
export async function getJwt(userId: string): Promise<string | null> {
  return await invoke<string | null>('get_jwt', { userId })
}

/**
 * Delete JWT token from system keychain
 */
export async function deleteJwt(userId: string): Promise<void> {
  await invoke('delete_jwt', { userId })
}

/**
 * Check if JWT exists in keychain
 */
export async function hasJwt(userId: string): Promise<boolean> {
  return await invoke<boolean>('has_jwt', { userId })
}
