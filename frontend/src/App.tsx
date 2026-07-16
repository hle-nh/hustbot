import './App.css';
import Sidebar from './components/Sidebar';
import MainArea from './components/MainArea';

export default function App() {
  return (
    <div className="app-layout">
      <Sidebar />
      <MainArea />
    </div>
  );
}
