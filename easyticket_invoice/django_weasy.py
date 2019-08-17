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

from .weasyprint_invoice import WeasyRenderer
from .invoice import PDFGenException

from django.template import TemplateDoesNotExist, Context
import django.template.loaders.cached as cl
import django.template.engine as de


class DjangoWeasyRenderer(WeasyRenderer):
    def __init__(self, template_name, engines=None, context_dict=None, **kwargs):
        super().__init(**kwargs)
        self.template_name = template_name
        if engines is None:
            engines = []
        self.engines = engines
        if context_dict is None:
            context_dict = dict()
        self.context_dict = context_dict

    def get_context(self, invoice=None, **kwargs):
        ctx = self.get_context_dict(invoice)
        ctx = ctx.update(self.context_dict)
        return Context(ctx, **kwargs)

    def get_template(self, template_name):
        chain = []
        for engine in self.engines:
            try:
                return engine.get_template(template_name)
            except TemplateDoesNotExist as e:
                chain.append(e)
        raise TemplateDoesNotExist(template_name, chain=chain)

    def select_template(self, template_name_list):
        chain = []
        for template_name in template_name_list:
            for engine in self.engines:
                try:
                    return engine.get_template(template_name)
                except TemplateDoesNotExist as e:
                    chain.append(e)
        if template_name_list:
            raise TemplateDoesNotExist(', '.join(template_name_list), chain=chain)
        else:
            raise TemplateDoesNotExist("No template names provided")

    def render(self, invoice, filepath):
        # first render the template to a string
        # then set the string content of weasy print and render
        template = None
        ctx = None
        content = None
        try:
            if isinstance(self.template_name, (list, tuple)):
                template = self.select_template(self.template_name)
            else:
                template = self.get_template(self.template_name)
            ctx = self.get_context(invoice)
            content = template.render(ctx)
        except Exception as e:
            raise PDFGenException('Django template error') from e
        # set content for weasy
        self.set_string(content)
        # render html
        return super().render(invoice, filepath)


class CachedLoader(cl.Loader):
    def __init__(self, engine, loaders):
        super().__init__(engine, loaders)

    def del_cache(self, template_name, skip=None):
        key = self.cache_key(template_name, skip)
        self.get_template_cache.pop(key, None)


class Engine(de.Engine):
    def __init__(self, loaders=None, app_dirs=None, debug=False, **kwargs):
        if loaders is None:
            loaders = ['django.template.loaders.filesystem.Loader']
            if app_dirs:
                loaders += ['django.template.loaders.app_directories.Loader']
            if not debug:
                # TODO fix once the path is determined
                loaders = [('easyticket_invoice.django_weasy.CachedLoader', loaders)]
                #loaders = [('django.template.loaders.cached.Loader', loaders)]
        else:
            if app_dirs:
                raise de.ImproperlyConfigured("app_dirs must not be set when loaders is defined.")
        super().__init__(loaders=loaders, app_dirs=app_dirs, debug=debug, **kwargs)
