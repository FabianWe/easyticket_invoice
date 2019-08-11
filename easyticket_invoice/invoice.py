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

"""Provides a class that represents an invoice and abstract classes for generating pdf invoices.
Also includes an implementation based on WeasyPrint and Django templates.
"""


from decimal import Decimal
from collections import defaultdict
from abc import ABC, abstractmethod


class Article(object):
    """
    An article in a an invoice.

    An article has a unique id (usually int or str), a name and a description.
    It also has a price that consists of three components (that must be given when the article is initialized):
    net, tax and gross (where gross should be net + tax).
    Just to be sure everything is okay this values must all be given and are not computed automatically.
    But there are some helper functions to compute those values: compute_gross and compute_taxes.

    An article also has a tax category that is used in an invoice to group together articles with the same tax rate.
    This is just a string identifier, for example for a tax of 19% the identifier could be just '19%'.

    Attributes:
        article_id: Id of the article, usually int or str.
        name (str): Name of the article.
        tax_category (str): Identifier for a tax category.
        net (Decimal): The net value of this article.
        tax (Decimal): The taxes included in this article.
        gross (Decimal): The gross value of this article.
        description (str): Optional description of an article.
    """
    def __init__(self, article_id, name, tax_category, net, tax, gross, description=''):
        self.article_id = article_id
        self.name = name
        self.tax_category = tax_category
        self.net = net
        self.tax = tax
        self.gross = gross
        self.description = description


def compute_gross(net, tax_rate, quantize=Decimal('0.01')):
    """Compute the gross value given the net value and the tax rate.

    If quantize is given the result will be rounded to a given exponent, for example quantize=Decimal('0.01') means
    round to two digits.
    The idea is to round at the latest moment, meaning to keep everything as accurate as possible as long as possible.
    This might have a small influence, depending on how much rounding is required (usually just one or two cents, but
    we want to be correct).
    The taxes will be computed as accurate as possible, after that with a given quantize value everything is rounded
    to the given exponent. So with quantize=Decimal('0.01') net, taxes and gross are quantized s.t. the returned gross
    value is exactly the sum of net and taxes. Thus, due to some rounding, the exact net value might change.
    This is why this method returns everything: net, taxes and gross (in this order) as Decimal values.

    Args:
        net (Decimal): The net value.
        tax_rate (Decimal): The tax rate, for example for 19% you could use Decimal('0.190').
        quantize (Decimal): Round to the given exponent (see Decimal.quantize).

    Returns:
        (Decimal, Decimal, Decimal): The (possibly quantized) net, taxes and gross values.
    """
    taxes = net * tax_rate
    if quantize is not None:
        net = net.quantize(quantize)
        taxes = taxes.quantize(quantize)
    gross = net + taxes
    return net, taxes, gross


def compute_taxes(gross, tax_rate, quantize=Decimal('0.01')):
    """Compute the taxes included in a gross value.

    This method computes the net value given the gross value and the tax. If quantize is given the result will be
    rounded to a given exponent, for example quantize=Decimal('0.01') means round to two digits.
    Because some rounding (if quantize is given) may change the actual gross value, the new gross value is returned
    as well.
    The net value is computed as exact as possible, then rounded given the quantized exponent. This might change the
    gross value due to some rounding.

    Args:
        gross (Decimal): The desired gross value, for example Decimal('50.00') for 50€ / $50.
        tax_rate (Decimal): The tax included in the gross value, for example Decimal('0.19') for 19%.
        quantize (Decimal): Round to the given exponent (see Decimal.quantize).

    Returns:
        (Decimal, Decimal, Decimal): The (possibly quantized) net, taxes and gross values.
    """
    if tax_rate is None:
        taxes = Decimal('0')
        if quantize is not None:
            gross = gross.quantize(quantize)
            taxes = taxes.quantize(quantize)
        return gross, taxes, gross
    net = gross / (Decimal('1') + tax_rate)
    return compute_gross(net, tax_rate, quantize)


class Address(object):
    """Represents an address of a person (issuer or recipient of an invoice).

    Attributes:
        first_name (str): First name.
        last_name (str): Last name.
        street (str): Street name without street number.
        street_number (str): Street number as a string (for example '7A').
        postcode (str): Postcode as a string.
        location (str): City / location.
        additional (str): Additional address line.
        phone (str): Phone number.
        mail (str): E-Mail address.
    """
    def __init__(self, first_name='', last_name='', street='', street_number='', postcode='', location='', additional='', phone='', mail=''):
        self.first_name = first_name
        self.last_name = last_name
        self.street = street
        self.street_number = street_number
        self.postcode = postcode
        self.location = location
        self.additional = additional
        self.phone = phone
        self.mail = mail


class Invoice(object):
    """Class representing an invoice.

    The invoice contains general information (such as issuer and recipient addresses) as well as information about
    articles and taxes.

    Taxes are grouped in to so called tax categories. For example if you have two different taxes on an invoice, one
    with a tax rate of 19% and one with 7% (German VAT) you could just add two categories, one with name '19%' and value
    Decimal(0.190) and one with name '7%' and value Decimal('0.070'). I've added a leading zero just to be more accurate
    when computing gross values and rounding them afterwards.
    Each article added to an invoice is associated with such a tax group. Before adding an article you should ensure
    that the tax category has been added before (see add_tax_category).

    The articles contained in this invoice are stored in a dictionary mapping the item identifier (usually int or str)
    to a list of articles.
    That is each article ID can occurr multiple times in the invoice, for example with a different description
    (seating information in the description etc.). Articles can be added with the add_article method.


    Attributes:
        issuer (Address): Address of the person that issued the invoice.
        recipient (Address): Address of the recipient of the invoice.
        date (datetime.date): Date the invoice was issued.
        service_date (datetime.date or None): Date of the service / sell / delivery.
        payment_information (list of str): List of information about how the debt has to be paid.
        tax_categories (dict of str to Decimal): Information about the tax categories, see above.
        articles (defaultdict of int / str to Article): Information about articles in this invoice, see above.
    """
    def __init__(self, issuer, recipient, date, payment_information, service_date=None, tax_categories=None):
        self.articles = defaultdict(list)
        if tax_categories is None:
            tax_categories = dict()
        self.tax_categories = tax_categories
        self.issuer = issuer
        self.recipient = recipient
        self.date = date
        self.service_date = service_date
        self.payment_information = payment_information

    def add_tax_category(self, name, tax_rate):
        """Add a new tax category to the invoice.

        Args:
            name (str): The identifier of the category.
            tax_rate (Decimal): The tax rate of this category.
        """
        self.tax_categories[name] = tax_rate

    def add_article(self, article):
        """Add an article to the articles dictionary.

        Args:
            article (Article): The article to add.

        Raises:
            KeyError: If the tax category of the article is not registered in the tax_categories dict.
        """
        if article.tax_category not in self.tax_categories:
            raise KeyError('Tax category "%s" is not registered in this invoice' % str(article.tax_category))
        self.articles[article.article_id].append(article)

    def get_context(self):
        ctx = {'articles': self.articles, 'tax_categories': self.tax_categories, 'issuer': self.issuer,
               'recipient': self.recipient, 'date': self.date, 'service_date': self.service_date,
               'payment_information': self.payment_information}
        return ctx


class PDFGenException(Exception):
    """Exception raised if an error occurred while generating a pdf.
    """
    pass


class InvoiceRenderer(ABC):
    """Abstract base class for everything that generateds a pdf for a given invoice.

    Attributes:
        show_single_articles (bool):
        show_net (bool):
        show_gross (bool):
        show_net_sum (bool):
        show_gross_sum (bool):
    """
    def __init__(self, show_single_articles=False, show_net=True, show_gross=True, show_net_sum=True, show_gross_sum=True):
        super().__init__()
        self.show_single_articles = show_single_articles
        self.show_net = show_net
        self.show_gross = show_gross
        self.show_net_sum = show_net_sum
        self.show_gross_sum = show_gross_sum

    @abstractmethod
    def render(self, invoice, filepath=None):
        pass
