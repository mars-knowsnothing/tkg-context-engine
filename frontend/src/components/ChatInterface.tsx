'use client';

import { useState, useEffect, useRef } from 'react';
import { Send, Bot, User, MessageCircle, Brain, Database, Clock } from 'lucide-react';
import { chatApi } from '@/lib/api';
import { ChatMessage, ChatResponse, KnowledgeNode } from '@/lib/types';
import { formatDate, generateId } from '@/lib/utils';
import { cn } from '@/lib/utils';

const ChatInterface = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Generate session ID on component mount
    setSessionId(generateId());
    
    // Add welcome message
    setMessages([{
      role: 'system',
      content: 'Welcome to the TKG Context Engine! I can help you query your knowledge graph and find relevant information. Ask me anything about your data.',
      timestamp: new Date().toISOString()
    }]);
  }, []);

  useEffect(() => {
    // Auto-scroll to bottom when new messages are added
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: inputMessage.trim(),
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await chatApi.chat({
        message: userMessage.content,
        session_id: sessionId
      });

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.response,
        timestamp: new Date().toISOString()
      };

      setMessages(prev => [...prev, assistantMessage]);

      // If there's query result data, add it as a system message
      if (response.query_result) {
        const resultMessage: ChatMessage = {
          role: 'system',
          content: JSON.stringify(response.query_result, null, 2),
          timestamp: new Date().toISOString()
        };
        setMessages(prev => [...prev, resultMessage]);
      }

    } catch (error) {
      console.error('Failed to send message:', error);
      const errorMessage: ChatMessage = {
        role: 'system',
        content: 'Sorry, I encountered an error processing your request. Please try again.',
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const clearSession = () => {
    setMessages([{
      role: 'system',
      content: 'Session cleared. How can I help you?',
      timestamp: new Date().toISOString()
    }]);
    setSessionId(generateId());
  };

  const MessageBubble = ({ message }: { message: ChatMessage }) => {
    const isUser = message.role === 'user';
    const isSystem = message.role === 'system';
    
    let parsedResult = null;
    if (isSystem && message.content.startsWith('{')) {
      try {
        parsedResult = JSON.parse(message.content);
      } catch (e) {
        // Not JSON, treat as regular message
      }
    }

    return (
      <div className={cn(
        "flex mb-6",
        isUser ? "justify-end" : "justify-start"
      )}>
        <div className={cn(
          "flex items-start space-x-3 max-w-3xl",
          isUser ? "flex-row-reverse space-x-reverse" : "flex-row"
        )}>
          {/* Avatar */}
          <div className={cn(
            "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
            isUser 
              ? "bg-blue-500" 
              : isSystem 
              ? "bg-purple-500"
              : "bg-green-500"
          )}>
            {isUser ? (
              <User className="w-4 h-4 text-white" />
            ) : isSystem ? (
              <Database className="w-4 h-4 text-white" />
            ) : (
              <Bot className="w-4 h-4 text-white" />
            )}
          </div>

          {/* Message Content */}
          <div className={cn(
            "glass p-4 rounded-2xl",
            isUser 
              ? "bg-blue-500/20 border-blue-500/30" 
              : isSystem 
              ? "bg-purple-500/20 border-purple-500/30"
              : "bg-gray-500/20 border-gray-500/30"
          )}>
            {/* Regular message */}
            {!parsedResult && (
              <div>
                <p className="text-white leading-relaxed whitespace-pre-wrap">
                  {message.content}
                </p>
                <p className="text-xs text-gray-400 mt-2">
                  {formatDate(message.timestamp)}
                </p>
              </div>
            )}

            {/* Query result */}
            {parsedResult && (
              <div className="space-y-4">
                <div className="flex items-center space-x-2">
                  <Brain className="w-5 h-5 text-purple-400" />
                  <h4 className="text-white font-medium">Query Results</h4>
                  <span className="px-2 py-1 bg-purple-500/20 text-purple-300 text-xs rounded-full">
                    {parsedResult.confidence * 100}% confidence
                  </span>
                </div>
                
                <p className="text-gray-300 text-sm">
                  {parsedResult.explanation}
                </p>

                {/* Nodes */}
                {parsedResult.nodes && parsedResult.nodes.length > 0 && (
                  <div>
                    <h5 className="text-white font-medium mb-2 flex items-center">
                      <Database className="w-4 h-4 mr-2 text-blue-400" />
                      Found Nodes ({parsedResult.nodes.length})
                    </h5>
                    <div className="space-y-2">
                      {parsedResult.nodes.map((node: KnowledgeNode) => (
                        <div key={node.id} className="glass p-3 rounded-lg border border-white/10">
                          <div className="flex items-center justify-between">
                            <div>
                              <h6 className="text-white font-medium text-sm">
                                {node.name}
                              </h6>
                              <p className="text-gray-400 text-xs mt-1">
                                {node.content}
                              </p>
                            </div>
                            <span className={cn(
                              "px-2 py-1 rounded-full text-xs font-medium",
                              node.type === 'entity' ? 'bg-blue-500/20 text-blue-300' :
                              node.type === 'event' ? 'bg-green-500/20 text-green-300' :
                              'bg-purple-500/20 text-purple-300'
                            )}>
                              {node.type}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <p className="text-xs text-gray-400">
                  {formatDate(message.timestamp)}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  const SuggestedQueries = () => {
    const suggestions = [
      "Show me all entities in the knowledge graph",
      "What events happened recently?",
      "Find concepts related to testing",
      "What is the Sample Entity?",
      "Tell me about the knowledge graph structure"
    ];

    return (
      <div className="glass p-4 rounded-lg mb-4">
        <h4 className="text-white font-medium mb-3 flex items-center">
          <MessageCircle className="w-4 h-4 mr-2 text-blue-400" />
          Suggested Queries
        </h4>
        <div className="flex flex-wrap gap-2">
          {suggestions.map((suggestion, index) => (
            <button
              key={index}
              onClick={() => setInputMessage(suggestion)}
              className="px-3 py-1 bg-blue-500/20 text-blue-300 text-sm rounded-full hover:bg-blue-500/30 transition-colors duration-200"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="h-[calc(100vh-12rem)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2 terminal-text">
            Interactive Chat Query
          </h1>
          <p className="text-gray-400">
            Ask questions about your knowledge graph in natural language
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2 glass px-3 py-2 rounded-lg">
            <Clock className="w-4 h-4 text-green-400" />
            <span className="text-sm text-gray-300">Session Active</span>
          </div>
          <button
            onClick={clearSession}
            className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg transition-colors duration-200"
          >
            Clear Session
          </button>
        </div>
      </div>

      {/* Chat Container */}
      <div className="flex-1 glass rounded-xl overflow-hidden flex flex-col">
        {/* Messages */}
        <div className="flex-1 p-6 overflow-y-auto custom-scrollbar">
          {messages.length === 1 && <SuggestedQueries />}
          
          {messages.map((message, index) => (
            <MessageBubble key={index} message={message} />
          ))}
          
          {/* Loading indicator */}
          {isLoading && (
            <div className="flex justify-start mb-6">
              <div className="flex items-start space-x-3 max-w-3xl">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-green-500 flex items-center justify-center">
                  <Bot className="w-4 h-4 text-white" />
                </div>
                <div className="glass p-4 rounded-2xl bg-gray-500/20 border-gray-500/30">
                  <div className="flex items-center space-x-2">
                    <div className="flex space-x-1">
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    </div>
                    <span className="text-gray-400 text-sm">Thinking...</span>
                  </div>
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="border-t border-white/10 p-4">
          <div className="flex space-x-4">
            <div className="flex-1 relative">
              <textarea
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Ask me anything about your knowledge graph..."
                className="w-full px-4 py-3 pr-12 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-400/50 resize-none"
                rows={1}
                style={{ minHeight: '44px', maxHeight: '120px' }}
              />
              <button
                onClick={handleSendMessage}
                disabled={!inputMessage.trim() || isLoading}
                className="absolute right-2 top-1/2 transform -translate-y-1/2 p-2 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg transition-colors duration-200"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;