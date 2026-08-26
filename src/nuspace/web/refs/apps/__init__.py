"""Apps section: VSCode-style tree + code editor over ``Space.apps``.

Ships one nu.ui ref (``AppsRef``) plus its per-connection driver
(``AppsDriver``) that recomputes the tree on any substrate change and
dispatches browser feedback events (select / edit / create / rename /
delete) into substrate writes.
"""

from nuspace.web.refs.apps.apps import AppsFeedbackDriver, AppsRef, AppsShipTree


__all__ = ["AppsFeedbackDriver", "AppsRef", "AppsShipTree"]
