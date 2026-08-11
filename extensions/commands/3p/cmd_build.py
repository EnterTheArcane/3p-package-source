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
def build(conan_api, parser, *args):
    """Build a platform into the Conan cache, without packaging it."""
    parser.add_argument("platform")
    parser.add_argument("--only", help="build a single catalog entry")
    parser.add_argument("--rebuild", action="store_true",
                        help="build from source even if a binary is cached")
    parsed = parser.parse_args(*args)
    _repo.implementation().cmd_build(
        _repo.options(platform=parsed.platform, only=parsed.only, rebuild=parsed.rebuild))
