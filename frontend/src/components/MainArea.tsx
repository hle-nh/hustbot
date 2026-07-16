import { useChatStore } from '../store/chatStore';
import ChatWindow from './ChatWindow';
import ChatInput from './ChatInput';
import Topbar from './Topbar';
import './MainArea.css';

export default function MainArea() {
  const { activeConversation } = useChatStore();
  const conv = activeConversation();

  return (
    <main className="main-area" role="main">
      <Topbar conversation={conv} />
      <ChatWindow messages={conv?.messages ?? []} />
      <ChatInput />
    </main>
  );
}
