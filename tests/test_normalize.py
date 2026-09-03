from ingestion.normalize import (
    age_to_years,
    clean_text,
    date_precision,
    extract_narrative_event_date,
    normalize_key,
    split_active_substances,
)


def test_clean_text_collapses_whitespace():
    assert clean_text("  POMALIDOMIDE   HCL \n") == "POMALIDOMIDE HCL"
    assert clean_text("") is None
    assert clean_text(None) is None


def test_normalize_key_uppercases():
    assert normalize_key("pomalidomide") == "POMALIDOMIDE"
    assert normalize_key("  Epinephrine ") == "EPINEPHRINE"
    assert normalize_key(None) is None


def test_split_active_substances_dedupes_and_splits():
    result = split_active_substances(["Acetaminophen; Oxycodone HCl", "acetaminophen"])
    assert result == ["Acetaminophen", "Oxycodone HCl"]


def test_age_to_years_requires_unit():
    assert age_to_years("30", "801") == 30.0  # Year
    assert age_to_years("10950", "804") == 30.0  # Day
    assert age_to_years("78", None) is None
    assert age_to_years(None, "801") is None
    assert age_to_years("30", "999") is None  # unknown unit code


def test_date_precision():
    assert date_precision("102") == "day"
    assert date_precision("610") == "month"
    assert date_precision("602") == "year"
    assert date_precision(None) is None


def test_extract_narrative_event_date():
    assert extract_narrative_event_date("CASE EVENT DATE: 20260211") == "20260211"
    assert extract_narrative_event_date("no date here") is None
    assert extract_narrative_event_date(None) is None
