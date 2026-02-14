import React from 'react';

export default function MessageBubble({ message }) {
    const { role, text, tool_results } = message;
    const isUser = role === 'user';

    return (
        <div className={`message-bubble message-bubble--${isUser ? 'user' : 'assistant'}`}>
            <div>{text}</div>
            {tool_results && tool_results.length > 0 && (
                <div className="message-bubble__tool-results">
                    {tool_results.map((tr, i) => (
                        <div key={i}>🔧 {tr.tool}: {tr.summary}</div>
                    ))}
                </div>
            )}
        </div>
    );
}
