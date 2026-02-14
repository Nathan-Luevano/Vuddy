import React from 'react';

export default function ProviderBadge({ provider }) {
    if (!provider) return null;

    const label = provider === 'patriotai' ? 'PatriotAI' : 'Ollama';
    const className = `provider-badge provider-badge--${provider}`;

    return (
        <div className={className}>
            {label}
        </div>
    );
}
