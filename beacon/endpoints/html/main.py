import logging
import re
import collections
import json

from aiohttp.web import json_response
from aiohttp_jinja2 import template
from aiohttp_session import get_session
from aiohttp_csrf import generate_token

from ... import conf
from ...utils import db, resolve_token, middlewares
from ...utils.exceptions import BeaconBadRequest, BeaconBadRequestUI

from ...validation.request import RequestParameters, print_qparams
from ...validation.fields import RegexField, Field, ChoiceField, MultipleField, ListField, IntegerField, FloatField, RangeField, DateField


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

    assemblyIdBasic = Field(required=False)  # default="grch37.p1"
    assemblyIdAdvanced = Field(required=False)  # default="grch37.p1"

    datasets = MultipleField(name="datasets")
    filters = ListField(items=Field(), trim=True, required=False)

    targetInstance = Field(required=False)
    targetId = Field(required=False)
    resultOption = Field(required=False)

    variantOption = Field(required=False)
    chromosome = Field(required=False)
    variantPosOption = Field(required=False)
    start = Field(required=False)
    end = Field(required=False)
    startMin = Field(required=False)
    startMax = Field(required=False)
    endMin = Field(required=False)
    endMax = Field(required=False)
    reference = Field(required=False)
    alternate = Field(required=False)

    def correlate(self, req, values):

        if values.variantPosOption == "variant-pos-exact":
            start = list(filter(None,[values.start]))
            end = list(filter(None,[values.end]))
        elif values.variantPosOption == "variant-pos-range":
            start = list(filter(None,[values.startMin, values.startMax]))
            end = list(filter(None,[values.endMin, values.endMax]))

        LOG.debug("""
        VALIDATION
        Chromosome: %s
        Start: %s
        End: %s
        Reference: %s
        Alternate: %s
        Filters: %s
        VariantQuery: %s
        AssemblyIdBasic: %s
        AssemblyIdAdvanced: %s
        """, 
        values.chromosome, start, end, values.reference, values.alternate, values.filters, values.variantQuery, values.assemblyIdBasic, values.assemblyIdAdvanced)

        if values.targetId is not None and (
                len(start) > 0
                or len(end) > 0
                or values.filters is not None
                or values.variantQuery is not None
                or values.reference is not None
                or values.alternate is not None
                or values.assemblyIdBasic is not None
                or values.assemblyIdAdvanced is not None
                or values.chromosome is not None):
            raise BeaconBadRequestUI("No other parameters are accepted when querying by Id")
        
        if values.variantOption == "advanced" and (
                len(start) > 0
                or len(end) > 0
                or values.reference is not None
                or values.alternate is not None
                or values.assemblyIdAdvanced is not None
                or values.chromosome is not None) and (
                len(start) == 0
                or len(end) == 0
                or values.reference is None
                or values.alternate is None
                or values.assemblyIdAdvanced is None
                or values.chromosome is None):
            raise BeaconBadRequestUI("All variant parameters are required")

        if values.variantOption == "basic" and (
                values.variantQuery is not None
                or values.assemblyIdBasic is not None) and (
                values.variantQuery is None
                or values.assemblyIdBasic is None):
            raise BeaconBadRequestUI("All variant parameters are required")

        if end is not None and len(end) == 1 and start is None:
            raise BeaconBadRequestUI("'start' is required if 'end' is provided")

        if values.reference is not None and (values.alternate is None or start is None):
            raise BeaconBadRequestUI("If 'reference' is provided then 'alternate' and ' start' are required")

        # if (values.reference is not None or values.alternate is not None) and len(end) > 0:
        #     raise BeaconBadRequestUI("'reference' cannot be combined with 'end'")

        if (start or values.chromosome or values.alternate or end ) \
                and (values.chromosome is None or values.assemblyIdAdvanced is None):
            raise BeaconBadRequestUI("'assemblyId' and 'chromosome' are mandatory")

        if values.variantQuery and values.assemblyIdBasic is None:
            raise BeaconBadRequestUI("'assemblyId' is mandatory")

        if len(start) == 2 and (end is None or len(end) == 1) \
                or len(end) == 2 and (start is None or len(start) == 1):
            raise BeaconBadRequestUI("All 'start[0]', 'start[1]', 'end[0]', 'end[1]' are required")

        if len(end) > 0 and end[0] < start[0]:
            raise BeaconBadRequestUI("'end[0]' must be greater than 'start[0]'")

        if len(start) > 1 and start[0] > start[1]:
            raise BeaconBadRequestUI("'start[0]' must be smaller than 'start[1]'")

        if len(end) > 1 and end[0] > end[1]:
            raise BeaconBadRequestUI("'end[0]' must be smaller than 'end[1]'")


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
            'allowedDatasets': allowed_datasets,
            'allDatasets': datasets_all,
            'variantPosOption': "variant-pos-exact",
            'variantOption': "basic"
    }

@template('index.html')
async def handler_datasets_get(request):
    LOG.info('Running a viral GET request')

    session = await get_session(request)
    access_token = session.get('access_token')
    LOG.debug('Access Token: %s', access_token)
    datasets_all = set( [name async for _,_,name in db.fetch_datasets_access()] )
    allowed_datasets, authenticated = await resolve_token(access_token, datasets_all)
    LOG.debug('Allowed Datasets: %s', allowed_datasets)

    # Fetch datasets info
    records = [r async for r in db.fetch_datasets_metadata()]

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
            'datasets_page': True,
            'allowedDatasets': allowed_datasets,
            'allDatasets': datasets_all,
            'variantPosOption': "variant-pos-exact",
            'variantOption': "basic"
    }

@template('index.html')
async def handler_filtering_terms_get(request):
    LOG.info('Running a viral GET request')

    session = await get_session(request)
    access_token = session.get('access_token')
    LOG.debug('Access Token: %s', access_token)
    datasets_all = set( [name async for _,_,name in db.fetch_datasets_access()] )
    allowed_datasets, authenticated = await resolve_token(access_token, datasets_all)
    LOG.debug('Allowed Datasets: %s', allowed_datasets)

    # Fetch filtering terms info
    records = [r async for r in db.fetch_filtering_terms()]

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
            'filtering_terms_page': True,
            'allowedDatasets': allowed_datasets,
            'allDatasets': datasets_all,
            'variantPosOption': "variant-pos-exact",
            'variantOption': "basic"
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

    except BeaconBadRequestUI as bad:
        LOG.error('Bad request %s', bad.text)

        return {
            'error': bad.text,
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
            'allowedDatasets': allowed_datasets,
            'allDatasets': datasets_all,
            'variantPosOption': "variant-pos-exact",
            'variantOption': "basic"
        }

    # parsing the variantQuery
    chromosome = None
    start = None
    end = None
    reference = None
    alternate = None
    assembly_id = None

    if qparams_raw.get("variantOption") == "advanced":
        assembly_id = qparams_db.assemblyIdAdvanced if qparams_db.assemblyIdAdvanced != "" else None

        if qparams_raw.get("variantPosOption") == "variant-pos-exact":
            startMin = int(qparams_raw.get("start")) if qparams_raw.get("start") else None
            endMin = int(qparams_raw.get("end")) if qparams_raw.get("end") else None
        else:
            startMin = int(qparams_raw.get("startMin")) if qparams_raw.get("startMin") else None
            endMin = int(qparams_raw.get("endMin")) if qparams_raw.get("endMin") else None

        startMax = int(qparams_raw.get("startMax")) if qparams_raw.get("startMax") else None
        endMax = int(qparams_raw.get("endMax")) if qparams_raw.get("endMax") else None

        chromosome = qparams_raw.get("chromosome") if qparams_raw.get("chromosome") != "" else None
        start = list(filter(None,[startMin, startMax]))
        end = list(filter(None,[endMin, endMax]))
        reference = qparams_raw.get("reference") if qparams_raw.get("reference") != "" else None
        alternate = qparams_raw.get("alternate") if qparams_raw.get("alternate") != "" else None
    else:
        assembly_id = qparams_db.assemblyIdBasic if qparams_db.assemblyIdBasic != "" else None

        if qparams_raw.get('variantQuery'):
            field = proxy.__fields__.get('variantQuery') # must exist
            flags = re.I if field.ignore_case else 0
            m = re.match(field.pattern, qparams_db.variantQuery, flags=flags)
            assert(m)
            chromosome = m.group(1)
            start = [int(m.group(2))]
            reference = m.group(3).upper()
            alternate = m.group(4).upper()
    LOG.debug("""
    Chromosome: %s
    Start: %s
    End: %s
    Reference: %s
    Alternate: %s""", 
    chromosome, start, end, reference, alternate)

    # prepare qparams
    parameters = {
        "variantType": None,  # HARDCODED
        "start": tuple(start) if start else tuple(),  # two items tuple
        "end": tuple(end) if end else tuple(),  # two items tuple
        "referenceName": chromosome,
        "referenceBases": reference,
        "alternateBases": alternate,
        "assemblyId": assembly_id,
        "filters": set([x.split(" ")[0] for x in qparams_db.filters if x != None]) if qparams_db.filters else None,
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
            'allowedDatasets': allowed_datasets,
            'allDatasets': datasets_all,
            'variantPosOption': qparams_raw.get('variantPosOption','variant-pos-exact'),
            'variantOption': qparams_raw.get('variantOption','basic'),
            'qparams': qparams
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
            'allowedDatasets': allowed_datasets,
            'allDatasets': datasets_all,
            'variantPosOption': qparams_raw.get('variantPosOption','variant-pos-exact'),
            'variantOption': qparams_raw.get('variantOption','basic'),
            'qparams': qparams
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
        'allowedDatasets': allowed_datasets,
        'allDatasets': datasets_all,
        'variantPosOption': qparams_raw.get('variantPosOption','variant-pos-exact'),
        'variantOption': qparams_raw.get('variantOption','basic'),
        'qparams': qparams
    }


##########################################
# AJAX suggestions / translations
##########################################

class Suggestions(RequestParameters):
    term = Field(required=True)
    limit = IntegerField(min_value=0) # limit=None. # default=_AUTOCOMPLETE_LIMIT)

suggestions_proxy = Suggestions()

async def suggestions(request):

    qparams_raw, qparams_db = await suggestions_proxy.fetch(request)
    LOG.debug("Original Query Parameters: %s", qparams_raw)

    if not qparams_db.term:
        return json_response([])

    # it's ok, there are not so many
    translations = list([ { 'label': f"{r['ontology']}:{r['term']} {r['meaning']}",
                            'ontology': f"{r['ontology']}:{r['term']}",
                            'meaning': r['meaning'],
                            }
                          async for r
                          in db.fetch_ontologies(qparams_db.term, qparams_db.limit)])
    
    return json_response(translations)