from __future__ import annotations
import unittest
from unittest.mock import MagicMock
from step1_fetch import detect_language, clean_lyrics
from step3_translate import LyricsTranslator
from step4_structure import _slugify
from config import PipelineConfig

class TestPipeline(unittest.TestCase):
    def test_detect_language(self):
        self.assertEqual(detect_language("Hello world"), "english")
        self.assertEqual(detect_language("안녕하세요"), "korean")
        self.assertEqual(detect_language("こんにちは"), "japanese")
        self.assertEqual(detect_language("Hello 안녕하세요"), "mixed_ko_en")
        self.assertEqual(detect_language("Hello こんにちは"), "mixed_ja_en")

    def test_clean_lyrics(self):
        raw = "[Verse 1]\nHello world\n123 Contributors"
        cleaned = clean_lyrics(raw, strip_headers=True)
        self.assertEqual(cleaned, "Hello world")
        
        raw_complex = "[Chorus]\nLine 1\n\n\nLine 2\n42 Contributors\nSome credits"
        cleaned_complex = clean_lyrics(raw_complex, strip_headers=True)
        self.assertIn("Line 1", cleaned_complex)
        self.assertIn("Line 2", cleaned_complex)
        self.assertNotIn("42 Contributors", cleaned_complex)
        self.assertNotIn("[Chorus]", cleaned_complex)

    def test_slugify(self):
        self.assertEqual(_slugify("BTS"), "bts")
        self.assertEqual(_slugify("Fake Love!"), "fake_love")
        self.assertEqual(_slugify("  Artist - Title  "), "artist_-_title")
        self.assertEqual(_slugify("!!!"), "unknown")

    def test_translate_mixed_alignment(self):
        config = PipelineConfig(deepl_api_key="fake_key")
        translator = LyricsTranslator(config)
        
        # Mock DeepL client
        mock_client = MagicMock()
        translator._client = mock_client
        
        # Mock translate_text to return objects with .text attribute
        mock_result1 = MagicMock()
        mock_result1.text = "Korean Translation"
        mock_result2 = MagicMock()
        mock_result2.text = "Another Korean Translation"
        mock_client.translate_text.return_value = [mock_result1, mock_result2]
        
        mixed_lyrics = "English Line 1\n안녕하세요\nEnglish Line 2\n또 만나요"
        # detected_language="mixed_ko_en"
        translated = translator.translate(mixed_lyrics, "mixed_ko_en")
        
        lines = translated.split("\n")
        self.assertEqual(lines[0], "English Line 1")
        self.assertEqual(lines[1], "Korean Translation")
        self.assertEqual(lines[2], "English Line 2")
        self.assertEqual(lines[3], "Another Korean Translation")
        
        # Verify call to translate_text
        mock_client.translate_text.assert_called_once()
        args, kwargs = mock_client.translate_text.call_args
        self.assertEqual(args[0], ["안녕하세요", "또 만나요"])

if __name__ == "__main__":
    unittest.main()
