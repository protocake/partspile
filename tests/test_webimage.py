"""Product-page image extraction tests — pure parsing, no network."""

import unittest

from partspile.webimage import find_image_url


class FindImageTest(unittest.TestCase):
    def test_og_image_wins(self):
        html = """<html><head>
          <img src="/logo.png"><meta property="og:image" content="/img/product.jpg">
          </head></html>"""
        self.assertEqual(find_image_url(html, "https://x.com/p/1"),
                         "https://x.com/img/product.jpg")

    def test_content_attr_first_variant(self):
        html = '<meta content="https://cdn.x.com/a.png" property="og:image">'
        self.assertEqual(find_image_url(html, "https://x.com"),
                         "https://cdn.x.com/a.png")

    def test_falls_back_to_first_content_img_skipping_icons(self):
        html = """<img src="/icons/star.svg"><img src="/logo.png">
                  <img src="/photos/board-large.jpg">"""
        self.assertEqual(find_image_url(html, "https://x.com/"),
                         "https://x.com/photos/board-large.jpg")

    def test_none_when_nothing_plausible(self):
        self.assertIsNone(find_image_url("<p>no images here</p>", "https://x.com"))


if __name__ == "__main__":
    unittest.main()
