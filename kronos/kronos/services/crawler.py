# -*- coding: utf-8 -*-
"""
    kronos.services.crawler
    ~~~~~~~~~~~~~~~~~~~~~~~

    Polite crawler that yields discovered HTML pages and PDF files present on the domain.
"""

import cgi
import time
from collections import deque
from contextlib import suppress
from typing import Generator
from urllib.parse import parse_qsl, urldefrag, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from pydantic import Field, field_validator
from requests.structures import CaseInsensitiveDict

from common.core import get_component_logger
from common.models.base import CustomBaseModel
from common.utils import exceptions as exc

logger = get_component_logger()

USER_AGENT = "KronosCrawler/1.0 (CIIRC_NLP; +https://sites.google.com/view/ciirc-nlp-tech/home)"
HEADERS = {
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "cs-CZ,cs;q=0.9,en-US;q=0.8,en;q=0.7",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": USER_AGENT,
}

EXT_TO_MIMETYPE_MAPPING = {
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "htm": "text/html",
    "html": "text/html",
    "pdf": "application/pdf",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

SUPPORTED_EXT = {"htm", "html", "pdf"}
SUPPORTED_MIMETYPES = {EXT_TO_MIMETYPE_MAPPING[ext] for ext in SUPPORTED_EXT}

HTML_BANNED_EXT = {
    "7z", "avi", "css", "doc", "docx", "flac", "gif", "gz", "ico", "jpeg", "jpg", "js", "mjs", "mkv", "mov", "mp3",
    "mp4", "otf", "pdf", "png", "ppt", "pptx", "rar", "svg", "tar", "tgz", "ttf", "wav", "webp", "woff", "woff2",
    "xls", "xlsx", "zip",
}


class CrawlOptions(CustomBaseModel):
    delay: float = 1.0
    max_pages: int = 1000
    timeout: float | tuple[float, float] = (10.0, 30.0)

    exclude_mimetypes: set[str] = Field(default_factory=set)
    exclude_query_params: set[str] = Field(default_factory=set)
    exclude_substrings: set[str] = Field(default_factory=set)
    exclude_suffixes: set[str] = Field(default_factory=set)

    same_host_only: bool = True

    @field_validator("exclude_mimetypes", "exclude_query_params", "exclude_substrings", "exclude_suffixes")
    @classmethod
    def clean_exclude_set(cls, v: set[str]) -> set[str]:
        return {xs.lower() for x in v if (xs := x.strip())}

    @field_validator("exclude_mimetypes", "exclude_query_params", "exclude_suffixes")
    @classmethod
    def strip_exclude_set(cls, v: set[str]) -> set[str]:
        return {x.strip("/").strip() for x in v}


class Scraper:

    def __init__(
            self,
            url: str,
            exclude_mimetypes: set[str] | None = None,
            request_headers: dict[str, str] | None = None,
            request_timeout: float | tuple[float, float] = (10.0, 30.0),
    ):
        """
        URL scraper.

        Properties are filled lazily based on user requests.

        :param url: URL to scrape
        :param request_headers: custom scraping request headers
        :param request_timeout: scraping request timeout(s)
        """

        self.url = url
        self._url_final = None

        self._content = None
        self._soup = None

        self._charset = None
        self._headers = None
        self._mimetype = None
        self._title = None

        if request_headers:
            self._request_headers = HEADERS.copy()
            self._request_headers.update(request_headers)
        else:
            self._request_headers = HEADERS

        self._request_timeout = request_timeout
        self._supported_mimetypes = SUPPORTED_MIMETYPES - (exclude_mimetypes or set())

    @property
    def url_final(self) -> str:
        """Get the final (redirected) URL."""

        if self._url_final is not None:
            return self._url_final

        r = requests.head(self.url, headers=self._request_headers, timeout=self._request_timeout, allow_redirects=True)
        if r.status_code == 404:
            raise exc.ResourceNotFoundURL(url=self.url)

        self._url_final = r.url
        self._headers = r.headers
        return self._url_final

    @property
    def content(self) -> bytes:
        """Get the URL page/file content."""

        if self._content is not None:
            return self._content

        if self.mimetype not in self._supported_mimetypes:
            raise exc.UnsupportedContentType(url=self.url, content_type=self.mimetype)

        r = requests.get(self.url_final, headers=self._request_headers, timeout=self._request_timeout)
        self._content = r.content
        return self._content

    @property
    def soup(self) -> BeautifulSoup | None:
        """Get BS4-parsed HTML content."""

        if self._soup is not None:
            return self._soup

        if self.mimetype != "text/html":
            return None

        self._soup = BeautifulSoup(self.content, "html.parser")
        return self._soup

    @property
    def charset(self) -> str:
        """Get content charset."""

        if self._charset is not None:
            return self._charset

        mimetype, self._charset = self.parse_content_type(self.headers.get("Content-Type", ""))
        return self._charset

    @property
    def headers(self) -> CaseInsensitiveDict:
        """Get the URL response headers."""

        _ = self.url_final
        return self._headers

    @property
    def mimetype(self) -> str:
        """
        Get content mimetype.

        Tries to get the mimetype from:
          1. final (redirected) URL
          2. original (init) URL
          3. Content-Type header
        """

        if self._mimetype is not None:
            return self._mimetype

        mimetype, self._charset = self.parse_content_type(self.headers.get("Content-Type", ""))
        self._mimetype = self.get_mimetype_from_url(self.url_final) or self.get_mimetype_from_url(self.url) or mimetype
        return self._mimetype

    @property
    def title(self) -> str:
        """
        Get HTML page title.

        Tries to get the title from:
          1. BS4 title (soup.title)
          2. h1 tag
        """

        if self._title is not None:
            return self._title

        self._title = ""

        if (soup := self.soup) is None:
            return self._title

        if soup.title and soup.title.string:
            self._title = soup.title.string.strip()
            return self._title

        for h1 in soup.find_all("h1"):
            if h1_text := h1.get_text(strip=True):
                self._title = h1_text
                return self._title

        return self._title

    @staticmethod
    def parse_content_type(content_type: str) -> tuple[str, str]:
        """
        Parse content type and return mimetype and charset.

        :param content_type: Content-Type header string
        :return: mimetype str, charset str
        """

        mimetype, options = cgi.parse_header(content_type)
        charset = options.get("charset", "utf-8")
        return mimetype, charset

    @staticmethod
    def get_mimetype_from_url(url: str) -> str | None:
        """
        Try to get mimetype from URL.

        :param url: input URL
        :return: mimetype str
        """

        if "." not in (path := urlparse(url).path.lower()):
            return None
        return EXT_TO_MIMETYPE_MAPPING.get(path.rsplit(".", 1)[-1])


class Crawler:

    def __init__(self, start_url: str, opts: CrawlOptions | None = None):
        """
        URL/Domain crawler.

        :param start_url: start/seed URL
        :param opts: crawling options
        """

        self.start_url = start_url
        self.opts = opts or CrawlOptions()

        self._rp = self._load_robots()

        unsupported_ext = {ext for ext, mt in EXT_TO_MIMETYPE_MAPPING.items() if mt in self.opts.exclude_mimetypes}
        self._supported_ext = SUPPORTED_EXT - unsupported_ext

    def _load_robots(self) -> RobotFileParser:
        """Load the robots.txt file."""

        base = urlparse(self.start_url)
        robots_url = f"{base.scheme}://{base.netloc}/robots.txt"
        rp = RobotFileParser()

        with suppress(Exception):
            rp.set_url(robots_url)
            rp.read()

        return rp

    def _can_fetch(self, url: str, seen: set[str]) -> bool:
        """
        Check if a URL can be fetched or should be skipped.

        :param url: input URL
        :param seen: set of URLs already seen during crawling
        :return: can-fetch flag
        """

        if url in seen:
            return False
        seen.add(url)

        if not self._can_fetch_per_url(url):
            return False
        if not self._can_fetch_per_robots(url):
            return False

        return True

    def _can_fetch_per_robots(self, url: str) -> bool:
        """Check if a URL can be fetched based on the robots file."""

        with suppress(Exception):
            return self._rp.can_fetch(USER_AGENT, url)
        return True

    def _can_fetch_per_url(self, url: str) -> bool:
        """Check if the URL can be fetched based on URL rules/exclusions only."""

        if self.opts.same_host_only and not self._is_same_host(self.start_url, url):
            return False
        if self._has_excluded_extension(url):
            return False
        if self._has_excluded_query_param(url):
            return False
        if self._has_excluded_substring(url):
            return False
        if self._has_excluded_suffix(url):
            return False
        return True

    @staticmethod
    def _is_same_host(a: str, b: str) -> bool:
        """Check if two URLs have the same host."""
        return urlparse(a).netloc.lower() == urlparse(b).netloc.lower()

    def _has_excluded_extension(self, url: str) -> bool:
        """Check if the URL path contains an excluded extension."""

        # The path does not have an extension
        if "." not in (path := urlparse(url).path.lower()):
            return False

        ext = path.rsplit(".", 1)[-1]

        # The extension is in the list of supported extensions
        if ext in self._supported_ext:
            return False

        # The extension is in the list of non-HTML extensions
        if ext in HTML_BANNED_EXT:
            return True

        return False

    def _has_excluded_query_param(self, url: str) -> bool:
        """Check if the URL contains an excluded query parameter."""

        if not self.opts.exclude_query_params:
            return False

        query_keys = {k.lower() for k, _ in parse_qsl(urlparse(url).query, keep_blank_values=True)}
        return not self.opts.exclude_query_params.isdisjoint(query_keys)

    def _has_excluded_substring(self, url: str) -> bool:
        """Check if the URL contains an excluded substring."""

        if not self.opts.exclude_substrings:
            return False

        url = url.lower()
        return any(s in url for s in self.opts.exclude_substrings)

    def _has_excluded_suffix(self, url: str) -> bool:
        """Check if the URL path contains an excluded suffix."""

        if not self.opts.exclude_suffixes:
            return False

        path = urlparse(url).path.lower()
        suffix = path.rstrip("/").rsplit("/", 1)[-1]
        return any(s == suffix for s in self.opts.exclude_suffixes)

    @staticmethod
    def _normalize_url(base_url: str, href: str) -> str | None:
        """
        Normalize URL.

        :param base_url: base URL of the href parent
        :param href: href link to normalize
        :return: normalized URL
        """

        with suppress(Exception):
            abs_url = urljoin(base_url, href)
            # noinspection HttpUrlsUsage
            if not abs_url.lower().startswith(("http://", "https://")):
                return None

            abs_url, _ = urldefrag(abs_url)
            scheme, netloc, path, params, query, _frag = urlparse(abs_url)
            scheme = scheme.lower()
            netloc = netloc.lower()

            if scheme == "http" and netloc.endswith(":80"):
                netloc = netloc.rsplit(":80", 1)[0]
            elif scheme == "https" and netloc.endswith(":443"):
                netloc = netloc.rsplit(":443", 1)[0]

            if path != "/":
                path = path.rstrip("/")

            return str(urlunparse((scheme, netloc, path, params, query, "")))

        return None

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> Generator[str, None, None]:
        """
        Extract href links from HTML content.

        :param soup: BS4-parsed HTML content
        :param base_url: base URL for the HTML
        :return: found URLs generator
        """

        for a in soup.find_all("a", href=True):
            if url := self._normalize_url(base_url, a["href"]):
                yield url

    def crawl(self) -> Generator[Scraper, None, None]:
        """Crawl the website."""

        seed_norm = self._normalize_url(self.start_url, "") or self.start_url
        q: deque[tuple[str, int]] = deque()
        q.append((seed_norm, 0))

        num_pages = 0
        seen: set[str] = set()

        while q and num_pages < self.opts.max_pages:
            url, depth = q.popleft()

            # Check the raw URL
            if not self._can_fetch(url, seen=seen):
                continue

            # Get final URL (redirect)
            scraper = Scraper(url, exclude_mimetypes=self.opts.exclude_mimetypes, request_timeout=self.opts.timeout)

            try:
                url_final = scraper.url_final
            except Exception as e:
                logger.error("Error occurred during crawling -> skipping URL %s: %s", url, e)
                continue

            # Check the final URL
            if url_final != url and not self._can_fetch(url_final, seen=seen):
                continue

            # Get URL content
            try:
                _ = scraper.content
            except Exception as e:
                logger.error("Error occurred during crawling -> skipping URL %s: %s", url, e)
                continue

            # Find new links in HTML
            if scraper.mimetype == "text/html":
                num_pages += 1

                with suppress(Exception):
                    q.extend([
                        (link, depth + 1)
                        for link in self._extract_links(soup=scraper.soup, base_url=url_final)
                    ])

            # Yield the Scraper object
            yield scraper

            # Apply delay
            if self.opts.delay > 0:
                time.sleep(self.opts.delay)
