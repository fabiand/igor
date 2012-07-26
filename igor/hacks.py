# -*- coding: utf-8 -*-
#
# Copyright (C) 2012  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: Fabian Deutsch <fabiand@fedoraproject.org>
#

import json

import igor.main
import igor.job
import igor.utils

class IgordJSONEncoder(json.encoder.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, igor.job.Job) or \
           isinstance(obj, igor.main.Testsuite) or \
           isinstance(obj, igor.main.Testset) or \
           isinstance(obj, igor.main.Testcase) or \
           isinstance(obj, igor.main.Profile) or \
           isinstance(obj, igor.main.Origin) or \
           isinstance(obj, igor.main.Host) or \
           isinstance(obj, igor.main.Testplan):
            return obj.__to_dict__()
        elif isinstance(obj, igor.utils.State):
            return str(obj)
        return json.encoder.JSONEncoder.default(self, obj)
