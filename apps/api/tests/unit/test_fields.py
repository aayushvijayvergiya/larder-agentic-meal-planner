import pytest

from larder.agents.onboarding.fields import FIELDS, coerce_widget_value, next_field, progress


def test_order_and_conditional_medical_notes():
    assert [f.name for f in FIELDS][:3] == ["display_name", "date_of_birth", "sex"]
    draft = {f.name: "x" for f in FIELDS if f.name != "medical_notes"}
    draft["medical_conditions"] = ["none"]
    assert next_field(draft) is None
    assert progress(draft) == (15, 15)
    draft["medical_conditions"] = [{"name": "type 2 diabetes", "notes": None}]
    assert next_field(draft).name == "medical_notes"
    assert progress(draft) == (15, 16)


def test_validation_rejects_bad_height_and_accepts_good():
    f = next(x for x in FIELDS if x.name == "height_cm")
    with pytest.raises(ValueError):
        f.validate(coerce_widget_value(f, 900))
    assert f.validate(coerce_widget_value(f, "172.4")) == 172


def test_list_fields_normalise_and_none():
    allergens = next(x for x in FIELDS if x.name == "allergens")
    assert allergens.validate(coerce_widget_value(allergens, ["Peanuts", "peanut", "none"])) == ["peanut", "none"]
    assert allergens.validate(coerce_widget_value(allergens, ["none"])) == []
    conditions = next(x for x in FIELDS if x.name == "medical_conditions")
    assert conditions.validate(coerce_widget_value(conditions, ["None"])) == []
    assert conditions.validate(coerce_widget_value(conditions, "type 2 diabetes, PCOS")) == [
        {"name": "type 2 diabetes", "notes": None},
        {"name": "PCOS", "notes": None},
    ]
    cuisines = next(x for x in FIELDS if x.name == "cuisines")
    assert cuisines.validate(coerce_widget_value(cuisines, ["North Indian", "gujarati"])) == [
        "north_indian",
        "gujarati",
    ]
    with pytest.raises(ValueError):
        cuisines.validate(coerce_widget_value(cuisines, []))


def test_date_and_prep_time():
    dob = next(x for x in FIELDS if x.name == "date_of_birth")
    assert dob.validate(coerce_widget_value(dob, "1995-04-02")) == "1995-04-02"
    with pytest.raises(ValueError):
        dob.validate(coerce_widget_value(dob, "2025-01-01"))
    prep = next(x for x in FIELDS if x.name == "max_prep_minutes")
    assert prep.validate(coerce_widget_value(prep, "30")) == 30
