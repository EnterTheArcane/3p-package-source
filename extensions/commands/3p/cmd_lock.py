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
def lock(conan_api, parser, *args):
    """Rebuild conan.lock across every platform."""
    parser.parse_args(*args)
    _repo.implementation().cmd_lock(_repo.options())
