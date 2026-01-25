import { useState, useEffect, useCallback } from 'react'
import { getMCPClient, type MCPServer, type MCPTool, type MCPResource } from '@/lib/mcp'

/**
 * Hook for interacting with MCP servers
 */
export function useMCP() {
  const [servers, setServers] = useState<MCPServer[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const client = getMCPClient()

  // Refresh server list
  const refreshServers = useCallback(() => {
    setServers(client.getServers())
  }, [client])

  // Register a new server
  const registerServer = useCallback(
    async (config: Omit<MCPServer, 'status'>) => {
      setIsLoading(true)
      setError(null)
      try {
        await client.registerServer(config)
        refreshServers()
      } catch (err) {
        setError(String(err))
      } finally {
        setIsLoading(false)
      }
    },
    [client, refreshServers]
  )

  // Connect to a server
  const connect = useCallback(
    async (serverId: string) => {
      setIsLoading(true)
      setError(null)
      try {
        const result = await client.connect(serverId)
        if (!result.success) {
          setError(result.error ?? 'Connection failed')
        }
        refreshServers()
      } catch (err) {
        setError(String(err))
      } finally {
        setIsLoading(false)
      }
    },
    [client, refreshServers]
  )

  // Disconnect from a server
  const disconnect = useCallback(
    async (serverId: string) => {
      setIsLoading(true)
      setError(null)
      try {
        const result = await client.disconnect(serverId)
        if (!result.success) {
          setError(result.error ?? 'Disconnection failed')
        }
        refreshServers()
      } catch (err) {
        setError(String(err))
      } finally {
        setIsLoading(false)
      }
    },
    [client, refreshServers]
  )

  // List tools from a server
  const listTools = useCallback(
    async (serverId: string): Promise<MCPTool[]> => {
      setIsLoading(true)
      setError(null)
      try {
        const result = await client.listTools(serverId)
        if (!result.success) {
          setError(result.error ?? 'Failed to list tools')
          return []
        }
        return result.data ?? []
      } catch (err) {
        setError(String(err))
        return []
      } finally {
        setIsLoading(false)
      }
    },
    [client]
  )

  // Invoke a tool
  const invokeTool = useCallback(
    async (
      serverId: string,
      toolName: string,
      args?: Record<string, unknown>
    ): Promise<unknown> => {
      setIsLoading(true)
      setError(null)
      try {
        const result = await client.invokeTool(serverId, toolName, args)
        if (!result.success) {
          setError(result.error ?? 'Failed to invoke tool')
          return null
        }
        return result.data
      } catch (err) {
        setError(String(err))
        return null
      } finally {
        setIsLoading(false)
      }
    },
    [client]
  )

  // List resources from a server
  const listResources = useCallback(
    async (serverId: string): Promise<MCPResource[]> => {
      setIsLoading(true)
      setError(null)
      try {
        const result = await client.listResources(serverId)
        if (!result.success) {
          setError(result.error ?? 'Failed to list resources')
          return []
        }
        return result.data ?? []
      } catch (err) {
        setError(String(err))
        return []
      } finally {
        setIsLoading(false)
      }
    },
    [client]
  )

  // Read a resource
  const readResource = useCallback(
    async (serverId: string, uri: string): Promise<string | null> => {
      setIsLoading(true)
      setError(null)
      try {
        const result = await client.readResource(serverId, uri)
        if (!result.success) {
          setError(result.error ?? 'Failed to read resource')
          return null
        }
        return result.data?.contents ?? null
      } catch (err) {
        setError(String(err))
        return null
      } finally {
        setIsLoading(false)
      }
    },
    [client]
  )

  // Initialize on mount
  useEffect(() => {
    refreshServers()
  }, [refreshServers])

  return {
    servers,
    isLoading,
    error,
    registerServer,
    connect,
    disconnect,
    listTools,
    invokeTool,
    listResources,
    readResource,
    refreshServers,
    clearError: () => setError(null),
  }
}

export default useMCP
