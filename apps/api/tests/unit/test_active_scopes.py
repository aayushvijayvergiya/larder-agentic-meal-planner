from types import SimpleNamespace as NS

from larder.services.households import active_scopes


def test_solo_household_is_single():
    h = NS(members=[NS(user_id="a", preferred_view="single")])
    assert active_scopes(h) == [("single", "a")]


def test_family_and_singles():
    h = NS(members=[NS(user_id="a", preferred_view="family"), NS(user_id="b", preferred_view="single")])
    assert active_scopes(h) == [("family", None), ("single", "b")]


def test_two_members_both_family_yields_only_family():
    h = NS(members=[NS(user_id="a", preferred_view="family"), NS(user_id="b", preferred_view="family")])
    assert active_scopes(h) == [("family", None)]
