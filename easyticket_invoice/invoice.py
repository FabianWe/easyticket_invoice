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

"""Provides a class that represents an invoice and abstract classes for generating pdf invoices (implementations
of these can be found in other packages).
"""


from decimal import Decimal


class Article(object):
    """
    An article in a an invoice.

    Attributes:
        article_id: Id of the article, usually int or str.
        name (str): Name of the article.
        price (int): Price of the article in cents.
        description (str): Optional description of an article.
        tax (int or decimal.Decimal or None): If not None represents the tax applied for the article, for example for
            19% tax you can use the int 19 or the decimal (not float!) Decimal(0.19).
    """
    def __init__(self, article_id, name, price, description='', tax=None):
        self.article_id = article_id
        self.name = name
        self.description = description
        self.price = price
        self.tax = tax


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
