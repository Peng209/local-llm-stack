export type Role = "user" | "assistant";

export interface Message {
  role: Role;
  content: string;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
}

export interface ChatStore {
  conversations: Conversation[];
  activeId: string | null;
}

export interface ChatConfig {
  model: string;
  maxContextTokens: number;
}

export interface User {
  id: string;
  email: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: number;
  updated_at: number;
}

export interface ConversationDetail {
  id: string;
  title: string;
  messages: { id: string; role: Role; content: string; seq: number }[];
  created_at: number;
  updated_at: number;
}
