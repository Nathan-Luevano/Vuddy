import React from 'react';

export default function ToolStatusBadge({ tool, status }) {
    return (
        <div className={`tool-status-badge tool-status-badge--${status}`}>
            {status === 'calling' && <div className="tool-status-badge__spinner" />}
            {status === 'done' && <span>✓</span>}
            {status === 'error' && <span>✗</span>}
            <span>{tool}</span>
        </div>
    );
}
