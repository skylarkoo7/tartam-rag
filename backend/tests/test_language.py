from app.language import detect_style, query_variants


def test_detect_style_hindi_script() -> None:
    assert detect_style("कैसे हो") == "hi"


def test_detect_style_gujarati_script() -> None:
    assert detect_style("કેમ છો") == "gu"


def test_detect_style_hinglish() -> None:
    assert detect_style("kaise ho aap") == "hi_latn"


def test_detect_style_gujarati_roman() -> None:
    assert detect_style("kem cho tame") == "gu_latn"


def test_query_variants_not_empty() -> None:
    variants = query_variants("kaise ho", "hi_latn")
    assert variants
