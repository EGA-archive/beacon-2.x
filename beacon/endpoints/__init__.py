
from aiohttp import web

from .rest import (filtering_terms,
                   info,
                   datasets,
                   handlers as rest_handlers
)



from . import html

# only for testing
from . import test

routes = [
    # Info
    web.get('/api'                  , info.handler),
    web.get('/api/info'             , info.handler),
    web.get('/api/service-info'     , info.handler_ga4gh_service_info),

    # Datasets
    web.get('/api/datasets'         , datasets.handler),

    # Filtering terms
    web.get('/api/filtering_terms'   , filtering_terms.handler),

    # Schemas
    # web.get('/api/schemas'          , schemas.handler),

    # Genomic query
    # web.get('/api/genomic_snp'                      , genomic_query.handler),
    # web.get('/api/genomic_region'                   , genomic_query.handler),

    # Biosamples
    web.get('/api/biosamples'                               , rest_handlers.biosamples_by_biosample),
    web.get('/api/biosamples/{target_id_req}'               , rest_handlers.biosamples_by_biosample),
    web.get('/api/biosamples/{target_id_req}/g_variants'    , rest_handlers.gvariants_by_biosample),
    web.get('/api/biosamples/{target_id_req}/individuals'   , rest_handlers.individuals_by_biosample),
    
    # # Individuals
    web.get('/api/individuals'                              , rest_handlers.individuals_by_individual),
    web.get('/api/individuals/{target_id_req}'              , rest_handlers.individuals_by_individual),
    web.get('/api/individuals/{target_id_req}/g_variants'   , rest_handlers.gvariants_by_individual),
    web.get('/api/individuals/{target_id_req}/biosamples'   , rest_handlers.biosamples_by_individual),

    # # GVariant
    web.get('/api/g_variants'                               , rest_handlers.gvariants_by_variant),
    web.get('/api/g_variants/{target_id_req}'               , rest_handlers.gvariants_by_variant),
    web.get('/api/g_variants/{target_id_req}/biosamples'    , rest_handlers.individuals_by_variant),
    web.get('/api/g_variants/{target_id_req}/individuals'   , rest_handlers.biosamples_by_variant),


    ## HTML UI
    web.get('/'       , html.handlers.index  , name='home'   ),
    web.get('/privacy', html.handlers.privacy, name='privacy'),
    web.get('/test', html.test_marta.handler_get),
    web.post('/test', html.test_marta.handler_post, name='test_marta'),

    # Auth endpoints
    web.get('/login'  , html.auth.login      , name='login'  ),
    web.get('/logout' , html.auth.logout     , name='logout' ),

    # AJAX
    web.get('/filtering_terms/{term}', html.filtering_terms.handler),

    # Just for test
    web.get('/api/test'                  , test.handler),
    web.get('/test'                      , test.handler),
]
