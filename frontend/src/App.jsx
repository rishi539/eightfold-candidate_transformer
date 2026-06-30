import React, { useState } from 'react';
import axios from 'axios';
import { UploadCloud, CheckCircle, AlertCircle, FileText, Upload } from 'lucide-react';
import './index.css';

// Components
import FileUpload from './components/FileUpload';
import CandidateList from './components/CandidateList';

function App() {
  const [files, setFiles] = useState([]);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleUpload = async () => {
    if (files.length === 0) return;
    
    setLoading(true);
    setError(null);
    
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });

    try {
      const response = await axios.post('http://127.0.0.1:5000/api/transform', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setResults(response.data);
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.error || err.message || 'An error occurred during transformation.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      <header className="header">
        <h1>Candidate Data Transformer</h1>
        <p>Intelligent multi-source identity resolution and normalization</p>
      </header>

      {!results ? (
        <div className="glass-panel" style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
          <FileUpload files={files} setFiles={setFiles} />
          
          {error && (
            <div className="alert alert-danger">
              <AlertCircle size={20} />
              <div>
                <strong>Error Processing Files</strong>
                <p style={{ margin: 0, fontSize: '0.9rem', marginTop: '0.25rem' }}>{error}</p>
              </div>
            </div>
          )}

          <div style={{ textAlign: 'center' }}>
            <button 
              className="btn-primary" 
              onClick={handleUpload}
              disabled={files.length === 0 || loading}
            >
              {loading ? (
                <>
                  <div className="spinner"><UploadCloud size={20} /></div>
                  Processing...
                </>
              ) : (
                <>
                  <Upload size={20} />
                  Transform Profiles
                </>
              )}
            </button>
          </div>
        </div>
      ) : (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
            <div>
              <h2 style={{ fontSize: '1.5rem', marginBottom: '0.25rem' }}>Transformation Complete</h2>
              <p style={{ color: 'var(--text-secondary)' }}>
                Merged {results.metadata.candidate_count} profiles from {results.metadata.source_count} sources.
              </p>
            </div>
            <button className="btn-primary" onClick={() => { setResults(null); setFiles([]); }}>
              Start Over
            </button>
          </div>
          
          <CandidateList candidates={results.candidates} />
        </div>
      )}
    </div>
  );
}

export default App;
