#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2019 Fabian Wenzelmann
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from .invoice import InvoiceRenderer
from weasyprint import default_url_fetcher


class WeasyRenderer(InvoiceRenderer):
    """An invoice renderer that uses WeasyPrint to create a pdf output.

    This implementation does not have a template engine attached, it simply takes a complete HTML input string and runs
    WeasyPrint on that string.
    Create a subclass to embed a template engine.

    The render method must have an additional argument 'string' that is the string representation of the HTML input.
    It also has an URL fetcher (see https://weasyprint.readthedocs.io/en/latest/tutorial.html#url-fetchers).
    This way we can dynamically access resources from for example a database.

    For this purpose we have a wrapper around the WeasyPrint url fetcher. We have factory method called
    create_url_fetcher. Thus, create_url_fetcher returns a WeasyPrint URL fetcher itself and you can pass it as an
    argument to render. Of course you can also create your own fetcher and just use it. Be careful though that you may
    give access to internal files via URLs like file://, see
    https://weasyprint.readthedocs.io/en/latest/tutorial.html#access-to-local-files

    The built-in fetchers provide some protection against that, but always take care on how and who can edit local
    resources or other personal information! Also you should never allow users to input html tags without escaping HTML
    (as Django does) to avoid HTML injections.
    """
    def render(self, filepath=None, **kwargs):
        pass

    @staticmethod
    def create_url_fetcher(mapping, allow_files=False, fallback_default=False, **kwargs):
        """Returns a new WeasyPrint URL fetcher (https://weasyprint.readthedocs.io/en/latest/tutorial.html#url-fetchers).

        The idea is to restrict access to only certain (local) resources. The default fetcher will fetch files, all
        kinds of URLs etc. In general we want only access to predefined files or we want dynamic images based on a
        request etc.
        Thus the mapping dictionary defines a set of local resources which can be accessed when rendering the pdf.
        This can be for example local CSS files, a logo image and so on.
        These local resources can be included in the HTML in a tag like <img src="resource:my_company_logo.png">.
        By default all local resources must start with "resource:". Then the mapping dict would contain an entry
        for "my_company_logo.png" and return an entry for a URL fetcher (a dictionary as defined in the link above).
        It is also possible that the dictionary contains no direct entries in the form of a d cit but a callable
        function taking exactly one argument (the name of the resource). For example we could map "my_company_logo.png"
        to a function taking one argument (which in this case would be "my_company_logo.png") which finds the file in
        some local directory.

        This fetcher also allows to disable local files (with path "file://") and can fallback to the WeasyPrint default
        fetcher.
        Local files can lead to security problems though if not handled correctly, thus they're disabled by default.
        The default fetcher will fetch many different (external) URLs and is therefor not enabled by default.

        The, in my opinion, must secure approach is to allow only resources of the type "resource:" and disallow
        everything else, which should be the case if you just use the mapping dict.

        This method returns a URL fetcher, thus a method. This method can then be passed to the render method
        as the keyword argument "url_fetcher".

        Args:
            mapping: A mapping from resource names to either dicts as defined by the WeasyPrint URL fetcher or a
                callable taking one argument that returns such a dict.
            allow_files: Allow files from the system with the "file://" path, because this may lead to security problems
                it is disabled by default.
            fallback_default: Fallback to the default URL fetcher of WeasyPrint if entry is not found.
            **kwargs:

        Returns:

        """
        def fetcher(url):
            if not allow_files and url.startswith('file://'):
                raise ValueError('Access denied to local file %s' % str(url))
            elif url.startswith('resource:'):
                key = url[9:]
                if key not in mapping:
                    raise ValueError('Resource "%s" not found' % key)
                value = mapping[key]
                if callable(value):
                    value = value(key)
                return value
            # if we reached this part we fallback to the default
            if fallback_default:
                return default_url_fetcher(url, **kwargs)
            raise ValueError('Invalid url: "%s"' % url)
        return fetcher
