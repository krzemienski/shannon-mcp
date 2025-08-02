/**
 * MCP Client for connecting to Shannon MCP Server
 * Implements all 30 MCP tools with proper request/response handling
 */

import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';
import { io, Socket } from 'socket.io-client';

export interface MCPRequest {
  jsonrpc: string;
  method: string;
  params: any;
  id: string;
}

export interface MCPResponse {
  jsonrpc: string;
  result?: any;
  error?: {
    code: number;
    message: string;
    data?: any;
  };
  id: string;
}

export interface MCPTool {
  name: string;
  description: string;
  inputSchema: any;
}

class MCPClient {
  private baseUrl: string;
  private wsUrl: string;
  private socket: Socket | null = null;
  private pendingRequests: Map<string, (response: MCPResponse) => void> = new Map();
  private onConnectionChange?: (connected: boolean) => void;
  private onMessage?: (message: any) => void;

  constructor(
    baseUrl: string = 'http://localhost:8765',
    wsUrl: string = 'ws://localhost:8765/ws'
  ) {
    this.baseUrl = baseUrl;
    this.wsUrl = wsUrl;
  }

  /**
   * Connect to MCP server via Socket.IO
   */
  async connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.socket = io(this.baseUrl, {
          reconnection: true,
          reconnectionAttempts: 5,
          reconnectionDelay: 1000,
        });

        this.socket.on('connect', () => {
          console.log('Connected to Shannon MCP Server');
          this.onConnectionChange?.(true);
          resolve();
        });

        this.socket.on('response', (response: MCPResponse) => {
          this.onMessage?.(response);

          // Handle pending requests
          const handler = this.pendingRequests.get(response.id);
          if (handler) {
            handler(response);
            this.pendingRequests.delete(response.id);
          }
        });

        this.socket.on('error', (error: any) => {
          console.error('Socket.IO error:', error);
          this.onConnectionChange?.(false);
        });

        this.socket.on('disconnect', () => {
          console.log('Disconnected from Shannon MCP Server');
          this.onConnectionChange?.(false);
        });

        // Handle connection errors
        this.socket.on('connect_error', (error: any) => {
          console.error('Connection error:', error);
          reject(error);
        });
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * Disconnect from MCP server
   */
  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
  }

  /**
   * Set connection change handler
   */
  setConnectionChangeHandler(handler: (connected: boolean) => void): void {
    this.onConnectionChange = handler;
  }

  /**
   * Set message handler
   */
  setMessageHandler(handler: (message: any) => void): void {
    this.onMessage = handler;
  }

  /**
   * Send MCP request
   */
  private async sendRequest(method: string, params: any): Promise<any> {
    const request: MCPRequest = {
      jsonrpc: '2.0',
      method,
      params,
      id: uuidv4()
    };

    if (this.socket && this.socket.connected) {
      // Use Socket.IO
      return new Promise((resolve, reject) => {
        this.pendingRequests.set(request.id, (response) => {
          if (response.error) {
            reject(new Error(response.error.message));
          } else {
            resolve(response.result);
          }
        });

        this.socket!.emit('message', request);

        // Timeout after 30 seconds
        setTimeout(() => {
          if (this.pendingRequests.has(request.id)) {
            this.pendingRequests.delete(request.id);
            reject(new Error('Request timeout'));
          }
        }, 30000);
      });
    } else {
      // Fallback to HTTP
      const response = await axios.post(this.baseUrl, request);
      if (response.data.error) {
        throw new Error(response.data.error.message);
      }
      return response.data.result;
    }
  }

  /**
   * Get available tools
   */
  async getTools(): Promise<MCPTool[]> {
    try {
      const response = await axios.get(`${this.baseUrl}/tools`);
      return response.data.tools || [];
    } catch (error) {
      console.error('Failed to get tools:', error);
      return [];
    }
  }

  // Binary Management Tools

  async findClaudeBinary(): Promise<any> {
    return this.sendRequest('tools/find_claude_binary', {});
  }

  async checkClaudeUpdates(): Promise<any> {
    return this.sendRequest('tools/check_claude_updates', {});
  }

  // Session Management Tools

  async createSession(params: {
    project_id: string;
    command: string;
    args?: string[];
    env?: Record<string, string>;
    cwd?: string;
  }): Promise<any> {
    return this.sendRequest('tools/create_session', params);
  }

  async listSessions(params: {
    status?: string;
    project_id?: string;
    limit?: number;
  } = {}): Promise<any> {
    return this.sendRequest('tools/list_sessions', params);
  }

  async cancelSession(params: {
    session_id: string;
    reason?: string;
  }): Promise<any> {
    return this.sendRequest('tools/cancel_session', params);
  }

  async sendMessage(params: {
    session_id: string;
    message: string;
    message_type?: string;
  }): Promise<any> {
    return this.sendRequest('tools/send_message', params);
  }

  // Agent Management Tools

  async createAgent(params: {
    name: string;
    type: string;
    capabilities?: string[];
    config?: any;
  }): Promise<any> {
    return this.sendRequest('tools/create_agent', params);
  }

  async listAgents(params: {
    status?: string;
    type?: string;
    limit?: number;
  } = {}): Promise<any> {
    return this.sendRequest('tools/list_agents', params);
  }

  async executeAgent(params: {
    agent_id: string;
    action: string;
    parameters?: any;
  }): Promise<any> {
    return this.sendRequest('tools/execute_agent', params);
  }

  async assignTask(params: {
    agent_id: string;
    task: string;
    priority?: string;
    deadline?: string;
    context?: any;
  }): Promise<any> {
    return this.sendRequest('tools/assign_task', params);
  }

  // Checkpoint Management Tools

  async createCheckpoint(params: {
    name: string;
    description?: string;
    files?: string[];
    metadata?: any;
  }): Promise<any> {
    return this.sendRequest('tools/create_checkpoint', params);
  }

  async listCheckpoints(params: {
    project_id?: string;
    limit?: number;
    offset?: number;
  } = {}): Promise<any> {
    return this.sendRequest('tools/list_checkpoints', params);
  }

  async restoreCheckpoint(params: {
    checkpoint_id: string;
    restore_path?: string;
    overwrite?: boolean;
  }): Promise<any> {
    return this.sendRequest('tools/restore_checkpoint', params);
  }

  async branchCheckpoint(params: {
    checkpoint_id: string;
    branch_name: string;
    description?: string;
  }): Promise<any> {
    return this.sendRequest('tools/branch_checkpoint', params);
  }

  // Analytics Tools

  async queryAnalytics(params: {
    metric_type: string;
    time_range?: string;
    aggregation?: string;
    filters?: any;
  }): Promise<any> {
    return this.sendRequest('tools/query_analytics', params);
  }

  // Settings Tools

  async manageSettings(params: {
    action: 'get' | 'update' | 'reset';
    key?: string;
    value?: any;
  }): Promise<any> {
    return this.sendRequest('tools/manage_settings', params);
  }

  async serverStatus(): Promise<any> {
    return this.sendRequest('tools/server_status', {});
  }

  // Project Management Tools

  async createProject(params: {
    name: string;
    path: string;
    description?: string;
    project_type?: string;
    metadata?: any;
  }): Promise<any> {
    return this.sendRequest('tools/create_project', params);
  }

  async listProjects(params: {
    status?: string;
    type?: string;
    limit?: number;
  } = {}): Promise<any> {
    return this.sendRequest('tools/list_projects', params);
  }

  async getProject(params: {
    project_id: string;
  }): Promise<any> {
    return this.sendRequest('tools/get_project', params);
  }

  async updateProject(params: {
    project_id: string;
    updates: {
      name?: string;
      description?: string;
      metadata?: any;
      tags?: string[];
    };
  }): Promise<any> {
    return this.sendRequest('tools/update_project', params);
  }

  async cloneProject(params: {
    project_id: string;
    new_name: string;
    new_path: string;
  }): Promise<any> {
    return this.sendRequest('tools/clone_project', params);
  }

  async archiveProject(params: {
    project_id: string;
    archive_path?: string;
    include_sessions?: boolean;
  }): Promise<any> {
    return this.sendRequest('tools/archive_project', params);
  }

  async getProjectSessions(params: {
    project_id: string;
    status?: string;
    limit?: number;
  }): Promise<any> {
    return this.sendRequest('tools/get_project_sessions', params);
  }

  async setProjectActiveSession(params: {
    project_id: string;
    session_id: string;
  }): Promise<any> {
    return this.sendRequest('tools/set_project_active_session', params);
  }

  async createProjectCheckpoint(params: {
    project_id: string;
    name: string;
    description?: string;
    include_sessions?: boolean;
  }): Promise<any> {
    return this.sendRequest('tools/create_project_checkpoint', params);
  }

  // MCP Server Management Tools

  async mcpAdd(params: {
    name: string;
    transport: string;
    command?: string;
    args?: string[];
    env?: Record<string, string>;
    url?: string;
    scope?: string;
  }): Promise<any> {
    return this.sendRequest('tools/mcp_add', params);
  }

  async mcpList(): Promise<any> {
    return this.sendRequest('tools/mcp_list', {});
  }

  async mcpRemove(name: string): Promise<any> {
    return this.sendRequest('tools/mcp_remove', { name });
  }

  async mcpAddJson(params: {
    name: string;
    jsonConfig: string;
    scope?: string;
  }): Promise<any> {
    return this.sendRequest('tools/mcp_add_json', params);
  }

  async mcpAddFromClaudeDesktop(): Promise<any> {
    return this.sendRequest('tools/mcp_add_from_claude_desktop', {});
  }

  async mcpServe(): Promise<any> {
    return this.sendRequest('tools/mcp_serve', {});
  }
}

export default MCPClient;