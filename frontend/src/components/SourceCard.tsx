import type { Source } from '../types';
import './SourceCard.css';

interface Props {
  source: Source;
  index: number;
}

// Strip .pdf from display name, shorten if too long
function formatFileName(file: string): string {
  return file.replace(/\.pdf$/i, '').replace(/_/g, ' ');
}

export default function SourceCard({ source, index }: Props) {
  return (
    <div className="source-card" title={source.preview}>
      <div className="source-card-header">
        <span className="source-card-num">[{index}]</span>
        <span className="source-card-file">{formatFileName(source.file)}</span>
      </div>
      <div className="source-card-page">Trang {source.page}</div>
    </div>
  );
}
