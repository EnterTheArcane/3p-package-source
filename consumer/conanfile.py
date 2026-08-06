#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

import importlib.util
import os

from conan import ConanFile

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_catalog():
    path = os.path.join(_HERE, os.pardir, "tools", "catalog.py")
    spec = importlib.util.spec_from_file_location("_3p_catalog", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


catalog = _load_catalog()


class ThirdParty(ConanFile):
    """Aggregate of every third party package built for one platform.

    Installing this with a platform profile resolves the whole graph; the
    deployer then turns each resolved package into an engine package.
    """

    name = "3rdparty"
    version = "1.0"
    settings = "os", "arch", "compiler", "build_type"

    def requirements(self):
        for name, spec in catalog.packages_for(catalog.platform_id(self.settings)).items():
            # The catalog decides versions. Dependencies often pin an older revision of
            # something we also ship, and we want one copy of each library in the engine,
            # not two; force makes the catalog entry win those conflicts.
            self.requires(f"{name}/{spec['version']}", force=True)
