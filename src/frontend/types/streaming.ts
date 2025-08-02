/**
 * Types for Claude Code streaming messages
 */

export interface ClaudeStreamMessage {
  type: "assistant" | "user" | "system" | "system_reminder" | "summary";
  subtype?: string;
  message?: ClaudeMessage;
  isMeta?: boolean;
  leafUuid?: string;
  summary?: string;
  session_id?: string;
  model?: string;
  cwd?: string;
  tools?: string[];
  content?: string;
  usage?: Usage;
}

export interface ClaudeMessage {
  content: MessageContent[] | string;
  usage?: Usage;
}

export type MessageContent = 
  | TextContent
  | ToolUseContent
  | ToolResultContent
  | ThinkingContent;

export interface TextContent {
  type: "text";
  text: string | { text: string };
}

export interface ToolUseContent {
  type: "tool_use";
  id: string;
  name: string;
  input: any;
}

export interface ToolResultContent {
  type: "tool_result";
  tool_use_id: string;
  content?: any;
  is_error?: boolean;
}

export interface ThinkingContent {
  type: "thinking";
  thinking: string;
  signature?: string;
}

export interface Usage {
  input_tokens: number;
  output_tokens: number;
  cache_write_tokens?: number;
  cache_read_tokens?: number;
}

/**
 * Session-related types
 */
export interface Session {
  id: string;
  project_id: string;
  project_path: string;
  todo_data?: any;
  created_at: number;
  first_message?: string;
  message_timestamp?: string;
}

export interface Project {
  id: string;
  path: string;
  sessions: string[];
  created_at: number;
}

/**
 * MCP Server types
 */
export interface MCPServer {
  name: string;
  transport: string;
  command?: string;
  args: string[];
  env: Record<string, string>;
  url?: string;
  scope: string;
  is_active: boolean;
  status: ServerStatus;
}

export interface ServerStatus {
  running: boolean;
  error?: string;
  last_checked?: number;
}

/**
 * Agent types
 */
export interface Agent {
  id?: number;
  name: string;
  icon: string;
  system_prompt: string;
  default_task?: string;
  model: string;
  hooks?: string;
  created_at: string;
  updated_at: string;
}

export interface AgentRun {
  id?: number;
  agent_id: number;
  agent_name: string;
  agent_icon: string;
  task: string;
  model: string;
  project_path: string;
  session_id: string;
  status: string;
  pid?: number;
  process_started_at?: string;
  created_at: string;
  completed_at?: string;
}

/**
 * Checkpoint types
 */
export interface Checkpoint {
  id: string;
  sessionId: string;
  projectId: string;
  messageIndex: number;
  timestamp: string;
  description?: string;
  parentCheckpointId?: string;
  metadata: CheckpointMetadata;
}

export interface CheckpointMetadata {
  totalTokens: number;
  modelUsed: string;
  userPrompt: string;
  fileChanges: number;
  snapshotSize: number;
}

export interface TimelineNode {
  checkpoint: Checkpoint;
  children: TimelineNode[];
  fileSnapshotIds: string[];
}

export interface SessionTimeline {
  sessionId: string;
  rootNode?: TimelineNode;
  currentCheckpointId?: string;
  autoCheckpointEnabled: boolean;
  checkpointStrategy: CheckpointStrategy;
  totalCheckpoints: number;
}

export enum CheckpointStrategy {
  Manual = "manual",
  Auto = "auto",
  Smart = "smart"
}