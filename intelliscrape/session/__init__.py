"""Session and authentication management."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class UserProfile:
    """A persistent browser profile."""
    name: str
    cookies: Dict[str, str] = field(default_factory=dict)
    local_storage: Dict[str, str] = field(default_factory=dict)
    session_storage: Dict[str, str] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)
    auth_token: str = ""  # JWT/Firebase token for SPA auth


class SessionManager:
    """Manages persistent sessions and authentication.

    Features:
    - Cookie persistence across requests
    - User profile management
    - Login state tracking
    """

    def __init__(self, profiles_dir: Optional[str] = None):
        self.profiles_dir = Path(profiles_dir or os.path.expanduser("~/.intelliscrape/profiles"))
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self._profiles: Dict[str, UserProfile] = {}
        self._current_profile: Optional[str] = None

    def create_profile(self, name: str) -> UserProfile:
        """Create a new user profile."""
        profile = UserProfile(name=name)
        self._profiles[name] = profile
        self._save_profile(profile)
        return profile

    def get_profile(self, name: str) -> Optional[UserProfile]:
        """Get a user profile by name."""
        if name in self._profiles:
            return self._profiles[name]

        # Try to load from disk
        profile = self._load_profile(name)
        if profile:
            self._profiles[name] = profile
        return profile

    def set_current_profile(self, name: str) -> UserProfile:
        """Set the current active profile."""
        profile = self.get_profile(name)
        if not profile:
            profile = self.create_profile(name)
        self._current_profile = name
        return profile

    @property
    def current_profile(self) -> Optional[UserProfile]:
        """Get the current active profile."""
        if self._current_profile:
            return self._profiles.get(self._current_profile)
        return None

    def update_cookies(self, cookies: Dict[str, str], profile_name: Optional[str] = None) -> None:
        """Update cookies for a profile."""
        target = profile_name or self._current_profile
        if not target:
            # Auto-create a default profile for cookie storage
            target = "default"
            self.set_current_profile(target)
        profile = self._profiles.get(target)
        if profile:
            profile.cookies.update(cookies)
            self._save_profile(profile)

    def get_cookies(self, profile_name: Optional[str] = None) -> Dict[str, str]:
        """Get cookies for a profile."""
        profile = self._profiles.get(profile_name or self._current_profile)
        return profile.cookies if profile else {}

    def set_auth_token(self, token: str, profile_name: Optional[str] = None) -> None:
        """Set auth token for a profile (JWT/Firebase token)."""
        target = profile_name or self._current_profile
        if not target:
            target = "default"
            self.set_current_profile(target)
        profile = self._profiles.get(target)
        if profile:
            profile.auth_token = token
            self._save_profile(profile)

    def get_auth_token(self, profile_name: Optional[str] = None) -> str:
        """Get auth token for a profile."""
        profile = self._profiles.get(profile_name or self._current_profile)
        return profile.auth_token if profile else ""

    def clear_profile(self, name: str) -> None:
        """Clear all data for a profile."""
        profile = self.get_profile(name)
        if profile:
            profile.cookies.clear()
            profile.local_storage.clear()
            profile.session_storage.clear()
            profile.meta.clear()
            self._save_profile(profile)

    def delete_profile(self, name: str) -> None:
        """Delete a profile."""
        profile_path = self.profiles_dir / f"{name}.json"
        if profile_path.exists():
            profile_path.unlink()
        self._profiles.pop(name, None)
        if self._current_profile == name:
            self._current_profile = None

    def list_profiles(self) -> List[str]:
        """List all available profiles."""
        profiles = []
        for f in self.profiles_dir.glob("*.json"):
            profiles.append(f.stem)
        return profiles

    def _save_profile(self, profile: UserProfile) -> None:
        """Save profile to disk."""
        profile_path = self.profiles_dir / f"{profile.name}.json"
        data = {
            "name": profile.name,
            "cookies": profile.cookies,
            "local_storage": profile.local_storage,
            "session_storage": profile.session_storage,
            "meta": profile.meta,
            "auth_token": profile.auth_token,
        }
        with open(profile_path, "w") as f:
            json.dump(data, f, indent=2)

    def _load_profile(self, name: str) -> Optional[UserProfile]:
        """Load profile from disk."""
        profile_path = self.profiles_dir / f"{name}.json"
        if not profile_path.exists():
            return None

        try:
            with open(profile_path) as f:
                data = json.load(f)
            return UserProfile(
                name=data["name"],
                cookies=data.get("cookies", {}),
                local_storage=data.get("local_storage", {}),
                session_storage=data.get("session_storage", {}),
                meta=data.get("meta", {}),
                auth_token=data.get("auth_token", ""),
            )
        except Exception:
            return None
