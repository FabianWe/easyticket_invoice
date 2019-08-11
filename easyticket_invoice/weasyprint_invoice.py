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

    It also has an URL fetcher (see https://weasyprint.readthedocs.io/en/latest/tutorial.html#url-fetchers).
    This way we can dynamically access resources from for example a database.

    The fetcher is controlled by a dict resources.
    The idea is to restrict access to only certain (local) resources. The default fetcher will fetch files, all
    kinds of URLs etc. In general we want only access to predefined files or we want dynamic images based on a
    request etc.
    Thus the resources dictionary defines a set of local resources which can be accessed when rendering the pdf.
    This can be for example a local CSS files, a logo image and so on.
    These local resources can be included in the HTML in a tag like <img src="resource:my_company_logo.png">.
    By default all local resources must start with "resource:". Then the mapping dict would contain an entry
    for "my_company_logo.png" and return an entry for a URL fetcher (a dictionary as defined in the link above).
    It is also possible that the dictionary contains no direct entries in the form of a dict but a callable
    function taking exactly one argument (the name of the resource). For example we could map "my_company_logo.png"
    to a function taking one argument (which in this case would be "my_company_logo.png") which finds the file in
    some local directory and returns the dict as discuess in the URL fetcher documentation above.

    This fetcher also allows to disable local files (with path "file://") and can fallback to the WeasyPrint default
    fetcher.
    Local files can lead to security problems though if not handled correctly, thus they're disabled by default.
    The default fetcher will fetch many different (external) URLs and is therefor not enabled by default.
    Set allow_files to True if you want to have access to local files.
    See https://weasyprint.readthedocs.io/en/latest/tutorial.html#access-to-local-files for more information.

    Set fallback_default to True if you want to use the default fetcher if now entry was found in the resources
    dict (this also means access to external URLs, so things not starting with "resource:").

    The, in my opinion, must secure approach is to allow only resources of the type "resource:" and disallow
    everything else.

    The built-in fetcher provides some protection against that, but always take care on how and who can edit local
    resources or other personal information! Also you should never allow users to input html tags without escaping HTML
    (as Django does) to avoid HTML injections.

    Please note: If allow_files is True the default fetcher will be used to fetch the content of this file.
    That means in this case the default fetcher may be called even if fallback_default is False.
    This should be the behavior we want, but it's possible that this leads to security risks.

    But you don't have to use this default behavior and can just implement your own fetcher. In this case
    the resources dict, allow_files and fallback_default will be ignored, just change the url_fetcher to a URL fetcher
    method.

    Attributes:
        resources (dict): Maps strings (resource identifiers) to a dict as defined in the WeasyPrint URL fetcher
            documentation or a callable taking one argument and returning such a dict.
        allow_files (bool): If True local files can be accessed via "file://".
        fallback_default (bool): Use the default URL fetcher for everything not starting with "resource:".
        url_fetcher (function): A URL fetcher function as defined in the WeasyPrint docs, if it is not None this
            will be used in fetch_url instead of the default behavior, thus all arguments discussed above will be
            ignored.
    """

    def __init__(self, resources=None, allow_files=False, fallback_default=False, url_fetcher=None):
        if resources is None:
            resources = dict()
        self.resources = resources
        self.allow_files = allow_files
        self.fallback_default = fallback_default
        self.url_fetcher = url_fetcher

    def render(self, filepath=None, **kwargs):
        pass

    def fetch_url(self, url):
        """A WeasyPrint URL fetcher.

        See class documentation for how a resource is located.
        It either uses the url_fetcher of the object (if provided) or otherwise the resources dict as discussed above.

        Args:
            url (str): The URL of the resource to fetch.

        Returns:
            dict: A dict as defined in the URL fetcher docs of WeasyPrint (string or file_obj, mime_type etc.).
        """
        if self.url_fetcher is not None:
            return self.url_fetcher(url)
        elif url.startswith('file://'):
            if not self.allow_files:
                raise ValueError('Access denied to local file "%s"' % str(url))
            else:
                return default_url_fetcher(url)
        elif url.startswith('resource:'):
            key = url[9:]
            if key not in self.resources:
                raise ValueError('Resource "%s" not found' % key)
            value = self.resources[key]
            if callable(value):
                value = value(key)
            return value
        elif self.fallback_default:
            return default_url_fetcher(url)
        else:
            raise ValueError('Invalid url: "%s"' % url)
