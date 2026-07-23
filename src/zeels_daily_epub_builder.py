"""Build the Zeel's Daily newspaper EPUB3 from a validated issue + cover.

Produces a minimal, valid EPUB3 (cover metadata, nav, NCX, spine, one
stylesheet, one chapter per desk) entirely in memory, mirroring the
approved prototype at
`prototypes/private-newspaper/build_and_send_sample_v1_1.py`.
"""
from __future__ import annotations

import io

from ebooklib import epub

from cover_image import validate_cover_jpeg
from zeels_daily_html import CSS_CONTENT, render_chapters
from zeels_daily_schema import Issue

LANGUAGE = "en"
AUTHOR = "Hermy"
CSS_FILE_NAME = "style/newspaper.css"


def _identifier(iso_date: str) -> str:
    return f"urn:zeels-daily:{iso_date}"


def build_epub(issue: Issue, cover_bytes: bytes) -> bytes:
    """Build the newspaper EPUB and return its raw bytes (no disk I/O).

    Hard-fails with :class:`cover_image.CoverImageError` if ``cover_bytes``
    is not a Kindle-safe grayscale baseline JPEG under 250KB.
    """
    validate_cover_jpeg(cover_bytes)

    md = issue.metadata
    book = epub.EpubBook()
    book.set_identifier(_identifier(md.date))
    book.set_title(f"{md.title} — {md.date}")
    book.set_language(LANGUAGE)
    book.add_author(AUTHOR)
    book.add_metadata("DC", "date", md.date)
    book.add_metadata("DC", "description", f"A private morning design digest made for Zeel — {md.date}.")

    book.set_cover("cover.jpg", cover_bytes)

    css = epub.EpubItem(uid="newspaper-style", file_name=CSS_FILE_NAME, media_type="text/css", content=CSS_CONTENT)
    book.add_item(css)

    chapters = []
    for title, file_name, body in render_chapters(issue):
        chapter = epub.EpubHtml(title=title, file_name=file_name, lang=LANGUAGE)
        chapter.content = body
        chapter.add_item(css)
        book.add_item(chapter)
        chapters.append(chapter)

    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["cover", "nav"] + chapters

    buffer = io.BytesIO()
    epub.write_epub(buffer, book)
    return buffer.getvalue()
