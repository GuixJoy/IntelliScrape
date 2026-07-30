"""Signature databases for API endpoint detection.

Each category maps detection patterns to their metadata.
Signal types: js (JavaScript source), html (HTML markup), header (HTTP headers),
meta (meta tags), url (URL patterns).
"""

from __future__ import annotations

# ── REST API patterns ─────────────────────────────────────────────────────────

REST_PATTERNS: dict[str, dict[str, list[str]]] = {
    "fetch_api": {
        "js": [
            r"fetch\s*\(\s*['\"\`]([^'\"\`\s]+)['\"\`]",
            r"fetch\s*\(\s*(?:url|endpoint|baseUrl|apiUrl)\s*[+.]",
        ],
        "html": [],
        "header": [],
        "meta": [],
        "url": [],
    },
    "axios_api": {
        "js": [
            r"axios\.(get|post|put|delete|patch|head|options)\s*\(\s*['\"\`]([^'\"\`]+)['\"\`]",
            r"axios\s*\(\s*\{[^}]*url\s*:\s*['\"\`]([^'\"\`]+)['\"\`]",
        ],
        "html": [],
        "header": [],
        "meta": [],
        "url": [],
    },
    "xhr_api": {
        "js": [
            r"\.open\s*\(\s*['\"\`](GET|POST|PUT|DELETE|PATCH)['\"\`]\s*,\s*['\"\`]([^'\"\`]+)['\"\`]",
        ],
        "html": [],
        "header": [],
        "meta": [],
        "url": [],
    },
    "api_paths": {
        "js": [
            r"['\"\`]/api/[a-zA-Z0-9/_-]{2,}['\"\`]",
            r"['\"\`]/rest/[a-zA-Z0-9/_-]{2,}['\"\`]",
            r"['\"\`]/v[0-9]+/[a-zA-Z0-9/_-]{2,}['\"\`]",
            r"['\"\`]https?://[^'\"\`\s]+/api/[^'\"\`\s]+['\"\`]",
        ],
        "html": [
            r"(?:href|src|action)\s*=\s*[\"'][^\"']*/api/[^\"']*[\"']",
        ],
        "header": [],
        "meta": [
            r"<meta[^>]*(?:name|property)\s*=\s*[\"'][^\"']*api[^\"']*[\"'][^>]*content\s*=\s*[\"']([^\"']+)[\"']",
        ],
        "url": [],
    },
    "config_vars": {
        "js": [
            r"(?:baseURL|BASE_URL|API_URL|API_BASE|apiUrl|apiBase|baseUrl|endpoint|ENDPOINT)\s*[:=]\s*['\"\`]([^'\"\`]+)['\"\`]",
            r"(?:REACT_APP_API|VITE_API|NEXT_PUBLIC_API|VUE_APP_API)_\w+\s*[:=]\s*['\"\`]([^'\"\`]+)['\"\`]",
        ],
        "html": [],
        "header": [],
        "meta": [],
        "url": [],
    },
}

# ── GraphQL patterns ──────────────────────────────────────────────────────────

GRAPHQL_PATTERNS: dict[str, dict[str, list[str]]] = {
    "graphql_endpoint": {
        "js": [
            r"['\"\`]/?graphql['\"\`]",
            r"['\"\`]/?gql['\"\`]",
            r"['\"\`]/?graphi?ql['\"\`]",
        ],
        "html": [
            r"(?:href|src|action)\s*=\s*[\"'][^\"']*graphql[^\"']*[\"']",
        ],
        "header": [],
        "meta": [],
        "url": [r"/graphql", r"/gql"],
    },
    "graphql_client": {
        "js": [
            r"ApolloClient|ApolloProvider|apollo-client",
            r"useQuery|useMutation|useSubscription",
            r"graphql-request|urql|relay-runtime",
            r"createClient.*graphql|new.*ApolloClient",
            r"gql`|graphql`",
        ],
        "html": [],
        "header": [],
        "meta": [],
        "url": [],
    },
    "graphql_queries": {
        "js": [
            r"query\s*\{",
            r"mutation\s*\{",
            r"subscription\s*\{",
            r"__schema",
            r"__typename",
        ],
        "html": [],
        "header": [],
        "meta": [],
        "url": [],
    },
}

# ── WebSocket patterns ────────────────────────────────────────────────────────

WEBSOCKET_PATTERNS: dict[str, dict[str, list[str]]] = {
    "websocket_urls": {
        "js": [
            r"['\"\`]wss?://[^'\"\`\s]+['\"\`]",
            r"new\s+WebSocket\s*\(",
            r"new\s+WebSocketServer\s*\(",
            r"\.connect\s*\(\s*['\"\`]wss?://",
        ],
        "html": [],
        "header": [],
        "meta": [],
        "url": [r"wss?://"],
    },
    "socket_io": {
        "js": [
            r"socket\.io|io\s*\(\s*['\"\`]https?://",
            r"sockjs|stompjs|STOMP",
            r"socket\.on\s*\(\s*['\"\`]message['\"\`]",
            r"socket\.emit\s*\(",
        ],
        "html": [],
        "header": [],
        "meta": [],
        "url": [],
    },
}

# ── API documentation paths ───────────────────────────────────────────────────

DOC_PATHS: list[str] = [
    "/swagger.json",
    "/swagger.yaml",
    "/swagger-ui.html",
    "/swagger-ui/",
    "/swagger/",
    "/swagger/index.html",
    "/swagger/v1/swagger.json",
    "/swagger/resources",
    "/swagger/docs",
    "/api-docs",
    "/api/swagger",
    "/v1/api-docs",
    "/v2/api-docs",
    "/v3/api-docs",
    "/openapi.json",
    "/openapi.yaml",
    "/openapi/docs",
    "/docs/api",
    "/api/docs",
    "/documentation",
    "/api-documentation",
    "/api-reference",
    "/api/explorer",
    "/redoc",
    "/redoc.yml",
    "/springdoc/swagger-ui.html",
    "/actuator",
]

DOC_SIGNATURES: dict[str, dict[str, list[str]]] = {
    "swagger": {
        "js": [
            r'"swagger"\s*:\s*"2\.\d',
            r'"openapi"\s*:\s*"3\.\d+\.\d+',
            r"SwaggerUIBundle|SwaggerUIStandalonePreset",
            r"swagger-ui",
        ],
        "html": [
            r"<redoc\s+spec-url=",
            r"swagger-ui",
        ],
        "header": [],
        "meta": [],
        "url": [],
    },
    "redoc": {
        "js": [
            r"redoc|RedocStandalone",
        ],
        "html": [
            r"redoc|RedocStandalone",
        ],
        "header": [],
        "meta": [],
        "url": [],
    },
}

# ── Third-party API domains ───────────────────────────────────────────────────

THIRD_PARTY_DOMAINS: dict[str, str] = {
    r"api\.stripe\.com": "stripe",
    r"js\.stripe\.com": "stripe",
    r"payments\.stripe\.com": "stripe",
    r"connect\.stripe\.com": "stripe",
    r"maps\.googleapis\.com": "google_maps",
    r"www\.googleapis\.com": "google",
    r"oauth\.googleapis\.com": "google_oauth",
    r"accounts\.google\.com": "google_auth",
    r"api\.twilio\.com": "twilio",
    r"api\.sendgrid\.com": "sendgrid",
    r"api\.mailgun\.net": "mailgun",
    r"graph\.facebook\.com": "facebook",
    r"connect\.facebook\.net": "facebook",
    r"api\.twitter\.com": "twitter",
    r"api\.x\.com": "twitter",
    r"api\.github\.com": "github",
    r"api\.slack\.com": "slack",
    r"api\.amazonaws\.com": "aws",
    r"execute-api\..*\.amazonaws\.com": "aws_lambda",
    r"api\.firebaseio\.com": "firebase",
    r"firestore\.googleapis\.com": "firebase",
    r"api\.contentful\.com": "contentful",
    r"api\.algolia\.com": "algolia",
    r"api\.openai\.com": "openai",
    r"api\.anthropic\.com": "anthropic",
    r"api\.cohere\.ai": "cohere",
    r"api\.replicate\.com": "replicate",
    r"api\.notion\.com": "notion",
    r"api\.airtable\.com": "airtable",
    r"cdn\.segment\.com": "segment",
    r"cdn\.amplitude\.com": "amplitude",
    r"plausible\.io": "plausible",
    r"googletagmanager\.com": "gtm",
    r"gtag\.js": "gtm",
    r"recaptcha\.net": "recaptcha",
    r"google\.com/recaptcha": "recaptcha",
    r"hcaptcha\.com": "hcaptcha",
    r"intercomcdn\.com": "intercom",
    r"widget\.intercom": "intercom",
    r"widget\.drift\.com": "drift",
    r"freshchat\.com": "freshchat",
    r"sentry\.io": "sentry",
    r"browser\.sentry-cdn\.com": "sentry",
    r"js\.heatmap\.me": "heatmap",
    r"fullstory\.com": "fullstory",
    r"hotjar\.com": "hotjar",
    r"cdn\.mixpanel\.com": "mixpanel",
    r"track\.customer\.io": "customerio",
    r"api\.postmarkapp\.com": "postmark",
    r"api\.sparkpost\.com": "sparkpost",
    r"mandrillapp\.com": "mandrill",
    r"api\.intercom\.io": "intercom",
    r"api\.zendesk\.com": "zendesk",
    r"api\.hubspot\.com": "hubspot",
    r"api\.salesforce\.com": "salesforce",
    r"login\.salesforce\.com": "salesforce",
    r"api\.freshdesk\.com": "freshdesk",
    r"api\.linear\.app": "linear",
    r"api\.vercel\.com": "vercel",
    r"api\.netlify\.com": "netlify",
    r"api\.cloudflare\.com": "cloudflare",
}

# ── SDK/script import signatures ──────────────────────────────────────────────

SDK_SIGNATURES: dict[str, str] = {
    r"js\.stripe\.com/v3|@stripe/stripe-js|loadStripe": "stripe",
    r"maps\.googleapis\.com/maps/api/js": "google_maps",
    r"sdk\.braintreegateway\.com": "braintree",
    r"sdk\.paypal\.com|paypal\.com/sdk": "paypal",
    r"js\.squarecdn\.com|square\.js": "square",
    r"fbevents\.js|fbq\s*\(": "facebook_pixel",
    r"cdn\.segment\.com/analytics": "segment",
    r"cdn\.amplitude\.com": "amplitude",
    r"plausible\.io/js/": "plausible",
    r"googletagmanager\.com/gtag": "google_tag_manager",
    r"recaptcha\.net|google\.com/recaptcha": "recaptcha",
    r"hcaptcha\.com": "hcaptcha",
    r"intercomcdn\.com|widget\.intercom": "intercom",
    r"widget\.drift\.com": "drift",
    r"sentry\.io|Sentry\.init": "sentry",
    r"hotjar\.com|hj\s*\(": "hotjar",
    r"fullstory\.com|FS\(": "fullstory",
    r"cdn\.mixpanel\.com|mixpanel\.init": "mixpanel",
}

# ── API key/token patterns ────────────────────────────────────────────────────

KEY_PATTERNS: dict[str, dict[str, str]] = {
    "aws_access_key": {
        "regex": r"\bAKIA[0-9A-Z]{16}\b",
        "provider": "aws",
        "key_type": "access_key",
        "severity": "high",
    },
    "google_api_key": {
        "regex": r"AIza[0-9A-Za-z\-_]{35}",
        "provider": "google",
        "key_type": "api_key",
        "severity": "high",
    },
    "github_pat_classic": {
        "regex": r"ghp_[A-Za-z0-9]{36}",
        "provider": "github",
        "key_type": "personal_access_token",
        "severity": "high",
    },
    "github_pat_fine_grained": {
        "regex": r"github_pat_[A-Za-z0-9]{22}_[A-Za-z0-9]{59}",
        "provider": "github",
        "key_type": "personal_access_token",
        "severity": "high",
    },
    "github_actions_token": {
        "regex": r"ghs_[A-Za-z0-9]{36}",
        "provider": "github",
        "key_type": "actions_token",
        "severity": "high",
    },
    "slack_token": {
        "regex": r"xox[baprs]-[0-9A-Za-z]{10,48}",
        "provider": "slack",
        "key_type": "token",
        "severity": "high",
    },
    "stripe_key": {
        "regex": r"(?<![A-Za-z0-9])(sk|pk)_(live|test)_[0-9A-Za-z]{24,}",
        "provider": "stripe",
        "key_type": "api_key",
        "severity": "high",
    },
    "mailgun_key": {
        "regex": r"key-[0-9A-Fa-f]{32}",
        "provider": "mailgun",
        "key_type": "api_key",
        "severity": "medium",
    },
    "sendgrid_key": {
        "regex": r"SG\.[A-Za-z0-9\-_]{22,}\.[A-Za-z0-9\-_]{43,}",
        "provider": "sendgrid",
        "key_type": "api_key",
        "severity": "high",
    },
    "square_token": {
        "regex": r"sq0atp-[0-9A-Za-z\-_]{22}",
        "provider": "square",
        "key_type": "access_token",
        "severity": "high",
    },
    "square_oauth": {
        "regex": r"sq0csp-[0-9A-Za-z\-_]{43}",
        "provider": "square",
        "key_type": "oauth_secret",
        "severity": "high",
    },
    "facebook_token": {
        "regex": r"EAACEdEose0cBA[0-9A-Za-z]+",
        "provider": "facebook",
        "key_type": "access_token",
        "severity": "high",
    },
    "heroku_api_key": {
        "regex": r"HEROKU_API_KEY\s*[:=]\s*['\"\`]([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})['\"\`]",
        "provider": "heroku",
        "key_type": "api_key",
        "severity": "high",
    },
}

# ── Generic credential patterns ───────────────────────────────────────────────

GENERIC_KEY_PATTERNS: dict[str, dict[str, str]] = {
    "generic_api_key": {
        "regex": r"(?i)(?:api[_-]?key|apikey|api[_-]?secret|access[_-]?key|auth[_-]?token|secret[_-]?key|private[_-]?key)\s*[:=]\s*['\"\`]([^'\"\`\s]{8,})['\"\`]",
        "key_type": "api_key",
        "severity": "medium",
    },
    "bearer_token": {
        "regex": r"Bearer\s+[A-Za-z0-9\-_]+\.?[A-Za-z0-9\-_]*\.?[A-Za-z0-9\-_]*",
        "key_type": "bearer_token",
        "severity": "medium",
    },
    "jwt_token": {
        "regex": r"eyJ[A-Za-z0-9\-_]+=*\.[A-Za-z0-9\-_]+=*\.?[A-Za-z0-9\-_+=]*",
        "key_type": "jwt",
        "severity": "medium",
    },
    "private_key_header": {
        "regex": r"-----BEGIN (?:RSA )?PRIVATE KEY-----",
        "key_type": "private_key",
        "severity": "high",
    },
    "client_secret": {
        "regex": r"(?i)(?:client[_-]?secret|client[_-]?id)\s*[:=]\s*['\"\`]([^'\"\`\s]{16,})['\"\`]",
        "key_type": "client_secret",
        "severity": "medium",
    },
    "env_var_leak_next": {
        "regex": r"NEXT_PUBLIC_\w*(?:KEY|SECRET|TOKEN|API)\w*\s*[:=]",
        "key_type": "env_leak",
        "severity": "low",
    },
    "env_var_leak_vite": {
        "regex": r"VITE_\w*(?:KEY|SECRET|TOKEN|API)\w*\s*[:=]",
        "key_type": "env_leak",
        "severity": "low",
    },
    "env_var_leak_react": {
        "regex": r"REACT_APP_\w*(?:KEY|SECRET|TOKEN|API)\w*\s*[:=]",
        "key_type": "env_leak",
        "severity": "low",
    },
}

# ── Noise strings to reject ───────────────────────────────────────────────────

NOISE_STRINGS: set[str] = {
    "http://",
    "https://",
    "/a",
    "/b",
    "/c",
    "/d",
    "/e",
    "/f",
    "/g",
    "/h",
    "/i",
    "/j",
    "/P",
    "//",
    "/",
    "#",
    "?",
    "null",
    "undefined",
    "true",
    "false",
    "0",
    "1",
    "example.com",
    "localhost",
    "placeholder",
    "test",
    "dummy",
    "xxx",
    "TODO",
    "FIXME",
}

# ── Path validation noise patterns (reject these) ────────────────────────────

NOISE_PATH_PATTERNS: list[str] = [
    r"^\.\.?/",           # relative imports
    r"/[a-z]\.js$",       # single-letter JS files
    r"/[a-z]\.css$",      # single-letter CSS files
    r"/en\.js$",          # locale files
    r"/index\.",          # index files
    r"/chunk-",           # webpack chunks
    r"/vendor\.",         # vendor bundles
    r"/polyfill",         # polyfills
    r"/webpack",          # webpack internals
    r"/ Type /Font",      # PDF structure
    r"/xl/",              # Excel internals
    r"/docProps/",        # Office internals
    r"/_next/",           # Next.js internals
    r"/_nuxt/",           # Nuxt.js internals
    r"/assets/",          # static assets
    r"/static/",          # static files
    r"/fonts/",           # font files
    r"/images/",          # image directories
    r"/css/",             # CSS directories
    r"/js/",              # JS directories
    r"\.svg",             # SVG files
    r"\.png",
    r"\.jpg",
    r"\.gif",
    r"\.ico",
    r"\.woff",
    r"\.woff2",
    r"\.ttf",
    r"\.eot",
    r"\.map",
]
