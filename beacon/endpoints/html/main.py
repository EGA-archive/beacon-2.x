import logging
import re
import collections

from aiohttp_jinja2 import template
from aiohttp_session import get_session
from aiohttp_csrf import generate_token

from ... import conf
from ...utils import db, resolve_token, middlewares
from ...utils.exceptions import BeaconBadRequest

from ...validation.request import RequestParameters, print_qparams
from ...validation.fields import RegexField, Field, MultipleField, ListField, IntegerField, FloatField, RangeField, DateField


LOG = logging.getLogger(__name__)


def _fetch_results(resultOption, targetInstance, qparams_db, datasets, authenticated):
    """"
    Decide which function is the appropriate depending on the targetInstance 
    and the resultOption selected by the user.
    """
    func_parameters = [qparams_db, datasets, authenticated]
    if resultOption == "variant":
        if targetInstance == "variant":
            return db.fetch_variants_by_variant(*func_parameters)
        elif targetInstance == "sample":
            return db.fetch_variants_by_biosample(*func_parameters)
        elif targetInstance == "individual":
            return db.fetch_variants_by_individual(*func_parameters)
    elif resultOption == "individual":
        if targetInstance == "variant":
            return db.fetch_individuals_by_variant(*func_parameters)
        elif targetInstance == "sample":
            return db.fetch_individuals_by_biosample(*func_parameters)
        elif targetInstance == "individual":
            return db.fetch_individuals_by_individual(*func_parameters)
    elif resultOption == "sample":
        if targetInstance == "variant":
            return db.fetch_biosamples_by_variant(*func_parameters)
        elif targetInstance == "sample":
            return db.fetch_biosamples_by_biosample(*func_parameters)
        elif targetInstance == "individual":
            return db.fetch_biosamples_by_individual(*func_parameters)


class Parameters(RequestParameters):

    # Variant filters
    variantQuery = RegexField(r'^(X|Y|MT|[1-9]|1[0-9]|2[0-2])\s*\:\s*(\d+)\s+([ATCGN]+)\s*\>\s*(DEL:ME|INS:ME|DUP:TANDEM|DUP|DEL|INS|INV|CNV|SNP|MNP|[ATCGN]+)$',
                       required=False,
                       ignore_case=True)
    # variantType = Field(required=False)
    # referenceName = Field(required=False)
    # referenceBases = Field(required=False)
    # alternateBases = Field(required=False)
    assemblyId = Field(required=False)  # default="grch37.p1"

    datasets = ListField(items=Field(), trim=True, required=False)
    filters = ListField(items=Field(), trim=True, required=False)

    targetInstance = Field(required=False)
    targetId = Field(required=False)
    resultOption = Field(required=False)


@template('index.html')
async def handler_get(request):
    LOG.info('Running a viral GET request')

    session = await get_session(request)
    access_token = session.get('access_token')
    LOG.debug('Access Token: %s', access_token)
    datasets_all = set( [name async for _,_,name in db.fetch_datasets_access()] )
    allowed_datasets, authenticated = await resolve_token(access_token, datasets_all)
    LOG.debug('Allowed Datasets: %s', allowed_datasets)

    # Fetch datasets info
    records = [r async for r in db.fetch_datasets_metadata()]
    types = [str(type(x)) for x in records[1].values()]

    return {
            'records': records,
            'variantQuery': '',
            'datasets': '',
            'filters': '',
            'targetInstance': 'individual',
            'targetId': '',
            'resultOption': 'individual',
            'homepage': True,
            'session': session,
            'request': request,
    }


proxy = Parameters()

@template('index.html')
async def handler_post(request):
    LOG.info('Running a viral POST request')

    session = await get_session(request)
    access_token = session.get('access_token')
    LOG.debug('Access Token: %s', access_token)
    datasets_all = set( [name async for _,_,name in db.fetch_datasets_access()] )
    allowed_datasets, authenticated = await resolve_token(access_token, datasets_all)
    LOG.debug('Allowed Datasets: %s', allowed_datasets)

    # parameters
    qparams_raw = {}
    try:
        qparams_raw, qparams_db = await proxy.fetch(request)
        LOG.debug("Original Query Parameters: %s", qparams_raw)

        # print only for debug
        if LOG.isEnabledFor(logging.DEBUG):
            print_qparams(qparams_db, proxy, LOG)

    except BeaconBadRequest as bad:
        LOG.error('Bad request %s', bad)
        return {
            'variantQuery': '',
            'datasets': '',
            'filters': '',
            'targetInstance': 'individual',
            'targetId': '',
            'resultOption': 'individual',
            'errors': str(bad),
            'records': [],
            'homepage': False,
            'session': session,
            'request': request,
        }

    # parsing the variantQuery
    chromosome = None
    position = None
    reference = None
    alternate = None

    if qparams_raw.get('variantQuery'):
        field = proxy.__fields__.get('variantQuery') # must exist
        flags = re.I if field.ignore_case else 0
        m = re.match(field.pattern, qparams_db.variantQuery, flags=flags)
        assert(m)
        chromosome = m.group(1)
        position = int(m.group(2))
        reference = m.group(3).upper()
        alternate = m.group(4).upper()
        LOG.debug("""
        Chromosome: %s
        Position: %s
        Reference: %s
        Alternate: %s""", 
        chromosome, position, reference, alternate)

    # prepare qparams
    parameters = {
        "variantType": None,  # HARDCODED
        "start": tuple([position]) if position else tuple(),  # two items tuple
        "end": tuple(),  # two items tuple
        "referenceName": chromosome,
        "referenceBases": reference,
        "alternateBases": alternate,
        "assemblyId": qparams_db.assemblyId,
        "filters": qparams_db.filters,
        "skip": 0,
        "limit": 10,
        "requestedSchema": [None], # list
        "requestedAnnotationSchema": [None], # list
        "targetIdReq": qparams_db.targetId,
        "includeDatasetResponses": None
    }
    LOG.debug("Parameters:")
    LOG.debug(parameters)
    qparams = collections.namedtuple('qparams_custom', parameters.keys())(*parameters.values())

    # Comparing requested datasets to allowed datasets
    final_datasets = allowed_datasets
    LOG.debug('Requested Datasets: %s', qparams_db.datasets)
    if qparams_db.datasets:
        final_datasets = [dataset for dataset in qparams_db.datasets if dataset in allowed_datasets]
    LOG.debug('Final Datasets: %s', final_datasets)
    if not final_datasets:
        LOG.debug("User not allowed")
        return {
            'records': [],
            'variantQuery': qparams_raw.get('variantQuery',''),
            'datasets': qparams_raw.get('datasets',''),
            'filters': qparams_raw.get('filters',''),
            'targetInstance': qparams_raw.get('targetInstance','individual'),
            'targetId': qparams_raw.get('targetId',''),
            'resultOption': qparams_raw.get('resultOption','individual'),
            'homepage': False,
            'session': session,
            'request': request,
        }

    # DB call
    response = _fetch_results(qparams_db.resultOption, qparams_db.targetInstance, qparams, final_datasets, None)
    LOG.debug("Response:")
    LOG.debug(response)

    if not response:
        LOG.debug("No Response")
        return {
            'records': [],
            'variantQuery': qparams_raw.get('variantQuery',''),
            'datasets': qparams_raw.get('datasets',''),
            'filters': qparams_raw.get('filters',''),
            'targetInstance': qparams_raw.get('targetInstance','individual'),
            'targetId': qparams_raw.get('targetId',''),
            'resultOption': qparams_raw.get('resultOption','individual'),
            'homepage': False,
            'session': session,
            'request': request,
        }

    records = [row async for row in response]

    return {
        'records': records,
        'variantQuery': qparams_raw.get('variantQuery',''),
        'datasets': qparams_raw.get('datasets',''),
        'filters': qparams_raw.get('filters',''),
        'targetInstance': qparams_raw.get('targetInstance',''),
        'targetId': qparams_raw.get('targetId',''),
        'resultOption': qparams_raw.get('resultOption',''),
        'homepage': False,
        'session': session,
        'request': request,
    }