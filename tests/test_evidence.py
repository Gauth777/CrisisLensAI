from copy import deepcopy
from datetime import datetime,timedelta,timezone
import pytest
from crisislens.evidence import assess,evidence_brief,historical_sources,report_sources
from crisislens.recommendations import RecommendationQuestion

NOW=datetime.now(timezone.utc)
Q=RecommendationQuestion(location='Velachery',question='What is happening and which supplies are needed?')

def source(id='F1',**changes):
    s={'id':id,'kind':'field_report','title':'MRTS request','publisher':'Coordinator report',
       'excerpt':'The coordinator reports waterlogging near the MRTS and requests drinking water.',
       'scope':'locality','location':'Velachery','content_scope':'reviewed_report',
       'published_at':NOW.isoformat(),'retrieved_at':NOW.isoformat(),'url':None}
    return {**s,**changes}

def claim(s,**changes):
    return {'id':'C1','statement':'The coordinator reports waterlogging near the MRTS.',
        'category':'incident','timeframe':'current','explanation':'The field record describes this site.',
        'next_check':'Confirm receiving time with the site contact.',
        'evidence':[{'source_id':s['id'],'direction':'supports','passage':s['excerpt'],
                     'reason':'This record names the site and the observed condition.'}],**changes}

class Provider:
    model='scripted-evidence-test'
    def __init__(self,claims,action=None):self.claims=claims;self.action=action;self.calls=0
    def generate_json(self,**kwargs):
        self.calls+=1
        if 'reviews' in kwargs['output_schema']['properties']:
            return {'reviews':[{'claim_id':c['id'],'verdict':'supported' if len(c['evidence'])<2 else 'conflicting','reason':'Scripted semantic review for guard testing.','omitted_source_ids':[]} for c in self.claims]}
        if self.calls==1:return {'claims':deepcopy(self.claims)}
        return {'location':'Velachery','headline':'Respond to the request','answer':'Prepare the requested supplies.',
          'claims':[],'recommendations':[self.action or {'title':'Confirm receiving time','explanation':'Agree when the site contact can receive help.','source_ids':['F1'],'claim_ids':['C1'],'intent':'check'}],
          'affected_groups':[],'supplies':[],'missing_information':[]}

def bundle(*sources):return {'sources':list(sources),'source_status':[],'coverage_note':'Test records'}

def test_passage_backed_current_local_report():
    s=source();result=assess(Provider([claim(s)]),Q,bundle(s),NOW)
    assert result['claims'][0]['status']=='supported'
    assert result['claims'][0]['evidence'][0]['eligible']

@pytest.mark.parametrize('changes',[
    {'kind':'weather','content_scope':'modelled_weather'},
    {'scope':'city_context','kind':'news','content_scope':'feed_excerpt'},
    {'kind':'historical','content_scope':'historical_note'},
    {'published_at':(NOW-timedelta(days=10)).isoformat()},
    {'published_at':None},{'location':'Tambaram'}, {'content_scope':'unverified_input'}])
def test_wrong_scope_type_date_or_review_cannot_establish_current_incident(changes):
    s=source(**changes);r=assess(Provider([claim(s)]),Q,bundle(s),NOW)
    assert r['claims'][0]['status']=='check_needed'
    assert r['claims'][0]['next_check']

@pytest.mark.parametrize('change',[{'source_id':'INVENTED'},{'passage':'This invented passage never appeared in the source.'}])
def test_fabricated_passage_or_source_fails_closed(change):
    s=source();c=claim(s);c['evidence'][0].update(change)
    with pytest.raises(ValueError):assess(Provider([c]),Q,bundle(s),NOW)

def test_support_and_opposition_remain_visible():
    a=source();b=source('F2',excerpt='The second coordinator reports that the MRTS approach is dry.')
    c=claim(a);c['evidence'].append({'source_id':'F2','direction':'contradicts','passage':b['excerpt'],'reason':'Describes opposing conditions at the same site.'})
    r=assess(Provider([c]),Q,bundle(a,b),NOW)['claims'][0]
    assert r['status']=='conflicting' and len(r['evidence'])==2

def test_repeated_text_does_not_add_another_evidence_vote():
    a=source();b=source('F2');c=claim(a);c['evidence'].append({**c['evidence'][0],'source_id':'F2'})
    r=assess(Provider([c]),Q,bundle(a,b),NOW)['claims'][0]
    assert r['evidence'][1]['duplicate'] and not r['evidence'][1]['eligible']

def test_response_requires_reviewed_demand_and_quantity_bounds():
    s=source();p=Provider([claim(s)],{'title':'Send water','explanation':'Supply the request.','source_ids':['F1'],'claim_ids':['C1'],'intent':'respond'})
    result,assessment=evidence_brief(p,Q,bundle(s))
    assert p.calls==3 and result.recommendations[0].intent=='check'
    assert result.supplies==[]

def test_action_cannot_cite_unassessed_source():
    a=source();b=source('F2',excerpt='Another unrelated report is present.')
    p=Provider([claim(a)],{'title':'Send water','explanation':'Supply the request.','source_ids':['F2'],'claim_ids':['C1'],'intent':'respond'})
    with pytest.raises(ValueError):evidence_brief(p,Q,bundle(a,b))

def test_no_evidence_does_not_mean_false():
    c=claim(source(),evidence=[])
    r=assess(Provider([c]),Q,bundle(),NOW)['claims'][0]
    assert r['status']=='check_needed'

def test_real_historical_conflict_sources_preserved():
    sources=historical_sources('Chromepet')
    pair=[s for s in sources if s['case_id']=='chromepet-2021']
    assert len(pair)==2 and all(s['conflicts'] for s in pair)
    c=claim(pair[0],timeframe='historical',statement='The 2021 accounts differ on flooded wards and patient transfers.')
    c['evidence'].append({'source_id':pair[1]['id'],'direction':'contradicts','passage':pair[1]['excerpt'],'reason':'The named official describes safe wards and continuing inpatient services.'})
    q=Q.model_copy(update={'location':'Chromepet'})
    r=assess(Provider([c]),q,bundle(*pair),NOW)['claims'][0]
    assert r['status']=='conflicting' and r['timeframe']=='historical'

def test_rejected_or_pending_field_reports_are_leads_not_reviewed_sources():
    r={'id':'one','location':'Velachery','landmark':'MRTS','description':'Water reported here.',
       'needs':'Check access','status':'reviewed','pending_updates':1,'observed_at':NOW.isoformat(),
       'submitted_at':NOW.isoformat()}
    assert report_sources({'reports':[r]},'one')[0]['content_scope']=='unverified_input'

@pytest.mark.parametrize('intent',['check','prepare','respond'])
def test_dispatch_text_cannot_bypass_policy_with_intent_label(intent):
    s=source()
    action={'title':'Dispatch 500 water kits immediately','explanation':'Send volunteers through the flooded road now.',
        'source_ids':['F1'],'claim_ids':['C1'],'intent':intent}
    result,_=evidence_brief(Provider([claim(s)],action),Q,bundle(s))
    public_text=result.model_dump_json()
    assert '500' not in public_text and 'through the flooded road' not in public_text
    assert all(a.title!='Dispatch 500 water kits immediately' for a in result.recommendations)


def test_real_passage_does_not_override_semantic_rejection():
    s=source();c=claim(s,statement='Fifty people are trapped and need helicopter evacuation.')
    class RejectUnsupported(Provider):
        def generate_json(self,**kwargs):
            if 'reviews' in kwargs['output_schema']['properties']:
                return {'reviews':[{'claim_id':'C1','verdict':'not_established',
                    'reason':'Waterlogging does not establish trapped people, a count or helicopter need.', 'omitted_source_ids':[]}]}
            return super().generate_json(**kwargs)
    r=assess(RejectUnsupported([c]),Q,bundle(s),NOW)['claims'][0]
    assert r['status']=='check_needed' and r['label']=='Check this detail'
    assert 'helicopter' in r['explanation']


def test_known_historical_conflict_survives_both_models_omitting_it():
    pair=[s for s in historical_sources('Chromepet') if s['case_id']=='chromepet-2021']
    c=claim(pair[0],timeframe='historical',statement='Hospital wards flooded in 2021.')
    q=Q.model_copy(update={'location':'Chromepet'})
    r=assess(Provider([c]),q,bundle(*pair),NOW)['claims'][0]
    assert r['status']=='conflicting'
    assert {e['source_id'] for e in r['evidence']}=={s['id'] for s in pair}


@pytest.mark.parametrize('reviews',[
    [],
    [{'claim_id':'C99','verdict':'supported','reason':'Wrong claim.','omitted_source_ids':[]}],
    [{'claim_id':'C1','verdict':'supported','reason':'Invented source.','omitted_source_ids':['FAKE']}],
])
def test_incomplete_or_fabricated_semantic_review_fails_closed(reviews):
    s=source()
    class BadReview(Provider):
        def generate_json(self,**kwargs):
            if 'reviews' in kwargs['output_schema']['properties']:return {'reviews':reviews}
            return super().generate_json(**kwargs)
    with pytest.raises(ValueError):assess(BadReview([claim(s)]),Q,bundle(s),NOW)


def test_semantic_reviewer_cannot_promote_stale_evidence():
    s=source(published_at=(NOW-timedelta(days=10)).isoformat())
    assert assess(Provider([claim(s)]),Q,bundle(s),NOW)['claims'][0]['status']=='check_needed'
