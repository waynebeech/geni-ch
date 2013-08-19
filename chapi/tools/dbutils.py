#----------------------------------------------------------------------
# Copyright (c) 2011-2013 Raytheon BBN Technologies
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and/or hardware specification (the "Work") to
# deal in the Work without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Work, and to permit persons to whom the Work
# is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Work.
#
# THE WORK IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE WORK OR THE USE OR OTHER DEALINGS
# IN THE WORK.
#----------------------------------------------------------------------

from chapi.Exceptions import *
import types

# A set of utilities for dealing with SQL alchemy as the database backend
# Convert between external (in get_version) and internal (in database) field names
# Support query and filter clauses

# Convert external field name to internal field name based on given mapping
def convert_to_internal(external_field, mapping):
    if not mapping.has_key(external_field):
        raise CHAPIv1ArgumentError("No such field in schema : " + external_field)
    return mapping[external_field]


# Convert internal field name to external field name based on given mapping
def convert_to_external(internal_field, mapping):
    external_field = None
    for external_key in mapping.keys():
        internal_field_name = mapping[external_key]
        if internal_field_name == internal_field:
            external_field = external_key
            break
    if not external_field:
        raise CHAPIv1ArgumentError("No such field in schema : " + internal_field)
    return external_field


# Add filter clauses to a query based on given match criteria
# Return updated query
def add_filters(query, match_criteria, table, mapping):
    for external_match_field in match_criteria.keys():
        internal_match_field = convert_to_internal(external_match_field, mapping)
        match_value = match_criteria[external_match_field]
        column = table.c[internal_match_field]
        if isinstance(match_value, types.ListType):
            query = query.filter(column.in_(match_value))
        else:
            query = query.filter(column == match_value)
    return query

# Construct a result row {external_field : value, external_field : value} 
# from row which is a set of values indexed by internal fields
def construct_result_row(row, columns, mapping):
    result_row = {}
    for column in columns:
        internal_name = convert_to_internal(column, mapping)
#        print "IN = " + str(internal_name) + " " + str(type(internal_name))
        if isinstance(internal_name, types.FunctionType):
            column_value = internal_name(row)
        else:
            column_value = eval("row.%s" % internal_name)
        result_row[column] = column_value
    return result_row

# Grab the query selection columns ('filter') and match criterial ('match') from options
def unpack_query_options(options, mapping):
    selected_columns = mapping.keys() # Default = all columns if not specified
    if options.has_key('filter'): selected_columns = options['filter']

    match_criteria = []
    if options.has_key('match'): match_criteria = options['match']

    return selected_columns, match_criteria

