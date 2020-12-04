# Copyright 2019 Canonical Ltd

from distro_info import UbuntuDistroInfo
from functools import total_ordering


@total_ordering
class UbuntuRelease(object):
    all_codenames = UbuntuDistroInfo().all

    def __init__(self, codename):
        if codename not in UbuntuRelease.all_codenames:
            raise ValueError("Unknown codename '{}'".format(codename))
        self.codename = codename

    def __eq__(self, other):
        return UbuntuRelease.all_codenames.index(
            self.codename
        ) == UbuntuRelease.all_codenames.index(other)

    def __le__(self, other):
        return UbuntuRelease.all_codenames.index(
            self.codename
        ) <= UbuntuRelease.all_codenames.index(other)
