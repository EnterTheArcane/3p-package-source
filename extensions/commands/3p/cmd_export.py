#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

from conan.cli.command import conan_command

import _repo

GROUP = "3rdParty"


@conan_command(group=GROUP)
def export(conan_api, parser, *args):
    """Export every recipe to the Conan cache and move the lockfile to match."""
    parser.parse_args(*args)
    _repo.implementation().cmd_export(_repo.options())
