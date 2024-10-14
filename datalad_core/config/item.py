from __future__ import annotations

from datasalad.settings import Setting


class ConfigItem(Setting):
    """ """

    # at this point this class does nothing different
    # than `Setting`. However, we foresee customization
    # and we want to change the foundational type
    # already now, such that we can have smoother upgrades
    # later on
