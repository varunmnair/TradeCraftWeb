import { useState, useEffect, useRef } from 'react';
import {
  Box,
  Paper,
  Typography,
  IconButton,
  TextField,
  Drawer,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Avatar,
  CircularProgress,
  Chip,
  Divider,
} from '@mui/material';
import {
  Close as CloseIcon,
  Send as SendIcon,
  SmartToy as BotIcon,
  Person as PersonIcon,
} from '@mui/icons-material';
import { api } from '../api/client';
import { useSession } from '../context/SessionContext';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface AIChatPanelProps {
  open: boolean;
  onClose: () => void;
  pageContext?: {
    page: string;
    selectedSymbols?: string[];
  };
}

export function AIChatPanel({ open, onClose, pageContext }: AIChatPanelProps) {
  const { sessionId } = useSession();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || !sessionId || loading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await api.chatWithAI(sessionId, userMessage.content, pageContext || undefined);
      
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.response,
        timestamp: new Date(),
      };
      
      setMessages(prev => [...prev, assistantMessage]);
    } catch (err) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `Error: ${err instanceof Error ? err.message : 'Failed to get response'}`,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{
        sx: { width: { xs: '100%', sm: 400 }, maxWidth: '100vw' }
      }}
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        {/* Header */}
        <Paper sx={{ p: 2, borderRadius: 0, display: 'flex', alignItems: 'center', gap: 1 }}>
          <BotIcon color="primary" />
          <Typography variant="h6" sx={{ flex: 1 }}>
            AI Analyst
          </Typography>
          <IconButton onClick={onClose} size="small">
            <CloseIcon />
          </IconButton>
        </Paper>

        {/* Context Info */}
        {pageContext && (
          <Paper sx={{ px: 2, py: 1, borderRadius: 0, bgcolor: 'grey.100' }}>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              <Chip size="small" label={pageContext.page} variant="outlined" />
              {pageContext.selectedSymbols && pageContext.selectedSymbols.length > 0 && (
                <Chip 
                  size="small" 
                  label={`${pageContext.selectedSymbols.length} selected`} 
                  variant="outlined" 
                />
              )}
            </Box>
          </Paper>
        )}

        {/* Messages */}
        <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
          {messages.length === 0 ? (
            <Box sx={{ textAlign: 'center', mt: 4 }}>
              <BotIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
              <Typography variant="body1" color="text.secondary">
                Ask me anything about your portfolio, holdings, or trading strategies.
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                I can help you analyze your positions and suggest actions.
              </Typography>
            </Box>
          ) : (
            <List>
              {messages.map((msg) => (
                <ListItem key={msg.id} alignItems="flex-start" sx={{ px: 0 }}>
                  <ListItemAvatar>
                    <Avatar sx={{ bgcolor: msg.role === 'user' ? 'primary.main' : 'secondary.main' }}>
                      {msg.role === 'user' ? <PersonIcon /> : <BotIcon />}
                    </Avatar>
                  </ListItemAvatar>
                  <ListItemText
                    primary={
                      <Typography
                        variant="body2"
                        sx={{ 
                          whiteSpace: 'pre-wrap',
                          fontFamily: 'monospace',
                          fontSize: '0.85rem',
                          bgcolor: msg.role === 'assistant' ? 'grey.100' : 'primary.50',
                          p: 1.5,
                          borderRadius: 1,
                        }}
                      >
                        {msg.content}
                      </Typography>
                    }
                    secondary={
                      <Typography variant="caption" color="text.secondary">
                        {msg.timestamp.toLocaleTimeString()}
                      </Typography>
                    }
                  />
                </ListItem>
              ))}
              {loading && (
                <ListItem alignItems="flex-start" sx={{ px: 0 }}>
                  <ListItemAvatar>
                    <Avatar sx={{ bgcolor: 'secondary.main' }}>
                      <BotIcon />
                    </Avatar>
                  </ListItemAvatar>
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <CircularProgress size={16} />
                        <Typography variant="body2" color="text.secondary">
                          Thinking...
                        </Typography>
                      </Box>
                    }
                  />
                </ListItem>
              )}
              <div ref={messagesEndRef} />
            </List>
          )}
        </Box>

        <Divider />

        {/* Input */}
        <Paper sx={{ p: 2, borderRadius: 0 }}>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <TextField
              fullWidth
              size="small"
              placeholder="Ask a question..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={loading || !sessionId}
              multiline
              maxRows={4}
            />
            <IconButton 
              color="primary" 
              onClick={handleSend}
              disabled={loading || !input.trim() || !sessionId}
            >
              {loading ? <CircularProgress size={24} /> : <SendIcon />}
            </IconButton>
          </Box>
          {!sessionId && (
            <Typography variant="caption" color="error" sx={{ mt: 1, display: 'block' }}>
              Please start a session to use AI Analyst
            </Typography>
          )}
        </Paper>
      </Box>
    </Drawer>
  );
}

// Floating Button Component
interface AIFloatingButtonProps {
  onClick: () => void;
}

export function AIFloatingButton({ onClick }: AIFloatingButtonProps) {
  return (
    <Box
      onClick={onClick}
      sx={{
        position: 'fixed',
        bottom: 24,
        right: 24,
        width: 56,
        height: 56,
        borderRadius: '50%',
        bgcolor: 'primary.main',
        color: 'white',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        boxShadow: 6,
        transition: 'transform 0.2s, box-shadow 0.2s',
        '&:hover': {
          transform: 'scale(1.1)',
          boxShadow: 8,
        },
        zIndex: 9999,
      }}
    >
      <BotIcon />
    </Box>
  );
}
