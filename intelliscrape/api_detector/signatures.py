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
            r"fetch\s*\(\s*['\"\`]([^'\"\`\s]{3,200})['\"\`]",
            r"fetch\s*\(\s*(?:url|endpoint|baseUrl|apiUrl|apiBase)\s*[+.]",
            r"fetch\s*\(\s*`([^`]{3,200})`",
        ],
        "html": [],
        "header": [],
        "meta": [],
        "url": [],
    },
    "axios_api": {
        "js": [
            r"axios\.\w+\s*\(\s*['\"\`]([^'\"\`]{3,200})['\"\`]",
            r"axios\s*\(\s*\{[^}]*url\s*:\s*['\"\`]([^'\"\`]+)['\"\`]",
            r"axios\s*\(\s*['\"\`]([^'\"\`]{3,200})['\"\`]",
        ],
        "html": [],
        "header": [],
        "meta": [],
        "url": [],
    },
    "xhr_api": {
        "js": [
            r"\.open\s*\(\s*['\"\`](GET|POST|PUT|DELETE|PATCH)['\"\`]\s*,\s*['\"\`]([^'\"\`]{3,200})['\"\`]",
            r"\.open\s*\(\s*['\"\`]([^'\"\`]{3,200})['\"\`]",
        ],
        "html": [],
        "header": [],
        "meta": [],
        "url": [],
    },
    "client_get_post": {
        "js": [
            r"\.(get|post|put|delete|patch)\s*\(\s*['\"\`]([^'\"\`]{3,200})['\"\`]",
            r"client\s*\.\s*(get|post|put|delete|patch)\s*\(\s*['\"\`]([^'\"\`]{3,200})['\"\`]",
            r"request\s*\(\s*['\"\`]([^'\"\`]{3,200})['\"\`]",
        ],
        "html": [],
        "header": [],
        "meta": [],
        "url": [],
    },
    "api_paths": {
        "js": [
            r"['\"\`]/api[a-zA-Z0-9/_\-\.]*['\"\`]",
            r"['\"\`]/rest[a-zA-Z0-9/_\-\.]*['\"\`]",
            r"['\"\`]/v[0-9]+/[a-zA-Z0-9/_\-\.]+['\"\`]",
        ],
        "html": [
            r"(?:href|src|action)\s*=\s*[\"'][^\"']*/api[^\"']*[\"']",
            r"(?:href|src|action)\s*=\s*[\"'][^\"']*/v[0-9]+/[^\"']*[\"']",
        ],
        "header": [],
        "meta": [],
        "url": [],
    },
    "common_api_keywords": {
        "js": [
            r"['\"\`]/(?:login|signin|signup|register|auth|oauth|token|callback)(?:[?/][^'\"\`\s]*)?['\"\`]",
            r"['\"\`]/(?:search|query|filter|autocomplete|suggest)(?:[?/][^'\"\`\s]*)?['\"\`]",
            r"['\"\`]/(?:users?|accounts?|profiles?|members?)(?:[?/][^'\"\`\s]*)?['\"\`]",
            r"['\"\`]/(?:products?|items?|catalog|inventory|orders?)(?:[?/][^'\"\`\s]*)?['\"\`]",
            r"['\"\`]/(?:upload|import|export|download|files?|media)(?:[?/][^'\"\`\s]*)?['\"\`]",
            r"['\"\`]/(?:admin|dashboard|settings?|config|preferences?)(?:[?/][^'\"\`\s]*)?['\"\`]",
            r"['\"\`]/(?:notifications?|alerts?|messages?|inbox)(?:[?/][^'\"\`\s]*)?['\"\`]",
            r"['\"\`]/(?:payments?|checkout|billing|invoices?|subscribe)(?:[?/][^'\"\`\s]*)?['\"\`]",
            r"['\"\`]/(?:comments?|reviews?|ratings?|feedback)(?:[?/][^'\"\`\s]*)?['\"\`]",
            r"['\"\`]/(?:posts?|articles?|blogs?|pages?|content)(?:[?/][^'\"\`\s]*)?['\"\`]",
            r"['\"\`]/(?:categories?|tags?|labels?|topics?)(?:[?/][^'\"\`\s]*)?['\"\`]",
            r"['\"\`]/(?:analytics|events?|metrics|stats|track)(?:[?/][^'\"\`\s]*)?['\"\`]",
            r"['\"\`]/(?:search|websearch|find|lookup)(?:[?/][^'\"\`\s]*)?['\"\`]",
            r"['\"\`]/(?:status|health|ping|version|info|meta)(?:[?/][^'\"\`\s]*)?['\"\`]",
            r"['\"\`]/(?:graphql|gql|graphi?ql)(?:[?/][^'\"\`\s]*)?['\"\`]",
        ],
        "html": [
            r"(?:href|src|action)\s*=\s*[\"'](?:/login|/signin|/signup|/register|/auth|/oauth|/token)[\"']",
            r"(?:href|src|action)\s*=\s*[\"'](?:/search|/query|/filter|/autocomplete)[\"']",
            r"(?:href|src|action)\s*=\s*[\"'](?:/users?|/accounts?|/profiles?|/members?)[\"']",
            r"(?:href|src|action)\s*=\s*[\"'](?:/products?|/items?|/catalog|/orders?)[\"']",
            r"(?:href|src|action)\s*=\s*[\"'](?:/upload|/import|/export|/files?|/media)[\"']",
            r"(?:href|src|action)\s*=\s*[\"'](?:/admin|/dashboard|/settings?|/config)[\"']",
            r"(?:href|src|action)\s*=\s*[\"'](?:/notifications?|/alerts?|/messages?)[\"']",
            r"(?:href|src|action)\s*=\s*[\"'](?:/payments?|/checkout|/billing|/invoices?)[\"']",
        ],
        "header": [],
        "meta": [],
        "url": [],
    },
    "full_api_urls": {
        "js": [
            r"['\"\`](https?://api\.[a-zA-Z0-9.\-]+/[^\s\"'`\]{3,200})['\"\`]",
            r"['\"\`](https?://[a-zA-Z0-9.\-]+/api/[^\s\"'`\]{3,200})['\"\`]",
            r"['\"\`](https?://[a-zA-Z0-9.\-]+/v[0-9]+/[^\s\"'`\]{3,200})['\"\`]",
        ],
        "html": [
            r"href\s*=\s*[\"'](https?://api\.[a-zA-Z0-9.\-]+/[^\"']+)[\"']",
            r"src\s*=\s*[\"'](https?://api\.[a-zA-Z0-9.\-]+/[^\"']+)[\"']",
        ],
        "header": [],
        "meta": [
            r"<meta[^>]*content\s*=\s*[\"'](https?://api\.[a-zA-Z0-9.\-]+/[^\"']+)[\"']",
        ],
        "url": [],
    },
    "config_vars": {
        "js": [
            r"(?:baseURL|BASE_URL|API_URL|API_BASE|apiUrl|apiBase|baseUrl|ENDPOINT|API_ENDPOINT)\s*[:=]\s*['\"\`]([^'\"\`]{5,200})['\"\`]",
            r"(?:REACT_APP_API|VITE_API|NEXT_PUBLIC_API|VUE_APP_API|NUXT_PUBLIC_API)\w*\s*[:=]\s*['\"\`]([^'\"\`]{5,200})['\"\`]",
            r"(?:apiPrefix|apiPath|API_PREFIX|API_PATH)\s*[:=]\s*['\"\`]([^'\"\`]{3,200})['\"\`]",
        ],
        "html": [],
        "header": [],
        "meta": [],
        "url": [],
    },
}

# ── Framework-specific routes ──────────────────────────────────────────────────

FRAMEWORK_ROUTES: dict[str, dict[str, list[str]]] = {
    "nextjs_routes": {
        "js": [
            r"_next/data/[^'\"\`\s]+\.json",
            r"getServerSideProps|getStaticProps|getStaticPaths",
            r"next/router|next/navigation|useRouter",
        ],
        "html": [
            r"/_next/data/[^\"]+\.json",
            r"<script[^>]*id=\"__NEXT_DATA__\"[^>]*>",
        ],
        "header": [],
        "meta": [],
        "url": [],
    },
    "nuxt_routes": {
        "js": [
            r"_nuxt/|useAsyncData|useFetch|useLazyFetch",
            r"fetch\(['\"]/_nuxt/data/",
        ],
        "html": [
            r"/_nuxt/data/[^\"]+",
            r"<script[^>]*id=\"__NUXT_DATA__\"[^>]*>",
        ],
        "header": [],
        "meta": [],
        "url": [],
    },
    "ssr_data_endpoints": {
        "js": [
            r"['\"\`]/(?:_next|_nuxt|__next|__nuxt)/data/[^'\"\`\s]+['\"\`]",
            r"['\"\`]/api/(?:ssr|server|render)/[^'\"\`\s]+['\"\`]",
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
            r"['\"\`][^'\"\`]*graphql[^'\"\`]*['\"\`]",
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
            r"ApolloClient|ApolloProvider|apollo-client|@apollo/client",
            r"useQuery|useMutation|useSubscription|useLazyQuery",
            r"graphql-request|urql|relay-runtime|@urql",
            r"createClient.*graphql|new.*ApolloClient",
            r"gql`|graphql`|`query\s*\{",
            r"graphql-ws|subscriptions-transport-ws",
        ],
        "html": [],
        "header": [],
        "meta": [],
        "url": [],
    },
    "graphql_queries": {
        "js": [
            r"query\s*\{[\s\S]{0,50}(?:__schema|__typename|id\b)",
            r"mutation\s*\{",
            r"subscription\s*\{",
            r"__schema\s*\{",
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
            r"['\"\`]wss?://[^'\"\`\s]{5,200}['\"\`]",
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
            r"sockjs|stompjs|STOMP|SockJS",
            r"socket\.on\s*\(\s*['\"\`]",
            r"socket\.emit\s*\(",
            r"\.on\s*\(\s*['\"\`]message['\"\`]",
            r"\.on\s*\(\s*['\"\`]connect['\"\`]",
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
    "/.well-known/openapi",
]

DOC_SIGNATURES: dict[str, dict[str, list[str]]] = {
    "swagger": {
        "js": [
            r'"swagger"\s*:\s*"2\.\d',
            r'"openapi"\s*:\s*"3\.\d+\.\d+',
            r"SwaggerUIBundle|SwaggerUIStandalonePreset",
            r"swagger-ui",
            r"swaggerJson|swaggerDoc|apiSpec",
        ],
        "html": [
            r"<redoc\s+spec-url=",
            r"swagger-ui",
            r"api-documentation|api-reference",
        ],
        "header": [],
        "meta": [
            r"<meta[^>]*content\s*=\s*[\"'][^\"']*swagger[^\"']*[\"']",
            r"<meta[^>]*content\s*=\s*[\"'][^\"']*openapi[^\"']*[\"']",
        ],
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
    r"github\.com.*api": "github",
    r"api\.slack\.com": "slack",
    r"slack\.com.*api": "slack",
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
    r"hotjar\.com": "hotjar",
    r"fullstory\.com": "fullstory",
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
    r"api\.githubcopilot\.com": "github_copilot",
    r"api\.github\.com": "github",
    r"objects\.githubusercontent\.com": "github",
    r"github\.githubassets\.com": "github",
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

# ── Common page routes (not API endpoints) ────────────────────────────────────

COMMON_PAGE_ROUTES: set[str] = {
    "/blog",
    "/about",
    "/contact",
    "/careers",
    "/pricing",
    "/docs",
    "/changelog",
    "/features",
    "/products",
    "/solutions",
    "/company",
    "/team",
    "/partners",
    "/customers",
    "/case-studies",
    "/events",
    "/webinars",
    "/podcast",
    "/newsletter",
    "/privacy",
    "/terms",
    "/security",
    "/status",
    "/support",
    "/help",
    "/community",
    "/forum",
    "/feedback",
    "/roadmap",
    "/open-source",
    "/license",
    "/sitemap",
    "/robots.txt",
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
    r" Type /Font",       # PDF structure
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

# ── HTTP method detection context patterns ────────────────────────────────────

METHOD_CONTEXT_PATTERNS: dict[str, list[str]] = {
    "POST": [
        r"\.post\s*\(",
        r"method\s*:\s*['\"]POST['\"]",
        r"['\"]POST['\"]",
        r"submit|create|add|insert|register|login|signup|upload|send",
    ],
    "PUT": [
        r"\.put\s*\(",
        r"method\s*:\s*['\"]PUT['\"]",
        r"['\"]PUT['\"]",
        r"update|modify|replace|edit",
    ],
    "DELETE": [
        r"\.delete\s*\(",
        r"method\s*:\s*['\"]DELETE['\"]",
        r"['\"]DELETE['\"]",
        r"remove|destroy|delete",
    ],
    "PATCH": [
        r"\.patch\s*\(",
        r"method\s*:\s*['\"]PATCH['\"]",
        r"['\"]PATCH['\"]",
        r"patch|partial",
    ],
}
