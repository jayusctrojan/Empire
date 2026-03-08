/**
 * Tauri Mocks
 * Provides mock implementations for Tauri APIs when running in browser
 */

// Check if running in Tauri environment
export function isTauri(): boolean {
  return typeof window !== 'undefined' && '__TAURI__' in window
}

// Mock database for browser environment
interface MockRow {
  [key: string]: unknown
}

interface MockTable {
  rows: MockRow[]
  autoIncrement: number
}

class MockDatabaseImpl {
  private tables: Map<string, MockTable> = new Map()
  private dbName: string

  constructor(dbName: string) {
    this.dbName = dbName
    this.initTables()
  }

  private initTables() {
    // Initialize default tables
    const defaultTables = [
      'conversations',
      'messages',
      'projects',
      'settings',
    ]
    defaultTables.forEach(name => {
      this.tables.set(name, { rows: [], autoIncrement: 1 })
    })
  }

  static async load(dbName: string): Promise<MockDatabaseImpl> {
    // Simulate async loading
    await new Promise(resolve => setTimeout(resolve, 10))
    return new MockDatabaseImpl(dbName)
  }

  async execute(query: string, params: unknown[] = []): Promise<{ rowsAffected: number }> {
    console.log('[MockDB] Execute:', query, params)

    // Parse basic SQL operations
    const queryLower = query.toLowerCase().trim()

    if (queryLower.startsWith('insert')) {
      return this.handleInsert(query, params)
    } else if (queryLower.startsWith('update')) {
      return this.handleUpdate(query, params)
    } else if (queryLower.startsWith('delete')) {
      return this.handleDelete(query, params)
    } else if (queryLower.startsWith('create table')) {
      return { rowsAffected: 0 }
    }

    return { rowsAffected: 0 }
  }

  async select<T>(query: string, params: unknown[] = []): Promise<T> {
    console.log('[MockDB] Select:', query, params)

    // Extract table name from query
    const tableMatch = query.match(/from\s+(\w+)/i)
    if (!tableMatch) {
      return [] as T
    }

    const tableName = tableMatch[1]
    const table = this.tables.get(tableName)
    if (!table) {
      return [] as T
    }

    // Simple WHERE clause handling
    let results = [...table.rows]

    // Handle WHERE clause with parameter placeholders
    const whereMatch = query.match(/where\s+(.+?)(?:\s+order|\s+limit|\s*$)/i)
    if (whereMatch && params.length > 0) {
      const conditions = whereMatch[1]
      let paramIndex = 0

      results = results.filter(row => {
        // Simple equality check for each parameter
        const parts = conditions.split(/\s+and\s+/i)
        return parts.every(part => {
          const eqMatch = part.match(/(\w+)\s*=\s*\?/i)
          if (eqMatch && paramIndex < params.length) {
            const column = eqMatch[1]
            const value = params[paramIndex++]
            return row[column] === value
          }
          return true
        })
      })
    }

    // Handle ORDER BY
    const orderMatch = query.match(/order\s+by\s+(\w+)\s+(asc|desc)?/i)
    if (orderMatch) {
      const column = orderMatch[1]
      const direction = (orderMatch[2] || 'asc').toLowerCase()
      results.sort((a, b) => {
        const aVal = a[column] as string | number | undefined
        const bVal = b[column] as string | number | undefined
        if (aVal === undefined || bVal === undefined) return 0
        if (aVal < bVal) return direction === 'asc' ? -1 : 1
        if (aVal > bVal) return direction === 'asc' ? 1 : -1
        return 0
      })
    }

    // Handle LIMIT
    const limitMatch = query.match(/limit\s+(\d+)/i)
    if (limitMatch) {
      const limit = parseInt(limitMatch[1], 10)
      results = results.slice(0, limit)
    }

    return results as T
  }

  private handleInsert(query: string, params: unknown[]): { rowsAffected: number } {
    const tableMatch = query.match(/into\s+(\w+)/i)
    if (!tableMatch) return { rowsAffected: 0 }

    const tableName = tableMatch[1]
    let table = this.tables.get(tableName)
    if (!table) {
      table = { rows: [], autoIncrement: 1 }
      this.tables.set(tableName, table)
    }

    // Extract column names
    const columnsMatch = query.match(/\(([^)]+)\)\s*values/i)
    if (!columnsMatch) return { rowsAffected: 0 }

    const columns = columnsMatch[1].split(',').map(c => c.trim())

    // Create new row
    const row: MockRow = {}
    columns.forEach((col, index) => {
      row[col] = params[index] ?? null
    })

    // Handle INSERT OR REPLACE
    if (query.toLowerCase().includes('or replace')) {
      const idColumn = columns.find(c => c === 'id')
      if (idColumn) {
        const existingIndex = table.rows.findIndex(r => r.id === row.id)
        if (existingIndex >= 0) {
          table.rows[existingIndex] = row
          return { rowsAffected: 1 }
        }
      }
    }

    table.rows.push(row)
    return { rowsAffected: 1 }
  }

  private handleUpdate(query: string, params: unknown[]): { rowsAffected: number } {
    const tableMatch = query.match(/update\s+(\w+)/i)
    if (!tableMatch) return { rowsAffected: 0 }

    const tableName = tableMatch[1]
    const table = this.tables.get(tableName)
    if (!table) return { rowsAffected: 0 }

    // Extract SET clause
    const setMatch = query.match(/set\s+(.+?)\s+where/i)
    if (!setMatch) return { rowsAffected: 0 }

    const setColumns = setMatch[1].split(',').map(s => {
      const [col] = s.split('=').map(c => c.trim())
      return col
    })

    // Extract WHERE clause
    const whereMatch = query.match(/where\s+(\w+)\s*=\s*\?/i)
    if (!whereMatch) return { rowsAffected: 0 }

    const whereColumn = whereMatch[1]
    const whereValue = params[params.length - 1]

    let rowsAffected = 0
    table.rows.forEach(row => {
      if (row[whereColumn] === whereValue) {
        setColumns.forEach((col, index) => {
          row[col] = params[index]
        })
        rowsAffected++
      }
    })

    return { rowsAffected }
  }

  private handleDelete(query: string, params: unknown[]): { rowsAffected: number } {
    const tableMatch = query.match(/from\s+(\w+)/i)
    if (!tableMatch) return { rowsAffected: 0 }

    const tableName = tableMatch[1]
    const table = this.tables.get(tableName)
    if (!table) return { rowsAffected: 0 }

    // Extract WHERE clause
    const whereMatch = query.match(/where\s+(\w+)\s*=\s*\?/i)
    if (!whereMatch || params.length === 0) return { rowsAffected: 0 }

    const whereColumn = whereMatch[1]
    const whereValue = params[0]

    const initialLength = table.rows.length
    table.rows = table.rows.filter(row => row[whereColumn] !== whereValue)

    return { rowsAffected: initialLength - table.rows.length }
  }

  async close(): Promise<void> {
    console.log('[MockDB] Database closed:', this.dbName)
  }
}

export const MockDatabase = MockDatabaseImpl
