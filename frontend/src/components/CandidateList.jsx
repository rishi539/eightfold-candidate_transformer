import React from 'react';
import { Mail, Phone, MapPin, Briefcase, GraduationCap, CheckCircle } from 'lucide-react';

export default function CandidateList({ candidates }) {
  if (!candidates || candidates.length === 0) {
    return (
      <div className="empty-state">
        <h3>No candidates found</h3>
        <p>Try uploading files with valid candidate data.</p>
      </div>
    );
  }

  return (
    <div className="candidates-grid">
      {candidates.map((c, idx) => (
        <CandidateCard key={c.candidate_id || idx} candidate={c} />
      ))}
    </div>
  );
}

function CandidateCard({ candidate }) {
  const getConfidenceLevel = (score) => {
    if (score >= 0.8) return { label: 'High Confidence', class: 'high' };
    if (score >= 0.5) return { label: 'Medium Confidence', class: 'medium' };
    return { label: 'Low Confidence', class: 'low' };
  };

  const conf = getConfidenceLevel(candidate.overall_confidence);

  return (
    <div className="glass-panel candidate-card">
      <div className="candidate-header">
        <div>
          <div className="candidate-name">{candidate.full_name || 'Unknown Candidate'}</div>
          {candidate.headline && <div className="candidate-role">{candidate.headline}</div>}
        </div>
        <div className={`confidence-badge ${conf.class}`} title={`Confidence Score: ${candidate.overall_confidence}`}>
          <CheckCircle size={14} />
          {Math.round(candidate.overall_confidence * 100)}%
        </div>
      </div>

      <div className="contact-info">
        {candidate.emails && candidate.emails.length > 0 && (
          <div className="contact-row">
            <Mail size={16} />
            <span>{candidate.emails[0]}</span>
            {candidate.emails.length > 1 && <span style={{fontSize: '0.75rem', opacity: 0.6}}>+{candidate.emails.length - 1} more</span>}
          </div>
        )}
        
        {candidate.phones && candidate.phones.length > 0 && (
          <div className="contact-row">
            <Phone size={16} />
            <span>{candidate.phones[0]}</span>
          </div>
        )}

        {candidate.location && (candidate.location.city || candidate.location.country) && (
          <div className="contact-row">
            <MapPin size={16} />
            <span>{[candidate.location.city, candidate.location.country].filter(Boolean).join(', ')}</span>
          </div>
        )}
      </div>

      {candidate.skills && candidate.skills.length > 0 && (
        <div>
          <div className="section-title">Top Skills</div>
          <div className="skills-container">
            {candidate.skills.slice(0, 8).map((skill, i) => (
              <span key={i} className="skill-tag">
                {skill.name}
                <span className="skill-conf" title={`Confidence: ${skill.confidence}`}>
                  {Math.round(skill.confidence * 100)}%
                </span>
              </span>
            ))}
            {candidate.skills.length > 8 && (
              <span className="skill-tag" style={{background: 'transparent', borderColor: 'transparent'}}>
                +{candidate.skills.length - 8}
              </span>
            )}
          </div>
        </div>
      )}

      {candidate.experience && candidate.experience.length > 0 && (
        <div>
          <div className="section-title">Latest Experience</div>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start', fontSize: '0.9rem' }}>
            <Briefcase size={16} style={{ color: 'var(--text-secondary)', marginTop: '0.1rem' }} />
            <div>
              <div style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{candidate.experience[0].title}</div>
              <div style={{ color: 'var(--text-secondary)' }}>{candidate.experience[0].company}</div>
              {(candidate.experience[0].start || candidate.experience[0].end) && (
                <div style={{ fontSize: '0.8rem', opacity: 0.7, marginTop: '0.2rem' }}>
                  {candidate.experience[0].start || 'Unknown'} - {candidate.experience[0].end || 'Present'}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {candidate.education && candidate.education.length > 0 && (
        <div style={{ marginTop: 'auto' }}>
          <div className="section-title">Education</div>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start', fontSize: '0.9rem' }}>
            <GraduationCap size={16} style={{ color: 'var(--text-secondary)', marginTop: '0.1rem' }} />
            <div>
              <div style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{candidate.education[0].degree || 'Degree'}</div>
              <div style={{ color: 'var(--text-secondary)' }}>{candidate.education[0].institution}</div>
            </div>
          </div>
        </div>
      )}

      <details style={{ marginTop: '1rem', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '0.5rem' }}>
        <summary style={{ cursor: 'pointer', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>View Raw Projected JSON</summary>
        <pre style={{ fontSize: '0.75rem', background: 'rgba(0,0,0,0.2)', padding: '0.5rem', borderRadius: '4px', overflowX: 'auto', marginTop: '0.5rem', color: 'var(--text-secondary)' }}>
          {JSON.stringify(candidate, null, 2)}
        </pre>
      </details>
    </div>
  );
}
