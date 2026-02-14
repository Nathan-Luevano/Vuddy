import React, { useState, useEffect, useCallback } from 'react';
import { TABS, WS_RECV_TYPES, ASSISTANT_STATES } from './constants';
import { useWebSocket } from './hooks/useWebSocket';
import { AudioProvider } from './AudioEngine';
import { ThemeProvider } from './ThemeContext';
import WakeScreen from './components/WakeScreen';
import ProviderBadge from './components/ProviderBadge';
import ErrorToast from './components/ErrorToast';
import BottomNav from './components/BottomNav';
import HomeTab from './components/HomeTab';
import EventsTab from './components/EventsTab';
import StudyTab from './components/StudyTab';
import CalendarTab from './components/CalendarTab';
import SettingsTab from './components/SettingsTab';

export default function App() {
    const [isAwake, setIsAwake] = useState(false);
    const [activeTab, setActiveTab] = useState(TABS.HOME);
    const [assistantState, setAssistantState] = useState(ASSISTANT_STATES.IDLE);
    const [error, setError] = useState(null);

    const { sendMessage, lastMessage, isConnected, llmProvider } = useWebSocket();

    // Handle incoming WS messages for state and error
    useEffect(() => {
        if (!lastMessage) return;

        switch (lastMessage.type) {
            case WS_RECV_TYPES.ASSISTANT_STATE:
                setAssistantState(lastMessage.state);
                break;

            case WS_RECV_TYPES.ERROR:
                setError({
                    message: lastMessage.message,
                    recoverable: lastMessage.recoverable,
                });
                break;

            default:
                break;
        }
    }, [lastMessage]);

    const handleDismissError = useCallback(() => {
        setError(null);
    }, []);

    // Show WakeScreen until user taps
    if (!isAwake) {
        return (
            <ThemeProvider>
                <WakeScreen onWake={() => setIsAwake(true)} />
            </ThemeProvider>
        );
    }

    return (
        <ThemeProvider>
            <AudioProvider>
                <div className="app-container">
                    {/* <ProviderBadge provider={llmProvider} /> */}
                    <ErrorToast error={error} onDismiss={handleDismissError} />

                    <main className="tab-content">
                        {activeTab === TABS.HOME && (
                            <HomeTab
                                sendMessage={sendMessage}
                                lastMessage={lastMessage}
                                assistantState={assistantState}
                            />
                        )}
                        {activeTab === TABS.EVENTS && <EventsTab />}
                        {activeTab === TABS.STUDY && <StudyTab />}
                        {activeTab === TABS.CALENDAR && <CalendarTab />}
                        {activeTab === TABS.SETTINGS && <SettingsTab />}
                    </main>

                    <BottomNav activeTab={activeTab} onTabChange={setActiveTab} />
                </div>
            </AudioProvider>
        </ThemeProvider>
    );
}
