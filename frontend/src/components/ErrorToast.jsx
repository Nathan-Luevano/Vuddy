import React, { useState, useEffect, useCallback } from 'react';

export default function ErrorToast({ error, onDismiss }) {
    const [visible, setVisible] = useState(false);

    useEffect(() => {
        if (error) {
            setVisible(true);

            // Auto-dismiss recoverable errors after 3s
            if (error.recoverable) {
                const timer = setTimeout(() => {
                    setVisible(false);
                    if (onDismiss) onDismiss();
                }, 3000);
                return () => clearTimeout(timer);
            }
        } else {
            setVisible(false);
        }
    }, [error, onDismiss]);

    const handleDismiss = useCallback(() => {
        setVisible(false);
        if (onDismiss) onDismiss();
    }, [onDismiss]);

    if (!visible || !error) return null;

    const className = error.recoverable
        ? 'error-toast error-toast--warning'
        : 'error-toast error-toast--error';

    return (
        <div className={className} role="alert">
            <span>{error.message}</span>
            <button className="error-toast__dismiss" onClick={handleDismiss} aria-label="Dismiss">
                ×
            </button>
        </div>
    );
}
