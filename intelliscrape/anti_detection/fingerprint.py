"""Browser fingerprint generation and randomization."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class BrowserFingerprint:
    """A randomized browser fingerprint."""
    screen_width: int = 1920
    screen_height: int = 1080
    viewport_width: int = 1920
    viewport_height: int = 969
    device_pixel_ratio: float = 1.0
    color_depth: int = 24
    hardware_concurrency: int = 8
    device_memory: int = 8
    platform: str = "Win32"
    language: str = "en-US"
    languages: List[str] = field(default_factory=lambda: ["en-US", "en"])
    timezone: str = "America/New_York"
    timezone_offset: int = -300
    webgl_vendor: str = "Google Inc. (NVIDIA)"
    webgl_renderer: str = "ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0)"
    canvas_hash: Optional[str] = None
    audio_context_hash: Optional[str] = None
    # Canvas fingerprint data (simulated)
    canvas_data: Optional[str] = None
    # WebGL fingerprint data
    webgl_extensions: List[str] = field(default_factory=lambda: [
        "WEBGL_debug_renderer_info",
        "EXT_texture_filter_anisotropic",
        "WEBGL_compressed_texture_s3tc",
    ])
    webgl_params: Dict[str, int] = field(default_factory=lambda: {
        "MAX_TEXTURE_SIZE": 16384,
        "MAX_VERTEX_ATTRIBS": 16,
        "MAX_VIEWPORT_DIMS": [32767, 32767],
    })


# Predefined realistic profiles
_WINDOWS_PROFILES = [
    BrowserFingerprint(
        screen_width=1920, screen_height=1080, viewport_width=1920, viewport_height=969,
        hardware_concurrency=8, device_memory=8, platform="Win32",
        webgl_vendor="Google Inc. (NVIDIA)",
        webgl_renderer="ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0)",
    ),
    BrowserFingerprint(
        screen_width=2560, screen_height=1440, viewport_width=2560, viewport_height=1369,
        hardware_concurrency=16, device_memory=16, platform="Win32",
        webgl_vendor="Google Inc. (NVIDIA)",
        webgl_renderer="ANGLE (NVIDIA, NVIDIA GeForce RTX 4090 Direct3D11 vs_5_0 ps_5_0)",
    ),
    BrowserFingerprint(
        screen_width=1366, screen_height=768, viewport_width=1366, viewport_height=657,
        hardware_concurrency=4, device_memory=4, platform="Win32",
        webgl_vendor="Google Inc. (Intel)",
        webgl_renderer="ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0)",
    ),
    BrowserFingerprint(
        screen_width=1536, screen_height=864, viewport_width=1536, viewport_height=753,
        hardware_concurrency=8, device_memory=8, platform="Win32",
        webgl_vendor="Google Inc. (AMD)",
        webgl_renderer="ANGLE (AMD, AMD Radeon RX 580 Direct3D11 vs_5_0 ps_5_0)",
    ),
]

_MAC_PROFILES = [
    BrowserFingerprint(
        screen_width=2560, screen_height=1600, viewport_width=2560, viewport_height=1509,
        hardware_concurrency=10, device_memory=16, platform="MacIntel",
        webgl_vendor="Apple",
        webgl_renderer="Apple M1 Pro",
    ),
    BrowserFingerprint(
        screen_width=1920, screen_height=1080, viewport_width=1920, viewport_height=969,
        hardware_concurrency=8, device_memory=8, platform="MacIntel",
        webgl_vendor="Apple",
        webgl_renderer="Apple M1",
    ),
]

_LINUX_PROFILES = [
    BrowserFingerprint(
        screen_width=1920, screen_height=1080, viewport_width=1920, viewport_height=969,
        hardware_concurrency=8, device_memory=8, platform="Linux x86_64",
        webgl_vendor="Mesa",
        webgl_renderer="AMD Radeon RX 6700 XT (navi22, LLVM 15.0.7, DRM 3.49)",
    ),
    BrowserFingerprint(
        screen_width=2560, screen_height=1440, viewport_width=2560, viewport_height=1369,
        hardware_concurrency=16, device_memory=16, platform="Linux x86_64",
        webgl_vendor="NVIDIA Corporation",
        webgl_renderer="NVIDIA GeForce RTX 3090/PCIe/SSE2",
    ),
]


def _generate_canvas_hash(seed: str) -> str:
    """Generate a realistic canvas fingerprint hash."""
    # Simulate canvas fingerprinting with deterministic but unique hash
    canvas_str = f"canvas_fingerprint_{seed}_{random.randint(1000, 9999)}"
    return hashlib.md5(canvas_str.encode()).hexdigest()[:16]


def _generate_audio_hash(seed: str) -> str:
    """Generate a realistic audio context fingerprint hash."""
    audio_str = f"audio_context_{seed}_{random.randint(1000, 9999)}"
    return hashlib.md5(audio_str.encode()).hexdigest()[:12]


class FingerprintGenerator:
    """Generates randomized browser fingerprints."""

    def __init__(self, *, seed: Optional[int] = None):
        self.seed = seed
        if seed is not None:
            random.seed(seed)

    def generate(self, platform: Optional[str] = None) -> BrowserFingerprint:
        """Generate a random fingerprint.

        Parameters
        ----------
        platform : str, optional
            Force a specific platform ("windows", "mac", "linux").
            If None, random selection.
        """
        if platform == "windows":
            fp = random.choice(_WINDOWS_PROFILES)
        elif platform == "mac":
            fp = random.choice(_MAC_PROFILES)
        elif platform == "linux":
            fp = random.choice(_LINUX_PROFILES)
        else:
            all_profiles = _WINDOWS_PROFILES + _MAC_PROFILES + _LINUX_PROFILES
            fp = random.choice(all_profiles)

        # Add randomness to the fingerprint
        fp.timezone_offset = random.choice([-300, -240, -180, -120, -60, 0, 60, 120, 180, 240, 300, 330, 345, 360, 390, 420, 480, 540, 570, 600])
        fp.timezone = random.choice([
            "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
            "Europe/London", "Europe/Paris", "Europe/Berlin", "Asia/Tokyo", "Asia/Shanghai",
        ])
        
        # Generate canvas and audio fingerprints
        seed_str = f"{fp.platform}_{fp.screen_width}_{fp.hardware_concurrency}"
        fp.canvas_hash = _generate_canvas_hash(seed_str)
        fp.audio_context_hash = _generate_audio_hash(seed_str)
        fp.canvas_data = f"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        return fp

    def get_js_overrides(self, fp: BrowserFingerprint) -> str:
        """Get JavaScript overrides for the fingerprint."""
        return f"""
        // Hardware
        Object.defineProperty(navigator, 'hardwareConcurrency', {{get: () => {fp.hardware_concurrency}}});
        Object.defineProperty(navigator, 'deviceMemory', {{get: () => {fp.device_memory}}});
        Object.defineProperty(navigator, 'platform', {{get: () => '{fp.platform}'}});
        
        // Screen
        Object.defineProperty(screen, 'width', {{get: () => {fp.screen_width}}});
        Object.defineProperty(screen, 'height', {{get: () => {fp.screen_height}}});
        Object.defineProperty(screen, 'colorDepth', {{get: () => {fp.color_depth}}});
        Object.defineProperty(screen, 'pixelDepth', {{get: () => {fp.color_depth}}});
        
        // Language
        Object.defineProperty(navigator, 'language', {{get: () => '{fp.language}'}});
        Object.defineProperty(navigator, 'languages', {{get: () => {fp.languages}}});
        
        // Timezone
        Date.prototype.getTimezoneOffset = function() {{ return {fp.timezone_offset}; }};
        
        // WebGL
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {{
            if (parameter === 37445) return '{fp.webgl_vendor}';
            if (parameter === 37446) return '{fp.webgl_renderer}';
            return getParameter.apply(this, arguments);
        }};
        
        // Canvas fingerprint
        const toDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = function(type) {{
            if (type === 'image/png' && this.width === 16 && this.height === 16) {{
                return '{fp.canvas_data}';
            }}
            return toDataURL.apply(this, arguments);
        }};
        
        // Audio context
        const audioContext = window.AudioContext || window.webkitAudioContext;
        if (audioContext) {{
            const originalGetChannelData = AudioBuffer.prototype.getChannelData;
            AudioBuffer.prototype.getChannelData = function() {{
                const data = originalGetChannelData.apply(this, arguments);
                // Slight modification to audio fingerprint
                data[0] = data[0] + 0.0001;
                return data;
            }};
        }}
        """
