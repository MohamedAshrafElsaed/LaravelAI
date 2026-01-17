'use client';

import { useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  Circle,
  Loader2,
  ListTodo,
} from 'lucide-react';

export interface TodoItem {
  id: string;
  content: string;
  activeForm?: string;
  status: 'pending' | 'in_progress' | 'completed';
}

interface TodoListProps {
  title?: string;
  todos: TodoItem[];
  collapsible?: boolean;
  defaultExpanded?: boolean;
}

export function TodoList({
  title = 'Tasks',
  todos,
  collapsible = true,
  defaultExpanded = true,
}: TodoListProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  const completedCount = todos.filter((t) => t.status === 'completed').length;
  const inProgressItem = todos.find((t) => t.status === 'in_progress');

  const getStatusIcon = (status: TodoItem['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-green-400" />;
      case 'in_progress':
        return <Loader2 className="h-4 w-4 text-blue-400 animate-spin" />;
      default:
        return <Circle className="h-4 w-4 text-gray-500" />;
    }
  };

  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900/50 overflow-hidden">
      {/* Header */}
      <div
        className={`flex items-center gap-3 px-3 py-2.5 ${collapsible ? 'cursor-pointer hover:bg-gray-800/50' : ''}`}
        onClick={() => collapsible && setIsExpanded(!isExpanded)}
      >
        {collapsible && (
          <span className="text-gray-500">
            {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </span>
        )}

        <ListTodo className="h-4 w-4 text-purple-400" />

        <div className="flex-1 flex items-center gap-2">
          <span className="text-sm font-medium text-white">{title}</span>
          <span className="text-xs text-gray-500">
            {completedCount}/{todos.length}
          </span>
        </div>

        {/* Progress bar */}
        <div className="w-20 h-1.5 bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-green-500 transition-all duration-300"
            style={{ width: `${(completedCount / todos.length) * 100}%` }}
          />
        </div>
      </div>

      {/* Active task indicator */}
      {!isExpanded && inProgressItem && (
        <div className="px-4 py-2 border-t border-gray-800 bg-blue-500/5">
          <div className="flex items-center gap-2 text-xs">
            <Loader2 className="h-3 w-3 text-blue-400 animate-spin" />
            <span className="text-blue-400">{inProgressItem.activeForm || inProgressItem.content}</span>
          </div>
        </div>
      )}

      {/* Todo items */}
      {isExpanded && (
        <div className="border-t border-gray-800">
          {todos.map((todo, index) => (
            <div
              key={todo.id}
              className={`flex items-start gap-3 px-4 py-2 ${
                index !== todos.length - 1 ? 'border-b border-gray-800/50' : ''
              } ${
                todo.status === 'in_progress' ? 'bg-blue-500/5' : ''
              }`}
            >
              <span className="mt-0.5">{getStatusIcon(todo.status)}</span>
              <div className="flex-1 min-w-0">
                <span
                  className={`text-sm ${
                    todo.status === 'completed'
                      ? 'text-gray-500 line-through'
                      : todo.status === 'in_progress'
                      ? 'text-blue-400'
                      : 'text-gray-300'
                  }`}
                >
                  {todo.content}
                </span>
                {todo.status === 'in_progress' && todo.activeForm && (
                  <p className="text-xs text-gray-500 mt-0.5">{todo.activeForm}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
