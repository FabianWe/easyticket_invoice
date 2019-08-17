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
    """An InvoiceRenderer that combines the WeasyRenderer with Django templates.

    A Django template is loaded, filled with context data and executed. The resulting HTML is then passed to WeasyPrint.

    To use this renderer you need templates to use and a Django template engine that finds and loads the template files.
    This package comes with an engine to use for that purpose.

    Example:
        >>> e = Engine(dirs=['PATH_TO_ROOT'])

    This will be aible to load templates from the given path.
    If your path has a file in "foo/bar.html" you could use that as a template_name for this renderer.
    The context for that template will contain the the values from InvoiceRenderer.get_context_dict.
    There are also a few template examples in this package.
    You can pass additional context data when initializing this class by providing the dict context_dict, these values
    will be merged into the existing context.
    Of course you can also write a subclass and overwrite the get_context method which must return a
    django.template.Context.
    The template name must be given when creating the renderer.

    Args:
        template_name (str): The name of the template to render, as in Django's methods it's also allowed to be a
            list or tuple of names, see https://docs.djangoproject.com/en/2.2/topics/http/shortcuts/#render
        engines (list of django.template.Engine): See https://docs.djangoproject.com/en/2.2/ref/templates/api/#django.template.Engine
            no engine is created, you have to initialize an engine on your own.
        context_dict (dict): Dictionary containing additional context values to use in the template.
        **kwargs: Additional parameters directly passed to django.template.engine.Engine, see
            https://docs.djangoproject.com/en/2.2/ref/templates/api/#django.template.Engine
    """
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
        """Creates the context used in the execution of the template.

        Args:
            invoice (Invoice): The invoice to create the context for.
            **kwargs: Additional arguments passed directly to the Context constructor.

        Returns:
            django.template.Context: The renderer context from get_context_dict combined with the additional
                context_dict.
        """
        ctx = self.get_context_dict(invoice)
        ctx = ctx.update(self.context_dict)
        return Context(ctx, **kwargs)

    def get_template(self, template_name):
        """Return a template given the template name.

        The first engine that returns a valid template with get_template is returned.

        Args:
            template_name (str): Name of the context.

        Returns:
            Template: The template with the given name.

        Raises:
            TemplateDoesNotExist: If no template with that name was found in any of the engines.
        """
        chain = []
        for engine in self.engines:
            try:
                return engine.get_template(template_name)
            except TemplateDoesNotExist as e:
                chain.append(e)
        raise TemplateDoesNotExist(template_name, chain=chain)

    def select_template(self, template_name_list):
        """Similar to get_template, but returns the first template from template_name_list that is found.

        Args:
            template_name_list (list of str): A list of template names.

        Returns:
            Template: The first template from template_name_list for which an engine returns a valid template.

        Raises:
            TemplateDoesNotExist: If no template in template_name_list is found in any of the engines.
        """
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
    """A loader for Django templates based on the cached loader from Django.

    It only provides one additional method del_cache to delete an entry from the cache.

    NOTE: Due to Django's middleware I'm not sure if this will delete the template correctly.
    It may take some time until the template is actually gone.
    """
    def __init__(self, engine, loaders):
        super().__init__(engine, loaders)

    def del_cache(self, template_name, skip=None):
        key = self.cache_key(template_name, skip)
        self.get_template_cache.pop(key, None)


class Engine(de.Engine):
    """An implementation of a Django template engine that uses a different loader.

    The default implementation uses a cached loader. We may have to delete entries from the cache if a file gets
    updated.
    Therefor the loaders are wrapped with our CachedLoader implementation.
    The arguments are exactly the arguments from the Django engine, see
    https://docs.djangoproject.com/en/2.2/ref/templates/api/#django.template.Engine.
    """
    def __init__(self, loaders=None, app_dirs=None, debug=False, **kwargs):
        if loaders is None:
            loaders = ['django.template.loaders.filesystem.Loader']
            if app_dirs:
                loaders += ['django.template.loaders.app_directories.Loader']
            if not debug:
                # TODO fix once the path is determined
                loaders = [('easyticket_invoice.django_weasy.CachedLoader', loaders)]
        else:
            if app_dirs:
                raise de.ImproperlyConfigured("app_dirs must not be set when loaders is defined.")
        super().__init__(loaders=loaders, app_dirs=app_dirs, debug=debug, **kwargs)
