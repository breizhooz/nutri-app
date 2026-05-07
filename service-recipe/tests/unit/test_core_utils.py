import pytest
from app.core.utils import slugify

class TestCoreUtils:
    """Test pour la classe TranslationLoader"""

    @pytest.mark.parametrize("input_text, expected_slug", [
    ("test d'un slug", "test-d-un-slug"),
    ("Pâtes à la carbonara", "pates-a-la-carbonara"),
    ("Hello World!!!", "hello-world"),
    ("---déjà-vu---", "deja-vu"),
    ("100% pur boeuf", "100-pur-boeuf"),
    ])
    def test_slugify(self, input_text, expected_slug):
        assert slugify(input_text) == expected_slug        