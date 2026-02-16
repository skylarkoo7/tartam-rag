from app.text_quality import likely_misencoded_indic_text


def test_likely_misencoded_indic_text_detects_latin_heavy_noise() -> None:
    sample = ("abcXYZ{}[]|^~" * 20) + ("12345" * 10)
    assert likely_misencoded_indic_text(sample)


def test_likely_misencoded_indic_text_accepts_devanagari_text() -> None:
    sample = "यह एक परीक्षण पाठ है। " * 20
    assert not likely_misencoded_indic_text(sample)
