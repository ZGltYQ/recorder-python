"""Tests for QuestionDetector (multilingual + stricter English rules).

Covers the three cases we want to get right:

1. True ``?`` at the end -> always a question, any language.
2. First-token WH-word (any of EN / RU / UK) -> question without requiring
   a ``?``. Qwen3-ASR often omits punctuation on interim results; this is
   where most of the early-dispatch wins come from.
3. English aux-verb starts (``Is this...``, ``Are you...``) -> question only
   if the text actually ends with ``?``. Otherwise ``Are you kidding me!``
   would fire the LLM on every exclamation.
"""

from __future__ import annotations

import pytest

from src.ai.openrouter import QuestionDetector


@pytest.fixture
def detector():
    return QuestionDetector()


class TestTrailingQuestionMark:
    def test_english_with_qmark(self, detector):
        assert detector.is_question("Why not?") is True

    def test_russian_with_qmark(self, detector):
        assert detector.is_question("Это правда?") is True

    def test_ukrainian_with_qmark(self, detector):
        assert detector.is_question("Це правда?") is True

    def test_trailing_whitespace_is_stripped(self, detector):
        assert detector.is_question("Ready?   ") is True


class TestEnglishWH:
    @pytest.mark.parametrize(
        "text",
        [
            "What is this",
            "why are we here",
            "How does it work",
            "When do we eat",
            "Where is the key",
            "Who said that",
            "Which one is yours",
            "Whose car is this",
        ],
    )
    def test_wh_word_without_qmark_fires(self, detector, text):
        assert detector.is_question(text) is True

    def test_non_question_not_flagged(self, detector):
        # Statement that happens to contain a WH-word later on.
        assert detector.is_question("I told him where to go") is False


class TestEnglishAuxStrictness:
    """Aux-verb starts only fire when the text actually ends with ``?``."""

    @pytest.mark.parametrize(
        "text",
        [
            "Is this the way?",
            "Are you sure?",
            "Does it work?",
            "Did you see that?",
            "Can you hear me?",
            "Would you help?",
            "Should we go?",
        ],
    )
    def test_aux_with_qmark_fires(self, detector, text):
        assert detector.is_question(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "Are you kidding me",  # exclamation without ?
            "Is this the way it goes.",  # declarative
            "Does he know what he's doing.",
            "Did you know that",  # missing ? -> treat as declarative
            "Can I just say this is insane",
            "Will do.",
            "Should be ready soon.",
        ],
    )
    def test_aux_without_qmark_not_flagged(self, detector, text):
        """No ``?`` -> must not trigger. Prevents false-positive LLM calls."""
        assert detector.is_question(text) is False


class TestRussian:
    @pytest.mark.parametrize(
        "text",
        [
            "Что ты делаешь",
            "Почему так",
            "Как это работает",
            "Когда уже",
            "Где он",
            "Куда идёшь",
            "Откуда ты знаешь",
            "Кто это",
            "Сколько времени",
            "Какой сегодня день",
            "Чей это пёс",
            "Разве ты не знал",
            "Неужели правда",
        ],
    )
    def test_ru_wh_without_qmark(self, detector, text):
        assert detector.is_question(text) is True

    def test_ru_li_particle(self, detector):
        # Classic Russian yes-no inversion with the ``ли`` clitic.
        assert detector.is_question("Знает ли он") is True
        assert detector.is_question("Можно ли сказать иначе") is True

    def test_ru_declarative_not_flagged(self, detector):
        assert detector.is_question("Он сказал что-то странное") is False

    def test_ru_qmark_always_wins(self, detector):
        assert detector.is_question("Скажи что-то интересное?") is True


class TestUkrainian:
    @pytest.mark.parametrize(
        "text",
        [
            "Що це",
            "Чому так",
            "Як це працює",
            "Коли ти прийдеш",
            "Де він",
            "Куди ти йдеш",
            "Звідки ти знаєш",
            "Хто це зробив",
            "Скільки часу",
            "Який у тебе план",
            "Чий це дім",
            "Хіба не знав",
            "Невже справді",
        ],
    )
    def test_uk_wh_without_qmark(self, detector, text):
        assert detector.is_question(text) is True

    def test_uk_chy_particle(self, detector):
        # Ukrainian yes-no questions often start with ``Чи``.
        assert detector.is_question("Чи ти готовий") is True

    def test_uk_declarative_not_flagged(self, detector):
        assert detector.is_question("Він щось сказав") is False


class TestEdgeCases:
    def test_empty(self, detector):
        assert detector.is_question("") is False

    def test_whitespace_only(self, detector):
        assert detector.is_question("   \n\t  ") is False

    def test_punctuation_only(self, detector):
        assert detector.is_question("!!!") is False

    def test_leading_dash_or_quote_doesnt_block(self, detector):
        # Transcripts sometimes include leading em-dash / quote marks.
        # First token extraction must skip those.
        assert detector.is_question("— Why not") is True
        assert detector.is_question('"What is this"') is True

    def test_long_non_question_sentence(self, detector):
        # Full declarative that happens to contain interrogative pronouns
        # later in the string. Must not false-positive.
        assert detector.is_question("I'll tell you later what I think about this plan") is False

    def test_case_insensitive(self, detector):
        assert detector.is_question("WHAT is happening") is True
        assert detector.is_question("почему это работает") is True
