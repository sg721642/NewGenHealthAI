const QUICK_QUESTIONS = [
  { icon: 'fa-thermometer', label: 'Fever Symptoms', q: 'What are the symptoms of fever and when is medical care needed?' },
  { icon: 'fa-head-side-virus', label: 'Headache Treatment', q: 'How can I safely manage a tension headache at home?' },
  { icon: 'fa-heart-pulse', label: 'High Blood Pressure', q: 'What causes elevated blood pressure and what are key warning signs?' },
  { icon: 'fa-notes-medical', label: 'Diabetes Management', q: 'Tell me about evidence-based lifestyle strategies for diabetes management.' },
  { icon: 'fa-virus-covid', label: 'COVID Prevention', q: 'What are the current preventive measures and guidelines for COVID-19?' },
  { icon: 'fa-pills', label: 'Cold Remedies', q: 'What are safe supportive remedies for common cold symptoms?' },
];

export default function WelcomeScreen({ onQuickQuestion, onTriggerImageUpload, onTriggerVoiceInput }) {
  return (
    <div className="welcome-screen">
      <div className="welcome-content-container">
        {/* Hero Eyebrow & Badge */}
        <div className="welcome-hero-badge">
          <span className="badge-pulse-dot" />
          <span className="badge-text">Clinical AI Intake & Educational Assistant</span>
        </div>

        {/* Main Title & Description */}
        <h1 className="welcome-title">Welcome to NewGenHealthAI</h1>
        <p className="welcome-description">
          A calm, private medical intake and clinical education system. Explore symptoms, analyze supported medical imagery, or discuss general health questions.
        </p>

        {/* Fast Action Capability Cards */}
        <div className="welcome-actions-row">
          <button
            type="button"
            className="action-card"
            onClick={() => onQuickQuestion('I would like to describe my symptoms for educational guidance.')}
          >
            <div className="action-card-icon">
              <i className="fas fa-stethoscope" />
            </div>
            <div className="action-card-text">
              <span className="action-card-title">Symptom Intake</span>
              <span className="action-card-desc">Educational evaluation of symptoms</span>
            </div>
          </button>

          <button
            type="button"
            className="action-card"
            onClick={onTriggerImageUpload}
          >
            <div className="action-card-icon">
              <i className="fas fa-image" />
            </div>
            <div className="action-card-text">
              <span className="action-card-title">Medical Image Analysis</span>
              <span className="action-card-desc">Skin, X-ray, or retinal scans</span>
            </div>
          </button>

          <button
            type="button"
            className="action-card"
            onClick={onTriggerVoiceInput}
          >
            <div className="action-card-icon">
              <i className="fas fa-microphone" />
            </div>
            <div className="action-card-text">
              <span className="action-card-title">Voice Consultation</span>
              <span className="action-card-desc">Speak directly using Groq Whisper</span>
            </div>
          </button>
        </div>

        {/* Quick Questions Section */}
        <div className="quick-questions-section">
          <div className="quick-questions-header">
            <span className="section-label">Example Health Questions</span>
            <span className="section-note">Click any question to begin</span>
          </div>

          <div className="quick-questions-grid">
            {QUICK_QUESTIONS.map(({ icon, label, q }) => (
              <button
                key={label}
                type="button"
                className="quick-question-card"
                onClick={() => onQuickQuestion(q)}
              >
                <div className="qq-card-top">
                  <div className="qq-icon-wrap" aria-hidden="true">
                    <i className={`fas ${icon}`} />
                  </div>
                  <span className="qq-label">{label}</span>
                </div>
                <p className="qq-text">{q}</p>
                <div className="qq-arrow" aria-hidden="true">
                  <i className="fas fa-arrow-right" />
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Emergency Notice & Clinical Scope */}
        <div className="welcome-clinical-notice">
          <div className="notice-icon">
            <i className="fas fa-shield-halved" />
          </div>
          <div className="notice-content">
            <strong>Important Clinical Notice:</strong> NewGenHealthAI provides AI-generated educational health information and does not establish a physician-patient relationship. In the event of chest pain, difficulty breathing, stroke symptoms, or severe trauma, immediately contact emergency services (112 / 108 in India, or your local emergency services) or visit the nearest emergency room.
          </div>
        </div>
      </div>
    </div>
  );
}
