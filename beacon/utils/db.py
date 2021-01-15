# -*- coding: utf-8 -*-

"""Database Connection."""

import logging
from contextlib import asynccontextmanager
from functools import wraps
import traceback
from itertools import chain
# import inspect

import asyncpg

from .. import conf
from .exceptions import BeaconServerError
from .json import jsonb, json_encoder, json_decoder

LOG = logging.getLogger(__name__)

class DBConnection():
    """Databse connection setup."""

    db_pool = None

    async def connect(self, force=False):
        """Get the database connection (which encapsulates a database session).

        Upon success, the connection is cached.
        """
        if force:
            await self.close()

        if self.db_pool:
            return

        LOG.info("Creating a connection pool to %s:%s", conf.database_url, conf.database_port)
        # Connection pool handles reconnections and keeps some expensive connections open for reuse
        self.db_pool = await asyncpg.create_pool(host=conf.database_url,
                                                 port=conf.database_port,
                                                 user=conf.database_user,
                                                 password=conf.database_password,
                                                 database=conf.database_name,
                                                 server_settings={'search_path': conf.database_schema,
                                                                  'application_name': conf.database_app_name},
                                                 min_size=0, # initializing with 0 connections allows the web server to
                                                 # start and also continue to live
                                                 max_queries=getattr(conf, 'database_max_queries', 50000),
                                                 max_size=10, # for now limiting the number of connections in the pool
                                                 timeout=getattr(conf, 'database_timeout', 120),
                                                 command_timeout=getattr(conf, 'database_command_timeout', 180),
                                                 max_cached_statement_lifetime=0,
                                                 max_inactive_connection_lifetime=180)
        # Ping the db
        async with self.db_pool.acquire() as conn:
            try:
                conn.execute('SELECT 1;')
                LOG.debug('Ping successful')
            except (asyncpg.exceptions._base.InterfaceError,
                    asyncpg.exceptions._base.PostgresError) as e:
                LOG.error('DB Error: %s', e)
                raise ValueError(f'DB Error: {e}') # not using a beacon error. We can ping _before_ the server starts.

    def asyncgen_execute(self, func):
        async def inner(*args, **kwargs):
            async with self.connection() as connection:
                async for obj in func(connection, *args, **kwargs):
                    yield obj
        return inner

    def coroutine_execute(self, func):
        async def inner(*args, **kwargs):
            async with self.connection() as connection:
                return await func(connection, *args, **kwargs)
        return inner

    @asynccontextmanager
    async def connection(self):
        if self.db_pool is None:
            await self.connect()
        LOG.debug('----------- acquiring connection')
        conn = await self.db_pool.acquire()
        try:
            await conn.set_type_codec('jsonb', encoder=json_encoder, decoder=json_decoder, schema='pg_catalog')
            yield conn
        except (asyncpg.exceptions._base.InterfaceError,
                asyncpg.exceptions._base.PostgresError,
                asyncpg.exceptions.UndefinedFunctionError) as e:
            LOG.error('DB Error: %s', e)
            # traceback.print_exc()
            raise BeaconServerError(f'DB Error: {e}')
        finally:
            LOG.debug('----------- releasing connection')
            await self.db_pool.release(conn)

    async def close(self):
        """Close DB Connection."""
        LOG.debug("Closing the database")
        if self.db_pool:
            self.db_pool.terminate()
        self.db_pool = None


######################################
#           Business logic           #
######################################

# Instantiate the global connection
pool = DBConnection()

async def close():
    await pool.close()

# Get the latest modification data of a DB dataset 
@pool.coroutine_execute
async def get_last_modified_date(connection):
    LOG.info('Retrieving last modified date')

    query = f"""SELECT MAX(updated_at) FROM {conf.database_schema}.dataset;"""
    LOG.debug("QUERY: %s", query)
    return await connection.fetchval(query)

@pool.coroutine_execute
async def _fetch_assemblyids(connection):
    """
    Return Assembly IDs from the dataset.
    """
    LOG.info('Retrieving assembly IDs (once)')
    query = f"""SELECT DISTINCT reference_genome FROM {conf.database_schema}.dataset;"""
    LOG.debug("QUERY: %s", query)
    response = await connection.fetch(query)
    return [r['reference_genome'] for r in response]

async def fetch_assemblyids():
    """
    Return Assembly IDs from the dataset.
    We cache the result in the conf module.
    """
    assemblyIDs = getattr(conf, 'assemblyIDs', None)
    if assemblyIDs is None:
        assemblyIDs = await _fetch_assemblyids()
        setattr(conf, 'assemblyIDs', assemblyIDs)
    else:
        LOG.debug('Using cached assemblyIDs: %s', assemblyIDs)
    return assemblyIDs

# @pool.coroutine_execute
# async def _fetch_dataset_partitions(connection):
#     """
#     Return Assembly IDs from the dataset.
#     """
#     LOG.info('Retrieving assembly IDs (once)')
#     query = f"""SELECT access_type,
#                        array_agg(stable_id) AS datasets
#                 FROM {conf.database_schema}.dataset
#                 GROUP BY access_type;"""
#     LOG.debug("QUERY: %s", query)
#     response = await connection.fetch(query)
#     partitions = {}
#     datasets = set()
#     for r in response:
#         d = set(r['datasets']) # list/array -> set
#         partitions[r['access_type']] = d
#         datasets.update(d)
#     return (partitions, datasets)

# async def fetch_dataset_partitions():
#     """
#     Return the Datasets.
#     We cache the result in the conf module.
#     """
#     datasets = getattr(conf, 'datasets', None)
#     if datasets is None:
#         datasets = await _fetch_datasets()
#         setattr(conf, 'datasets', datasets)
#     else:
#         LOG.debug('Using cached datasets: %s', datasets)
#     return datasets


# We might be able to use postgres partitioning
# https://www.postgresql.org/docs/12/ddl-partitioning.html
# We can use the 3 access types: PUBLIC, REGISTERED and CONTROLLED
#
# Returns a generator of record, make sure to consume them before the connection is closed
@pool.asyncgen_execute
async def fetch_datasets_access(connection, datasets=None):
    """
    Retrieve available datasets as triples (access_type::str, id::int, datasetId::str)

    In this case, any error executing the database request is captured and an empty list is returned.
    """
    LOG.info('Retrieving info about the available datasets (id and access type).')
    LOG.debug('Originally selecting datasets: %s', datasets)
    #async with connection.transaction():
    where_clause = ' WHERE stable_id = ANY($1)' if datasets else ''
    query = f"""SELECT access_type, id, stable_id FROM {conf.database_schema}.dataset{where_clause};"""
    LOG.debug("QUERY datasets access: %s", query)
    try:
        statement = await connection.prepare(query)
        coro = statement.fetch(datasets) if datasets else statement.fetch()
        response = await coro
        for record in response:
            yield (record['access_type'], record['id'], record['stable_id']) # not using record: copy
    except Exception as e:
        LOG.error("DB error while retrieving datasets: %s", e)

@pool.asyncgen_execute
async def filter_out_non_public_datasets(connection, datasets):
    """
    Retrieve available datasets as triples (access_type::str, id::int, datasetId::str)

    In this case, any error executing the database request is captured and an empty list is returned.
    """
    LOG.info('Retrieving info about the available datasets (id and access type).')
    LOG.debug('Originally selecting datasets: %s', datasets)

    if not datasets:
        return

    query = f"""SELECT stable_id 
                FROM {conf.database_schema}.dataset 
                WHERE stable_id = ANY($1)
                   AND access_type = 'PUBLIC';"""
    LOG.debug("QUERY datasets access: %s", query)
    statement = await connection.prepare(query)
    response = await statement.fetch(datasets)
    for record in response:
        yield record['stable_id']


# Returns a generator of record, make sure to consume them before the connection is closed
@pool.asyncgen_execute
async def fetch_datasets_metadata(connection, transform=None):
    """
    Execute query for returning dataset metadata.
    """
    LOG.info('Retrieving datasets metadata')
    query = f"""SELECT stable_id                AS "datasetId",
                        name                    AS "name",
                        description              AS "description",
                        access_type              AS "accessType",
                        reference_genome         AS "assemblyId",
                        COALESCE(variant_cnt, 0) AS "variantCount",
                        COALESCE(call_cnt   , 0) AS "callCount",
                        COALESCE(sample_cnt , 0) AS "sampleCount",
                        dataset_source          AS "datasetSource",
                        dataset_type            AS "datasetType",
                        created_at               AS "createdAt",
                        updated_at               AS "updatedAt"
                FROM {conf.database_schema}.dataset;"""
    LOG.debug("QUERY: %s", query)
    response = await connection.fetch(query)
    # for record in response:
    #     yield transform(record) if callable(transform) else record
    for record in response:
        yield record


# Returns a generator of record, make sure to consume them before the connection is closed
@pool.asyncgen_execute
async def fetch_filtering_terms(connection):
    """
    Execute query for returning the filtering terms.
    """
    # async with connection.transaction():
    query = "SELECT DISTINCT ontology, term, label FROM ontology_term ORDER BY ontology, term;"
    response = await connection.fetch(query)
    for record in response:
        yield record


# Returns a generator of record, make sure to consume them before the connection is closed
@pool.asyncgen_execute
async def access_levels_datasets(connection):
    """ Fetch the special datasets (with different access levels).
    They are stored in the dataset_access_level_table in the DB.
    Return two dicts prepared to be shown in the response (one for displayDatasetDifferences=false, the other for true).
    """
    LOG.debug('fetch special datasets access levels info')
    query = """SELECT dt.stable_id    AS dataset_id,
                      al.parent_field AS parent_field,
                      al.field        AS field,
                      al.access_level AS access_level
               FROM dataset_access_level_table al
               JOIN dataset dt
               ON al.dataset_id=dt.id;"""
    LOG.debug("QUERY: %s", query)
    response = await connection.fetch(query)
    for record in response:
        yield record


# Returns a generator of record, make sure to consume them before the connection is closed
@pool.asyncgen_execute
async def _fetch_variants(connection,
                          qparams_db,
                          datasets,
                          authenticated,
                          variant_id=None,
                          biosample_stable_id=None,
                          individual_stable_id=None):
    LOG.info('Retrieving viral variant information')

    # We want just the names, not the formatting functions
    requested_schemas = [qparams_db.requestedSchema[0], qparams_db.requestedAnnotationSchema[0]]

    dollars = ", ".join([ f"${i}" for i in range(1, 22)]) # 1..21
    LOG.debug("dollars: %s", dollars)
    query = f"SELECT * FROM {conf.database_schema}.query_gvariants({dollars});"
    LOG.debug("QUERY: %s", query)
    statement = await connection.prepare(query)
    response = await statement.fetch(qparams_db.variantType,  # _variant_type text,
                                     qparams_db.start[0] if len(qparams_db.start) == 1 else None,  # _start integer,
                                     qparams_db.start[0] if len(qparams_db.start) > 1 else None,  # _start_min integer,
                                     qparams_db.start[1] if len(qparams_db.start) > 1 else None,  # _start_max integer,
                                     qparams_db.end[0] if len(qparams_db.end) == 1 else None,  # _end integer,
                                     qparams_db.end[0] if len(qparams_db.end) > 1 else None,  # _end_min integer,
                                     qparams_db.end[1] if len(qparams_db.end) > 1 else None,  # _end_max integer,
                                     qparams_db.referenceName, # qparams_db.referenceName,  # _chromosome character varying,
                                     qparams_db.referenceBases,  # _reference_bases text,
                                     qparams_db.alternateBases,  # _alternate_bases text,
                                     qparams_db.assemblyId.lower() if qparams_db.assemblyId else None, #qparams_db.assemblyId,  # _reference_genome text,
                                     qparams_db.includeDatasetResponses, # _include_dataset_responses
                                     datasets, #qparams_db.datasets[0],  # _dataset_ids text[],
                                     authenticated, #qparams_db.datasets[1],  # _is_authenticated bool,
                                     biosample_stable_id,  # _biosample_stable_id text,
                                     individual_stable_id,  # _individual_stable_id text,
                                     int(variant_id) if variant_id else None,  # _gvariant_id
                                     qparams_db.filters,   # filters as-is,  # _filters text[],
                                     qparams_db.skip * qparams_db.limit,  # _skip
                                     qparams_db.limit, # _limit integer
                                     requested_schemas)  # requestedSchemas
    for record in response:
        yield record

def fetch_variants_by_variant(qparams_db, datasets, authenticated):
    return _fetch_variants(qparams_db, datasets, authenticated, variant_id=qparams_db.targetIdReq)

def fetch_variants_by_biosample(qparams_db, datasets, authenticated):
    return _fetch_variants(qparams_db, datasets, authenticated, biosample_stable_id=qparams_db.targetIdReq)

def fetch_variants_by_individual(qparams_db, datasets, authenticated):
    return _fetch_variants(qparams_db, datasets, authenticated, individual_stable_id=qparams_db.targetIdReq)

# Returns a generator of record, make sure to consume them before the connection is closed
@pool.asyncgen_execute
async def _fetch_individuals(connection,
                             qparams_db,
                             datasets,
                             authenticated,
                             variant_id=None,
                             biosample_stable_id=None,
                             individual_stable_id=None):
    """
    Contacts the DB to fetch the info.
    Returns a pd.DataFrame with the response.
    """
    # connection.add_log_listener(simple_listener)
    dollars = ", ".join([f"${i}" for i in range(1, 21)])  # 1..20
    query = f"SELECT * FROM {conf.database_schema}.query_individuals({dollars});"
    LOG.debug("QUERY: %s", query)
    statement = await connection.prepare(query)
    response = await statement.fetch(qparams_db.variantType,  # _variant_type text,
                                     qparams_db.start[0] if len(qparams_db.start) == 1 else None,  # _start integer,
                                     qparams_db.start[0] if len(qparams_db.start) > 1 else None,  # _start_min integer,
                                     qparams_db.start[1] if len(qparams_db.start) > 1 else None,  # _start_max integer,
                                     qparams_db.end[0] if len(qparams_db.end) == 1 else None,  # _end integer,
                                     qparams_db.end[0] if len(qparams_db.end) > 1 else None,  # _end_min integer,
                                     qparams_db.end[1] if len(qparams_db.end) > 1 else None,  # _end_max integer,
                                     qparams_db.referenceName, # reference_name
                                     qparams_db.referenceBases,
                                     qparams_db.alternateBases,
                                     qparams_db.assemblyId.lower() if qparams_db.assemblyId else None, # assembly_id
                                     datasets, # dataset_stable_ids
                                     authenticated, #is_authenticated
                                     biosample_stable_id,
                                     individual_stable_id, # individual_stable_id
                                     int(variant_id) if variant_id else None,
                                     qparams_db.filters, # filters
                                     qparams_db.skip * qparams_db.limit,  # _skip
                                     qparams_db.limit,  # _limit integer
                                     # we keep a list for the moment
                                     [qparams_db.requestedSchema[0]])  # requestedSchemas
    

    for record in response:
        yield record


def fetch_individuals_by_variant(qparams_db, datasets, authenticated):
    return _fetch_individuals(qparams_db, datasets, authenticated, variant_id=qparams_db.targetIdReq)

def fetch_individuals_by_biosample(qparams_db, datasets, authenticated):
    return _fetch_individuals(qparams_db, datasets, authenticated, biosample_stable_id=qparams_db.targetIdReq)

def fetch_individuals_by_individual(qparams_db, datasets, authenticated):
    return _fetch_individuals(qparams_db, datasets, authenticated, individual_stable_id=qparams_db.targetIdReq)


# Returns a generator of record, make sure to consume them before the connection is closed
@pool.asyncgen_execute
async def _fetch_biosamples(connection,
                            qparams_db,
                            datasets,
                            authenticated,
                            variant_id=None,
                            biosample_stable_id=None,
                            individual_stable_id=None):
    LOG.info('Retrieving viral biosample information')

    dollars = ", ".join([ f"${i}" for i in range(1, 21)]) # 1..20
    # LOG.debug("dollars: %s", dollars)
    query = f"SELECT * FROM {conf.database_schema}.query_samples({dollars});"
    LOG.debug("QUERY: %s", query)
    statement = await connection.prepare(query)
    response = await statement.fetch(qparams_db.variantType,  # _variant_type text,
                                     qparams_db.start[0] if len(qparams_db.start) == 1 else None,  # _start integer,
                                     qparams_db.start[0] if len(qparams_db.start) > 1 else None,  # _start_min integer,
                                     qparams_db.start[1] if len(qparams_db.start) > 1 else None,  # _start_max integer,
                                     qparams_db.end[0] if len(qparams_db.end) == 1 else None,  # _end integer,
                                     qparams_db.end[0] if len(qparams_db.end) > 1 else None,  # _end_min integer,
                                     qparams_db.end[1] if len(qparams_db.end) > 1 else None,  # _end_max integer,
                                     qparams_db.referenceName,  # reference_name
                                     qparams_db.referenceBases,
                                     qparams_db.alternateBases,
                                     qparams_db.assemblyId.lower() if qparams_db.assemblyId else None, # assembly_id
                                     datasets, # dataset_stable_ids
                                     authenticated, #is_authenticated
                                     biosample_stable_id,
                                     individual_stable_id, # individual_stable_id
                                     int(variant_id) if variant_id else None,
                                     qparams_db.filters, # filters
                                     qparams_db.skip * qparams_db.limit,  # _skip
                                     qparams_db.limit, # limit
                                     # we keep a list for the moment
                                     [qparams_db.requestedSchema[0]])  # requestedSchemas

    for record in response:
        yield record

def fetch_biosamples_by_variant(qparams_db, datasets, authenticated):
    return _fetch_biosamples(qparams_db, datasets, authenticated, variant_id=qparams_db.targetIdReq)

def fetch_biosamples_by_biosample(qparams_db, datasets, authenticated):
    return _fetch_biosamples(qparams_db, datasets, authenticated, biosample_stable_id=qparams_db.targetIdReq)

def fetch_biosamples_by_individual(qparams_db, datasets, authenticated):
    return _fetch_biosamples(qparams_db, datasets, authenticated, individual_stable_id=qparams_db.targetIdReq)

# function for ontologies filter autocomplete feature
@pool.asyncgen_execute
async def fetch_ontologies(connection, term, limit):
    LOG.info('Retrieving ontologies information')

    query = f"""SELECT t.ontology, t.term, t.label as meaning
                FROM {conf.database_schema}.ontology_term t
                WHERE t.ontology ILIKE  '%' || $1 || '%'
                OR t.term ILIKE  '%' || $1 || '%'
                OR t.label ILIKE  '%' || $1 || '%'
                OR CONCAT_WS(':', t.ontology, t.term) ILIKE  '%' || $1 || '%' 
                ORDER BY t.ontology, t.term ASC
                LIMIT $2;"""
    LOG.debug("QUERY: %s", query)
    statement = await connection.prepare(query)
    response = await statement.fetch(str(term), limit)
    for record in response:
        yield record
