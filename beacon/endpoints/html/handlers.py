import logging

from aiohttp_jinja2 import template
from aiohttp_session import get_session
# from aiohttp_csrf import generate_token

from ... import conf
from ...utils import db, resolve_token, middlewares

LOG = logging.getLogger(__name__)

@template('examples.html')
async def examples(request):
    #csrf_token = await generate_token(request)

    session = await get_session(request)
    access_token = session.get('access_token')
    datasets, authenticated = await resolve_token(access_token, [])
    LOG.debug('Datasets: %s', datasets)
    return {
        'request': request,
        'session': session,
        'assemblyIDs': await db.fetch_assemblyids(),
        'datasets': datasets, #db.fetch_datasets_access(datasets=datasets),
        'form': {},
        'selected_datasets': set(),
        'filters': set(),
        'beacon_response': None,
        'cookies': request.cookies,
        #'csrf_token': f'<input type="hidden" name="{middlewares.CSRF_FIELD_NAME}" value="{csrf_token}" />',
    }

@template('privacy.html')
async def privacy(request):
    session = await get_session(request)
    access_token = session.get('access_token')
    return {
        'request': request,
        'session': session,
        'cookies': request.cookies,
    }

# ----------------------------------------------------------------------------------------------------------------------
#                                         QUERY VALIDATION
# ----------------------------------------------------------------------------------------------------------------------

# class QueryParameters(RequestParameters):
#     json_error = False
#     query = Field(required=True)
#     assemblyId = RegexField(r'^((GRCh|hg)[0-9]+([.]?p[0-9]+)?)$', required=True) # GRCh007.p9 is valid
#     datasets = ListField(items=RegexField(r'^[^<>"/;%{}+=]*$'))
#     includeDatasetResponses = ChoiceField("ALL", "HIT", "MISS", "NONE", default="NONE")
#     filters = ListField(items=RegexField(r'.*:.+=?>?<?[0-9]*$'))

# class BaseView(TemplateView):

#     def get(self, request):

#         form = getattr(forms, self.formbase)()

#         ctx = { 'form': form,
#                 'selected_datasets': set(),
#                 'filters': set(),
#                 'beacon_response': None,
#         }
#         return render(request, 'index.html', ctx)

#     def post(self, request):

#         form = getattr(forms, self.formbase)(request.POST)

#         selected_datasets = set(request.POST.getlist("datasetIds", []))
#         LOG.debug('selected_datasets: %s', selected_datasets )
#         filters = set( clean_empty_strings( request.POST.getlist("filters", []) ) )
#         LOG.debug('filters: %s', filters )

#         ctx = { 'form': form,
#                 'selected_datasets': selected_datasets,
#                 'filters': filters,
#         }

#         # Form validation... for the regex
#         if not form.is_valid():
#             return render(request, 'index.html', ctx)

#         # Valid Form 
#         params_d = form.query_deconstructed_data
#         LOG.debug('Deconstructed Data: %s', params_d)

#         #params_d['datasets'] = ','.join(selected_datasets) if selected_datasets else 'all'
#         if selected_datasets:
#             params_d['datasetIds'] = ','.join(selected_datasets) 
#         if filters:
#             params_d['filters'] = ','.join(filters)

#         # Don't check anything and forward to backend        
#         query_url = self.api_endpoint
#         if not query_url:
#             return render(request, 'error.html', { 'message': self.api_endpoint_error })
 
#         query_url += urlencode(params_d, safe=',')
#         LOG.debug('Forwarding to %s',query_url)

#         # Access token
#         headers = {}
#         access_token = request.session.get('access_token')
#         if access_token:
#             LOG.debug('with a token: %s', access_token)
#             headers['Authorization'] = 'Bearer ' + access_token
#         else:
#             LOG.debug('No Access token supplied')
        
#         # Forwarding the request to the Beacon API
#         r = requests.get(query_url,headers=headers)
#         LOG.debug('------------------- %s', r)
#         if not r:
#             return render(request, 'error.html', {'message':'Beacon backend API not available' })

#         response = None
#         if r.status_code == 200:
#             response = r.json()

#         #LOG.debug('Response: %s', response)

#         ctx['beacon_response'] = response
#         ctx['query_url'] = query_url
#         ctx['beacon_query'] = { 'params': params_d, 
#                                 'exists': 'Y' if response.get('exists', False) else 'N'
#         }

#         return render(request, 'index.html', ctx)



# class BeaconQueryView(BaseView):
#     formbase = 'QueryForm'

# class BeaconSNPView(BaseView):
#     formbase = 'QueryForm'

# class BeaconRegionView(BaseView):
#     formbase = 'QueryRegionForm'

# class BeaconSamplesView(BaseView):
#     formbase = 'QuerySamplesForm'

# class BeaconAccessLevelsView(TemplateView):

#     def get(self, request):

#         query_url = conf.CONF.get('beacon-api', 'access_levels', fallback=None)
#         if not query_url:
#             return render(request, 'error.html', {'message':'[beacon-api] access_levels is misconfigured' })

#         if request.GET:
#             query_url += '?' + request.GET.urlencode()

#         LOG.info('Contacting Beacon backend: %s', query_url)
#         headers = { 'Accept': 'application/json',
#                     'Content-type': 'application/json',
#         }

#         access_token = request.session.get('access_token')
#         if access_token:
#             headers['Authorization'] = 'Bearer ' + access_token
#         else:
#             LOG.debug('No Access token supplied')

#         resp = requests.get(query_url, headers=headers)
#         if resp.status_code > 200:
#             return render(request, 'error.html', {'message':'Backend not available' })

#         ctx = resp.json()

#         ctx['fieldsParam'] = True if request.GET.get('includeFieldDetails', 'false') == 'true' else False
#         ctx['datasetsParam'] = True if request.GET.get('displayDatasetDifferences', 'false') == 'true' else False

#         return render(request, 'access_levels.html', ctx)



