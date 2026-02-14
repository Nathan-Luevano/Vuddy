// University Theme Presets

export const THEMES = {
    GMU: {
        id: 'gmu',
        label: 'George Mason (Default)',
        colors: {
            '--accent-blue': '#FFCC33',       // Mason Gold (Primary Action)
            '--accent-teal': '#006633',       // Patriot Green (Secondary)
            '--accent-glow': 'rgba(255, 204, 51, 0.2)',
            '--bg-deep': '#002A18',           // Deepest Green
            '--bg-surface': '#004724',        // Dark Green
            '--bg-elevated': '#006633',       // Lighter Green
            '--text-primary': '#ffffff',
            '--text-muted': '#a3c2b0',
        }
    },
    UVA: {
        id: 'uva',
        label: 'UVA',
        colors: {
            '--accent-blue': '#E57200',       // Rotunda Orange
            '--accent-teal': '#232D4B',       // Jefferson Blue
            '--accent-glow': 'rgba(229, 114, 0, 0.2)',
            '--bg-deep': '#0a1628',           // Standard Dark Blue
            '--bg-surface': '#162544',
            '--bg-elevated': '#1e3460',
            '--text-primary': '#f0f4ff',
            '--text-muted': '#8ba3c7',
        }
    },
    VT: {
        id: 'vt',
        label: 'Virginia Tech',
        colors: {
            '--accent-blue': '#CF4420',       // Burnt Orange
            '--accent-teal': '#8B1F41',       // Chicago Maroon (Secondary)
            '--accent-glow': 'rgba(207, 68, 32, 0.15)',
            '--bg-deep': '#f5f5f7',           // Light Gray / White
            '--bg-surface': '#ffffff',        // Pure White
            '--bg-elevated': '#e5e5ea',       // Light Gray for inputs
            '--text-primary': '#630031',      // Maroon for main text
            '--text-muted': '#757575',        // Gray for muted text
            '--text-dim': '#9e9e9e',
        }
    },
    JMU: {
        id: 'jmu',
        label: 'James Madison',
        colors: {
            '--accent-blue': '#CBB677',       // JMU Gold (Primary)
            '--accent-teal': '#450084',       // Duke Dog Purple (Secondary)
            '--accent-glow': 'rgba(203, 182, 119, 0.2)',
            '--bg-deep': '#2C1B3D',           // Deep Purple
            '--bg-surface': '#450084',        // Purple Surface
            '--bg-elevated': '#5C1F8B',       // Lighter Purple
            '--text-primary': '#ffffff',
            '--text-muted': '#e0d4fc',
        }
    },
    ORIGINAL: {
        id: 'original',
        label: 'Vuddy Original',
        colors: {
            '--accent-blue': '#4A90D9',
            '--accent-teal': '#38B2AC',
            '--accent-glow': 'rgba(74, 144, 217, 0.15)',
            '--bg-deep': '#0a1628',
            '--bg-surface': '#162544',
            '--bg-elevated': '#1e3460',
            '--text-primary': '#f0f4ff',
            '--text-muted': '#8ba3c7',
        }
    }
};

export const DEFAULT_THEME = 'gmu';
