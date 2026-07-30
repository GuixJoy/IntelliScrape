"""Signature databases for technology detection.

Each category maps tech names to detection signatures across multiple signals:
- html: patterns in HTML body (meta tags, script sources, class names, DOM markers)
- headers: HTTP response header patterns
- cookies: cookie name patterns
- url: URL path patterns in script/link src attributes
- js: JavaScript global variables or function names
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Frameworks (frontend / full-stack)
# ---------------------------------------------------------------------------
FRAMEWORKS: dict[str, dict[str, list[str]]] = {
    "react": {
        "html": [
            "data-reactroot",
            "data-reactid",
            "__REACT_DEVTOOLS_GLOBAL_HOOK__",
            "_reactRootContainer",
            "react.production.min.js",
            "react-dom",
        ],
        "js": ["React", "ReactDOM", "__NEXT_DATA__"],
        "url": ["react", "react-dom"],
        "headers": [],
        "cookies": [],
    },
    "next.js": {
        "html": [
            "__NEXT_DATA__",
            'id="__next"',
            "_next/static",
            "next/dist",
            "next/image",
            "next/link",
            "next/head",
        ],
        "js": ["__NEXT_DATA__", "__next_f"],
        "url": ["_next/static", "_next/image"],
        "headers": ["x-powered-by: Next.js"],
        "cookies": ["__next_preview_data", "__next_refresh"],
    },
    "vue.js": {
        "html": [
            "data-v-",
            "Vue.",
            "vue.global",
            "vue.runtime",
            "__VUE__",
            "v-cloak",
            "v-bind:",
            "v-on:",
            "data-server-rendered",
        ],
        "js": ["Vue", "__VUE__"],
        "url": ["vue"],
        "headers": [],
        "cookies": [],
    },
    "nuxt.js": {
        "html": [
            "__NUXT__",
            "data-n-head",
            "data-server-rendered",
            "_nuxt/",
            "nuxt.config",
        ],
        "js": ["__NUXT__", "$nuxt"],
        "url": ["_nuxt/"],
        "headers": ["x-powered-by: Nuxt"],
        "cookies": [],
    },
    "angular": {
        "html": [
            "ng-version",
            "ng-app",
            "ng-controller",
            "ng-cloak",
            "data-ng-app",
            "angular.min.js",
            "angular.js",
            "ng-new",
        ],
        "js": ["angular", "ng"],
        "url": ["angular"],
        "headers": [],
        "cookies": [],
    },
    "svelte": {
        "html": [
            "svelte",
            "sapper-app",
            "__sveltekit",
        ],
        "js": ["__sveltekit"],
        "url": ["/_app/"],
        "headers": [],
        "cookies": [],
    },
    "solid.js": {
        "html": ["__SOLID__"],
        "js": ["Solid", "SolidJS"],
        "url": ["solid"],
        "headers": [],
        "cookies": [],
    },
    "remix": {
        "html": [
            "__remixContext",
            "__remixEntryManifest",
            "remix-run",
        ],
        "js": ["__remixContext", "remix"],
        "url": ["__remix"],
        "headers": ["x-powered-by: Remix"],
        "cookies": [],
    },
    "astro": {
        "html": [
            "astro-island",
            "data-astro-cid",
            "astro-dev-toolbar",
        ],
        "js": [],
        "url": ["_astro/"],
        "headers": [],
        "cookies": [],
    },
    "gatsby": {
        "html": [
            "___gatsby",
            "gatsby-",
            "gatsby-plugin",
        ],
        "js": ["___gatsby"],
        "url": ["gatsby", "static/gatsby"],
        "headers": [],
        "cookies": [],
    },
    "hugo": {
        "html": [
            "hugo-",
            "powered-by hugo",
        ],
        "js": [],
        "url": [],
        "headers": ["x-powered-by: Hugo"],
        "cookies": [],
    },
    "jekyll": {
        "html": [
            "jekyll-",
            "powered by jekyll",
        ],
        "js": [],
        "url": [],
        "headers": ["x-powered-by: Jekyll"],
        "cookies": [],
    },
    "laravel": {
        "html": [],
        "js": [],
        "url": [],
        "headers": ["x-powered-by: Laravel"],
        "cookies": ["laravel_session", "XSRF-TOKEN"],
    },
    "rails": {
        "html": [],
        "js": [],
        "url": [],
        "headers": ["x-powered-by: Phusion Passenger", "x-runtime"],
        "cookies": ["_session_id"],
    },
    "django": {
        "html": [],
        "js": [],
        "url": [],
        "headers": ["x-frame-options: DENY"],
        "cookies": ["csrftoken", "sessionid"],
    },
    "flask": {
        "html": [],
        "js": [],
        "url": [],
        "headers": [],
        "cookies": ["session=ey"],
    },
    "express.js": {
        "html": [],
        "js": [],
        "url": [],
        "headers": ["x-powered-by: Express"],
        "cookies": ["connect.sid"],
    },
    "asp.net": {
        "html": [],
        "js": [],
        "url": [],
        "headers": [
            "x-powered-by: ASP.NET",
            "x-aspnet-version",
            "x-aspnetmvc-version",
        ],
        "cookies": [".ASPXAUTH", "ASP.NET_SessionId", "__RequestVerificationToken"],
    },
    "php": {
        "html": [],
        "js": [],
        "url": [],
        "headers": ["x-powered-by: PHP"],
        "cookies": ["PHPSESSID"],
    },
}

# ---------------------------------------------------------------------------
# CSS Frameworks
# ---------------------------------------------------------------------------
CSS_FRAMEWORKS: dict[str, dict[str, list[str]]] = {
    "tailwind css": {
        "html": [
            "tailwindcss",
            "tailwind",
            "tw-",
        ],
        "url": ["tailwindcss", "tailwind"],
        "headers": [],
        "cookies": [],
        "js": [],
    },
    "bootstrap": {
        "html": [
            "bootstrap.min.css",
            "bootstrap.bundle.min.js",
            "bootstrap-",
        ],
        "url": ["bootstrap.min.css", "bootstrap.bundle"],
        "headers": [],
        "cookies": [],
        "js": [],
    },
    "material ui": {
        "html": [
            "mui-",
            "material-ui",
            "@mui/material",
        ],
        "url": ["mui", "material-ui"],
        "headers": [],
        "cookies": [],
        "js": [],
    },
    "chakra ui": {
        "html": ["chakra-ui"],
        "url": ["chakra-ui"],
        "headers": [],
        "cookies": [],
        "js": [],
    },
    "bulma": {
        "html": ["bulma.min.css", "bulma.css"],
        "url": ["bulma"],
        "headers": [],
        "cookies": [],
        "js": [],
    },
    "foundation": {
        "html": ["foundation.min.css", "foundation.min.js"],
        "url": ["foundation"],
        "headers": [],
        "cookies": [],
        "js": [],
    },
    "materialize": {
        "html": ["materialize.min.css", "materialize.min.js"],
        "url": ["materialize"],
        "headers": [],
        "cookies": [],
        "js": [],
    },
    "ant design": {
        "html": ["antd", "ant-design"],
        "url": ["antd", "ant-design"],
        "headers": [],
        "cookies": [],
        "js": [],
    },
    "semantic ui": {
        "html": ["semantic.min.css", "semantic-ui"],
        "url": ["semantic"],
        "headers": [],
        "cookies": [],
        "js": [],
    },
}

# ---------------------------------------------------------------------------
# JavaScript Libraries
# ---------------------------------------------------------------------------
JS_LIBRARIES: dict[str, dict[str, list[str]]] = {
    "jquery": {
        "html": ["jquery.min.js", "jquery-", "jquery.js"],
        "url": ["jquery"],
        "js": ["jQuery", "$."],
        "headers": [],
        "cookies": [],
    },
    "gsap": {
        "html": ["gsap.min.js", "gsap.js", "ScrollTrigger"],
        "url": ["gsap"],
        "js": ["gsap", "ScrollTrigger"],
        "headers": [],
        "cookies": [],
    },
    "three.js": {
        "html": ["three.min.js", "three.js"],
        "url": ["three.js", "three.min.js"],
        "js": ["THREE"],
        "headers": [],
        "cookies": [],
    },
    "d3.js": {
        "html": ["d3.min.js", "d3.v"],
        "url": ["d3.min.js", "d3.v"],
        "js": ["d3"],
        "headers": [],
        "cookies": [],
    },
    "chart.js": {
        "html": ["chart.min.js", "chart.js"],
        "url": ["chart.js", "chart.min.js"],
        "js": ["Chart"],
        "headers": [],
        "cookies": [],
    },
    "lodash": {
        "html": ["lodash.min.js"],
        "url": ["lodash"],
        "js": ["_"],
        "headers": [],
        "cookies": [],
    },
    "moment.js": {
        "html": ["moment.min.js", "moment.js"],
        "url": ["moment"],
        "js": ["moment"],
        "headers": [],
        "cookies": [],
    },
    "alpine.js": {
        "html": ["alpine.min.js", "alpine.js", "x-data"],
        "url": ["alpine"],
        "js": ["Alpine"],
        "headers": [],
        "cookies": [],
    },
    "stimulus": {
        "html": ["data-controller"],
        "js": ["Stimulus", "Application"],
        "url": ["stimulus"],
        "headers": [],
        "cookies": [],
    },
}

# ---------------------------------------------------------------------------
# Analytics & Tracking
# ---------------------------------------------------------------------------
ANALYTICS: dict[str, dict[str, list[str]]] = {
    "google analytics": {
        "html": [
            "google-analytics.com",
            "googletagmanager.com",
            "gtag/js",
            "ga.js",
            "analytics.js",
            "UA-",
            "G-",
            "GTM-",
        ],
        "url": ["google-analytics.com", "googletagmanager.com", "gtag"],
        "js": ["gtag", "ga(", "_gaq", "GoogleAnalyticsObject"],
        "headers": [],
        "cookies": ["_ga", "_gid", "_gat"],
    },
    "google tag manager": {
        "html": [
            "googletagmanager.com/gtm.js",
            "GTM-",
            "data-gtm",
        ],
        "url": ["googletagmanager.com/gtm.js"],
        "js": ["dataLayer", "gtm.js"],
        "headers": [],
        "cookies": ["_ga", "_gid"],
    },
    "hotjar": {
        "html": ["hotjar.com", "hotjar.js", "_hjSettings"],
        "url": ["hotjar.com"],
        "js": ["hj(", "_hjSettings", "hotjar"],
        "headers": [],
        "cookies": ["_hj"],
    },
    "mixpanel": {
        "html": ["mixpanel.com", "mixpanel.min.js"],
        "url": ["mixpanel.com"],
        "js": ["mixpanel.", "mixpanel.track"],
        "headers": [],
        "cookies": ["mp_"],
    },
    "amplitude": {
        "html": ["amplitude.com", "amplitude.min.js"],
        "url": ["amplitude.com"],
        "js": ["amplitude.", "amplitude.getInstance"],
        "headers": [],
        "cookies": ["amp_"],
    },
    "segment": {
        "html": ["segment.com", "analytics.min.js", "segment.io"],
        "url": ["segment.com", "cdn.segment.com"],
        "js": ["analytics.", "analytics.track"],
        "headers": [],
        "cookies": [],
    },
    "plausible": {
        "html": ["plausible.io", "plausible.js"],
        "url": ["plausible.io"],
        "js": ["plausible"],
        "headers": [],
        "cookies": [],
    },
    "matomo": {
        "html": ["matomo", "piwik", "_paq"],
        "url": ["matomo", "piwik"],
        "js": ["_paq.push"],
        "headers": [],
        "cookies": ["_pk_id", "_pk_ses"],
    },
    "heap": {
        "html": ["heap-api.com", "heap.js"],
        "url": ["heap-api.com"],
        "js": ["heap.", "heap.load"],
        "headers": [],
        "cookies": [],
    },
    "clarity": {
        "html": ["clarity.ms", "clarity.js"],
        "url": ["clarity.ms"],
        "js": ["clarity("],
        "headers": [],
        "cookies": ["_clck", "_clsk"],
    },
    "fullstory": {
        "html": ["fullstory.com", "fullstory.js"],
        "url": ["fullstory.com"],
        "js": ["FS.record", "FullStory"],
        "headers": [],
        "cookies": [],
    },
    "posthog": {
        "html": ["posthog.com", "posthog.js"],
        "url": ["posthog"],
        "js": ["posthog."],
        "headers": [],
        "cookies": ["ph_"],
    },
}

# ---------------------------------------------------------------------------
# CDN
# ---------------------------------------------------------------------------
CDN: dict[str, dict[str, list[str]]] = {
    "cloudflare": {
        "html": [],
        "headers": [
            "server: cloudflare",
            "cf-ray",
            "cf-cache-status",
            "cf-connecting-ip",
        ],
        "cookies": ["__cfduid", "cf_clearance"],
        "url": [],
        "js": [],
    },
    "aws cloudfront": {
        "html": [],
        "headers": [
            "x-amz-cf-id",
            "x-amz-cf-pop",
            "via: cloudfront",
            "x-cache: cloudfront",
        ],
        "cookies": [],
        "url": [],
        "js": [],
    },
    "fastly": {
        "html": [],
        "headers": [
            "via: varnish",
            "x-served-by: cache-",
            "x-fastly",
            "fastly-debug-digest",
        ],
        "cookies": [],
        "url": [],
        "js": [],
    },
    "akamai": {
        "html": [],
        "headers": [
            "x-akamai",
            "akamai-origin-hop",
            "server: akamai",
        ],
        "cookies": ["akamai_"],
        "url": [],
        "js": [],
    },
    "keycdn": {
        "html": [],
        "headers": ["x-edge-location", "server: keycdn"],
        "cookies": [],
        "url": ["kxcdn.com"],
        "js": [],
    },
    "stackpath": {
        "html": [],
        "headers": ["server: stackpath"],
        "cookies": [],
        "url": ["stackpathdns.com", "stackpathcdn.com"],
        "js": [],
    },
    "vercel edge": {
        "html": [],
        "headers": ["x-vercel", "server: Vercel"],
        "cookies": ["__vercel_insights_id"],
        "url": [],
        "js": [],
    },
    "netlify": {
        "html": [],
        "headers": ["server: netlify", "x-nf-request-id"],
        "cookies": [],
        "url": ["netlify.app"],
        "js": [],
    },
    "bunny cdn": {
        "html": [],
        "headers": ["server: BunnyCDN", "cdn-pullzone"],
        "cookies": [],
        "url": ["b-cdn.net"],
        "js": [],
    },
    "azure cdn": {
        "html": [],
        "headers": ["x-azure-ref", "x-msedge-ref"],
        "cookies": [],
        "url": [],
        "js": [],
    },
}

# ---------------------------------------------------------------------------
# Hosting / Platform
# ---------------------------------------------------------------------------
HOSTING: dict[str, dict[str, list[str]]] = {
    "vercel": {
        "html": [],
        "headers": ["server: Vercel", "x-vercel-id"],
        "cookies": ["__vercel_preview_mode"],
        "url": ["vercel.app"],
        "js": [],
    },
    "netlify": {
        "html": [],
        "headers": ["server: Netlify"],
        "cookies": [],
        "url": ["netlify.app", "netlify.com"],
        "js": [],
    },
    "heroku": {
        "html": [],
        "headers": ["via: 1.1 vegur", "server: Heroku"],
        "cookies": [],
        "url": ["herokuapp.com"],
        "js": [],
    },
    "aws": {
        "html": [],
        "headers": ["server: AmazonS3", "x-amz-request-id"],
        "cookies": [],
        "url": ["amazonaws.com", "s3.amazonaws.com"],
        "js": [],
    },
    "google cloud": {
        "html": [],
        "headers": ["server: Google Frontend"],
        "cookies": [],
        "url": ["googleapis.com", "appspot.com"],
        "js": [],
    },
    "azure": {
        "html": [],
        "headers": ["server: Microsoft-IIS", "x-azure-ref"],
        "cookies": [],
        "url": ["azurewebsites.net"],
        "js": [],
    },
    "digitalocean": {
        "html": [],
        "headers": [],
        "cookies": [],
        "url": ["digitaloceanspaces.com"],
        "js": [],
    },
    "fly.io": {
        "html": [],
        "headers": ["server: Fly/", "fly-request-id"],
        "cookies": [],
        "url": ["fly.dev"],
        "js": [],
    },
    "cloudflare pages": {
        "html": [],
        "headers": ["server: cloudflare"],
        "cookies": [],
        "url": ["pages.dev"],
        "js": [],
    },
    "firebase": {
        "html": [],
        "headers": [],
        "cookies": [],
        "url": ["firebaseio.com", "firebaseapp.com", "web.app"],
        "js": ["firebase", "firebase.initializeApp"],
    },
}

# ---------------------------------------------------------------------------
# CMS
# ---------------------------------------------------------------------------
CMS: dict[str, dict[str, list[str]]] = {
    "wordpress": {
        "html": [
            "wp-content",
            "wp-includes",
            "wp-json",
            "wordpress",
            "generator\" content=\"WordPress",
        ],
        "url": ["wp-content", "wp-includes", "wp-json"],
        "headers": ["x-powered-by: WordPress", "link: <...wp-json"],
        "cookies": ["wordpress_"],
        "js": ["wp.", "wpApiSettings"],
    },
    "shopify": {
        "html": [
            "shopify",
            "Shopify.theme",
            "cdn.shopify.com",
        ],
        "url": ["cdn.shopify.com", "shopify.com"],
        "headers": ["x-shopify-stage"],
        "cookies": ["_shopify_"],
        "js": ["Shopify", "Shopify.theme"],
    },
    "drupal": {
        "html": [
            "drupal",
            "sites/default/files",
            "Drupal.settings",
        ],
        "url": ["sites/default/files", "drupal.js"],
        "headers": ["x-generator: Drupal", "x-drupal-cache"],
        "cookies": ["SSESS", "Drupal.", "drupal_"],
        "js": ["Drupal.settings"],
    },
    "joomla": {
        "html": [
            "joomla",
            "/media/jui/",
            "Joomla!",
        ],
        "url": ["/media/jui/", "joomla"],
        "headers": ["x-content-encoded-by: Joomla"],
        "cookies": [],
        "js": ["Joomla"],
    },
    "squarespace": {
        "html": [
            "squarespace",
            "static.squarespace.com",
        ],
        "url": ["static.squarespace.com"],
        "headers": [],
        "cookies": ["ss_*"],
        "js": ["Squarespace"],
    },
    "wix": {
        "html": [
            "wix.com",
            "wixstatic.com",
            "wix-html-app",
        ],
        "url": ["static.wixstatic.com", "wix.com"],
        "headers": [],
        "cookies": [],
        "js": ["wix", "wixWindow"],
    },
    "webflow": {
        "html": [
            "webflow",
            "webflow.com",
        ],
        "url": ["assets.website-files.com", "webflow.com"],
        "headers": [],
        "cookies": [],
        "js": ["Webflow"],
    },
    "ghost": {
        "html": [
            "ghost/",
            "ghost-url",
            "ghost-theme",
        ],
        "url": ["ghost.io", "ghost/"],
        "headers": ["x-ghost-"],
        "cookies": [],
        "js": [],
    },
    "contentful": {
        "html": ["contentful", "ctf_assets"],
        "url": ["ctfassets.net", "contentful.com"],
        "headers": [],
        "cookies": [],
        "js": [],
    },
    "strapi": {
        "html": ["strapi"],
        "url": ["strapi"],
        "headers": [],
        "cookies": [],
        "js": [],
    },
}

# ---------------------------------------------------------------------------
# Payment Providers
# ---------------------------------------------------------------------------
PAYMENT: dict[str, dict[str, list[str]]] = {
    "stripe": {
        "html": [
            "stripe.com",
            "js.stripe.com",
            "Stripe(",
        ],
        "url": ["js.stripe.com", "stripe.com"],
        "js": ["Stripe(", "stripe.elements"],
        "headers": [],
        "cookies": ["__stripe_mid", "__stripe_sid"],
    },
    "paypal": {
        "html": [
            "paypal.com",
            "paypalobjects.com",
            "PayPal",
        ],
        "url": ["paypal.com", "paypalobjects.com"],
        "js": ["paypal", "PayPal"],
        "headers": [],
        "cookies": [],
    },
    "square": {
        "html": [
            "square",
            "squareup.com",
            "sqpaymentform",
        ],
        "url": ["squareup.com", "square.js"],
        "js": ["Square"],
        "headers": [],
        "cookies": [],
    },
    "braintree": {
        "html": [
            "braintree",
            "braintreegateway.com",
        ],
        "url": ["braintreegateway.com", "braintree-api.com"],
        "js": ["braintree"],
        "headers": [],
        "cookies": [],
    },
    "paddle": {
        "html": ["paddle.com", "Paddle"],
        "url": ["paddle.com"],
        "js": ["Paddle"],
        "headers": [],
        "cookies": [],
    },
}

# ---------------------------------------------------------------------------
# Languages / Runtimes (server-side hints)
# ---------------------------------------------------------------------------
LANGUAGES: dict[str, dict[str, list[str]]] = {
    "php": {
        "html": [],
        "headers": ["x-powered-by: PHP", "x-debug-mode"],
        "cookies": ["PHPSESSID"],
        "url": [".php"],
        "js": [],
    },
    "python": {
        "html": [],
        "headers": ["x-powered-by: Python", "server: Gunicorn", "server: uWSGI"],
        "cookies": [],
        "url": [".py"],
        "js": [],
    },
    "ruby": {
        "html": [],
        "headers": ["x-powered-by: Phusion Passenger", "x-runtime"],
        "cookies": ["_session_id"],
        "url": [".rb"],
        "js": [],
    },
    "node.js": {
        "html": [],
        "headers": ["x-powered-by: Express", "x-powered-by: Express.js"],
        "cookies": ["connect.sid"],
        "url": [],
        "js": [],
    },
    "java": {
        "html": [],
        "headers": ["x-powered-by: Servlet", "server: Apache-Coyote"],
        "cookies": ["JSESSIONID"],
        "url": [".jsp", ".do", ".action"],
        "js": [],
    },
    "dotnet": {
        "html": [],
        "headers": [
            "x-powered-by: ASP.NET",
            "x-aspnet-version",
            "x-aspnetmvc-version",
        ],
        "cookies": [".ASPXAUTH", "ASP.NET_SessionId"],
        "url": [".aspx", ".ashx", ".axd"],
        "js": [],
    },
}

# ---------------------------------------------------------------------------
# Email / Marketing
# ---------------------------------------------------------------------------
EMAIL_MARKETING: dict[str, dict[str, list[str]]] = {
    "sendgrid": {
        "html": ["sendgrid.com", "sendgrid"],
        "url": ["sendgrid.net", "sendgrid.com"],
        "headers": [],
        "cookies": [],
        "js": [],
    },
    "mailchimp": {
        "html": ["mailchimp.com", "list-manage.com", "mc.us"],
        "url": ["list-manage.com", "mailchimp.com"],
        "headers": [],
        "cookies": [],
        "js": [],
    },
    "hubspot": {
        "html": [
            "hubspot.com",
            "hs-scripts",
            "hbspt",
            "hubspot.net",
        ],
        "url": ["hubspot.com", "hs-scripts"],
        "js": ["hbspt", "HubSpot"],
        "headers": [],
        "cookies": ["__hs", "hs_ab_test"],
    },
    "intercom": {
        "html": ["intercom.com", "intercom-settings"],
        "url": ["intercom.com", "intercom.io"],
        "js": ["Intercom("],
        "headers": [],
        "cookies": ["intercom-"],
    },
    "crisp": {
        "html": ["crisp.chat", "CRISP_WEBSITE_ID"],
        "url": ["crisp.chat"],
        "js": ["CRISP_WEBSITE_ID"],
        "headers": [],
        "cookies": [],
    },
    "drift": {
        "html": ["drift.com", "driftt"],
        "url": ["drift.com", "driftt.com"],
        "js": ["drift"],
        "headers": [],
        "cookies": [],
    },
}

# ---------------------------------------------------------------------------
# Other / Meta
# ---------------------------------------------------------------------------
OTHER: dict[str, dict[str, list[str]]] = {
    "recaptcha": {
        "html": ["recaptcha", "grecaptcha", "google.com/recaptcha"],
        "url": ["recaptcha", "google.com/recaptcha"],
        "js": ["grecaptcha", "recaptcha"],
        "headers": [],
        "cookies": [],
    },
    "hcapTCHA": {
        "html": ["hcaptcha.com", "h-captcha"],
        "url": ["hcaptcha.com"],
        "js": ["hcaptcha"],
        "headers": [],
        "cookies": [],
    },
    "cloudflare turnstile": {
        "html": ["turnstile", "challenges.cloudflare.com"],
        "url": ["challenges.cloudflare.com"],
        "js": ["turnstile"],
        "headers": [],
        "cookies": [],
    },
    "schema.org": {
        "html": ["schema.org", "itemtype=", "itemscope"],
        "url": [],
        "js": [],
        "headers": [],
        "cookies": [],
    },
    "open graph": {
        "html": ['property="og:'],
        "url": [],
        "js": [],
        "headers": [],
        "cookies": [],
    },
    "twitter card": {
        "html": ['name="twitter:'],
        "url": [],
        "js": [],
        "headers": [],
        "cookies": [],
    },
    "service worker": {
        "html": ["serviceWorker", "navigator.serviceWorker"],
        "url": ["sw.js", "service-worker.js"],
        "js": ["serviceWorker"],
        "headers": [],
        "cookies": [],
    },
    "web manifest": {
        "html": ['rel="manifest"'],
        "url": ["manifest.json", "manifest.webmanifest"],
        "js": [],
        "headers": [],
        "cookies": [],
    },
    "amp": {
        "html": ["amphtml", "<amp-", "amp-ad", "amp-analytics"],
        "url": ["cdn.ampproject.org"],
        "js": ["AMP"],
        "headers": [],
        "cookies": [],
    },
}
