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
def validate(conan_api, parser, *args):
    """Check built packages against what the engine expects of them."""
    parser.add_argument("platform")
    parser.add_argument("-o", "--output", help="folder holding the packages")
    parsed = parser.parse_args(*args)
    _repo.implementation().cmd_validate(
        _repo.options(platform=parsed.platform, output=parsed.output))
