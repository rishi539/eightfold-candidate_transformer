import React, { useCallback } from 'react';
import { UploadCloud, X, File, FileText } from 'lucide-react';

export default function FileUpload({ files, setFiles }) {
  const onDragOver = useCallback((e) => {
    e.preventDefault();
    e.currentTarget.classList.add('drag-active');
  }, []);

  const onDragLeave = useCallback((e) => {
    e.preventDefault();
    e.currentTarget.classList.remove('drag-active');
  }, []);

  const onDrop = useCallback((e) => {
    e.preventDefault();
    e.currentTarget.classList.remove('drag-active');
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const newFiles = Array.from(e.dataTransfer.files);
      setFiles((prev) => [...prev, ...newFiles]);
    }
  }, [setFiles]);

  const onFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const newFiles = Array.from(e.target.files);
      setFiles((prev) => [...prev, ...newFiles]);
    }
  };

  const removeFile = (indexToRemove) => {
    setFiles((prev) => prev.filter((_, idx) => idx !== indexToRemove));
  };

  return (
    <div style={{ marginBottom: '2rem' }}>
      <div 
        className="upload-container"
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => document.getElementById('file-upload-input').click()}
      >
        <input 
          id="file-upload-input" 
          type="file" 
          multiple 
          onChange={onFileChange} 
          style={{ display: 'none' }}
          accept=".json,.pdf,.docx"
        />
        <UploadCloud className="upload-icon" size={48} />
        <div className="upload-text">Click or drag files to upload</div>
        <div className="upload-subtext">Supported formats: JSON (Structured), PDF/DOCX (Unstructured)</div>
      </div>

      {files.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <div className="section-title">Selected Files ({files.length})</div>
          {files.map((f, idx) => (
            <div key={idx} style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center', 
              background: 'rgba(255,255,255,0.05)',
              padding: '0.75rem 1rem',
              borderRadius: '8px',
              border: '1px solid rgba(255,255,255,0.1)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <FileText size={18} color="var(--primary-accent)" />
                <span style={{ fontSize: '0.9rem' }}>{f.name}</span>
              </div>
              <button 
                onClick={() => removeFile(idx)}
                style={{ 
                  background: 'transparent', 
                  border: 'none', 
                  color: 'var(--text-secondary)', 
                  cursor: 'pointer' 
                }}
              >
                <X size={18} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
