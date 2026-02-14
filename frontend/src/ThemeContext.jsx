import React, { createContext, useContext, useState, useEffect } from 'react';
import { THEMES } from './themes';

const ThemeContext = createContext();

export function useTheme() {
    return useContext(ThemeContext);
}

export function ThemeProvider({ children }) {
    // Load from localStorage or default to GMU
    const [activeTheme, setActiveTheme] = useState(() => {
        return localStorage.getItem('vuddy_theme') || 'gmu';
    });

    useEffect(() => {
        const theme = Object.values(THEMES).find(t => t.id === activeTheme) || THEMES.GMU;

        // Apply CSS variables to :root
        const root = document.documentElement;
        if (theme && theme.colors) {
            Object.entries(theme.colors).forEach(([key, value]) => {
                root.style.setProperty(key, value);
            });
        }

        localStorage.setItem('vuddy_theme', activeTheme);
    }, [activeTheme]);

    return (
        <ThemeContext.Provider value={{ activeTheme, setActiveTheme, themes: Object.values(THEMES) }}>
            {children}
        </ThemeContext.Provider>
    );
}
