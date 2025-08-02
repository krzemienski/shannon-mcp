/**
 * Tool widgets for displaying Claude Code tool usage
 * Extracted from Claudia implementation
 */

import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Check, X, FileText, FolderOpen, Terminal, Search, Edit, Save } from 'lucide-react';

interface ToolWidgetProps {
  children: React.ReactNode;
  title: string;
  icon?: React.ReactNode;
  collapsible?: boolean;
  defaultCollapsed?: boolean;
  status?: 'pending' | 'success' | 'error';
}

export const ToolWidget: React.FC<ToolWidgetProps> = ({
  children,
  title,
  icon,
  collapsible = true,
  defaultCollapsed = false,
  status,
}) => {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  const statusIcon = status === 'success' ? <Check className="h-4 w-4 text-green-500" /> :
                     status === 'error' ? <X className="h-4 w-4 text-red-500" /> :
                     null;

  return (
    <div className="tool-widget border rounded-lg overflow-hidden bg-muted/30">
      <div 
        className={`tool-header px-3 py-2 flex items-center gap-2 ${collapsible ? 'cursor-pointer hover:bg-muted/50' : ''}`}
        onClick={() => collapsible && setCollapsed(!collapsed)}
      >
        {icon}
        <span className="font-medium text-sm">{title}</span>
        {statusIcon}
        <div className="flex-1" />
        {collapsible && (
          collapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />
        )}
      </div>
      {!collapsed && (
        <div className="tool-content px-3 py-2 border-t">
          {children}
        </div>
      )}
    </div>
  );
};

interface TodoWidgetProps {
  todos: Array<{
    id: string;
    content: string;
    status: string;
    priority: string;
  }>;
  result?: any;
}

export const TodoWidget: React.FC<TodoWidgetProps> = ({ todos, result }) => {
  const getStatusEmoji = (status: string) => {
    switch (status) {
      case 'completed': return '✅';
      case 'in_progress': return '🔄';
      case 'blocked': return '🚧';
      default: return '📋';
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high': return 'text-red-500';
      case 'medium': return 'text-yellow-500';
      case 'low': return 'text-green-500';
      default: return '';
    }
  };

  return (
    <ToolWidget 
      title={`Todo List (${todos.length} items)`}
      icon={<FileText className="h-4 w-4 text-blue-500" />}
      status={result?.error ? 'error' : result ? 'success' : 'pending'}
    >
      <div className="space-y-1">
        {todos.map((todo, idx) => (
          <div key={todo.id || idx} className="flex items-start gap-2 text-sm">
            <span>{getStatusEmoji(todo.status)}</span>
            <span className={`flex-1 ${todo.status === 'completed' ? 'line-through opacity-60' : ''}`}>
              {todo.content}
            </span>
            <span className={`text-xs ${getPriorityColor(todo.priority)}`}>
              {todo.priority}
            </span>
          </div>
        ))}
      </div>
    </ToolWidget>
  );
};

interface EditWidgetProps {
  file_path: string;
  old_string?: string;
  new_string?: string;
  result?: any;
}

export const EditWidget: React.FC<EditWidgetProps> = ({ file_path, old_string, new_string, result }) => {
  const [showDiff, setShowDiff] = useState(true);

  return (
    <ToolWidget 
      title={`Edit: ${file_path.split('/').pop()}`}
      icon={<Edit className="h-4 w-4 text-yellow-500" />}
      status={result?.error ? 'error' : result ? 'success' : 'pending'}
    >
      <div className="space-y-2">
        <div className="text-xs text-muted-foreground">{file_path}</div>
        
        {showDiff && old_string && new_string && (
          <div className="space-y-2">
            <div className="bg-red-50 dark:bg-red-950/30 p-2 rounded text-xs">
              <div className="font-semibold text-red-600 dark:text-red-400 mb-1">- Old</div>
              <pre className="whitespace-pre-wrap">{old_string}</pre>
            </div>
            <div className="bg-green-50 dark:bg-green-950/30 p-2 rounded text-xs">
              <div className="font-semibold text-green-600 dark:text-green-400 mb-1">+ New</div>
              <pre className="whitespace-pre-wrap">{new_string}</pre>
            </div>
          </div>
        )}
        
        {result?.error && (
          <div className="text-red-500 text-sm">{result.error}</div>
        )}
      </div>
    </ToolWidget>
  );
};

interface BashWidgetProps {
  command: string;
  description?: string;
  timeout?: number;
  result?: any;
}

export const BashWidget: React.FC<BashWidgetProps> = ({ command, description, result }) => {
  const [showOutput, setShowOutput] = useState(true);

  return (
    <ToolWidget 
      title={description || 'Bash Command'}
      icon={<Terminal className="h-4 w-4 text-green-500" />}
      status={result?.error ? 'error' : result ? 'success' : 'pending'}
    >
      <div className="space-y-2">
        <div className="bg-muted p-2 rounded font-mono text-sm">
          $ {command}
        </div>
        
        {result?.output && showOutput && (
          <div className="bg-black text-green-400 p-2 rounded font-mono text-xs max-h-96 overflow-auto">
            <pre>{result.output}</pre>
          </div>
        )}
        
        {result?.error && (
          <div className="text-red-500 text-sm">{result.error}</div>
        )}
      </div>
    </ToolWidget>
  );
};

interface ReadWidgetProps {
  file_path: string;
  limit?: number;
  offset?: number;
  result?: any;
}

export const ReadWidget: React.FC<ReadWidgetProps> = ({ file_path, limit, offset, result }) => {
  const [showContent, setShowContent] = useState(false);

  return (
    <ToolWidget 
      title={`Read: ${file_path.split('/').pop()}`}
      icon={<FileText className="h-4 w-4 text-blue-500" />}
      status={result?.error ? 'error' : result ? 'success' : 'pending'}
      defaultCollapsed={true}
    >
      <div className="space-y-2">
        <div className="text-xs text-muted-foreground">
          {file_path}
          {(limit || offset) && (
            <span className="ml-2">
              {offset && `offset: ${offset}`}
              {limit && offset && ', '}
              {limit && `limit: ${limit}`}
            </span>
          )}
        </div>
        
        {result?.content && (
          <div 
            className="bg-muted p-2 rounded font-mono text-xs cursor-pointer"
            onClick={() => setShowContent(!showContent)}
          >
            {showContent ? (
              <pre className="whitespace-pre-wrap max-h-96 overflow-auto">{result.content}</pre>
            ) : (
              <div className="text-muted-foreground">Click to show content ({result.content.split('\n').length} lines)</div>
            )}
          </div>
        )}
        
        {result?.error && (
          <div className="text-red-500 text-sm">{result.error}</div>
        )}
      </div>
    </ToolWidget>
  );
};

interface LSWidgetProps {
  path: string;
  result?: any;
}

export const LSWidget: React.FC<LSWidgetProps> = ({ path, result }) => {
  return (
    <ToolWidget 
      title={`List Directory: ${path.split('/').pop() || '/'}`}
      icon={<FolderOpen className="h-4 w-4 text-yellow-500" />}
      status={result?.error ? 'error' : result ? 'success' : 'pending'}
      defaultCollapsed={true}
    >
      <div className="space-y-2">
        <div className="text-xs text-muted-foreground">{path}</div>
        
        {result?.entries && (
          <div className="space-y-1 max-h-96 overflow-auto">
            {result.entries.map((entry: any, idx: number) => (
              <div key={idx} className="flex items-center gap-2 text-sm font-mono">
                {entry.is_directory ? (
                  <FolderOpen className="h-3 w-3 text-yellow-500" />
                ) : (
                  <FileText className="h-3 w-3 text-blue-500" />
                )}
                <span>{entry.name}</span>
                {!entry.is_directory && entry.size && (
                  <span className="text-xs text-muted-foreground ml-auto">
                    {formatFileSize(entry.size)}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
        
        {result?.error && (
          <div className="text-red-500 text-sm">{result.error}</div>
        )}
      </div>
    </ToolWidget>
  );
};

interface GrepWidgetProps {
  pattern: string;
  path?: string;
  glob?: string;
  result?: any;
}

export const GrepWidget: React.FC<GrepWidgetProps> = ({ pattern, path, glob, result }) => {
  return (
    <ToolWidget 
      title="Search Files"
      icon={<Search className="h-4 w-4 text-purple-500" />}
      status={result?.error ? 'error' : result ? 'success' : 'pending'}
    >
      <div className="space-y-2">
        <div className="text-sm">
          <span className="font-medium">Pattern:</span> <code className="bg-muted px-1 rounded">{pattern}</code>
        </div>
        {path && (
          <div className="text-sm">
            <span className="font-medium">Path:</span> {path}
          </div>
        )}
        {glob && (
          <div className="text-sm">
            <span className="font-medium">Files:</span> {glob}
          </div>
        )}
        
        {result?.matches && (
          <div className="space-y-2 max-h-96 overflow-auto">
            {result.matches.map((match: any, idx: number) => (
              <div key={idx} className="bg-muted p-2 rounded text-xs">
                <div className="font-medium">{match.file}:{match.line}</div>
                <pre className="whitespace-pre-wrap">{match.content}</pre>
              </div>
            ))}
          </div>
        )}
        
        {result?.error && (
          <div className="text-red-500 text-sm">{result.error}</div>
        )}
      </div>
    </ToolWidget>
  );
};

interface WriteWidgetProps {
  file_path: string;
  content: string;
  result?: any;
}

export const WriteWidget: React.FC<WriteWidgetProps> = ({ file_path, content, result }) => {
  const [showContent, setShowContent] = useState(false);
  const lineCount = content.split('\n').length;

  return (
    <ToolWidget 
      title={`Write: ${file_path.split('/').pop()}`}
      icon={<Save className="h-4 w-4 text-green-500" />}
      status={result?.error ? 'error' : result ? 'success' : 'pending'}
    >
      <div className="space-y-2">
        <div className="text-xs text-muted-foreground">{file_path}</div>
        
        <div 
          className="bg-muted p-2 rounded text-xs cursor-pointer"
          onClick={() => setShowContent(!showContent)}
        >
          {showContent ? (
            <pre className="whitespace-pre-wrap max-h-96 overflow-auto">{content}</pre>
          ) : (
            <div className="text-muted-foreground">
              Click to show content ({lineCount} lines, {content.length} chars)
            </div>
          )}
        </div>
        
        {result?.error && (
          <div className="text-red-500 text-sm">{result.error}</div>
        )}
      </div>
    </ToolWidget>
  );
};

// Helper functions
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B';
  const kb = bytes / 1024;
  if (kb < 1024) return kb.toFixed(1) + ' KB';
  const mb = kb / 1024;
  if (mb < 1024) return mb.toFixed(1) + ' MB';
  const gb = mb / 1024;
  return gb.toFixed(1) + ' GB';
}

// Export all widgets
export default {
  ToolWidget,
  TodoWidget,
  EditWidget,
  BashWidget,
  ReadWidget,
  LSWidget,
  GrepWidget,
  WriteWidget,
};