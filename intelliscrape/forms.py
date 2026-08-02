"""Form submission and interaction for IntelliScrape."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


@dataclass
class FormField:
    """A form field."""
    name: str
    type: str = "text"
    value: str = ""
    required: bool = False
    options: List[str] = field(default_factory=list)


@dataclass
class Form:
    """An HTML form."""
    action: str
    method: str = "GET"
    fields: List[FormField] = field(default_factory=list)
    enctype: str = "application/x-www-form-urlencoded"


class FormSubmitter:
    """Handle form detection and submission."""
    
    def __init__(self, session=None):
        self.session = session
    
    def find_forms(self, html: str, base_url: str = "") -> List[Form]:
        """Find all forms in HTML.
        
        Parameters
        ----------
        html : str
            HTML content.
        base_url : str, optional
            Base URL for resolving relative action URLs.
            
        Returns
        -------
        List[Form]
            List of detected forms.
        """
        soup = BeautifulSoup(html, "html.parser")
        forms = []
        
        for form_tag in soup.find_all("form"):
            action = form_tag.get("action", "")
            if action and base_url:
                action = urljoin(base_url, action)
            elif not action:
                action = base_url
            
            method = form_tag.get("method", "GET").upper()
            enctype = form_tag.get("enctype", "application/x-www-form-urlencoded")
            
            fields = []
            for input_tag in form_tag.find_all(["input", "select", "textarea"]):
                field = self._parse_field(input_tag)
                if field:
                    fields.append(field)
            
            forms.append(Form(
                action=action,
                method=method,
                fields=fields,
                enctype=enctype,
            ))
        
        return forms
    
    def find_search_form(self, html: str, base_url: str = "") -> Optional[Form]:
        """Try to find the search form (common patterns)."""
        soup = BeautifulSoup(html, "html.parser")
        
        # Common search form patterns
        search_patterns = [
            {"attrs": {"role": "search"}},
            {"attrs": {"aria-label": "search"}},
            {"attrs": {"aria-label": "Search"}},
            {"class_": "search"},
            {"class_": "search-form"},
            {"id": "search"},
            {"id": "search-form"},
        ]
        
        for pattern in search_patterns:
            form_tag = soup.find("form", **pattern)
            if form_tag:
                action = form_tag.get("action", "")
                if action and base_url:
                    action = urljoin(base_url, action)
                
                method = form_tag.get("method", "GET").upper()
                
                fields = []
                for input_tag in form_tag.find_all(["input", "select", "textarea"]):
                    field = self._parse_field(input_tag)
                    if field:
                        fields.append(field)
                
                return Form(
                    action=action,
                    method=method,
                    fields=fields,
                )
        
        # Try to find form with search-related input
        for form_tag in soup.find_all("form"):
            for input_tag in form_tag.find_all("input"):
                name = input_tag.get("name", "").lower()
                placeholder = input_tag.get("placeholder", "").lower()
                if any(term in name or term in placeholder for term in ["search", "query", "q", "keyword"]):
                    action = form_tag.get("action", "")
                    if action and base_url:
                        action = urljoin(base_url, action)
                    
                    method = form_tag.get("method", "GET").upper()
                    
                    fields = []
                    for inp in form_tag.find_all(["input", "select", "textarea"]):
                        field = self._parse_field(inp)
                        if field:
                            fields.append(field)
                    
                    return Form(
                        action=action,
                        method=method,
                        fields=fields,
                    )
        
        return None
    
    def submit(
        self,
        form: Form,
        data: Dict[str, str],
        *,
        session=None,
        timeout: int = 30,
    ) -> Optional[str]:
        """Submit a form.
        
        Parameters
        ----------
        form : Form
            Form to submit.
        data : Dict[str, str]
            Form data (field_name: value).
        session : requests.Session, optional
            Session to use for request.
        timeout : int
            Request timeout.
            
        Returns
        -------
        str or None
            Response HTML if successful.
        """
        if not self.session and not session:
            raise ValueError("Session required for form submission")
        
        sess = session or self.session
        
        # Merge form data with provided data
        form_data = {}
        for field in form.fields:
            if field.name in data:
                form_data[field.name] = data[field.name]
            elif field.value:
                form_data[field.name] = field.value
        
        # Add any extra data
        for key, value in data.items():
            if key not in form_data:
                form_data[key] = value
        
        try:
            if form.method == "GET":
                response = sess.get(
                    form.action,
                    params=form_data,
                    timeout=timeout,
                    allow_redirects=True,
                )
            else:
                response = sess.post(
                    form.action,
                    data=form_data,
                    timeout=timeout,
                    allow_redirects=True,
                )
            
            return response.text
            
        except Exception as e:
            print(f"Form submission failed: {e}")
            return None
    
    def search(
        self,
        html: str,
        query: str,
        base_url: str = "",
        *,
        session=None,
        timeout: int = 30,
    ) -> Optional[str]:
        """Find and submit search form.
        
        Parameters
        ----------
        html : str
            HTML content containing search form.
        query : str
            Search query.
        base_url : str, optional
            Base URL for form action.
        session : requests.Session, optional
            Session to use.
        timeout : int
            Request timeout.
            
        Returns
        -------
        str or None
            Search results HTML.
        """
        form = self.find_search_form(html, base_url)
        if not form:
            return None
        
        # Find the search field and set query
        data = {}
        for field in form.fields:
            if field.type == "search" or field.name.lower() in ["q", "query", "search", "keyword", "s"]:
                data[field.name] = query
                break
        
        if not data:
            # Try first text field
            for field in form.fields:
                if field.type in ["text", "search"]:
                    data[field.name] = query
                    break
        
        return self.submit(form, data, session=session, timeout=timeout)
    
    def _parse_field(self, tag) -> Optional[FormField]:
        """Parse an input/select/textarea tag into a FormField."""
        name = tag.get("name")
        if not name:
            return None
        
        tag_name = tag.name.lower()
        
        if tag_name == "select":
            options = [opt.get("value", opt.text) for opt in tag.find_all("option")]
            return FormField(
                name=name,
                type="select",
                options=options,
            )
        elif tag_name == "textarea":
            return FormField(
                name=name,
                type="textarea",
                value=tag.text or "",
            )
        else:
            field_type = tag.get("type", "text").lower()
            value = tag.get("value", "")
            required = tag.get("required") is not None
            
            return FormField(
                name=name,
                type=field_type,
                value=value,
                required=required,
            )
