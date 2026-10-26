"""Fingerprint-specific browser stealth patches (init-script JavaScript).

Shared by the Playwright scraping engine and the design-extraction adapter so
both apply exactly the same patches. Kept dependency-free (no engine imports)
so a deployment that only needs design extraction can vendor it as-is.

These patches remove automation tells that bot detectors check first:
``navigator.webdriver``, missing ``window.chrome``, empty ``navigator.plugins``,
and the software-renderer WebGL strings of headless Chromium.
"""

from __future__ import annotations


# JavaScript patches for stealth mode - base version (overridden per-fingerprint)
STEALTH_JS_BASE = """
// Override navigator.webdriver
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});

// Override navigator.plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5]
});

// Override navigator.languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en']
});

// Override chrome runtime
window.chrome = {
    runtime: {},
    loadTimes: function() {},
    csi: function() {},
    app: {}
};

// Override permissions
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);

// Override navigator.connection
Object.defineProperty(navigator, 'connection', {
    get: () => ({
        rtt: 50,
        downlink: 10,
        effectiveType: '4g',
        saveData: false
    })
});

// Override Date to prevent timezone fingerprinting
const OriginalDate = Date;
const originalGetMinutes = OriginalDate.prototype.getMinutes;
OriginalDate.prototype.getMinutes = function() {
    const date = new OriginalDate(this);
    return originalGetMinutes.call(date);
};
"""


def build_stealth_js(fp) -> str:
    """Build fingerprint-specific stealth JS from a FingerprintGenerator profile."""
    return STEALTH_JS_BASE + f"""
// Override navigator.hardwareConcurrency
Object.defineProperty(navigator, 'hardwareConcurrency', {{
    get: () => {fp.hardware_concurrency}
}});

// Override navigator.deviceMemory
Object.defineProperty(navigator, 'deviceMemory', {{
    get: () => {fp.device_memory}
}});

// Override screen dimensions
Object.defineProperty(screen, 'width', {{ get: () => {fp.screen_width} }});
Object.defineProperty(screen, 'height', {{ get: () => {fp.screen_height} }});
Object.defineProperty(screen, 'availWidth', {{ get: () => {fp.screen_width} }});
Object.defineProperty(screen, 'availHeight', {{ get: () => {fp.screen_height} }});
Object.defineProperty(screen, 'colorDepth', {{ get: () => {fp.color_depth} }});

// Override WebGL vendor and renderer
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {{
    if (parameter === 37445) {{
        return '{fp.webgl_vendor}';
    }}
    if (parameter === 37446) {{
        return '{fp.webgl_renderer}';
    }}
    return getParameter.apply(this, arguments);
}};
"""
