"""
Extra HTTP headers that tell browsers to be strict with our pages.

Content-Security-Policy (CSP) lists where scripts, styles, images and
frames may load from. Ours: only this site, plus video frames from
YouTube (privacy-enhanced domain) and TikTok. Even if some text slipped
past escaping, the browser would refuse to run inline <script> code.
"""

CSP = "; ".join([
    "default-src 'self'",
    "img-src 'self' data:",
    "style-src 'self'",
    "script-src 'self'",
    "frame-src https://www.youtube-nocookie.com https://www.tiktok.com",
    "form-action 'self'",
    "frame-ancestors 'none'",   # nobody may put OUR site in a frame (clickjacking)
    "base-uri 'self'",
    "object-src 'none'",
])


def register_security_headers(app):
    @app.after_request
    def add_headers(response):
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response
