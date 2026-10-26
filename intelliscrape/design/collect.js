// IntelliScrape Design Extract collector — runs in a live, rendered page.
//
// Versioned, packaged application code. It is NOT caller-supplied JavaScript
// and must never be replaced by arbitrary user input. Everything it reads is
// treated as untrusted data on return.
//
// Collects a bounded, representative set of visible elements plus their
// resolved computed styles and geometry, the :root custom properties, and any
// declared @media (min/max-width) conditions reachable from accessible
// stylesheets. Inaccessible cssRules (cross-origin) are caught, not fatal.

(() => {
  const MAX_ELEMENTS = __MAX_ELEMENTS__;
  const LABEL_MAX = 80;

  // Property set we record. Longhand where shorthand would lose meaning.
  const STYLE_PROPS = [
    // text
    "fontFamily", "fontSize", "fontWeight", "fontStyle", "lineHeight",
    "letterSpacing", "textAlign", "textTransform", "textDecorationLine",
    "color",
    // background / fill
    "backgroundColor", "backgroundImage", "backgroundSize", "backgroundPosition",
    // box
    "borderTopWidth", "borderTopStyle", "borderTopColor",
    "borderBottomWidth", "borderRightWidth", "borderLeftWidth",
    "borderTopLeftRadius", "borderTopRightRadius",
    "borderBottomLeftRadius", "borderBottomRightRadius",
    "boxShadow", "opacity", "outlineWidth", "outlineStyle", "outlineColor",
    // spacing (longhand top/right/bottom/left)
    "paddingTop", "paddingRight", "paddingBottom", "paddingLeft",
    "marginTop", "marginBottom",
    // layout
    "display", "position", "flexDirection", "justifyContent", "alignItems",
    "gap", "gridTemplateColumns", "width", "height", "maxWidth",
    // effects
    "filter", "backdropFilter", "transform",
    // svg
    "fill", "stroke",
  ];

  const sanitizeLabel = (s) => {
    if (!s) return "";
    return s.replace(/\s+/g, " ").trim().slice(0, LABEL_MAX);
  };

  // Stable-ish element id: tag + nth-of-type path. Deterministic for a fixed
  // DOM so re-runs of the same page produce comparable ids.
  const idFor = (() => {
    let counter = 0;
    const map = new Map();
    return (el) => {
      if (map.has(el)) return map.get(el);
      const parts = [];
      let node = el;
      while (node && node.nodeType === 1 && node !== document.documentElement) {
        let idx = 1;
        let sib = node.previousElementSibling;
        while (sib) {
          if (sib.tagName === node.tagName) idx++;
          sib = sib.previousElementSibling;
        }
        parts.unshift(node.tagName.toLowerCase() + ":" + idx);
        node = node.parentElement;
      }
      const id = "el-" + (counter++) + "|" + parts.slice(-4).join(">");
      map.set(el, id);
      return id;
    };
  })();

  const visible = (el, rect, cs) => {
    if (cs.display === "none" || cs.visibility === "hidden") return false;
    if (parseFloat(cs.opacity) === 0) return false;
    if (rect.width < 1 || rect.height < 1) return false;
    return true;
  };

  const observations = [];
  const rootVars = {};
  const mediaWidths = new Set();

  // --- :root custom properties (token candidates) ---
  try {
    const rootCS = getComputedStyle(document.documentElement);
    // Enumerate declared custom properties via a style probe of the root
    // stylesheet rules where accessible.
    for (const sheet of Array.from(document.styleSheets)) {
      let rules;
      try {
        rules = sheet.cssRules;
      } catch (e) {
        continue; // cross-origin stylesheet; still affects computed styles
      }
      if (!rules) continue;
      for (const rule of Array.from(rules)) {
        // @media (min-width / max-width) conditions = declared evidence.
        if (rule.media && rule.media.mediaText) {
          const txt = rule.media.mediaText;
          const m = txt.match(/(?:min|max)-width:\s*([\d.]+(?:px|rem|em))/i);
          if (m) mediaWidths.add(txt.trim());
        }
        if (rule.style) {
          for (const name of Array.from(rule.style)) {
            if (name.startsWith("--")) {
              const val = rootCS.getPropertyValue(name).trim();
              if (val) rootVars[name] = val;
            }
          }
        }
      }
    }
    // Fallback probe: some roots expose vars not captured above.
    if (Object.keys(rootVars).length === 0) {
      const probe = document.createElement("div");
      probe.style.cssText = "position:absolute;visibility:hidden;";
      document.body && document.body.appendChild(probe);
      probe.style.setProperty("--__probe", "1");
      // No portable way to enumerate without cssRules; leave as-is.
      probe.remove && probe.remove();
    }
  } catch (e) {
    /* root var enumeration is best-effort */
  }

  // --- element walk (TreeWalker) ---
  const walker = document.createTreeWalker(
    document.body || document.documentElement,
    NodeFilter.SHOW_ELEMENT,
    {
      acceptNode: (node) => {
        // Skip obviously non-visual containers.
        const tag = node.tagName;
        if (tag === "SCRIPT" || tag === "STYLE" || tag === "NOSCRIPT" || tag === "TEMPLATE") {
          return NodeFilter.FILTER_REJECT;
        }
        return NodeFilter.FILTER_ACCEPT;
      },
    },
  );

  // Single pass: filter for visibility WHILE walking, so MAX_ELEMENTS bounds
  // usable observations rather than raw DOM nodes. Walking first and filtering
  // afterward let invisible scaffolding consume the whole cap — an inline icon
  // sprite's zero-size <defs>/<symbol>/<path> children stack at the top of
  // document order, so a 120-node walk of sentry.io kept 7 of ~2500 visible
  // elements. The cap now counts only what can actually be measured.
  let node;
  while ((node = walker.nextNode()) && observations.length < MAX_ELEMENTS) {
    const el = node;
    let rect, cs;
    try {
      rect = el.getBoundingClientRect();
      cs = getComputedStyle(el);
    } catch (e) {
      continue;
    }
    if (!visible(el, rect, cs)) continue;

    const styles = {};
    for (const prop of STYLE_PROPS) {
      try {
        // getComputedStyle exposes camelCase properties directly.
        const v = cs[prop];
        if (v != null && v !== "") styles[prop] = v;
      } catch (e) {
        /* skip unreadable property */
      }
    }

    const role =
      el.getAttribute("role") ||
      (el.tagName === "BUTTON" ? "button" : el.tagName === "A" ? "link" : el.tagName === "INPUT" ? "input" : "");

    observations.push({
      id: idFor(el),
      tag: el.tagName.toLowerCase(),
      role,
      label: sanitizeLabel(el.getAttribute("aria-label") || el.textContent || ""),
      bbox: {
        x: Math.round(rect.x * 100) / 100,
        y: Math.round(rect.y * 100) / 100,
        width: Math.round(rect.width * 100) / 100,
        height: Math.round(rect.height * 100) / 100,
      },
      area: Math.round(rect.width * rect.height * 100) / 100,
      styles,
    });
  }

  return JSON.stringify({
    observations,
    rootVars,
    mediaWidths: Array.from(mediaWidths),
    title: document.title || "",
    finalUrl: location.href,
  });
})();
